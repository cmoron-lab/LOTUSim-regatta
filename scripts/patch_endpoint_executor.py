#!/usr/bin/env python3
"""Runtime patch for ros_tcp_endpoint under rclpy 7.1.x (Jazzy, 2026 images).

Symptom: the endpoint accepts Unity registrations ("RegisterSubscriber OK")
but never forwards a single ROS message; the main thread spins at ~70% CPU
in MultiThreadedExecutor._wait_for_ready_callbacks.

Root cause (proven live, 2026-08-01, container lotusim:focus-v2):
- nodes added to an already-spinning central executor are never serviced;
- Executor.shutdown() poisons the shared context (RCLError: context invalid)
  so a rebuild-on-change loop is not possible either;
- spinning each node on its own thread with its OWN SingleThreadedExecutor
  works (rclpy.spin_once(node) is not an option: it routes every call to the
  shared global executor, so all but one thread die with "Executor is
  already spinning").

Patch: replace the central executor with per-node daemon spinner threads,
each owning a private SingleThreadedExecutor.
Idempotent. Applies to the INSTALLED package inside the container:
  docker exec regatta python3 /lab/LOTUSim-regatta/scripts/patch_endpoint_executor.py
"""
import py_compile
import re
import sys

TARGET = "/lotusim_ws/install/lib/python3.12/site-packages/ros_tcp_endpoint/server.py"

NEW_SETUP = '''    def _spin_node(self, node):
        """Spin one node on its own daemon thread.

        rclpy 7.1.x (Jazzy): a central executor never services nodes added
        after spin started, and Executor.shutdown() poisons the shared
        context (RCLError: context is not valid). Per-node spin_once threads
        sidestep both; proven against a live 80 Hz publisher."""
        from rclpy.executors import SingleThreadedExecutor
        def loop(n):
            executor = SingleThreadedExecutor()
            executor.add_node(n)
            while rclpy.ok():
                try:
                    executor.spin_once(timeout_sec=0.1)
                except Exception as e:
                    self.logerr("spinner exited for {}: {}".format(n.get_name(), e))
                    return
        t = threading.Thread(target=loop, args=(node,), daemon=True)
        t.start()

    def setup_executor(self):
        self._spin_node(self)
        # Park the main thread; the per-node daemon threads do the work.
        threading.Event().wait()
'''


def main() -> int:
    src = open(TARGET).read()
    if "_spin_node" in src:
        print("already patched")
        return 0

    src = re.sub(
        r"    def setup_executor\(self\):.*?(?=    def unregister_node)",
        NEW_SETUP + "\n",
        src,
        count=1,
        flags=re.S,
    )

    # SysCommands: spin each dynamically registered node on its own thread
    # instead of adding it to the (dead) central executor.
    src, n = re.subn(
        r"^        if self\.tcp_server\.executor is not None:\n"
        r"            self\.tcp_server\.executor\.add_node\((new_\w+)\)$",
        r"        self.tcp_server._spin_node(\1)",
        src,
        flags=re.M,
    )

    # unregister_node: the central executor no longer exists.
    src = src.replace(
        "        if old_node is not None:\n"
        "            old_node.unregister()\n"
        "            if self.executor is not None:\n"
        "                self.executor.remove_node(old_node)",
        "        if old_node is not None:\n"
        "            old_node.unregister()",
    )

    assert "_spin_node(self)" in src, "setup_executor replacement failed"
    assert n == 4, f"expected 4 add_node sites, got {n}"
    assert "executor.remove_node" not in src

    open(TARGET, "w").write(src)
    py_compile.compile(TARGET, doraise=True)
    print("patched OK (4 spinner sites)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
