#!/usr/bin/env python3
"""Focus V2 physics acceptance harness — chantier A (arcade-honest tuning).

Boucle rapide xdyn standalone (sans gz/ROS). Critères :
  no-go   : près du vent debout -> vitesse d'avance ~nulle (pas de progrès au vent)
  reach   : travers/largue nettement plus rapide que le près et que le vent arrière
  no-360  : helm=0 sur un bord de travers -> lacet borné (pas de rotation continue)
  trim    : à allure fixe, la vitesse pique à un réglage de voile, mal réglé = plus lent

Prérequis : Docker up + image lotusim:focus-v2. Harnais DEV (amd64/Rosetta), pas un test shippé.
Le modèle réel (LOTUSim/assets/models/focus_v2/focus_v2.yaml) est LU (jamais modifié) : on écrit
une COPIE temporaire avec vent/mesh/sortie en chemins absolus, pour balayer les allures sans
toucher au livrable ni casser la résolution de chemins.
"""
import csv, math, os, re, statistics, subprocess, sys

LAB = os.path.expanduser("~/src/lotusim-lab")
IMAGE = "lotusim:focus-v2"
MODEL_SRC = f"{LAB}/LOTUSim/assets/models/focus_v2/focus_v2.yaml"
OFF = f"{LAB}/_offline"
# chemins vus DANS le conteneur (LAB monté sur /lab)
C_MODEL = "/lab/_offline/_check_model.yaml"
C_CMD = "/lab/_offline/_check_cmd.yaml"
C_CSV = "/lab/_offline/_check.csv"
C_MESH = "/lab/LOTUSim/assets/models/focus_v2/meshes/focus_v2.stl"
AOA_OPT = 20.0  # deg — trim ideal : sheet ~ AWA - AOA_OPT


def _write_cmd(sheet_deg, helm_deg):
    open(f"{OFF}/_check_cmd.yaml", "w").write(
        "commands:\n  - name: mainsail\n    t: [0.0]\n"
        f"    sheet: {{unit: deg, values: [{sheet_deg}]}}\n"
        "  - name: rudder\n    t: [0.0]\n"
        f"    helm: {{unit: deg, values: [{helm_deg}]}}\n")


def _write_model(wind_dir_deg, seed_u=0.0):
    src = open(MODEL_SRC).read()
    # 1) direction du vent (seule clé 'direction' du modèle)
    src, n = re.subn(r"(direction:\s*\{unit:\s*deg,\s*value:\s*)[-\d.]+",
                     rf"\g<1>{wind_dir_deg}", src, count=1)
    assert n == 1, "ligne 'direction' du vent introuvable — format modèle changé"
    # 1b) vitesse initiale d'avance (flux sur les foils dès t=0) — seule clé 'u: {value:'
    src, n = re.subn(r"(u:\s*\{value:\s*)[-\d.]+(,\s*unit:\s*m/s\})",
                     rf"\g<1>{seed_u}\g<2>", src, count=1)
    assert n == 1, "ligne 'u:' vitesse initiale introuvable — format modèle changé"
    # 2) mesh en absolu (ancré sur .stl pour ne PAS matcher 'relative to mesh:')
    src = re.sub(r"^(\s*mesh:\s*)\S+\.stl", rf"\g<1>{C_MESH}", src, count=1, flags=re.M)
    # 3) sortie CSV en absolu (robuste quel que soit le cwd / le flag -o)
    src, n = re.subn(r"^(\s*filename:\s*)\S+\.csv", rf"\g<1>{C_CSV}", src, count=1, flags=re.M)
    assert n == 1, "ligne 'filename' de sortie introuvable — format modèle changé"
    open(f"{OFF}/_check_model.yaml", "w").write(src)


def run_sim(wind_dir_deg, sheet_deg, helm_deg=0.0, tend=40.0, seed_u=0.0, solver="rk4", dt=0.005):
    # dt=0.005 : le modèle est raide, rk4 à pas fixe 0.02 diverge (artefact numérique) ;
    # 0.005 converge (identique à 0.001). Co-sim (dt fixe 0.02) = à traiter en itération 2.
    _write_cmd(sheet_deg, helm_deg)
    _write_model(wind_dir_deg, seed_u)
    if os.path.exists(f"{OFF}/_check.csv"):
        os.remove(f"{OFF}/_check.csv")  # pas de lecture d'un vieux CSV si xdyn échoue
    # PAS de -o : il ajoute un dump complet (161 col) qui entre en collision avec la
    # sortie curée du bloc 'output:' du modèle (11 col). On s'appuie sur ce bloc seul
    # (son 'filename:' est déjà réécrit vers C_CSV en absolu par _write_model).
    inner = ("chmod +x /lab/LOTUSim/physics/xdyn 2>/dev/null; "
             f"/lab/LOTUSim/physics/xdyn {C_MODEL} {C_CMD} -s {solver} --dt {dt} "
             f"--tend {tend} 2>/lab/_offline/_check.err")
    # PAS de check=True : une divergence (NaN) fait sortir xdyn en code 1 mais laisse une
    # trace partielle exploitable. On tolère et on annote `diverged` sur les lignes.
    proc = subprocess.run(
        ["docker", "run", "--rm", "--platform", "linux/amd64", "-v", f"{LAB}:/lab",
         "-w", "/lab/LOTUSim/assets/models", "-e", "LD_LIBRARY_PATH=/lab/LOTUSim/physics",
         IMAGE, "bash", "-lc", inner], capture_output=True)
    if not os.path.exists(f"{OFF}/_check.csv"):
        raise RuntimeError(f"pas de CSV produit — err:\n{open(f'{OFF}/_check.err').read()[-400:]}")
    rows = []
    with open(f"{OFF}/_check.csv") as f:
        for r in csv.DictReader(f):
            rows.append({k.strip(): float(v) for k, v in r.items()})
    if not rows:
        raise RuntimeError("CSV vide — voir _offline/_check.err")
    diverged = proc.returncode != 0 and "diverged" in open(f"{OFF}/_check.err").read().lower()
    for r in rows:
        r["_diverged"] = diverged
    return rows


