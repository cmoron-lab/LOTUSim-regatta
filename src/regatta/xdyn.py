#!/usr/bin/env python3
"""Websocket client for xdyn-for-cs, driving it directly with no gz and no ROS.
The control brain lives in regatta.pilot; this file is pure transport plus the
proven xdyn co-sim conventions.

Nothing here is regatta-specific: it speaks xdyn's co-simulation API, the same
one the gz physics_interface_plugin uses. It is a second client of that API for
testing, never a bypass of the production path.

Co-sim rule: rkck is forbidden (monotonic clock) -> rk4. Launch with a fine --dt
and, for maneuvers, communicate no faster than needed (effective step = min(--dt,
Dt)). xdyn convention (verified): quaternion (qr,qi,qj,qk) = attitude body->NED;
velocities (u,v,w),(p,q,r) = body frame; position (x,y,z) = NED."""

import base64
import json
import math
import os
import re
import socket
import struct
import subprocess
import time

# The temp model and the launch log both live in /tmp. The previous version derived
# a repo path by counting parent directories, which silently depended on this file
# sitting exactly two levels below the root -- it now sits three.
XDYN_LOG = "/tmp/xdyn_offline.log"  # where a failed launch explains itself
MODEL_TMP = "/tmp/regatta_cosim_model.yaml"


def _lotusim_path():
    """Root of the installed LOTUSim tree.

    Checked here rather than at import time. Raising at module scope made the
    traceback end on `import ws`, so a missing environment variable was reported as
    a missing module -- which is exactly how this failure reached us."""
    path = os.environ.get("LOTUSIM_PATH", "")
    if not path:
        raise RuntimeError("LOTUSIM_PATH is unset -- source the environment first: . ./env.sh")
    return path


def write_model(wind_dir_deg, wind_speed=None):
    """Write a temp model yaml with the requested wind direction and an absolute mesh path."""
    lotusim = _lotusim_path()
    # Absolute mesh path: xdyn resolves a relative one against its cwd, and the cwd
    # differs between the offline and the gz paths.
    mesh = f"{lotusim}/assets/models/focus_v2/meshes/focus_v2.stl"
    src = open(f"{lotusim}/assets/models/focus_v2/focus_v2.yaml").read()
    src, n = re.subn(
        r"(direction:\s*\{unit:\s*deg,\s*value:\s*)[-\d.]+",
        rf"\g<1>{wind_dir_deg}",
        src,
        count=1,
    )
    assert n == 1, "wind direction not found in model yaml"
    if wind_speed is not None:
        src = re.sub(
            r"(velocity:\s*\{unit:\s*m/s,\s*value:\s*)[-\d.]+",
            rf"\g<1>{wind_speed}",
            src,
            count=1,
        )
    src = re.sub(r"^(\s*mesh:\s*)\S+\.stl", rf"\g<1>{mesh}", src, count=1, flags=re.M)
    open(MODEL_TMP, "w").write(src)


