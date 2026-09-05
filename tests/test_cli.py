import subprocess
import sys

from leakproof.cli import main


def test_verify_runs_registered_gates(capsys):
    assert main(["verify"]) == 0
    out = capsys.readouterr().out
    assert "contract-self-check" in out
    assert "0 failed" in out


def test_unbuilt_commands_name_their_lane(capsys):
    assert main(["throughput"]) == 2
    assert "lane N" in capsys.readouterr().err


def test_a_built_command_is_not_in_the_unbuilt_table():
    # gen moved out of NOT_BUILT at the Wave 1 close; the table and the
    # dispatch have to agree or a wired command still exits 2.
    from leakproof.cli import NOT_BUILT

    assert "gen" not in NOT_BUILT


def test_module_entry_point():
    proc = subprocess.run(
        [sys.executable, "-m", "leakproof", "verify"], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
