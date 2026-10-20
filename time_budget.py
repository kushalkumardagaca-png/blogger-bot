"""One clock for a Master preparation run, so a slow network cannot eat the publication day."""
from __future__ import annotations

import os
import time

DEFAULT_MINUTES = 30.0
HARD_MAX_MINUTES = 38.0
FLOOR_SECONDS = 45


def configured_minutes() -> float:
    raw = str(os.environ.get("MASTER_PREPARATION_BUDGET_MINUTES", "")).strip()
    try:
        value = float(raw) if raw else DEFAULT_MINUTES
    except ValueError:
        value = DEFAULT_MINUTES
    return min(HARD_MAX_MINUTES, max(5.0, value))


class Budget:
    """A monotonic deadline shared by research, writing, validation and photo selection.

    Before this existed a Master attempt had no internal clock: the workflow allowed 120
    minutes, and one slow Commons download or one hung model call could spend the whole
    publication day while the slot quietly went unfilled. The owner's instruction on
    20 October 2026 was that preparation must not exceed 40 minutes, so the run now works to
    a deadline and stops politely - it fails with a named reason and a persisted number, and
    recovery starts a fresh attempt within ten minutes instead of a single job grinding until
    midnight.

    The deadline never weakens a quality gate. It only decides when to stop trying.
    """

    def __init__(self, minutes: float | None = None):
        self.minutes = configured_minutes() if minutes is None else float(minutes)
        self._start = time.monotonic()
        self._end = self._start + self.minutes * 60

    def remaining(self) -> float:
        return max(0.0, self._end - time.monotonic())

    def elapsed_minutes(self) -> float:
        return round((time.monotonic() - self._start) / 60, 1)

    def out(self) -> bool:
        return self.remaining() <= 0

    def seconds(self, ceiling: int = 60, floor: int = FLOOR_SECONDS) -> int:
        """How long one network call may block: never more than the run has left."""
        return int(max(min(floor, ceiling), min(ceiling, self.remaining())))

    def note(self) -> dict:
        return {"budgetMinutes": round(self.minutes, 1), "elapsedMinutes": self.elapsed_minutes(),
                "remainingMinutes": round(self.remaining() / 60, 1)}

    def stop(self, doing: str) -> "RuntimeError":
        """The error every loop raises when the clock runs out, so the reason is readable."""
        return RuntimeError(f"time budget of {self.minutes:.0f} minutes exhausted while {doing} "
                            f"(elapsed {self.elapsed_minutes()} minutes); the slot is retried by recovery")


BUDGET = Budget()