# ---------- minimal websocket client (stdlib, RFC6455) ----------
def ws_connect(host, port, path="/", timeout=10):
    s = socket.create_connection((host, port), timeout=timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    s.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        d = s.recv(4096)
        if not d:
            raise RuntimeError("handshake: connection closed")
        buf += d
    if b" 101 " not in buf.split(b"\r\n", 1)[0]:
        raise RuntimeError(f"handshake failed: {buf.split(chr(13).encode())[0]!r}")
    return s


def _recv_exact(s, n):
    buf = b""
    while len(buf) < n:
        d = s.recv(n - len(buf))
        if not d:
            raise RuntimeError("frame: connection closed")
        buf += d
    return buf


def ws_send(s, text):
    p = text.encode()
    hdr = bytearray([0x81])  # FIN + text opcode
    n = len(p)
    mask = os.urandom(4)
    if n < 126:
        hdr.append(0x80 | n)
    elif n < 65536:
        hdr.append(0x80 | 126)
        hdr += struct.pack(">H", n)
    else:
        hdr.append(0x80 | 127)
        hdr += struct.pack(">Q", n)
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
            raise RuntimeError("server closed (close frame)")
        if opcode == 0x9:  # ping -> ignore
            continue
        if opcode in (0x1, 0x2):
            return payload.decode()


# ---------- launch / step ----------
_XDYN_PROC = None


def launch_xdyn(port=12345, solver="rk4", dt=0.005):
    """Start xdyn-for-cs locally. The binary is x86-64: this needs an x86-64 host.
    `dt` = INTERNAL integration step (--dt). rk4 mandatory."""
    global _XDYN_PROC
    # A leftover xdyn holding the port is worse than a crash: the new one dies of
    # "Address already in use" while _wait_listening happily connects to the OLD
    # server, and the run silently uses the wrong model. Refuse instead.
    # ponytail: TOCTOU between this bind and xdyn's own -- fine for a test harness.
    with socket.socket() as probe:
        # SO_REUSEADDR like asio does, or sockets left in TIME_WAIT by the previous
        # run would read as "busy" for a minute and block every relaunch.
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise RuntimeError(
                f"port {port} is busy -- another xdyn is still running. "
                f"Who owns it: ss -ltnp '( sport = :{port} )' -- check whether it is "
                f"someone's run before killing it."
            ) from None
    lotusim = _lotusim_path()
    physics = os.path.join(lotusim, "physics")
    _XDYN_PROC = subprocess.Popen(
        [
            os.path.join(physics, "xdyn-for-cs"),
            MODEL_TMP,
            "-s",
            solver,
            "--dt",
            str(dt),
            "-a",
            "127.0.0.1",
            "-p",
            str(port),
        ],
        cwd=os.path.join(lotusim, "assets", "models"),
        env=dict(os.environ, LD_LIBRARY_PATH=physics),
        stdout=open(XDYN_LOG, "w"),
        stderr=subprocess.STDOUT,
    )
    _wait_listening(_XDYN_PROC, port)


def _wait_listening(proc, port, timeout=20.0):
    """Block until xdyn accepts connections. It binds only once the websocket
    server is up, so an accepted TCP connect means the handshake will work.
    Raises rather than returning early: a dead xdyn otherwise shows up much
    later as an unexplained hang in the first step()."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        rc = proc.poll()
        if rc is not None:
            raise RuntimeError(f"xdyn-for-cs exited with {rc} -- see {XDYN_LOG}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"xdyn-for-cs not listening on {port} after {timeout}s")


def stop_xdyn():
    global _XDYN_PROC
    if _XDYN_PROC is not None:
        _XDYN_PROC.kill()  # xdyn, like gz, is not reliable on SIGTERM
        _XDYN_PROC.wait()
        _XDYN_PROC = None


INIT = {
    "t": 0.0,
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "qi": 0.0,
    "qj": 0.0,
    "qk": 0.0,
    "qr": 1.0,
    "u": 0.0,
    "v": 0.0,
    "w": 0.0,
    "p": 0.0,
    "q": 0.0,
    "r": 0.0,
}
FIELDS = ("t", "x", "y", "z", "qi", "qj", "qk", "qr", "u", "v", "w", "p", "q", "r")


_LOGF = None


def _wslog(direction, msg):
    global _LOGF
    path = os.environ.get("WS_LOG")
    if not path:
        return
    if _LOGF is None:
        _LOGF = open(path, "w", buffering=1)
    _LOGF.write(
        json.dumps({"ts": time.time(), "dir": direction, "msg": msg}, separators=(",", ":")) + "\n"
    )


def step(sock, state, sheet_rad, helm_rad, dt):
    req = {
        "Dt": dt,
        "states": [state],
        "commands": {"mainsail(sheet)": sheet_rad, "rudder(helm)": helm_rad},
        "requested_output": [],
    }
    _wslog("c2x", req)
    ws_send(sock, json.dumps(req))
    reply_text = ws_recv(sock)
    reply = json.loads(reply_text)
    _wslog("x2c", reply)
    if isinstance(reply, dict) and "error" in reply:
        raise RuntimeError("xdyn: " + str(reply["error"])[:200])
    out = {}
    for k in FIELDS:
        v = reply.get(k)
        out[k] = (v[-1] if isinstance(v, list) else v) if v is not None else state[k]
    return out


def yaw_of(st):
    """Compass heading (rad, NED) from the body->NED attitude quaternion."""
    qr, qi, qj, qk = st["qr"], st["qi"], st["qj"], st["qk"]
    return math.atan2(2 * (qr * qk + qi * qj), 1 - 2 * (qj * qj + qk * qk))


def init_at(heading, u=0.0):
    """Initial state at `heading` (rad, NED) with body surge speed `u`."""
    st = dict(INIT)
    st["qr"] = math.cos(heading / 2.0)
    st["qk"] = math.sin(heading / 2.0)
    st["u"] = u
    return st
