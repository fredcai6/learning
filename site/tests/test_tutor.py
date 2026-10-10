"""The tutor's core against a stand-in model: grounding, citations, gaps, photos."""

from __future__ import annotations

import asyncio
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from starlette.testclient import TestClient

from learnsite.app import Settings, create_app
from learnsite.state import State
from learnsite.tutor.core import Tutor
from learnsite.tutor.llm import TutorUnavailable
from learnsite.tutor.mathtext import needs_rendering, to_unicode
from learnsite.vault import Vault

REPO = Path(__file__).resolve().parents[2]

CITING_LESSON = """<!doctype html><html><head><meta charset="utf-8">
<meta name="lesson-id" content="lie-algebra/0001-rotations"><meta name="nodes" content="so3">
<title>Rotations</title><script defer src="x.js"></script></head><body><main>
<p>A rotation matrix satisfies $R^T R = I$.<a class="cite" href="#src-1">1</a></p>
<ol class="sources"><li id="src-1" data-source="lp">Modern Robotics</li></ol>
</main></body></html>"""

PAGES = "\f".join([
    "Front matter and a table of contents with nothing relevant on this page at all, filler filler filler.",
    "Chapter 3 rigid body motions. The rotation matrix R satisfies R transpose R equals identity, "
    "and its determinant is one. Differentiating R transpose R gives a skew symmetric matrix.",
    "Chapter 8 dynamics of open chains: mass matrix, Coriolis terms, gravity, nothing about rotation groups here.",
])


class FakeLLM:
    def __init__(self, reply: str = "Yes: $R^\\top R = I$ [lp, PDF p. 2]. What is $\\det R$?"):
        self.reply = reply
        self.calls: list[tuple[str, list]] = []
        self.down = False

    async def chat(self, system, messages, max_tokens=900, temperature=0.4):
        if self.down:
            raise TutorUnavailable("down")
        self.calls.append((system, messages))
        return self.reply


@pytest.fixture
def setup(vault: Path):
    (vault / "topics/lie-algebra/lessons/0001-rotations.html").write_text(CITING_LESSON)
    (vault.parent / "archive" / "lp.txt").write_text(PAGES)
    with open(vault / "learners.toml", "a") as f:
        f.write("")
    toml = (vault / "learners.toml").read_text().replace('email = "ann@example.com"\n',
                                                           'email = "ann@example.com"\ntelegram_chat_id = 42\n')
    (vault / "learners.toml").write_text(toml)
    state = State(vault.parent / "state.sqlite")
    llm = FakeLLM()
    tutor = Tutor(Vault(vault), state, llm, vault.parent / "archive", "https://site/learn", ZoneInfo("UTC"), 10)
    return tutor, llm, state


def run(coro):
    return asyncio.run(coro)


def test_chat_ids_map_to_learners(setup):
    tutor, _, _ = setup
    assert tutor.learner_for_chat(42).id == "ann"
    assert tutor.learner_for_chat(999) is None


def test_lesson_defaults_to_the_last_one_opened(setup):
    tutor, _, state = setup
    ann = tutor.learner_for_chat(42)
    assert tutor.current_lesson(ann) is None
    state.record_event("ann", "lie-algebra/0001-rotations", "view", None, None)
    assert tutor.current_lesson(ann).id == "lie-algebra/0001-rotations"


def test_find_lesson_by_number_or_title(setup):
    tutor, _, _ = setup
    ann = tutor.learner_for_chat(42)
    assert tutor.find_lesson(ann, "1").stem == "0001-rotations"
    assert tutor.find_lesson(ann, "rotat").stem == "0001-rotations"
    assert tutor.find_lesson(ann, "7") is None


def test_the_prompt_carries_the_lesson_and_the_matching_page(setup):
    tutor, llm, _ = setup
    ann = tutor.learner_for_chat(42)
    lesson = tutor.find_lesson(ann, "1")
    reply = run(tutor.ask(ann, lesson, "why is the derivative of R transpose R skew symmetric?"))
    system, messages = llm.calls[0]
    assert "A rotation matrix satisfies" in system                 # the lesson
    assert "[lp, PDF p. 2]" in system                              # the page that matches
    assert "PDF p. 3" not in system                                # not the page that does not
    assert "Everything sits on it." in system                      # the route's why for this node
    assert messages[-1]["content"].startswith("why is the derivative")
    assert reply.text.startswith("Yes: Rᵀ R = I")                  # Unicode for Telegram
    assert not reply.rendered_link


