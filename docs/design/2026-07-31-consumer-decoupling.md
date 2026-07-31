# Consumer decoupling: bound the queues, open per-topic QoS

Status: **draft — pending review** (patch ready on a local branch, not pushed)

## Problem

The sim→renderer path is backpressure-free by design (verified in code,
2026-07-31: fire-and-forget DDS publish in `render_plugin`, unbounded queues at
every process boundary). That is the right architecture — a slow consumer
cannot slow the simulation — but the two unbounded queues are its debt:

1. **`ros_tcp_endpoint` sender queue** (`tcp_sender.py`, `local_queue =
   Queue()`): a client reading slower than gz publishes (100 pose msg/s at
   comm 0.01) grows the queue without limit. Memory is the visible cost; the
   worse one is **latency**: every queued state message is staler than the
   next, so a struggling renderer shows an increasingly out-of-date world —
   the "swap death spiral" row in `measurements/2026-07-30-macOS.md` had this
   as a plausible contributor.
2. **One QoS for every subscription** (`subscriber.py:45`):
   `RELIABLE`+`TRANSIENT_LOCAL`, depth 1000, hardcoded — already flagged in the
   ROADMAP ("a Unity client cannot choose BEST_EFFORT"). State streams want
   the latest sample; commands want lossless delivery. One profile cannot
   serve both.

The Unity-side `ROSConnection` queue (unbounded `ConcurrentQueue`, drained
once per frame) is the residual third queue; endpoint-side coalescing bounds
what reaches it in practice (at most ~one state frame per send cycle), so it
is out of scope here.

## Patch (fork `LOTUSim-Unity-ros-tcp-endpoint`, branch `feat/consumer-decoupling`, commit `0578e71`)

Two opt-in ROS parameters on the endpoint node, **empty by default —
behavior unchanged unless configured**:

| Parameter | Effect |
|---|---|
| `COALESCE_TOPICS` (csv regex) | Matching topics keep at most **one pending frame** in the sender queue: a newer frame replaces the pending one instead of queuing behind it. FIFO order and losslessness preserved for everything else (commands, handshake, services, logs). |
| `BEST_EFFORT_TOPICS` (csv regex) | Matching subscriptions use `BEST_EFFORT`/`VOLATILE`/`KEEP_LAST(1)` instead of the historical profile. A BEST_EFFORT subscriber under a RELIABLE publisher is valid DDS. |

Implementation: coalescing isolated in `outgoing_queue.py` (stdlib-only, so it
is unit-testable without rclpy — 6 tests including a 5000-frame flood proving
"latest always arrives, older never re-delivered after newer").

## Deployment (follow-up, one line in `regatta_stack.sh`)

```
--ros-args -p 'COALESCE_TOPICS:=renderer_poses$' -p 'BEST_EFFORT_TOPICS:=renderer_poses$'
```

The pattern targets only the pose stream (both `/renderer_poses` and
`lotusim/renderer_poses` registrations match). `renderer_cmd` must keep
RELIABLE+TRANSIENT_LOCAL: the latched CREATE is exactly what that profile is
for.

## Validation plan

1. Unit: done (6/6, host, no ROS).
2. In-stack: run the demo with the parameters set; verify poses flow and the
   boat spawns (CREATE unaffected). Then artificially stall the client
   (SIGSTOP the player a few seconds, resume): with coalescing the world must
   snap to the present, not replay the backlog; endpoint memory must stay flat.
3. Only then: PR to the fork (opensource-contributor process: check existing
   issues/PRs upstream, tracking issue first, via cmoron-lab).

## Non-goals

- No protocol change (the Unity client still cannot *request* a QoS; the
  endpoint operator decides — good enough for our deployments, and
  upstream-friendly).
- No Unity-side queue work (see residual above).
- No change to defaults: upstream-safe by construction.
