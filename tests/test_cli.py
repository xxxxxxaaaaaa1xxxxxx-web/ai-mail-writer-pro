from datetime import datetime, timedelta, timezone
from pathlib import Path

from x_auto import cli
from x_auto.analytics import AccountMetrics
from x_auto.storage import MetricsRow, Storage


def _base_args(tmp_path: Path) -> list[str]:
    return [
        "--state-file",
        str(tmp_path / "ks.json"),
        "--db",
        str(tmp_path / "x.db"),
    ]


def test_kill_reset_status_cycle(tmp_path: Path, capsys) -> None:
    state = tmp_path / "state" / "ks.json"
    db = tmp_path / "x.db"
    args = ["--state-file", str(state), "--db", str(db)]

    assert cli.main([*args, "status"]) == 0
    assert "kill_switch: ok" in capsys.readouterr().out

    assert cli.main([*args, "kill", "--reason", "boom"]) == 0
    assert state.exists()

    assert cli.main([*args, "status"]) == 0
    assert "TRIPPED" in capsys.readouterr().out

    assert cli.main([*args, "reset"]) == 0
    assert not state.exists()


def test_kill_command_records_incident(tmp_path: Path) -> None:
    cli.main(
        [
            *_base_args(tmp_path),
            "kill",
            "--reason",
            "integration_test",
            "--account-handle",
            "alice",
        ]
    )
    storage = Storage(tmp_path / "x.db")
    incidents = storage.recent_incidents()
    assert len(incidents) == 1
    assert incidents[0]["kind"] == "kill_switch"
    assert incidents[0]["account_handle"] == "alice"
    assert incidents[0]["detail"]["reason"] == "integration_test"


def test_incidents_command_empty(tmp_path: Path, capsys) -> None:
    rc = cli.main([*_base_args(tmp_path), "incidents"])
    assert rc == 0
    assert "no incidents" in capsys.readouterr().out


def test_incidents_command_lists_rows(tmp_path: Path, capsys) -> None:
    storage = Storage(tmp_path / "x.db")
    storage.record_incident("manual", account="alice", detail={"reason": "x"})
    storage.record_incident("rate_limit", account="bob")

    rc = cli.main([*_base_args(tmp_path), "incidents"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "manual" in out
    assert "rate_limit" in out
    assert "@alice" in out
    assert "@bob" in out


def test_history_command_empty(tmp_path: Path, capsys) -> None:
    account_yml = tmp_path / "acc.yml"
    account_yml.write_text(
        "handle: me\nuser_data_dir: /tmp/me\n",
        encoding="utf-8",
    )
    rc = cli.main(
        [*_base_args(tmp_path), "history", "--account", str(account_yml)]
    )
    assert rc == 0
    assert "no snapshots for @me" in capsys.readouterr().out


def test_history_command_prints_time_series(tmp_path: Path, capsys) -> None:
    account_yml = tmp_path / "acc.yml"
    account_yml.write_text(
        "handle: me\nuser_data_dir: /tmp/me\n",
        encoding="utf-8",
    )
    storage = Storage(tmp_path / "x.db")
    base = datetime(2026, 4, 10, tzinfo=timezone.utc)
    for i, f in enumerate([100, 110, 120]):
        storage.record_metrics(
            AccountMetrics(
                handle="me",
                followers=f,
                verified_followers=f // 10,
                posts=f * 2,
                collected_at=(base + timedelta(hours=i)).isoformat(),
            )
        )

    rc = cli.main(
        [*_base_args(tmp_path), "history", "--account", str(account_yml)]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "metrics history (latest 3)" in out
    assert "followers=   120" in out
    assert "followers=   100" in out


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
    assert "█" in text
    assert "░" in text
    assert "follow ratio:       0.21" in text
    assert "⚠" not in text


def test_render_metrics_with_delta() -> None:
    current = AccountMetrics(
        handle="me",
        followers=1200,
        verified_followers=125,
        posts=876,
    )
    previous = MetricsRow(
        handle="me",
        collected_at="2026-04-09T12:00:00+00:00",
        followers=1150,
        following=None,
        verified_followers=120,
        posts=870,
    )
    text = cli._render_metrics(current, previous=previous)
    assert "(+50)" in text
    assert "(+5)" in text
    assert "(+6)" in text
    assert "Δ since:            2026-04-09T12:00:00+00:00" in text


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
