# learning

A personal teaching system: Claude Code writes the course, a private website
delivers it, and a Telegram bot on a local model tutors and sends review
reminders. Built on Matt Pocock's [`/teach`](https://github.com/mattpocock/skills)
skill.

This repo is the mechanism only. The learning itself — sources, lessons,
cards, learner records — lives in a separate private vault, and secrets live
in `.env` on the machine running it.

See [PLAN.md](PLAN.md) for the design.

## Setup

```bash
# Create a vault (its own private repo) and say where archived source copies go.
python3 skill/teach/scripts/init_vault.py ../learning-vault --archive-dir /path/outside/the/vault

# Install the skill for Claude Code.
ln -s "$PWD/skill/teach" ~/.claude/skills/teach
```

Then, from the vault: `/teach <learner> <topic>`.

## Before the website: lessons on the home network

```bash
python3 scripts/serve_local.py ../learning-vault --port 8090
```

Read only. Serves lessons, reference sheets and assets, plus an index; nothing
under `learners/` or `sources/`. Reachable by anything on the same network.

## Checking a vault

```bash
python3 skill/teach/scripts/check.py ~/projects/learning-vault
uvx pytest tests      # the checker's own tests
```

## Licence

MIT. Third-party pieces and their licences are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
