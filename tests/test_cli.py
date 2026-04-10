from pathlib import Path

from x_auto import cli
from x_auto.analytics import AccountMetrics


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


def test_render_metrics_full() -> None:
    m = AccountMetrics(
        handle="me",
        followers=1200,
        following=250,
        verified_followers=125,
        posts=876,
    )
    text = cli._render_metrics(m)
    assert "@me" in text
    assert "1200" in text
    assert "125 / 500" in text
    assert "25.0%" in text
    assert "876" in text
    # Progress bar uses block characters.
    assert "█" in text
    assert "░" in text
    # follow ratio 250/1200 ~= 0.21, below the 1.1 guard.
    assert "follow ratio:       0.21" in text
    assert "⚠" not in text


def test_render_metrics_partial_unknown() -> None:
    m = AccountMetrics(handle="me", followers=10)
    text = cli._render_metrics(m)
    assert "followers:          10" in text
    assert "following:          ?" in text
    assert "verified followers: ? / 500" in text
    assert "posts:              ?" in text


def test_render_metrics_follow_ratio_warning() -> None:
    m = AccountMetrics(handle="me", followers=100, following=200)
    text = cli._render_metrics(m)
    assert "follow ratio:       2.00" in text
    assert "⚠ above 1.1 guard" in text


def test_progress_bar_shape() -> None:
    bar_empty = cli._progress_bar(0.0)
    bar_full = cli._progress_bar(1.0)
    bar_half = cli._progress_bar(0.5)
    assert len(bar_empty) == cli._BAR_WIDTH
    assert len(bar_full) == cli._BAR_WIDTH
    assert len(bar_half) == cli._BAR_WIDTH
    assert bar_empty.count("█") == 0
    assert bar_full.count("█") == cli._BAR_WIDTH
    assert bar_half.count("█") == cli._BAR_WIDTH // 2 or bar_half.count("█") == (cli._BAR_WIDTH // 2) + 1
