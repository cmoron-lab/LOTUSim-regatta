#!/usr/bin/env python3
"""Boucle fermée Python <-> xdyn-for-cs (websocket), SANS gz/ROS.

xdyn-for-cs est un serveur de pas : on lui envoie {Dt, states:[état NED], commands, ...},
il intègre jusqu'à Dt et renvoie le nouvel état. CE client tient l'état, un contrôleur calcule
les commandes, on avance. Client websocket = stdlib pure (RFC6455), aucune dépendance ; tourne
sur l'hôte, se connecte au port exposé du conteneur. Fondation de l'interface étudiante + parcours.

╔═ TECHNIQUE CLÉ : DÉCOUPLER le pas d'intégration de la fréquence de communication ═══════════╗
║ Le co-sim INTERDIT les solveurs adaptatifs (horloge monotone -> rkck refusé). On est en rk4  ║
║ PAS FIXE. MAIS xdyn SOUS-CADENCE : le flag de lancement `--dt` = pas d'intégration RÉEL du    ║
║ solveur ; le `Dt` envoyé dans le message = horizon co-sim. Si Dt_message > --dt, xdyn fait    ║
║ plusieurs sous-pas `--dt` par échange. Pas effectif = min(--dt, Dt_message). PROUVÉ           ║
║ (`subdiv.py`) : --dt=0.001 + Dt_message=0.02 == trajectoire du full-fin, != du grossier 0.02. ║
║ => On lance avec un --dt FIN (0.001, propre au faible amortissement / manœuvres) et on         ║
║    communique/pilote plus lentement (0.02 = 50 Hz) : stabilité numérique SANS surcoût de comm.  ║
║    launch_xdyn(dt=<--dt fin>) ; step(..., dt=<Dt comm, plus grand>). Coût wall-clock ~ 1/--dt.  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

⚠️ CAUSE RACINE (issue naval-group/LOTUSim-Xdyn#1) : l'ingouvernabilité au près = BUG INTERNE à xdyn.
Le force model `hydrodynamic polar` calcule l'angle d'attaque du foil sur la vitesse MONDE (NED) au lieu du
repère corps -> la force des foils (quille/safran) DÉPEND DU CAP (correcte seulement étrave N/S) -> le voilier
CRABE tant que xdyn n'est pas patché. Ni le yaml (sain), ni le plugin, ni CE harnais (convention standard,
correcte). Détails + TU + fix : ../xdyn-foil-heading-bug.md. Le voilier navigera une fois xdyn patché.
"""
import base64, json, math, os, re, socket, struct, subprocess, time

LAB = os.path.expanduser("~/src/lotusim-lab")
IMAGE = "lotusim:focus-v2"
MODEL_SRC = f"{LAB}/LOTUSim/assets/models/focus_v2/focus_v2.yaml"
OFF = f"{LAB}/_offline"
C_MESH = "/lab/LOTUSim/assets/models/focus_v2/meshes/focus_v2.stl"


# ---------- modèle temporaire (vent réglable, mesh absolu) ----------
def write_model(wind_dir_deg, wind_speed=None):
    src = open(MODEL_SRC).read()
    src, n = re.subn(r"(direction:\s*\{unit:\s*deg,\s*value:\s*)[-\d.]+",
                     rf"\g<1>{wind_dir_deg}", src, count=1)
    assert n == 1, "direction vent introuvable"
    if wind_speed is not None:
        src = re.sub(r"(velocity:\s*\{unit:\s*m/s,\s*value:\s*)[-\d.]+",
                     rf"\g<1>{wind_speed}", src, count=1)
    src = re.sub(r"^(\s*mesh:\s*)\S+\.stl", rf"\g<1>{C_MESH}", src, count=1, flags=re.M)
    open(f"{OFF}/_cosim_model.yaml", "w").write(src)


