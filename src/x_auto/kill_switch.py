"""Global kill switch.

A single file on disk represents the tripped state. Any process (including
ad-hoc CLI invocations) can trip it, and every automation action must call
``KillSwitch.check()`` before touching the network.

Rationale: a file-based implementation is resilient to process crashes and
trivially observable by humans (``ls state/``), which matters more than
performance at this stage.

An optional ``on_trigger`` callback lets a caller record every trip to a
side channel (e.g. the incidents SQLite table) without the KillSwitch itself
needing to know about storage.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class KillSwitchTripped(RuntimeError):
    """Raised when automation attempts to act while the kill switch is tripped."""


TriggerCallback = Callable[[dict[str, Any]], None]


class KillSwitch:
    def __init__(
        self,
        state_file: Path,
        on_trigger: TriggerCallback | None = None,
    ) -> None:
        self.state_file = state_file
        self.on_trigger = on_trigger

    def is_tripped(self) -> bool:
        return self.state_file.exists()

    def state(self) -> dict | None:
        if not self.is_tripped():
            return None
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"reason": "unknown (state file unreadable)"}

    def trigger(self, reason: str, account: str | None = None) -> None:
        payload = {
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "account": account,
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if self.on_trigger is not None:
            # Best-effort — a failing recorder must not prevent the trip.
            try:
                self.on_trigger(payload)
            except Exception:
                pass

    def reset(self) -> None:
        if self.state_file.exists():
            self.state_file.unlink()

    def check(self) -> None:
        """Raise ``KillSwitchTripped`` if tripped. Cheap — call before every action."""
        if self.is_tripped():
            raise KillSwitchTripped(json.dumps(self.state() or {}, ensure_ascii=False))
