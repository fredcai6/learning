"""The website against a small vault: sign-in, lessons, results, reviews."""

from __future__ import annotations

import json
import time
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from starlette.testclient import TestClient

from learnsite.app import Settings, create_app
from learnsite.state import State, now

REPO = Path(__file__).resolve().parents[2]
AUD = "test-aud"
ISSUER = "https://team.cloudflareaccess.com"

LESSON = """<!doctype html><html><head><meta charset="utf-8">
<meta name="lesson-id" content="lie-algebra/0001-rotations"><meta name="nodes" content="so3">
<title>Rotations</title></head><body><main><p>Hi</p></main></body></html>"""

CARDS = """from = "lessons/0001-rotations.html"
[[card]]
id = "orthogonal"
kind = "produce"
front = "What is $R^T R$ for a rotation?"
back = "$I$"
source = "lp"
loc = "§3.2"
nodes = ["so3"]

[[card]]
id = "det"
kind = "recall"
front = "What is $\\\\det R$?"
back = "$1$"
source = "lp"
loc = "§3.2"
nodes = ["so3"]
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "topics/lie-algebra/lessons").mkdir(parents=True)
    (root / "topics/lie-algebra/cards").mkdir(parents=True)
    (root / "topics/lie-algebra/lessons/0001-rotations.html").write_text(LESSON)
    (root / "topics/lie-algebra/cards/0001-rotations.toml").write_text(CARDS)
    (root / "sources").mkdir()
    (root / "sources/lp.md").write_text('+++\nid = "lp"\ntitle = "Modern Robotics"\nkind = "book"\n'
                                        'archive = "lp.pdf"\ntrust = "t"\nuse_for = "u"\n+++\n')
    (root / "map").mkdir()
    (root / "map/so3.md").write_text('+++\nid = "so3"\ntitle = "Rotation matrices"\n+++\n')
    (root / "learners/ann/lie-algebra/records").mkdir(parents=True)
    (root / "learners/ann/lie-algebra/route.toml").write_text(
        'goal = "Read SE(3)"\n[[node]]\nid = "so3"\nstate = "shaky"\nevidence = []\nwhy = "Everything sits on it."\n')
    (root / "learners/ann/lie-algebra/records/0001-knows-matrices.md").write_text(
        '+++\nnodes = ["so3"]\n+++\n\n# Knows matrices\n\nFrom aerospace.\n')
    (root / "learners.toml").write_text('[learners.ann]\nname = "Ann"\nemail = "ann@example.com"\n'
                                        '[learners.bo]\nname = "Bo"\nemail = "bo@example.com"\n')
    (root / "vault.toml").write_text("")
    archive = tmp_path / "archive"
    archive.mkdir()
    (archive / "lp.pdf").write_bytes(b"%PDF-1.4 copy")
    (tmp_path / "secret.txt").write_text("outside")
    return root


def settings(vault: Path, **over) -> Settings:
    base = dict(vault=vault, state_db=vault.parent / "state.sqlite", archive=vault.parent / "archive",
                base_assets=REPO / "assets" / "base", base_url="/learn", access_certs=None, access_aud=None,
                access_issuer=None, dev_learner="ann", tz=ZoneInfo("UTC"), new_per_day=10)
    base.update(over)
    return Settings(**base)


@pytest.fixture
def client(vault) -> TestClient:
    return TestClient(create_app(settings(vault)))


# --- sign-in -------------------------------------------------------------------

@pytest.fixture
def signer(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "k1"
    certs = tmp_path / "certs.json"
    certs.write_text(json.dumps({"keys": [jwk]}))

    def sign(email: str, aud: str = AUD, iss: str = ISSUER, kid: str = "k1", exp: int = 300) -> str:
        t = int(time.time())
        return jwt.encode({"email": email, "aud": [aud], "iss": iss, "iat": t, "exp": t + exp},
                          key, algorithm="RS256", headers={"kid": kid})
    return certs, sign


def access_client(vault, certs) -> TestClient:
    return TestClient(create_app(settings(vault, dev_learner=None, access_certs=certs,
                                          access_aud=AUD, access_issuer=ISSUER)))


def test_no_token_is_refused(vault, signer):
    c = access_client(vault, signer[0])
    assert c.get("/").status_code == 403


def test_a_learners_token_signs_them_in(vault, signer):
    certs, sign = signer
    r = access_client(vault, certs).get("/", headers={"cf-access-jwt-assertion": sign("Ann@Example.com")})
    assert r.status_code == 200 and "Ann" in r.text


@pytest.mark.parametrize("make", [
    lambda sign: sign("stranger@example.com"),
    lambda sign: sign("ann@example.com", aud="other-app"),
    lambda sign: sign("ann@example.com", iss="https://evil.cloudflareaccess.com"),
    lambda sign: sign("ann@example.com", kid="unknown"),
    lambda sign: sign("ann@example.com", exp=-60),
    lambda sign: "not-a-token",
])
def test_bad_tokens_are_refused(vault, signer, make):
    certs, sign = signer
    r = access_client(vault, certs).get("/", headers={"cf-access-jwt-assertion": make(sign)})
    assert r.status_code == 403


def test_the_email_header_alone_is_not_trusted(vault, signer):
    r = access_client(vault, signer[0]).get("/", headers={"cf-access-authenticated-user-email": "ann@example.com"})
    assert r.status_code == 403


def test_token_signed_by_another_key_is_refused(vault, signer, tmp_path):
    certs, _ = signer
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    t = int(time.time())
    forged = jwt.encode({"email": "ann@example.com", "aud": [AUD], "iss": ISSUER, "iat": t, "exp": t + 300},
                        other, algorithm="RS256", headers={"kid": "k1"})
    assert access_client(vault, certs).get("/", headers={"cf-access-jwt-assertion": forged}).status_code == 403


def test_healthz_needs_no_sign_in(vault, signer):
    assert access_client(vault, signer[0]).get("/healthz").text == "ok"


# --- files ---------------------------------------------------------------------

def test_lesson_and_assets_are_served_with_the_policy(client):
    r = client.get("/topics/lie-algebra/lessons/0001-rotations.html")
    assert r.status_code == 200 and "Rotations" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert client.get("/assets/base/lesson.js").status_code == 200
    assert client.get("/assets/base/katex/katex.min.js").status_code == 200


@pytest.mark.parametrize("path", [
    "/topics/lie-algebra/cards/0001-rotations.toml",
    "/topics/../learners.toml",
    "/topics/%2e%2e/learners.toml",
    "/topics/..%2f..%2fsecret.txt",
    "/assets/base/../../../../etc/passwd",
    "/assets/..%2flearners.toml",
])
def test_nothing_outside_the_served_trees(client, path):
    assert client.get(path).status_code == 404


def test_archived_copy_is_served(client):
    r = client.get("/sources/lp/copy")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


# --- results and reviews ---------------------------------------------------------

def post(client, body):
    return client.post("/api/result", json=body)


def test_cards_wait_until_their_lesson_is_opened(client):
    assert "Nothing to review" in client.get("/").text
    assert post(client, {"lesson": "lie-algebra/0001-rotations", "kind": "view"}).status_code == 200
    assert "2 cards to review" in client.get("/").text


def test_quiz_and_exercise_results_show_on_lessons(client):
    lesson = "lie-algebra/0001-rotations"
    post(client, {"lesson": lesson, "kind": "view"})
    post(client, {"lesson": lesson, "kind": "quiz", "id": "q1", "correct": True})
    post(client, {"lesson": lesson, "kind": "quiz", "id": "q1", "correct": False})   # first answer counts
    post(client, {"lesson": lesson, "kind": "exercise", "id": "e1", "grade": "partly"})
    page = client.get("/lessons").text
    assert "quizzes 1/1" in page and "1 partly" in page


@pytest.mark.parametrize("body", [
    {"lesson": "lie-algebra/0009-nope", "kind": "view"},
    {"lesson": "lie-algebra/0001-rotations", "kind": "delete"},
    {"lesson": "lie-algebra/0001-rotations", "kind": "exercise", "grade": "perfect"},
])
def test_bad_results_are_refused(client, body):
    assert post(client, body).status_code == 400


def test_cross_origin_posts_are_refused(client):
    r = client.post("/api/result", json={"lesson": "lie-algebra/0001-rotations", "kind": "view"},
                    headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_review_round_trip(client, vault):
    post(client, {"lesson": "lie-algebra/0001-rotations", "kind": "view"})
    page = client.get("/review").text
    assert "R^T R" in page and "Again" in page and "new card" in page
    r = client.post("/review/lie-algebra/0001-rotations/orthogonal", data={"rating": "3"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/learn/review"
    assert "det R" in client.get("/review").text           # the other card is next
    client.post("/review/lie-algebra/0001-rotations/det", data={"rating": "3"})
    states = State(vault.parent / "state.sqlite").card_states("ann")
    assert set(states) == {"lie-algebra/0001-rotations/orthogonal", "lie-algebra/0001-rotations/det"}


def test_bad_rating_and_unknown_card_are_refused(client):
    assert client.post("/review/lie-algebra/0001-rotations/orthogonal", data={"rating": "9"}).status_code == 400
    assert client.post("/review/lie-algebra/0001-rotations/ghost", data={"rating": "3"}).status_code == 404


def test_flagged_card_leaves_the_queue(client):
    post(client, {"lesson": "lie-algebra/0001-rotations", "kind": "view"})
    client.post("/flag/lie-algebra/0001-rotations/orthogonal", data={"note": "ambiguous"})
    assert "1 card to review" in client.get("/").text


def test_new_card_allowance_per_day(vault):
    c = TestClient(create_app(settings(vault, new_per_day=1)))
    post(c, {"lesson": "lie-algebra/0001-rotations", "kind": "view"})
    assert "1 card to review" in c.get("/").text
    c.post("/review/lie-algebra/0001-rotations/orthogonal", data={"rating": "4"})
    assert "1 card to review" not in c.get("/").text


def test_due_card_returns_after_its_interval(vault):
    state = State(vault.parent / "state.sqlite")
    card = state.review("ann", "lie-algebra/0001-rotations/det", 3, at=now() - timedelta(days=30))
    assert card.due < now()
    c = TestClient(create_app(settings(vault, new_per_day=0)))
    post(c, {"lesson": "lie-algebra/0001-rotations", "kind": "view"})
    assert "1 due" in c.get("/").text


# --- pages ---------------------------------------------------------------------

def test_pages_render(client):
    for path, expect in [("/map", "Everything sits on it."), ("/log", "Knows matrices"),
                         ("/sources", "Modern Robotics"), ("/lessons", "Rotations")]:
        r = client.get(path)
        assert r.status_code == 200 and expect in r.text, path


def test_other_learner_is_shown_alongside(client):
    assert "Bo" in client.get("/").text
