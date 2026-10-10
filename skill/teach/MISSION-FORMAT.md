# Mission Format

`learners/<learner>/<topic>/MISSION.md` captures why this learner is learning this topic. Every teaching decision — what to teach next, which sources to surface, which exercises to design — traces back to it. Written at the end of the mission interview, in the learner's own words wherever possible. Light by design: it is a compass, not a commitment.

## Template

```md
# Mission: {Topic}

## Where it came from
{1-2 sentences: what brought the topic up.}

## Practical use
- {Something they want to be able to do with it, in their words}
- {Or: "Understanding for its own sake" — then Connections carries the weight}

## Goal
{Only when the learner named an explicit goal. Their words, after sharpening.}
- First milestone: {…}
- If {moment}, then I will {action}.

## Connections
- Already knows: {topic} — {how it seems to relate}
- Wants to poke at: {neighbouring topic}

## Constraints
- {Time, rhythm, preferences, anything that bounds the approach}

## Out of scope
- {Adjacent topics they do not want to chase now}
```

## Rules

- **One mission per learner per topic.** Two unrelated goals are two topics.
- **The learner's words, not yours.**
- **Concrete where it can be.** "Read SE(3) in a paper and know what it means" beats "understand Lie theory"; "understanding for its own sake" is also a real answer.
- **Leave out what is empty.** No explicit goal means no Goal section.
- **Revise when reality shifts**, with the learner's agreement, and write a learning record saying why.
- **Keep it to a screen.** Past that it has become a plan, and the plan lives in `route.toml`.