# ---------- websocket client minimal (stdlib) ----------
def ws_connect(host, port, path="/", timeout=10):
    s = socket.create_connection((host, port), timeout=timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
           "Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
    s.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = s.recv(4096)
        if not d:
            raise RuntimeError("handshake: connexion fermée")
        buf += d
    line0 = buf.split(b"\r\n", 1)[0]
    if b" 101 " not in line0:
        raise RuntimeError(f"handshake échoué: {line0!r}")
    return s


def _recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        d = s.recv(n - len(buf))
        if not d:
            raise RuntimeError("frame: connexion fermée")
        buf += d
    return buf


def ws_send(s, text):
    p = text.encode()
    hdr = bytearray([0x81])  # FIN + opcode texte
    n = len(p)
    mask = os.urandom(4)
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr.append(0x80 | 126); hdr += struct.pack(">H", n)
    else:
        hdr.append(0x80 | 127); hdr += struct.pack(">Q", n)
    hdr += mask
    s.sendall(bytes(hdr) + bytes(b ^ mask[i % 4] for i, b in enumerate(p)))


def ws_recv(s):
    while True:
        b0, b1 = _recv_exact(s, 2)
        opcode = b0 & 0x0F
        n = b1 & 0x7F
        if n == 126:
            n = struct.unpack(">H", _recv_exact(s, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _recv_exact(s, 8))[0]
        mk = _recv_exact(s, 4) if (b1 & 0x80) else b""
        payload = _recv_exact(s, n)
        if mk:
            payload = bytes(c ^ mk[i % 4] for i, c in enumerate(payload))
        if opcode == 0x8:
            raise RuntimeError("serveur a fermé (close frame)")
        if opcode == 0x9:  # ping -> ignore (xdyn n'en envoie pas en pratique)
            continue
        if opcode in (0x1, 0x2):
            return payload.decode()


# ---------- lancement / pas ----------
def launch_xdyn(port=12345, solver="rk4", dt=0.005, name="fv2cosim"):
    """Lance xdyn-for-cs. `dt` = pas d'intégration INTERNE (--dt). En co-sim, solver="rk4"
    OBLIGATOIRE (rkck interdit, horloge monotone). Pour un régime peu amorti / des manœuvres,
    prendre dt FIN (0.001) et communiquer plus lentement dans step(...,dt=0.02) -> xdyn sous-cadence
    (cf docstring module). Coût wall-clock ~ 1/dt : garder les sims courtes à dt=0.001."""
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    inner = ("chmod +x /lab/LOTUSim/physics/xdyn-for-cs 2>/dev/null; "
             f"/lab/LOTUSim/physics/xdyn-for-cs /lab/_offline/_cosim_model.yaml "
             f"-s {solver} --dt {dt} -a 0.0.0.0 -p {port}")
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "--platform", "linux/amd64",
         "-p", f"{port}:{port}", "-v", f"{LAB}:/lab", "-w", "/lab/LOTUSim/assets/models",
         "-e", "LD_LIBRARY_PATH=/lab/LOTUSim/physics", IMAGE, "bash", "-lc", inner],
        check=True, capture_output=True)
    return name


def stop_xdyn(name="fv2cosim"):
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


INIT = {"t": 0.0, "x": 0.0, "y": 0.0, "z": 0.0, "qi": 0.0, "qj": 0.0, "qk": 0.0,
        "qr": 1.0, "u": 0.0, "v": 0.0, "w": 0.0, "p": 0.0, "q": 0.0, "r": 0.0}
FIELDS = ("t", "x", "y", "z", "qi", "qj", "qk", "qr", "u", "v", "w", "p", "q", "r")


def step(sock, state, sheet_rad, helm_rad, dt):
    req = {"Dt": dt, "states": [state],
           "commands": {"mainsail(sheet)": sheet_rad, "rudder(helm)": helm_rad},
           "requested_output": []}
    ws_send(sock, json.dumps(req))
    reply = json.loads(ws_recv(sock))
    if isinstance(reply, dict) and "error" in reply:
        raise RuntimeError("xdyn: " + str(reply["error"])[:200])
    out = {}
    for k in FIELDS:
        v = reply.get(k)
        out[k] = (v[-1] if isinstance(v, list) else v) if v is not None else state[k]
    return out


