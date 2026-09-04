import subprocess
import sys

from leakproof.cli import main


def test_verify_runs_registered_gates(capsys):
    assert main(["verify"]) == 0
    out = capsys.readouterr().out
    assert "contract-self-check" in out
    assert "0 failed" in out


def test_unbuilt_commands_name_their_lane(capsys):
    assert main(["gen"]) == 2
    assert "lane B" in capsys.readouterr().err


def test_module_entry_point():
    proc = subprocess.run(
        [sys.executable, "-m", "leakproof", "verify"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
