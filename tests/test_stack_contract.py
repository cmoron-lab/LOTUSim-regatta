import os
import subprocess
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
