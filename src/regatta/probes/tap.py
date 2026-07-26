#!/usr/bin/env python3
"""Passive websocket tap: TCP passthrough (listen -> target) that logs decoded
websocket text frames as JSONL. Bytes are forwarded verbatim; decoding is
purely passive, so a decode bug can never corrupt the plugin<->xdyn stream.

Stdlib only, so it runs anywhere the harness does. Point the gz plugin's
<uri> at ws://127.0.0.1:9999 and xdyn stays on 12345.

Log lines: {"ts": <epoch>, "dir": "c2x"|"x2c", "msg": <json|string>}
           ("c2x" = gz plugin -> xdyn, "x2c" = xdyn -> gz plugin)
"""

import argparse
import asyncio
import json
import time


class Sniffer:
    """Incremental passive decoder of one direction of a ws byte stream."""

    def __init__(self, direction, logf):
        self.dir, self.logf = direction, logf
        self.buf = bytearray()
        self.in_http = True
        self.frag = bytearray()
        self.dead = False

    def log(self, obj):
        self.logf.write(json.dumps(obj, separators=(",", ":")) + "\n")

    def feed(self, data):
        if self.dead:
            return
        try:
            self.buf += data
            if self.in_http:
                i = self.buf.find(b"\r\n\r\n")
                if i < 0:
                    return
                self.log(
                    {
                        "ts": time.time(),
                        "dir": self.dir,
                        "http": self.buf[:i].decode("latin1"),
                    }
                )
                del self.buf[: i + 4]
                self.in_http = False
            while self._frame():
                pass
        except Exception as e:  # decode must never kill the pump
            self.dead = True
            self.log({"ts": time.time(), "dir": self.dir, "decode_error": repr(e)})

    def _frame(self):
        b = self.buf
        if len(b) < 2:
            return False
        fin, op = b[0] & 0x80, b[0] & 0x0F
        masked, ln = b[1] & 0x80, b[1] & 0x7F
        i = 2
        if ln == 126:
            if len(b) < 4:
                return False
            ln = int.from_bytes(b[2:4], "big")
            i = 4
        elif ln == 127:
            if len(b) < 10:
                return False
            ln = int.from_bytes(b[2:10], "big")
            i = 10
        key = None
        if masked:
            if len(b) < i + 4:
                return False
            key = bytes(b[i : i + 4])
            i += 4
        if len(b) < i + ln:
            return False
        payload = bytes(b[i : i + ln])
        del b[: i + ln]
        if key:
            payload = bytes(c ^ key[j % 4] for j, c in enumerate(payload))
        if op in (0, 1, 2):  # continuation / text / binary
            self.frag += payload
            if fin:
                text = self.frag.decode("utf-8", "replace")
                self.frag = bytearray()
                try:
                    msg = json.loads(text)
                except ValueError:
                    msg = text
                self.log({"ts": time.time(), "dir": self.dir, "msg": msg})
        elif op == 8:
            self.log({"ts": time.time(), "dir": self.dir, "close": True})
        return True


async def pump(reader, writer, sniffer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            sniffer.feed(data)
            writer.write(data)
            await writer.drain()
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(client_r, client_w, target, logf):
    tr, tw = await asyncio.open_connection(*target)
    await asyncio.gather(
        pump(client_r, tw, Sniffer("c2x", logf)),
        pump(tr, client_w, Sniffer("x2c", logf)),
        return_exceptions=True,
    )


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=int, default=9999)
    ap.add_argument("--target", default="127.0.0.1:12345")
    # /lab/... was the path inside the Docker image, dead since the native port.
    ap.add_argument("--log", default="/tmp/regatta_tap.jsonl")
    a = ap.parse_args()
    host, port = a.target.rsplit(":", 1)
    logf = open(a.log, "w", buffering=1)
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, (host, int(port)), logf), "127.0.0.1", a.listen
    )
    print(f"ws_tap: :{a.listen} -> {a.target}, log {a.log}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
