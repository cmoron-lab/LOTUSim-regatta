"""merge_conditions.py must replace the model's environment section with the
conditions' one -- ONE occurrence, conditions values -- and touch nothing else.
Duplicate top-level keys are exactly what the xdyn binaries disagree on."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "merge_conditions.py"

MODEL = """rotations convention: [psi, theta', phi'']

environment models:
  - model: uniform wind
    direction: {unit: deg, value: 90.0}

bodies:
  - name: focus_v2
"""

CONDITIONS = """# scenario conditions
environment models:
  - model: no waves
  - model: uniform wind
    direction: {unit: deg, value: 180.0}
"""


def merge(tmp_path, model, conditions):
    m, c, out = tmp_path / "m.yaml", tmp_path / "c.yaml", tmp_path / "out.yaml"
    m.write_text(model)
    c.write_text(conditions)
    r = subprocess.run([sys.executable, str(SCRIPT), str(m), str(c), str(out)])
    return r.returncode, out


def test_conditions_replace_model_environment(tmp_path):
    rc, out = merge(tmp_path, MODEL, CONDITIONS)
    assert rc == 0
    merged = out.read_text()
    assert merged.count("environment models:") == 1
    assert "value: 180.0" in merged
    assert "value: 90.0" not in merged
    # the rest of the model is untouched, sections before and after alike
    assert merged.startswith("rotations convention:")
    assert "bodies:\n  - name: focus_v2" in merged


def test_missing_section_fails_loudly(tmp_path):
    rc, out = merge(tmp_path, MODEL, "just: noise\n")
    assert rc != 0
    assert not out.exists()