# ╔═ CONVENTION CO-SIM xdyn (STANDARD — vérifiée dans le source, cf ../xdyn-foil-heading-bug.md) ══════════╗
# ║ quaternion (qr,qi,qj,qk) = ATTITUDE corps→NED ; vitesses (u,v,w),(p,q,r) = repère CORPS ;              ║
# ║ position (x,y,z) = NED.  (core/Body.cpp:173-194 ; prouvé par le coast test.) Round-trip brut = correct.║
# ║ ⚠️ BUG xdyn (issue naval-group/LOTUSim-Xdyn#1) : le force model `hydrodynamic polar` calcule l'angle    ║
# ║   d'attaque du foil sur la vitesse MONDE → force dépendante du cap → le voilier CRABE tant que xdyn     ║
# ║   n'est pas patché. La convention du harnais ci-dessous est correcte (standard) — c'est xdyn qui bugue. ║
# ╚═══════════════════════════════════════════════════════════════════════════════════════════════════════╝

def yaw_of(st):
    """Cap boussole (rad, NED) depuis le quaternion d'attitude corps→NED."""
    qr, qi, qj, qk = st["qr"], st["qi"], st["qj"], st["qk"]
    return math.atan2(2 * (qr * qk + qi * qj), 1 - 2 * (qj * qj + qk * qk))


heading_of = yaw_of  # alias


def roll_of(st):
    """Gîte (rad)."""
    qr, qi, qj, qk = st["qr"], st["qi"], st["qj"], st["qk"]
    return math.atan2(2 * (qr * qi + qj * qk), 1 - 2 * (qi * qi + qj * qj))


def body_vel(st):
    """Vitesse repère CORPS (surge, sway, heave). En convention standard xdyn, (u,v,w) SONT déjà en corps."""
    return (st["u"], st["v"], st["w"])


def leeway_of(st):
    """Angle de dérive (rad) = atan2(sway, surge). >0 = dérive tribord."""
    return math.atan2(st["v"], st["u"])


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


HELM_SIGN = -1.0  # safran monté inversé dans le modèle (convention standard attitude+corps)


def init_at(heading, u=0.0):
    """État initial au `heading` (rad, NED), vitesse d'avance CORPS `u`. Convention standard xdyn :
    quaternion = attitude corps→NED, vitesse (u,v,w) en repère corps."""
    st = dict(INIT)
    st["qr"] = math.cos(heading / 2.0)
    st["qk"] = math.sin(heading / 2.0)
    st["u"] = u
    return st


def run_leg(sock, target_head, sheet_rad, dt=0.005, tsim=18.0,
            kp=2.2, kd=0.9, helm_max=math.radians(35)):
    """Tient `target_head` (rad, NED) au safran (PD cap, signe safran inversé), voile bordée
    à `sheet_rad`, départ déjà orienté au cap. Renvoie la trajectoire (liste d'états)."""
    st = init_at(target_head, u=0.5)
    traj = []
    for _ in range(int(tsim / dt)):
        pd = kp * wrap(target_head - yaw_of(st)) - kd * st["r"]
        helm = clamp(HELM_SIGN * pd, -helm_max, helm_max)
        st = step(sock, st, sheet_rad, helm, dt)
        traj.append(dict(st))
    return traj


def leg_speed(traj, secs=4.0):
    """Vitesse au sol moyenne sur la fin de la trajectoire."""
    t_end = traj[-1]["t"]
    tail = [s for s in traj if s["t"] >= t_end - secs]
    if len(tail) < 2:
        return 0.0
    d = sum(math.hypot(tail[i + 1]["x"] - tail[i]["x"], tail[i + 1]["y"] - tail[i]["y"])
            for i in range(len(tail) - 1))
    return d / (tail[-1]["t"] - tail[0]["t"])


