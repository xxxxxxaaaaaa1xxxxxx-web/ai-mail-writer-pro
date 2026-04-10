from pathlib import Path

import pytest

from x_auto.kill_switch import KillSwitch, KillSwitchTripped


def test_kill_switch_lifecycle(tmp_path: Path) -> None:
    ks = KillSwitch(tmp_path / "state" / "kill_switch.json")
    assert not ks.is_tripped()
    ks.check()  # should not raise

    ks.trigger(reason="test", account="alice")
    assert ks.is_tripped()
    state = ks.state()
    assert state is not None
    assert state["reason"] == "test"
    assert state["account"] == "alice"
    assert "triggered_at" in state

    with pytest.raises(KillSwitchTripped):
        ks.check()

    ks.reset()
    assert not ks.is_tripped()
    ks.check()  # no longer raises
