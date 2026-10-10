"""The Telegram side of the tutor: commands, messages, photos, daily review reminders."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler,
                          filters)

from ..state import State
from ..vault import Vault
from .core import Reply, Tutor
from .llm import LLM, TutorUnavailable
from .mathtext import to_unicode

log = logging.getLogger("learnsite.tutor")

TELEGRAM_LIMIT = 4000
DOWN = "The tutor's model isn't answering right now (it may be switched off). Try again later."

HELP = """I'm your tutor. Ask me anything about the lesson you're on, or send a photo of your working and I'll check it.

/lesson — which lesson we're on, and the others
/lesson 2 — switch to lesson 2 (or a word from its title)
/due — how many cards are due
/web — links to the site"""


def chunks(text: str) -> list[str]:
    out = []
    while len(text) > TELEGRAM_LIMIT:
        cut = text.rfind("\n", 0, TELEGRAM_LIMIT)
        cut = cut if cut > 0 else TELEGRAM_LIMIT
        out.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return out + [text] if text else out


def build(tutor: Tutor, token: str, poke_hour: int) -> Application:
    app = Application.builder().token(token).concurrent_updates(False).build()

    def learner_of(update: Update):
        return tutor.learner_for_chat(update.effective_chat.id) if update.effective_chat else None

    async def send_reply(update: Update, reply: Reply) -> None:
        text = reply.text
        if reply.rendered_link and reply.message_id:
            text += f"\n\nThe math, rendered: {tutor.link(f'chat#m{reply.message_id}')}"
        for part in chunks(text):
            await update.effective_message.reply_text(part, disable_web_page_preview=True)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        learner = learner_of(update)
        if learner is None:
            chat_id = update.effective_chat.id
            log.warning("message from unlinked chat %s", chat_id)
            await update.effective_message.reply_text(
                f"This chat isn't linked to a learner yet. Its chat id is {chat_id}; "
                "it goes in learners.toml as telegram_chat_id.")
            return
        lesson = tutor.current_lesson(learner)
        on = f"\n\nWe're on: {lesson.title}" if lesson else "\n\nOpen a lesson on the site, or pick one with /lesson."
        await update.effective_message.reply_text(f"Hi {learner.name}. " + HELP + on)

    async def lesson_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        learner = learner_of(update)
        if learner is None:
            return
        arg = " ".join(context.args).strip()
        if arg:
            lesson = tutor.find_lesson(learner, arg)
            if lesson is None:
                await update.effective_message.reply_text("I couldn't pick out one lesson from that. Try its number.")
                return
            tutor.state.set_focus(learner.id, lesson.id)
            await update.effective_message.reply_text(f"Now on: {lesson.title}\n{tutor.link(lesson.href)}",
                                                      disable_web_page_preview=True)
            return
        current = tutor.current_lesson(learner)
        lines = [f"{'→' if current and l.id == current.id else ' '} {int(l.stem[:4])}. {l.title}"
                 for l in tutor.lessons_for(learner) if l.kind == "lessons"]
        await update.effective_message.reply_text("\n".join(lines) or "No lessons yet.")

    async def due_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        learner = learner_of(update)
        if learner is None:
            return
        n = tutor.due_count(learner)
        text = f"{n} card{'s' if n != 1 else ''} to review: {tutor.link('review')}" if n else "Nothing due right now."
        await update.effective_message.reply_text(text, disable_web_page_preview=True)

    async def web_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if learner_of(update) is None:
            return
        await update.effective_message.reply_text(
            f"Today: {tutor.link('')}\nOur conversation, with the math rendered: {tutor.link('chat')}",
            disable_web_page_preview=True)

    async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        learner = learner_of(update)
        if learner is None:
            return
        lesson = tutor.current_lesson(learner)
        if lesson is None:
            await update.effective_message.reply_text("Which lesson? Open one on the site, or use /lesson.")
            return
        await update.effective_chat.send_action(ChatAction.TYPING)
        try:
            reply = await tutor.ask(learner, lesson, update.effective_message.text)
        except TutorUnavailable as exc:
            log.warning("tutor unavailable: %s", exc)
            await update.effective_message.reply_text(DOWN)
            return
        await send_reply(update, reply)

    async def photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        learner = learner_of(update)
        if learner is None:
            return
        lesson = tutor.current_lesson(learner)
        if lesson is None:
            await update.effective_message.reply_text("Which lesson is this for? Use /lesson first.")
            return
        message = update.effective_message
        if message.photo:
            # The largest size Telegram offers is plenty; it is already capped near 1280px.
            file = await message.photo[-1].get_file()
        elif message.document and (message.document.mime_type or "").startswith("image/"):
            file = await message.document.get_file()
        else:
            return
        image = bytes(await file.download_as_bytearray())
        await update.effective_chat.send_action(ChatAction.TYPING)
        try:
            latex = await tutor.transcribe(image)
        except TutorUnavailable as exc:
            log.warning("transcription unavailable: %s", exc)
            await message.reply_text(DOWN)
            return
        note = message.caption or ""
        context.user_data["pending"] = {"latex": latex, "note": note, "lesson": lesson.id}
        shown_id = tutor.state.add_message(learner.id, lesson.id, "tutor", f"I read your photo as:\n\n{latex}")
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("That's right, check it", callback_data="check"),
                                         InlineKeyboardButton("Not quite", callback_data="fix")]])
        text = f"I read it as:\n\n{to_unicode(latex)}\n\nRendered: {tutor.link(f'chat#m{shown_id}')}"
        await message.reply_text(text[:TELEGRAM_LIMIT], reply_markup=buttons, disable_web_page_preview=True)

    async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        learner = learner_of(update)
        pending = context.user_data.pop("pending", None)
        if learner is None or pending is None:
            await query.edit_message_reply_markup(None)
            return
        await query.edit_message_reply_markup(None)
        if query.data == "fix":
            await update.effective_message.reply_text(
                "Send a clearer photo, or type the line I got wrong and I'll go from there.")
            return
        lesson = next((l for l in tutor.vault.lessons() if l.id == pending["lesson"]), None) or tutor.current_lesson(learner)
        latex = pending["latex"] + (f"\n\n(My note: {pending['note']})" if pending["note"] else "")
        await update.effective_chat.send_action(ChatAction.TYPING)
        try:
            reply = await tutor.check_work(learner, lesson, latex)
        except TutorUnavailable as exc:
            log.warning("tutor unavailable: %s", exc)
            await update.effective_message.reply_text(DOWN)
            return
        await send_reply(update, reply)

    async def poke(context: ContextTypes.DEFAULT_TYPE) -> None:
        """Once a day, from poke_hour local time, tell each learner with cards due."""
        local = datetime.now(tutor.tz)
        if local.hour < poke_hour:
            return
        today = local.date().isoformat()
        for learner in tutor.vault.learners().values():
            if not learner.telegram_chat_id or tutor.state.poked_on(learner.id) == today:
                continue
            n = tutor.due_count(learner)
            if n:
                await context.bot.send_message(learner.telegram_chat_id,
                                               f"{n} card{'s' if n != 1 else ''} due today: {tutor.link('review')}",
                                               disable_web_page_preview=True)
            tutor.state.mark_poked(learner.id, today)

    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("lesson", lesson_cmd))
    app.add_handler(CommandHandler("due", due_cmd))
    app.add_handler(CommandHandler("web", web_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, photo_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    app.job_queue.run_repeating(poke, interval=900, first=30)
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # every poll would be logged, token in the URL
    env = os.environ
    tz = ZoneInfo(env.get("LEARN_TZ", "UTC"))
    tutor = Tutor(
        vault=Vault(Path(env.get("LEARN_VAULT", "/vault"))),
        state=State(Path(env.get("LEARN_STATE_DB", "/state/learning.sqlite"))),
        llm=LLM(env.get("LEARN_LLM_URL", "http://host.docker.internal:8005/v1"), env.get("LEARN_LLM_MODEL", "local")),
        archive=Path(env["LEARN_ARCHIVE"]) if env.get("LEARN_ARCHIVE") else None,
        site_url=env["LEARN_PUBLIC_URL"],
        tz=tz,
        new_per_day=int(env.get("LEARN_NEW_PER_DAY", "10")),
    )
    app = build(tutor, env["LEARN_TELEGRAM_TOKEN"], int(env.get("LEARN_POKE_HOUR", "18")))
    app.run_polling(allowed_updates=Update.ALL_TYPES)