def _col(rows, prefix):
    keys = [k for k in rows[0] if k.startswith(prefix)]
    assert keys, f"colonne '{prefix}' absente du CSV: {list(rows[0])}"
    return [r[keys[0]] for r in rows]


def tail_speed(rows, secs=5.0):
    if rows[-1].get("_diverged"):
        return float("nan")               # run divergé -> vitesse non fiable
    t_end = rows[-1]["t"]
    us = [u for r, u in zip(rows, _col(rows, "u(")) if r["t"] >= t_end - secs]
    m = statistics.mean(us) if us else 0.0
    if math.isnan(m) or abs(m) > 8.0:      # >8 m/s impossible pour un 1 m RC -> aberrant
        return float("nan")
    return m


def ground_speed(rows, secs=5.0):
    """Vitesse au SOL (distance parcourue / temps) sur la fin du run — robuste au cap
    (le u corps devient négatif quand le bateau lofe, ce n'est pas 'reculer')."""
    if rows[-1].get("_diverged"):
        return float("nan")
    t_end = rows[-1]["t"]
    tail = [r for r in rows if r["t"] >= t_end - secs]
    if len(tail) < 2:
        return 0.0
    xs, ys, ts = _col(tail, "x("), _col(tail, "y("), [r["t"] for r in tail]
    if ts[-1] == ts[0]:
        return 0.0
    dist = sum(math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(len(tail) - 1))
    v = dist / (ts[-1] - ts[0])
    return float("nan") if v > 8.0 else v


def made_good(rows):
    """Progrès NET le long de l'étrave initiale (+x = Nord) / temps. C'est le VMG vers la
    direction visée : ~0 au près (on ne progresse pas vers le vent, on ne fait que dériver),
    maxi au travers, positif mais moindre au portant. Distingue 'naviguer' de 'dériver'."""
    if rows[-1].get("_diverged"):
        return float("nan")
    xs, ts = _col(rows, "x("), [r["t"] for r in rows]
    if ts[-1] <= ts[0]:
        return 0.0
    v = (xs[-1] - xs[0]) / (ts[-1] - ts[0])
    return float("nan") if abs(v) > 8.0 else v


def max_abs_r(rows):
    vals = [abs(x) for x in _col(rows, "r(") if not math.isnan(x)]
    return max(vals) if vals else float("inf")


def psi_span(rows):
    ps = [x for x in _col(rows, "psi(") if not math.isnan(x)]
    return (max(ps) - min(ps)) if ps else float("inf")


def _opt_sheet(awa_deg):
    return max(5.0, min(85.0, awa_deg - AOA_OPT))


def polar():
    """TWA = angle du vent réel par rapport à l'étrave (0=vent debout, 90=travers, 180=arrière).
    Convention xdyn établie EMPIRIQUEMENT : `direction` = vent VENANT DE (pas 'soufflant vers',
    le commentaire du yaml est trompeur). Bateau étrave Nord (psi=0) -> wind_dir = twa."""
    out = []
    for twa in (15, 30, 45, 60, 90, 120, 150, 180):
        rows = run_sim(twa, _opt_sheet(twa), helm_deg=0.0, tend=30.0)
        out.append((twa, made_good(rows)))
    return out


def main():
    print("=== POLAR (VMG vers l'avant, par angle de vent réel TWA) ===")
    p = polar()
    for twa, spd in p:
        print(f"  TWA {twa:3d} deg -> {spd:+.2f} m/s")
    d = {twa: (0.0 if math.isnan(s) else s) for twa, s in p}   # nan (divergé) -> 0
    mx = max(d.values())
    no_go = d[15] < 0.25 and d[30] < 0.40          # près serré : ~pas de progrès vers le vent
    reach_fast = mx > 0.5 and d[90] >= 0.8 * mx    # pic au travers
    run_slower = d[180] < d[90]                     # vent arrière plus lent que le travers
    print(f"  no-go(TWA<=30)={no_go}  reach_rapide={reach_fast}  run<reach={run_slower}")

    print("=== NO-360 (helm=0, travers) ===")
    rows = run_sim(90, _opt_sheet(90), helm_deg=0.0, tend=40.0)
    span = math.degrees(psi_span(rows))
    # anti-spin : pas de tour complet + pas de divergence. Le pic transitoire de |r| lors du
    # lofe n'est PAS un spin -> on juge sur l'excursion de cap, pas sur max|r|.
    no_360 = span < 150.0 and not rows[-1].get("_diverged")
    print(f"  max|r|={max_abs_r(rows):.3f} rad/s  cap_span={span:.0f} deg  no_360={no_360}")

    print("=== TRIM (travers, balayage sheet) ===")
    trim = [(s, ground_speed(run_sim(90, s, 0.0, 25.0))) for s in (20, 40, 60, 75, 90)]
    for s, spd in trim:
        print(f"  sheet {s:3d} deg -> {spd:.2f} m/s")
    speeds = [(0.0 if math.isnan(x[1]) else x[1]) for x in trim]
    best = max(speeds)
    trim_matters = best > 0.5 and min(speeds) < 0.7 * best
    print(f"  trim_matters={trim_matters}")

    ok = no_go and reach_fast and run_slower and no_360 and trim_matters
    print(f"\n=== {'PASS' if ok else 'FAIL'} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
