# Learning Record Format

Learning records live in `learners/<learner>/<topic>/records/` and use sequential numbering: `0001-slug.md`, `0002-slug.md`, etc. Create the directory lazily: only when the first record is written.

They are the teaching equivalent of ADRs: they capture non-obvious lessons, key insights, and stated prior knowledge that will steer future sessions. They are used to calculate the zone of proximal development.

## Template

```md
+++
nodes = ["{map node id}", "…"]
+++

# {Short title of what was learned or established}

{1-3 sentences: what was learned (or what prior knowledge was established), and why it matters for future sessions.}
```

`nodes` names the map nodes the record is evidence for; the route's states cite records by filename. That is the whole format. A learning record can be a single paragraph. The value is recording _that_ this is now known and _why_ it changes what to teach next, not in filling out sections.

## Optional sections

Only include these when they add genuine value. Most records won't need them.

- **status** in the frontmatter (`status = "superseded by 0007"`): useful when an earlier understanding turns out to be wrong and is replaced.
- **Evidence**: how the learner demonstrated the understanding (a question answered, an exercise completed, prior experience cited). Useful when the claim might be revisited.
- **Implications**: what this unlocks or rules out for future sessions. Worth recording when non-obvious.

## Numbering

Scan the learner's `records/` directory for this topic for the highest existing number and increment by one.

## When to write a learning record

Write one when any of these is true:

1. **The learner demonstrated genuine understanding of something non-trivial**: not just exposure, but evidence they can use the concept correctly. This sets a new floor for what to teach next.
2. **The learner disclosed prior knowledge**: "I already know X." Record it so future sessions don't re-teach it. Also record the _depth_ claimed.
3. **A misconception was corrected**: the learner previously believed something wrong and now sees why. These are high-value: they predict future stumbling blocks for related topics.
4. **The mission shifted in response to learning**: the learner discovered they cared about something different than they thought. Update `MISSION.md` with the learner's agreement.

### What does _not_ qualify

- Material that was merely covered. Coverage is not learning. Wait for evidence.
- Anything already captured tersely in the topic glossary as a term definition. Don't duplicate.
- Session-by-session activity logs. Learning records are not a journal: they are decision-grade insights.

## Supersession

When a later record contradicts an earlier one (the learner's understanding deepened or corrected), mark the old record `status = "superseded by NNNN"` rather than deleting it. The history of how understanding evolved is itself useful signal.
