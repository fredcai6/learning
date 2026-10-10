"""The learning website: lessons, reviews, map, sources and log for each learner."""

from __future__ import annotations

import copy
import logging
import mimetypes
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import markdown as md
from fsrs import Card as FsrsCard, Rating
from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from . import queue
from .identity import Keys, email_from_token
from .state import SCHEDULER, State, now
from .vault import Vault

log = logging.getLogger("learnsite")

CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
       "script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; "
       "frame-ancestors 'none'")

STATE_LABELS = {"unknown": "Unknown", "new": "New", "shaky": "Shaky", "working": "Working", "solid": "Solid"}
RATINGS = [(Rating.Again, "Again"), (Rating.Hard, "Hard"), (Rating.Good, "Good"), (Rating.Easy, "Easy")]


@dataclass
class Settings:
    vault: Path
    state_db: Path
    archive: Path | None
    base_assets: Path
    base_url: str               # the path prefix the site is served under, e.g. "/learn"
    access_certs: Path | None
    access_aud: str | None
    access_issuer: str | None
    dev_learner: str | None
    tz: ZoneInfo
    new_per_day: int

    @classmethod
    def from_env(cls) -> "Settings":
        env = os.environ
        return cls(
            vault=Path(env.get("LEARN_VAULT", "/vault")),
            state_db=Path(env.get("LEARN_STATE_DB", "/state/learning.sqlite")),
            archive=Path(env["LEARN_ARCHIVE"]) if env.get("LEARN_ARCHIVE") else None,
            base_assets=Path(env.get("LEARN_BASE_ASSETS", Path(__file__).resolve().parents[2] / "assets" / "base")),
            base_url=env.get("LEARN_BASE_URL", "").rstrip("/"),
            access_certs=Path(env["LEARN_ACCESS_CERTS"]) if env.get("LEARN_ACCESS_CERTS") else None,
            access_aud=env.get("LEARN_ACCESS_AUD") or None,
            access_issuer=env.get("LEARN_ACCESS_ISSUER") or None,
            dev_learner=env.get("LEARN_DEV_LEARNER") or None,
            tz=ZoneInfo(env.get("LEARN_TZ", "UTC")),
            new_per_day=int(env.get("LEARN_NEW_PER_DAY", "10")),
        )


def human_interval(delta: timedelta) -> str:
    minutes = delta.total_seconds() / 60
    if minutes < 60:
        return f"{max(round(minutes), 1)}m"
    if minutes < 60 * 24:
        return f"{round(minutes / 60)}h"
    days = minutes / (60 * 24)
    if days < 31:
        return f"{round(days)}d"
    if days < 365:
        return f"{round(days / 30)}mo"
    return f"{days / 365:.1f}y"


def safe_child(root: Path, relative: str) -> Path | None:
    """The file at root/relative, or None if it is missing or escapes root."""
    target = (root / relative).resolve()
    root = root.resolve()
    if root not in target.parents or not target.is_file():
        return None
    return target


