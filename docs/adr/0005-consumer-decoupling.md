# 0005 — Bounded sender queue and per-topic QoS

Status: **proposed — designed, unit-tested, not integrated**, 2026-07-31

## Context

The sim→renderer path is backpressure-free by design, verified in code: fire-and-forget
DDS publish in `render_plugin`, unbounded queues at every process boundary. That is
the right architecture — a slow consumer must not slow the simulation — but two
unbounded queues are its debt.

The `ros_tcp_endpoint` sender queue grows without limit when a client reads slower
than gz publishes. Memory is the visible cost; the worse one is latency, since every
queued state message is staler than the next, so a struggling renderer shows an
increasingly out-of-date world.

And one hardcoded QoS serves every subscription — `RELIABLE`+`TRANSIENT_LOCAL`,
depth 1000. State streams want the latest sample, commands want lossless delivery;
one profile cannot serve both.

## Decision

Two opt-in ROS parameters on the endpoint node, empty by default so behaviour is
unchanged unless configured. `COALESCE_TOPICS` keeps at most one pending frame for
matching topics, a newer frame replacing the pending one. `BEST_EFFORT_TOPICS`
switches matching subscriptions to `BEST_EFFORT`/`VOLATILE`/`KEEP_LAST(1)`.

Coalescing is isolated in `outgoing_queue.py`, stdlib-only so it is unit-testable
without rclpy: 6 tests including a 5000-frame flood proving the latest always arrives
and an older frame is never re-delivered after a newer one.

## Consequences

`renderer_cmd` must keep `RELIABLE`+`TRANSIENT_LOCAL` — the latched CREATE is exactly
what that profile is for; only the pose stream is targeted.

Still owed before this becomes `accepted`: in-stack validation (stall the client with
SIGSTOP, resume, and check the world snaps to the present rather than replaying the
backlog) and an upstream PR to the endpoint fork.
