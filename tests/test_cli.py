from pathlib import Path

from x_auto import cli


def test_kill_reset_status_cycle(tmp_path: Path, capsys) -> None:
    state = tmp_path / "state" / "ks.json"

    assert cli.main(["--state-file", str(state), "status"]) == 0
    assert "kill_switch: ok" in capsys.readouterr().out

    assert (
        cli.main(["--state-file", str(state), "kill", "--reason", "boom"]) == 0
    )
    assert state.exists()

    assert cli.main(["--state-file", str(state), "status"]) == 0
    assert "TRIPPED" in capsys.readouterr().out

    assert cli.main(["--state-file", str(state), "reset"]) == 0
    assert not state.exists()
