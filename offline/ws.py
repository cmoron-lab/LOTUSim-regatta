#!/usr/bin/env python3
"""Websocket + Docker helpers to drive xdyn-for-cs directly (no gz/ROS), migrated
from _offline/cosim.py. The control brain lives in regatta_agents.pilot; this file
is pure transport + the proven xdyn co-sim conventions.

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

LAB = os.path.expanduser("~/src/lotusim-lab")
IMAGE = "lotusim:focus-v2"
MODEL_SRC = f"{LAB}/LOTUSim/assets/models/focus_v2/focus_v2.yaml"
OFF = f"{LAB}/LOTUSim-regatta/offline"
C_MESH = "/lab/LOTUSim/assets/models/focus_v2/meshes/focus_v2.stl"


def write_model(wind_dir_deg, wind_speed=None):
    """Write a temp model yaml with the requested wind direction and an absolute mesh path."""
    src = open(MODEL_SRC).read()
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
    src = re.sub(r"^(\s*mesh:\s*)\S+\.stl", rf"\g<1>{C_MESH}", src, count=1, flags=re.M)
    open(f"{OFF}/_cosim_model.yaml", "w").write(src)


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
def launch_xdyn(port=12345, solver="rk4", dt=0.005, name="regatta_cosim"):
    """Launch xdyn-for-cs in Docker. `dt` = INTERNAL integration step (--dt). rk4 mandatory."""
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    inner = (
        "chmod +x /lab/LOTUSim/physics/xdyn-for-cs 2>/dev/null; "
        f"/lab/LOTUSim/physics/xdyn-for-cs /lab/LOTUSim-regatta/offline/_cosim_model.yaml "
        f"-s {solver} --dt {dt} -a 0.0.0.0 -p {port}"
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "--platform",
            "linux/amd64",
            "-p",
            f"{port}:{port}",
            "-v",
            f"{LAB}:/lab",
            "-w",
            "/lab/LOTUSim/assets/models",
            "-e",
            "LD_LIBRARY_PATH=/lab/LOTUSim/physics",
            IMAGE,
            "bash",
            "-lc",
            inner,
        ],
        check=True,
        capture_output=True,
    )
    return name


def stop_xdyn(name="regatta_cosim"):
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)


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
        json.dumps(
            {"ts": time.time(), "dir": direction, "msg": msg}, separators=(",", ":")
        )
        + "\n"
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
