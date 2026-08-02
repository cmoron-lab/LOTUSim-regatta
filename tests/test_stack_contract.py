import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]


def _stack_env(tmp_path: Path, commands: dict[str, str], **extra: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in commands.items():
        command = bin_dir / name
        command.write_text(f"#!/bin/sh\n{body}\n")
        command.chmod(0o755)

    core = tmp_path / "core"
    physics = core / "physics"
    physics.mkdir(parents=True)
    xdyn = physics / "xdyn-for-cs"
    xdyn.write_text("#!/bin/sh\nexit 0\n")
    xdyn.chmod(0o755)

    return os.environ | {
        "LOTUSIM_PATH": str(core),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        **extra,
    }


def test_endpoint_patch_uses_lotusim_workspace(tmp_path):
    target = (
        tmp_path
        / "install"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "ros_tcp_endpoint"
        / "server.py"
    )
    target.parent.mkdir(parents=True)
    target.write_text(
        """class Server:
    def setup_executor(self):
        self.executor = object()

    def unregister_node(self, old_node):
        if old_node is not None:
            old_node.unregister()
            if self.executor is not None:
                self.executor.remove_node(old_node)


class Commands:
    def subscriber(self, new_subscriber):
        if self.tcp_server.executor is not None:
            self.tcp_server.executor.add_node(new_subscriber)

    def publisher(self, new_publisher):
        if self.tcp_server.executor is not None:
            self.tcp_server.executor.add_node(new_publisher)

    def service(self, new_service):
        if self.tcp_server.executor is not None:
            self.tcp_server.executor.add_node(new_service)

    def service_response(self, new_service):
        if self.tcp_server.executor is not None:
            self.tcp_server.executor.add_node(new_service)
"""
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/patch_endpoint_executor.py")],
        env=os.environ | {"LOTUSIM_WS": str(tmp_path)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert target.read_text().count("self.tcp_server._spin_node(") == 4


def test_unity_endpoint_patch_failure_stops_stack(tmp_path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/regatta_stack.sh"), "0", "hold"],
        env=_stack_env(
            tmp_path,
            {
                "lotusim": "exit 0",
                "ros2": "exit 0",
                "sleep": "exit 0",
                "timeout": "exit 1",
                "python3": 'case "$*" in *patch_endpoint_executor.py*) exit 42;; *) exit 0;; esac',
            },
            UNITY="1",
        ),
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode != 0
    assert "endpoint patch failed" in result.stdout


def test_missing_clock_bridge_stops_stack(tmp_path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/regatta_stack.sh"), "0", "hold"],
        env=_stack_env(
            tmp_path,
            {
                "gz": "exit 0",
                "lotusim": "exit 0",
                "python3": "exit 0",
                "ros2": 'case "$*" in "pkg prefix ros_gz_bridge") exit 1;; *) exit 0;; esac',
                "sleep": "exit 0",
                "timeout": "exit 1",
            },
        ),
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode != 0
    assert "ros_gz_bridge is unavailable" in result.stdout


def test_stack_keeps_system_gazebo_commands_visible(tmp_path):
    gz_config_log = tmp_path / "gz-config.log"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/regatta_stack.sh"), "0", "hold"],
        env=_stack_env(
            tmp_path,
            {
                "gz": "exit 0",
                "lotusim": 'printf "%s" "$GZ_CONFIG_PATH" > "$FAKE_GZ_CONFIG_LOG"',
                "python3": "exit 0",
                "ros2": "exit 0",
                "sleep": "exit 0",
                "timeout": "exit 1",
            },
            FAKE_GZ_CONFIG_LOG=str(gz_config_log),
            GZ_CONFIG_PATH="/opt/ros/vendor/share/gz",
        ),
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0
    assert gz_config_log.read_text() == "/usr/share/gz:/opt/ros/vendor/share/gz"


def test_first_sigint_removes_docker_container(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    container = tmp_path / "container-running"
    docker_log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = run ]; then\n'
        "  trap '' INT TERM\n"
        '  touch "$FAKE_CONTAINER"\n'
        '  while [ -e "$FAKE_CONTAINER" ]; do /bin/sleep 0.05; done\n'
        "else\n"
        '  echo "$*" >> "$FAKE_DOCKER_LOG"\n'
        '  rm -f "$FAKE_CONTAINER"\n'
        "fi\n"
    )
    docker.chmod(0o755)

    env = os.environ | {
        "FAKE_CONTAINER": str(container),
        "FAKE_DOCKER_LOG": str(docker_log),
        "LAB": str(tmp_path),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "RUNNER": "docker",
    }
    process = subprocess.Popen(
        ["bash", str(ROOT / "scripts/run_regatta.sh"), "900", "hold"],
        env=env,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 2
        while not container.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert container.exists(), "fake docker run did not start"

        process.send_signal(signal.SIGINT)
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            returncode = None

        assert returncode == 130, "one SIGINT must stop the wrapper"
        assert not container.exists()
        assert docker_log.read_text().strip() == "rm -f regatta"
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
