"""Which card to review next."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fsrs import State as FsrsState

from .state import LEARN_AHEAD
from .vault import Card


@dataclass
class Queue:
    due: list[Card]            # reviewed before and due now, most overdue first
    new: list[Card]            # never reviewed, from lessons already opened, within today's allowance
    ahead: list[Card]          # still in learning steps, due within LEARN_AHEAD

    def next(self) -> Card | None:
        for bucket in (self.due, self.new, self.ahead):
            if bucket:
                return bucket[0]
        return None

    def __len__(self) -> int:
        return len(self.due) + len(self.new)


def build(cards: dict[str, Card], viewed: set[str], states: dict, flagged: set[str],
          new_allowance: int, at: datetime) -> Queue:
    """A card enters review only once its lesson has been opened: reviewing
    something never taught builds nothing. Flagged cards wait for a rewrite."""
    live = [c for c in cards.values() if c.lesson_id in viewed and c.id not in flagged]
    due, new, ahead = [], [], []
    for card in live:
        state = states.get(card.id)
        if state is None:
            new.append(card)
        elif state.due <= at:
            due.append(card)
        elif state.state in (FsrsState.Learning, FsrsState.Relearning) and state.due <= at + LEARN_AHEAD:
            ahead.append(card)
    due.sort(key=lambda c: states[c.id].due)
    ahead.sort(key=lambda c: states[c.id].due)
    return Queue(due, new[: max(new_allowance, 0)], ahead)
