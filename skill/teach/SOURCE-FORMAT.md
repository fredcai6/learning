# Source Format

One file per source: `sources/<id>.md`. Shared by every topic and learner. The record lives in the vault; an archived copy, where text exists, lives in the vault's `archive_dir` (outside git — copyrighted text never reaches a repo).

The id is dash-case: author or institution, then year or a short distinguishing word. `hall-2015`, `mit-18-745-notes`, `3b1b-essence-linear-algebra`.

## Template

```md
+++
id = "hall-2015"
title = "Lie Groups, Lie Algebras, and Representations (2nd ed.)"
kind = "book"                      # book | notes | paper | video | web | course | community
authors = ["Brian C. Hall"]
year = 2015
url = "https://doi.org/10.1007/978-3-319-13467-3"
accessed = 2026-10-09
archive = "hall-2015.pdf"          # filename in archive_dir; leave out when there is no copy
trust = "Standard graduate text; matrix-group approach, so no manifold theory needed up front."
use_for = "Definitions and first results on matrix Lie groups and their Lie algebras; chapters 1-3."
topics = ["lie-algebra"]

[[timestamps]]                     # video only: one per useful stretch
at = "12:30"
covers = "Why the commutator measures failure to commute"
+++

{Free notes: what is in it, chapter map, notation it uses that differs from the glossary, anything the tutor or a future session should know.}
```

## Rules

- **Annotate.** `trust` and `use_for` are required: a bare link is useless in three months.
- **High trust only.** Primary sources, standard texts, notes from recognised courses, recognised lecturers, moderated communities.
- **Archive when text exists.** `python3 scripts/archive.py <id> <url-or-file>` saves the copy and its extracted text and fills `archive` in the record. Video and paywalled books get no copy; their record still stands.
- **Cite with a location.** Lessons and cards cite a source id plus where in it (`Prop. 3.7`, `§2.1`, `14:05`), so the learner and the tutor can go straight there.
- **Prune** a source that proves wrong, shallow or off-mission, and re-cite whatever used it.
