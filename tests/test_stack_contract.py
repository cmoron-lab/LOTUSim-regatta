import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_unity_endpoint_patch_failure_stops_stack(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    commands = {
        "lotusim": "exit 0",
        "ros2": "exit 0",
        "sleep": "exit 0",
        "timeout": "exit 1",
        "python3": 'case "$*" in *patch_endpoint_executor.py*) exit 42;; *) exit 0;; esac',
    }
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

    env = os.environ | {
        "LOTUSIM_PATH": str(core),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "UNITY": "1",
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/regatta_stack.sh"), "0", "hold"],
        env=env,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )

    assert result.returncode != 0
    assert "endpoint patch failed" in result.stdout


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