def leg_made_good(traj, heading, secs=4.0):
    """Progrès NET projeté sur le cap (m/s) : positif = avance vers où pointe l'étrave,
    négatif = dérive à reculons (vraie zone morte au vent)."""
    t_end = traj[-1]["t"]
    tail = [s for s in traj if s["t"] >= t_end - secs]
    if len(tail) < 2 or tail[-1]["t"] == tail[0]["t"]:
        return 0.0
    dx, dy = tail[-1]["x"] - tail[0]["x"], tail[-1]["y"] - tail[0]["y"]
    return (dx * math.cos(heading) + dy * math.sin(heading)) / (tail[-1]["t"] - tail[0]["t"])


def leg_head_err(traj, target_head, secs=4.0):
    """Erreur de tenue de cap moyenne (deg) sur la fin — le pilote a-t-il tenu ?"""
    t_end = traj[-1]["t"]
    tail = [s for s in traj if s["t"] >= t_end - secs]
    return math.degrees(sum(abs(wrap(target_head - yaw_of(s))) for s in tail) / max(1, len(tail)))


AOA_OPT = 20.0
NO_GO = math.radians(50.0)          # demi-zone morte : marque plus près que ça du vent -> tacking
CLOSE_HAULED = math.radians(60.0)   # cap de près réel : 60° = allure TENABLE + bon VMG (à 48° le
                                    # bateau ne tient pas le cap et abat). On "foote" pour la vitesse.
KP, KD, HELM_MAX = 2.2, 0.9, math.radians(35)


def opt_sheet(twa_deg):
    # Ease curve calibrated on the patched-xdyn beat sweep (beat_diag): sheet must stay ~HARD
    # upwind (~5deg at close-hauled twa~45-52) or the sail barely drives -> crawl + huge leeway.
    # The old twa-AOA_OPT gave 40deg at close-hauled (over-eased). Gentle slope, eased downwind.
    return math.radians(clamp(0.6 * (twa_deg - 42.0), 4.0, 80.0))


def desired_heading(pos, mark, wind_from, tack):
    """Cap visé. Marque dans la zone morte -> près sur le bord courant (tack=+1/-1) ;
    sinon cap direct sur la marque."""
    brg = math.atan2(mark[1] - pos[1], mark[0] - pos[0])
    if abs(wrap(brg - wind_from)) < NO_GO:
        return wrap(wind_from + tack * CLOSE_HAULED)
    return brg


def cross_track(pos, a, b):
    """Écart perpendiculaire signé de pos à la ligne a->b (>0 = à gauche de a->b)."""
    lx, ly = b[0] - a[0], b[1] - a[1]
    L = math.hypot(lx, ly) or 1.0
    return ((pos[0] - a[0]) * (-ly) + (pos[1] - a[1]) * lx) / L


def sail_course(sock, marks, wind_from, dt=0.005, tmax=170.0, corridor=5.0, wp_radius=1.8):
    """Pilote le bateau de marque en marque. Au vent : bords alternés dans un couloir, avec
    une routine de VIREMENT ENGAGÉ (rudder ferme + gain élevé pour passer franc le lit du vent,
    sans re-déclencher) au lieu de caler en irons. Sinon : cap direct.
    Renvoie (trajectoire, nb_marques_atteintes, nb_virements)."""
    st = init_at(wind_from + CLOSE_HAULED, 0.8)
    wp, tack, tacks = 0, 1, 0
    leg_start = (0.0, 0.0)
    tacking = False
    traj = []
    for _ in range(int(tmax / dt)):
        pos = (st["x"], st["y"])
        mark = marks[wp]
        if math.hypot(mark[0] - pos[0], mark[1] - pos[1]) < wp_radius:
            wp += 1
            if wp >= len(marks):
                break
            leg_start, mark, tacking = pos, marks[wp], False

        yaw = yaw_of(st)
        brg = math.atan2(mark[1] - pos[1], mark[0] - pos[0])
        upwind = abs(wrap(brg - wind_from)) < NO_GO

        # NOTE : le virement (changer d'amure) reste NON RÉSOLU cette session — vent devant le
        # bateau cale en irons, empannage il diverge. Le BEAT (grimper au vent sur une amure)
        # marche. Ci-dessous = tentative "virement engagé" (sails-straight, sans crash).
        if tacking:
            desired = wrap(wind_from + tack * CLOSE_HAULED)
            if abs(wrap(desired - yaw)) < math.radians(18):
                tacking = False
        else:
            if upwind:
                c = cross_track(pos, leg_start, mark)
                if (c > corridor and tack > 0) or (c < -corridor and tack < 0):
                    tack, tacks, tacking = -tack, tacks + 1, True
            desired = desired_heading(pos, mark, wind_from, tack)

        kp = KP * (2.4 if tacking else 1.0)
        helm = clamp(HELM_SIGN * (kp * wrap(desired - yaw) - KD * st["r"]), -HELM_MAX, HELM_MAX)
        twa = abs(math.degrees(wrap(yaw - wind_from)))
        st = step(sock, st, opt_sheet(twa), helm, dt)
        traj.append(dict(st))
    return traj, wp, tacks