def create_app(settings: Settings | None = None) -> Starlette:
    settings = settings or Settings.from_env()
    vault = Vault(settings.vault)
    state = State(settings.state_db)
    keys = Keys(settings.access_certs)
    if settings.dev_learner:
        log.warning("LEARN_DEV_LEARNER is set: every request is %s, with no sign-in. Local testing only.",
                    settings.dev_learner)

    env = Environment(loader=PackageLoader("learnsite"), autoescape=select_autoescape())
    env.filters["markdown"] = lambda text: Markup(md.markdown(text or "", extensions=["tables"]))

    def render(request: Request, template: str, **context) -> HTMLResponse:
        context.update(base=settings.base_url, learner=request.state.learner,
                       learners=vault.learners(), path=request.url.path, state_labels=STATE_LABELS)
        return HTMLResponse(env.get_template(template).render(**context))

    def url(path: str) -> str:
        return f"{settings.base_url}/{path.lstrip('/')}"

    def day_start() -> datetime:
        local = datetime.now(settings.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        return local.astimezone(timezone.utc)

    def review_queue(learner: str) -> queue.Queue:
        allowance = settings.new_per_day - state.new_cards_started_today(learner, day_start())
        return queue.build(vault.cards(), state.viewed_lessons(learner), state.card_states(learner),
                           state.open_flags(), allowance, now())

    # --- identity ------------------------------------------------------------

    class Identify(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.url.path == "/healthz":
                return PlainTextResponse("ok")
            learner = None
            if settings.dev_learner:
                learner = vault.learners().get(settings.dev_learner)
            else:
                email = email_from_token(request.headers.get("cf-access-jwt-assertion"), keys,
                                         settings.access_aud, settings.access_issuer)
                learner = vault.learner_by_email(email) if email else None
            if learner is None:
                return PlainTextResponse("Not signed in, or not a learner here.", status_code=403)
            if request.method == "POST":
                origin = request.headers.get("origin")
                if origin and urlsplit(origin).netloc != request.headers.get("host"):
                    return PlainTextResponse("Cross-origin request refused.", status_code=403)
            request.state.learner = learner
            response = await call_next(request)
            response.headers.setdefault("Content-Security-Policy", CSP)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "same-origin")
            return response

    # --- pages ---------------------------------------------------------------

    async def today(request: Request):
        me = request.state.learner
        q = review_queue(me.id)
        viewed = state.viewed_lessons(me.id)
        my_topics = vault.learner_topics(me.id) or vault.topics()
        unopened = [l for l in vault.lessons() if l.topic in my_topics and l.kind == "lessons" and l.id not in viewed]
        week_ago = now() - timedelta(days=7)
        others = []
        lessons_by_id = {l.id: l for l in vault.lessons()}
        for other in vault.learners().values():
            if other.id == me.id:
                continue
            seen = state.viewed_lessons(other.id)
            others.append({
                "name": other.name,
                "reviews_week": len(state.reviews_since(other.id, week_ago)),
                "lessons_opened": len(seen),
                "topics": vault.learner_topics(other.id),
            })
        return render(request, "today.html", due=len(q.due), new=len(q.new), ahead=len(q.ahead),
                      next_lesson=unopened[0] if unopened else None,
                      reviews_week=len(state.reviews_since(me.id, week_ago)), others=others,
                      lessons_by_id=lessons_by_id)

    async def review_page(request: Request):
        me = request.state.learner
        q = review_queue(me.id)
        card = q.next()
        if card is None:
            return render(request, "review_done.html")
        current = state.card_states(me.id).get(card.id)
        at = now()
        options = []
        for rating, label in RATINGS:
            preview, _ = SCHEDULER.review_card(copy.deepcopy(current) if current else FsrsCard(), rating, review_datetime=at)
            options.append({"value": int(rating), "label": label, "after": human_interval(preview.due - at)})
        lesson = next((l for l in vault.lessons() if l.id == card.lesson_id), None)
        source = vault.sources().get(card.source, {})
        return render(request, "review.html", card=card, options=options, lesson=lesson, source=source,
                      remaining=len(q) or len(q.ahead), is_new=current is None)

    async def review_submit(request: Request):
        me = request.state.learner
        card_id = request.path_params["card_id"]
        form = await request.form()
        if card_id not in vault.cards():
            return PlainTextResponse("No such card.", status_code=404)
        try:
            rating = int(form.get("rating", ""))
            Rating(rating)
        except ValueError:
            return PlainTextResponse("Bad rating.", status_code=400)
        state.review(me.id, card_id, rating)
        return RedirectResponse(url("review"), status_code=303)

    async def flag_submit(request: Request):
        me = request.state.learner
        card_id = request.path_params["card_id"]
        if card_id not in vault.cards():
            return PlainTextResponse("No such card.", status_code=404)
        form = await request.form()
        state.flag(me.id, card_id, (form.get("note") or "").strip()[:1000])
        return RedirectResponse(url("review"), status_code=303)

    async def lessons_page(request: Request):
        me = request.state.learner
        viewed = state.viewed_lessons(me.id)
        results = state.lesson_results(me.id)
        topics = []
        for topic in vault.topics():
            items = []
            for lesson in vault.lessons(topic):
                r = results.get(lesson.id, {"quiz": {}, "exercise": {}})
                quiz = list(r["quiz"].values())
                items.append({"lesson": lesson, "opened": lesson.id in viewed,
                              "quiz_right": quiz.count("right"), "quiz_total": len(quiz),
                              "exercises": Counter(r["exercise"].values())})
            topics.append({"name": topic, "entries": items})
        return render(request, "lessons.html", topics=topics)

    async def map_page(request: Request):
        me = request.state.learner
        nodes = vault.map_nodes()
        lessons = vault.lessons()
        learners = vault.learners()
        topics = []
        for topic in vault.learner_topics(me.id) or vault.topics():
            route = vault.route(me.id, topic)
            if not route:
                continue
            other_routes = {o.name: vault.route(o.id, topic) for o in learners.values() if o.id != me.id}
            rows = []
            for entry in route.get("node", []):
                others = {}
                for name, r in other_routes.items():
                    match = next((n for n in (r or {}).get("node", []) if n.get("id") == entry["id"]), None)
                    if match:
                        others[name] = match.get("state")
                rows.append({"entry": entry, "node": nodes.get(entry["id"], {}), "others": others,
                             "lessons": [l for l in lessons if entry["id"] in l.nodes]})
            topics.append({"name": topic, "goal": route.get("goal"), "rows": rows,
                           "connections": route.get("connection", []), "gaps": route.get("gaps", []),
                           "others": list(other_routes)})
        return render(request, "map.html", topics=topics)

    async def sources_page(request: Request):
        sources = sorted(vault.sources().values(), key=lambda s: (s.get("kind", ""), s.get("title", "")))
        for s in sources:
            s["has_copy"] = bool(settings.archive and s.get("archive") and (settings.archive / s["archive"]).is_file())
        return render(request, "sources.html", sources=sources)

    async def source_copy(request: Request):
        source = vault.sources().get(request.path_params["source_id"])
        if not source or not source.get("archive") or settings.archive is None:
            return PlainTextResponse("No archived copy.", status_code=404)
        path = safe_child(settings.archive, source["archive"])
        if path is None:
            return PlainTextResponse("No archived copy.", status_code=404)
        return FileResponse(path, headers={"Content-Disposition": f'inline; filename="{path.name}"'})

    async def log_page(request: Request):
        me = request.state.learner
        records = sorted(vault.records(me.id), key=lambda r: (r.topic, r.name), reverse=True)
        since = now() - timedelta(days=14)
        reviews = state.reviews_since(me.id, since)
        days = []
        counts = Counter(datetime.fromisoformat(r["reviewed_at"]).astimezone(settings.tz).date() for r in reviews)
        today_local = datetime.now(settings.tz).date()
        for i in range(13, -1, -1):
            d = today_local - timedelta(days=i)
            days.append({"label": d.strftime("%a")[0], "date": d.isoformat(), "n": counts.get(d, 0)})
        recalled = sum(1 for r in reviews if r["rating"] >= int(Rating.Hard))
        missions = {t: vault.mission(me.id, t) for t in vault.learner_topics(me.id)}
        return render(request, "log.html", records=records, days=days, peak=max([d["n"] for d in days] + [1]),
                      total=len(reviews), recalled=recalled, missions=missions)

    # --- lesson files and their results --------------------------------------

    async def topic_file(request: Request):
        path = safe_child(settings.vault / "topics", request.path_params["path"])
        if path is None or path.suffix == ".toml":
            return PlainTextResponse("Not found.", status_code=404)
        return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0], headers={"Cache-Control": "no-cache"})

    async def base_asset(request: Request):
        path = safe_child(settings.base_assets, request.path_params["path"])
        if path is None:
            return PlainTextResponse("Not found.", status_code=404)
        return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})

    async def vault_asset(request: Request):
        path = safe_child(settings.vault / "assets", request.path_params["path"])
        if path is None:
            return PlainTextResponse("Not found.", status_code=404)
        return FileResponse(path, headers={"Cache-Control": "no-cache"})

    async def api_result(request: Request):
        me = request.state.learner
        try:
            data = await request.json()
        except ValueError:
            return JSONResponse({"error": "not json"}, status_code=400)
        lesson_id = data.get("lesson")
        kind = data.get("kind")
        known = {l.id for l in vault.lessons()}
        if lesson_id not in known or kind not in ("view", "quiz", "exercise"):
            return JSONResponse({"error": "unknown lesson or kind"}, status_code=400)
        result = None
        if kind == "quiz":
            result = "right" if data.get("correct") else "wrong"
        elif kind == "exercise":
            result = data.get("grade") if data.get("grade") in ("got", "partly", "missed") else None
            if result is None:
                return JSONResponse({"error": "bad grade"}, status_code=400)
        item = data.get("id")
        state.record_event(me.id, lesson_id, kind, str(item)[:200] if item else None, result)
        return JSONResponse({"ok": True})

    routes = [
        Route("/", today),
        Route("/review", review_page),
        Route("/review/{card_id:path}", review_submit, methods=["POST"]),
        Route("/flag/{card_id:path}", flag_submit, methods=["POST"]),
        Route("/lessons", lessons_page),
        Route("/map", map_page),
        Route("/sources", sources_page),
        Route("/sources/{source_id}/copy", source_copy),
        Route("/log", log_page),
        Route("/topics/{path:path}", topic_file),
        Route("/assets/base/{path:path}", base_asset),
        Route("/assets/{path:path}", vault_asset),
        Route("/api/result", api_result, methods=["POST"]),
        Mount("/static", StaticFiles(packages=[("learnsite", "static")]), name="static"),
    ]
    return Starlette(routes=routes, middleware=[Middleware(Identify)])