def test_history_is_carried_within_a_lesson(setup):
    tutor, llm, _ = setup
    ann = tutor.learner_for_chat(42)
    lesson = tutor.find_lesson(ann, "1")
    tutor.state.set_focus("ann", lesson.id)
    run(tutor.ask(ann, lesson, "first question"))
    run(tutor.ask(ann, lesson, "second question"))
    _, messages = llm.calls[1]
    assert [m["content"] for m in messages][:2] == ["first question", llm.reply]


def test_gap_lines_are_logged_and_stripped(setup, vault):
    tutor, llm, state = setup
    llm.reply = "The lesson's sources don't cover that; Solà's paper is the likeliest.\nGAP: adjoint of SE(3)"
    ann = tutor.learner_for_chat(42)
    reply = run(tutor.ask(ann, tutor.find_lesson(ann, "1"), "what is the adjoint of SE(3)?"))
    assert "GAP" not in reply.text
    with state.connect() as db:
        gap = db.execute("SELECT question, note FROM tutor_gap").fetchone()
    assert gap["note"] == "adjoint of SE(3)" and "adjoint" in gap["question"]


def test_display_math_gets_a_rendered_link(setup):
    tutor, llm, _ = setup
    llm.reply = "$$\\begin{pmatrix}0 & -w_3\\\\ w_3 & 0\\end{pmatrix}$$"
    ann = tutor.learner_for_chat(42)
    reply = run(tutor.ask(ann, tutor.find_lesson(ann, "1"), "show the hat matrix"))
    assert reply.rendered_link and reply.message_id


def test_photo_check_sends_the_transcription_as_work(setup):
    tutor, llm, state = setup
    ann = tutor.learner_for_chat(42)
    run(tutor.check_work(ann, tutor.find_lesson(ann, "1"), "$$R^T R = 2I$$"))
    _, messages = llm.calls[0]
    assert "R^T R = 2I" in messages[-1]["content"]
    assert state.messages("ann")[0]["photo"] == 1


def test_model_down_raises_for_the_bot_to_report(setup):
    tutor, llm, _ = setup
    llm.down = True
    ann = tutor.learner_for_chat(42)
    with pytest.raises(TutorUnavailable):
        run(tutor.ask(ann, tutor.find_lesson(ann, "1"), "hello?"))


def test_due_count_matches_the_site(setup):
    tutor, _, state = setup
    ann = tutor.learner_for_chat(42)
    assert tutor.due_count(ann) == 0
    state.record_event("ann", "lie-algebra/0001-rotations", "view", None, None)
    assert tutor.due_count(ann) == 2


def test_chat_page_renders_the_conversation(setup, vault):
    tutor, _, _ = setup
    ann = tutor.learner_for_chat(42)
    run(tutor.ask(ann, tutor.find_lesson(ann, "1"), "a question with $x_1$"))
    settings = Settings(vault=vault, state_db=vault.parent / "state.sqlite", archive=None,
                        base_assets=REPO / "assets" / "base", base_url="/learn", access_certs=None, access_aud=None,
                        access_issuer=None, dev_learner="ann", tz=ZoneInfo("UTC"), new_per_day=10)
    page = TestClient(create_app(settings)).get("/chat").text
    assert 'id="m2"' in page and "a question with $x_1$" in page and "Rotations" in page


@pytest.mark.parametrize("latex, expected", [
    (r"$\det R = 1$", "det R = 1"),
    (r"$\operatorname{tr}(A) = 0$", "tr (A) = 0"),
    (r"$R^\top R = I$", "Rᵀ R = I"),
    (r"$\omega_3$ and $x^2$", "ω₃ and x²"),
    (r"$\mathfrak{so}(3)$", "𝔰𝔬(3)"),
    (r"$\exp(\hat\omega\theta)$", "exp (ω̂θ)"),
])
def test_unicode_keeps_the_meaning(latex, expected):
    assert to_unicode(latex) == expected


def test_matrices_need_rendering():
    assert needs_rendering(r"$$\begin{pmatrix}a&b\\c&d\end{pmatrix}$$")
    assert not needs_rendering(r"$a + b$")
