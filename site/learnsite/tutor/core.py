"""The tutor, independent of Telegram: who is asking, about which lesson, and what to say."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import queue
from ..state import State, now
from ..vault import Learner, Lesson, Vault
from . import context
from .llm import LLM, image_part
from .mathtext import needs_rendering, to_unicode

HISTORY_TURNS = 12

TUTOR_RULES = """You are a tutor working one to one with {name}, on a phone, by chat.

Teach only from the MATERIAL below: the lesson and passages of the sources it cites. Your own background knowledge is not a source.
- Cite what you say in square brackets: [lesson], or [source-id, PDF p. N] for a passage, or [source-id] for a source's record.
- If the material does not answer the question, say so plainly in one sentence, say which cited source is most likely to cover it, and add a final line of exactly this form:
  GAP: <the question, in a few words>
- Default to questions over answers. When {name} asks how or why, give the smallest hint that lets them take the next step, then ask a question that has them take it. When they ask for a fact or a definition, give it, with its citation, then ask one short question that uses it.
- When they show work: find the first error only, and ask a question that leads them to it. If the work is right, say so and say what it shows.
- Keep replies short: a few sentences. One idea per message.
- Write math in LaTeX: $...$ inline. Put matrices and multi-line working in $$...$$ on their own lines.
- Never invent a page number, a theorem number, or a quotation.

Where this lesson sits for {name}: {why}

MATERIAL
{material}"""

TRANSCRIBE = ("Transcribe the handwritten or printed mathematics in this image to LaTeX, exactly as written, "
              "including any mistakes — do not correct anything. Keep the line structure: one line of working per "
              "line, using $$...$$ for each line. Output only the transcription. If part of it is unreadable, "
              "write [unreadable] there.")

GAP_LINE = re.compile(r"^\s*GAP:\s*(.+?)\s*$", re.M)


@dataclass
class Reply:
    text: str              # Unicode, for Telegram
    message_id: int | None
    rendered_link: bool    # True when the math needs the website to read properly


class Tutor:
    def __init__(self, vault: Vault, state: State, llm: LLM, archive: Path | None, site_url: str,
                 tz: ZoneInfo, new_per_day: int):
        self.vault = vault
        self.state = state
        self.llm = llm
        self.archive = archive
        self.site_url = site_url.rstrip("/")
        self.tz = tz
        self.new_per_day = new_per_day

    # --- who and what -------------------------------------------------------------

    def learner_for_chat(self, chat_id: int) -> Learner | None:
        for learner in self.vault.learners().values():
            if learner.telegram_chat_id == chat_id:
                return learner
        return None

    def lessons_for(self, learner: Learner) -> list[Lesson]:
        topics = self.vault.learner_topics(learner.id) or self.vault.topics()
        return [l for l in self.vault.lessons() if l.topic in topics]

    def find_lesson(self, learner: Learner, query: str) -> Lesson | None:
        lessons = [l for l in self.lessons_for(learner) if l.kind == "lessons"]
        query = query.strip().lower()
        if query.isdigit():
            n = int(query)
            matches = [l for l in lessons if int(l.stem[:4]) == n]
            return matches[0] if len(matches) == 1 else None
        hits = [l for l in lessons if query in l.title.lower() or query in l.stem]
        return hits[0] if len(hits) == 1 else None

    def current_lesson(self, learner: Learner) -> Lesson | None:
        by_id = {l.id: l for l in self.vault.lessons()}
        focus = self.state.focus(learner.id)
        if focus and focus["lesson_id"] in by_id:
            return by_id[focus["lesson_id"]]
        last = self.state.last_viewed_lesson(learner.id)
        if last in by_id:
            self.state.set_focus(learner.id, last)
            return by_id[last]
        return None

    def link(self, path: str) -> str:
        return f"{self.site_url}/{path.lstrip('/')}"

    # --- conversation -------------------------------------------------------------

    def _why(self, learner: Learner, lesson: Lesson) -> str:
        route = self.vault.route(learner.id, lesson.topic) or {}
        whys = [n.get("why", "") for n in route.get("node", []) if n.get("id") in lesson.nodes]
        goal = route.get("goal", "")
        return " ".join(filter(None, [f"Goal: {goal}." if goal else "", *whys])) or "(no route yet)"

    def _finish(self, learner: Learner, lesson: Lesson, question: str, raw: str) -> Reply:
        for gap in GAP_LINE.findall(raw):
            self.state.add_gap(learner.id, lesson.id, question[:1000], gap[:300])
        text = GAP_LINE.sub("", raw).strip()
        message_id = self.state.add_message(learner.id, lesson.id, "tutor", text)
        return Reply(to_unicode(text), message_id, needs_rendering(text))

    async def ask(self, learner: Learner, lesson: Lesson, question: str, photo: bool = False) -> Reply:
        focus = self.state.focus(learner.id)
        since = focus["since"] if focus and focus["lesson_id"] == lesson.id else "0"
        history = self.state.conversation(learner.id, lesson.id, since, HISTORY_TURNS)
        self.state.add_message(learner.id, lesson.id, "learner", question, photo=photo)
        system = TUTOR_RULES.format(
            name=learner.name, why=self._why(learner, lesson),
            material=context.build(self.vault, self.archive, lesson, question))
        messages = [{"role": "user" if r["role"] == "learner" else "assistant", "content": r["content"]} for r in history]
        messages.append({"role": "user", "content": question})
        raw = await self.llm.chat(system, messages)
        return self._finish(learner, lesson, question, raw)

    async def transcribe(self, image: bytes) -> str:
        return await self.llm.chat("You transcribe mathematics from images into LaTeX.",
                                   [{"role": "user", "content": [image_part(image), {"type": "text", "text": TRANSCRIBE}]}],
                                   max_tokens=1200, temperature=0.0)

    async def check_work(self, learner: Learner, lesson: Lesson, latex: str) -> Reply:
        return await self.ask(learner, lesson, f"Here is my written work (transcribed from a photo):\n\n{latex}\n\nCan you check it?",
                              photo=True)

    # --- reviews ------------------------------------------------------------------

    def due_count(self, learner: Learner) -> int:
        local = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        allowance = self.new_per_day - self.state.new_cards_started_today(learner.id, local)
        q = queue.build(self.vault.cards(), self.state.viewed_lessons(learner.id), self.state.card_states(learner.id),
                        self.state.open_flags(), allowance, now())
        return len(q)
