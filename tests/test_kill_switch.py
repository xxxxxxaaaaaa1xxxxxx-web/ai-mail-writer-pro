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


def test_kill_switch_on_trigger_callback(tmp_path: Path) -> None:
    captured: list[dict] = []
    ks = KillSwitch(
        tmp_path / "ks.json",
        on_trigger=lambda payload: captured.append(payload),
    )
    ks.trigger(reason="boom", account="alice")
    assert len(captured) == 1
    assert captured[0]["reason"] == "boom"
    assert captured[0]["account"] == "alice"


def test_kill_switch_callback_failure_does_not_mask_trip(tmp_path: Path) -> None:
    def explode(_payload: dict) -> None:
        raise RuntimeError("recorder is down")

    ks = KillSwitch(tmp_path / "ks.json", on_trigger=explode)
    ks.trigger(reason="boom")  # must not raise
    assert ks.is_tripped()
