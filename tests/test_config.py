from pathlib import Path

import pytest

from x_auto.config import AccountConfig


REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_YML = REPO_ROOT / "accounts" / "example.yml"


def test_example_yaml_loads() -> None:
    cfg = AccountConfig.from_yaml(EXAMPLE_YML)
    assert cfg.handle == "example_handle"
    assert cfg.mode == "shadow"
    assert cfg.stage == "S0"
    assert cfg.timezone == "Asia/Tokyo"
    assert cfg.daily_post_quota == 3
    assert cfg.circadian_start == "01:00"
    assert cfg.circadian_end == "08:00"
    assert cfg.viewport.width == 390


def test_invalid_circadian_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text(
        "handle: x\n"
        "user_data_dir: /tmp/x\n"
        'circadian_start: "25:00"\n'
        'circadian_end: "08:00"\n',
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        AccountConfig.from_yaml(bad)


def test_env_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_PROXY_PASS", "s3cret")
    bad = tmp_path / "env.yml"
    bad.write_text(
        "handle: x\n"
        "user_data_dir: /tmp/x\n"
        'proxy_url: "http://u:${MY_PROXY_PASS}@host:1"\n',
        encoding="utf-8",
    )
    cfg = AccountConfig.from_yaml(bad)
    assert cfg.proxy_url == "http://u:s3cret@host:1"
