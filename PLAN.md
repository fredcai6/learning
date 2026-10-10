# learning — plan

A personal teaching system for two learners. Claude Code writes the course;
a private website delivers it; a Telegram bot with a local model tutors and
pokes. Starts from Matt Pocock's `/teach` (MIT, attributed) and keeps
everything it does.

First topic: Lie algebras, starting from wherever the prerequisites actually
are.

## The three parts

| Part | Where it runs | What it does |
| --- | --- | --- |
| `/teach` skill | Claude Code, locally | Mission interview, research, sources, lessons, cards, map. The only author. |
| Website | A path on a personal site, behind Cloudflare Access | Lessons, quizzes, reviews, map, sources, log. Phone first. |
| Tutor bot | Its own Telegram bot, own container | Daily review pokes; tutor chat; photos of written work. |

They share two things: the repo (read only for the site and bot) and one
state database on disk (reviews, quiz attempts, chats, gaps). No network path
between the site and the bot.

## What we take from where

- **Matt's `/teach`**: mission, learning records, short self-contained HTML
  lessons, a shared component library, reference sheets, research before
  teaching, fluency vs storage strength.
- **Mission interview**: short and practical — where the topic came from, what use it might have, and what it connects to in the learner's wider knowledge.
- **socratic-skills**: one question at a time; on a partly right answer, probe
  before correcting.
- **study-skill / agent-tutor**: FSRS review scheduling.
- **learning-opportunities**: cards favour prediction and production over
  recognition.

## Sources

Every source is a record in `content/sources/<id>.md`: link, author, date,
when accessed, why it is trusted, and what it is good for. Where text exists
(web pages, PDFs, lecture notes) an archived copy is kept at
the data drive — outside git, so no copyrighted text reaches
GitHub. YouTube is a link plus timestamps for the useful stretch.

Records live in the vault; copies live on the data drive.

Lessons, reference sheets and cards cite by source id. A check script fails a
lesson that cites an unknown id or has no primary source. The tutor sees only
the lesson and the archived text it cites, and every claim it makes carries a
source id; a question the sources cannot answer is logged as a gap, and the
next `/teach` session researches it.

## The map

Concepts are nodes; links read "helps with", never "requires". A node's state
for a learner is evidence (review results, quiz attempts, tutor gaps), not a
checkbox, so being half-ready is representable.

Each learner's map carries the reason each node matters to *their* mission,
in plain words. Every prerequisite lesson opens with where it sits on the way
to the goal and closes with what it unlocks; every few lessons a short "back
to the goal" lesson uses what you have so far on the real topic.

Nodes are shared across topics, so representation theory or differential
geometry later reuse the linear algebra and group nodes instead of starting
over.

## Two learners

Shared: sources, map nodes, lessons, cards. Per learner: mission, learning
records, map state, review schedule, chats. Progress is visible to both.

The website knows who you are from the email Cloudflare Access passes through;
the bot knows from your Telegram chat id. Both onboard through `/teach` in
Claude Code.

## Two repos, and what stays off both

**`learning` (public)** is the mechanism: how everything is pulled together.
Nothing personal in it — anyone could point it at their own vault.

```
learning/
  skill/teach/            SKILL.md + format files (symlinked into ~/.claude/skills)
  assets/                 shared stylesheet, KaTeX, quiz and review widgets
  site/                   the web app
  bot/                    the tutor bot
  scripts/check           citations, cards, links
  .env.example            every setting, no values
```

**`learning-vault` (private)** is the learning itself: what was taught, from
what, and how it went.

```
learning-vault/
  sources/                one record per source
  map/                    one file per concept node
  lessons/<topic>/        0001-<name>.html ...
  reference/              cheat sheets, glossaries
  cards/                  one file per lesson / reference sheet
  learners/<name>/        MISSION.md, learning-records/, map overlay, NOTES.md
  learners.toml           who each learner is (Access email, Telegram chat id)
```

**On this machine only, never in git:**

- `.env` beside each running service — the bot token and anything else
  secret. Both repos ignore `.env`.
- The data drive: archived source copies (copyrighted text), and the state
  database — reviews, quiz attempts, chats, gaps — with a backup.

The vault's location, the data directory, the site's base URL and path are
all settings in `.env`, so the public repo names no personal paths or
hostnames.

## Website

A small Python app on the site's existing internal network, with no other
network. It serves the content read only and writes review and quiz results to
the state database. Pages: Today (due reviews), Lessons, Map, Sources, Log, and
the other learner's progress. Phone first, installable to the home screen,
math via KaTeX bundled locally. `/learn` needs a looser script policy than the
landing page (scripts from the site itself) — set on that path only.

Cloudflare Access on the site path is a dashboard step; the setup doc gives
the clicks.

## Tutor bot

Created in BotFather; the token goes in `.env`. Runs as its own compose
project, talking to Telegram outbound and to a local OpenAI-compatible LLM
server (llama.cpp with a vision projector).

- **Pokes**: once a day per learner, "6 cards due" with a link to Today.
- **Tutor**: `/tutor` opens a session on your current lesson (or a named one).
  Questions back by default; answers cite source ids; gaps logged.
- **Written work**: send a photo. It transcribes to LaTeX first and shows you
  what it read; you confirm; then it checks the work.
- **Math in chat**: Unicode for short things (`[X, Y] = XY − YX`), a rendered
  image for matrices and anything heavier.

## Cards

The skill writes small one-fact cards from every lesson and reference sheet,
each with its source id and a link back. FSRS schedules them per learner. A
"bad card" button on the review page queues the card for a rewrite at the next
session.

## Order of work

1. **Repo, skill, content formats, check script.** Then the first real
   session: mission, map placement, sources, first lesson and its cards. Usable
   on day one by opening the HTML locally.
2. **Website.** Lessons, map, sources, then reviews and quizzes that save.
   Access in front.
3. **Tutor bot.** Pokes, tutor chat, photos.
4. **Second learner** onboards through `/teach`.

## Known risks

- **Tutor latency.** With thinking on, one small vision check took 112s and
  3,000 tokens. The tutor needs thinking switched off or capped for chat.
- **GPU memory.** 29.6 of 32.6 GB in use after adding the vision projector.
  Large photos cost more; downscale before sending.
- **Handwriting.** Vision is verified on a printed image only (it caught a
  planted sign error). Real handwriting is the test — first thing in
  phase 3.