def maneuver_probe(sock, dt=0.005, wind_from=0.0):
    """Repro de robustesse : beat 8s puis VIRAGE FORCÉ (safran à fond) 12s. Renvoie
    (diverged, vitesse_max, t_ou_yaw_final). Sert à mesurer si le modèle encaisse les
    manœuvres agressives sans diverger."""
    st = init_at(wind_from + CLOSE_HAULED, 0.8)
    maxspd = 0.0
    n = int(20.0 / dt)
    for i in range(n):
        t = i * dt
        if t < 8.0:
            d = wrap(wind_from + CLOSE_HAULED)
            helm = clamp(HELM_SIGN * (KP * wrap(d - yaw_of(st)) - KD * st["r"]), -HELM_MAX, HELM_MAX)
        else:
            helm = HELM_MAX                      # safran à fond = virage forcé (repro divergence)
        twa = abs(math.degrees(wrap(yaw_of(st) - wind_from)))
        try:
            st = step(sock, st, opt_sheet(twa), helm, dt)
        except RuntimeError:
            return True, maxspd, t               # divergé
        maxspd = max(maxspd, math.hypot(st["u"], st["v"]))
    return False, maxspd, math.degrees(yaw_of(st))


if __name__ == "__main__" and len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "probe":
    import sys
    dt = float(sys.argv[2]) if len(sys.argv) > 2 else 0.005
    write_model(180)
    launch_xdyn(solver="rk4", dt=dt)
    try:
        time.sleep(4)
        sock = ws_connect("127.0.0.1", 12345)
        div, mx, last = maneuver_probe(sock, dt=dt)
        print(f"PROBE dt={dt}: diverged={div}  vitesse_max={mx:.2f}  "
              + (f"t_div={last:.1f}s" if div else f"yaw_final={last:.0f}deg"))
    finally:
        stop_xdyn()
    sys.exit(0)


if __name__ == "__main__":
    # DÉMO PARCOURS windward-leeward : vent DU Nord (direction 180 = souffle vers le Sud).
    # Marque au vent à 15 m Nord = DEAD UPWIND -> le bateau DOIT tirer des bords pour l'atteindre,
    # puis redescend au portant vers la marque sous le vent. Preuve que la physique impose le tacking.
    WIND_DIR, WIND_FROM = 180, 0.0
    MARKS = [(15.0, 0.0), (0.0, 0.0)]
    write_model(WIND_DIR)
    launch_xdyn()
    try:
        time.sleep(4)
        sock = ws_connect("127.0.0.1", 12345)
        traj, reached, tacks = sail_course(sock, MARKS, WIND_FROM)
    finally:
        stop_xdyn()
    xs = [s["x"] for s in traj]
    print(f"=== DÉMO PARCOURS ===  marques atteintes {reached}/{len(MARKS)}  virements {tacks}")
    print(f"  Nord max atteint x={max(xs):.1f} m (marque au vent à 15)  durée {traj[-1]['t']:.0f}s")
    with open(f"{OFF}/tack_traj.txt", "w") as f:
        for s in traj[::20]:
            f.write(f"{s['t']:.2f} {s['x']:.3f} {s['y']:.3f} {math.degrees(yaw_of(s)):.1f}\n")
    print(f"  trajectoire -> {OFF}/tack_traj.txt ({len(traj)} pas)")
