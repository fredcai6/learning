# Map and Route Format

## Map nodes

One file per concept: `map/<node-id>.md`. Shared across topics and learners, so the linear algebra a Lie algebra route needs is the same node a representation theory route will need later.

```md
+++
id = "matrix-exponential"
title = "The matrix exponential"
helps_with = ["one-parameter-subgroups", "lie-algebra-of-a-matrix-group"]
sources = ["hall-2015"]
+++

{One short paragraph in plain words: what this is, and what it is for.}
```

`helps_with` reads "understanding this helps with those". It is never "required for": prerequisites are soft, and a learner can make real progress on a node whose helpers are shaky.

Granularity: a node is something one to three lessons can teach. Split a node that needs more.

## Routes

One per learner per topic: `learners/<learner>/<topic>/route.toml`. The learner's path through the map toward their goal.

```toml
goal = "Read Hall chapters 1-3 and do the exercises"   # short form of the mission goal
gaps = ["No good video found yet on the adjoint representation."]   # before the first [[node]]

[[node]]
id = "matrix-exponential"
state = "shaky"                  # unknown | new | shaky | working | solid
evidence = ["0003-exp-of-nilpotent.md"]
why = "It is how a Lie algebra turns back into its group: exp takes the tangent direction to the curve."

[[node]]
id = "lie-bracket"
state = "new"
evidence = []
why = "The one operation the whole subject is about."
```

- **Order** the nodes roughly in the order you expect to teach them. The order is a guess and will change.
- **`why`** connects the node to this learner's goal in plain words. It is what a lesson's opening and closing draw on.
- **`state`** comes from evidence and cites it: record filenames, or `"diagnostic"` for an answer in the mission interview not yet worth a record. `unknown` is honest; use it when evidence is thin.
- **`gaps`** lists what the mission needs that no source covers yet. It sits above the first `[[node]]`: in TOML, a key after a table header belongs to that table.
