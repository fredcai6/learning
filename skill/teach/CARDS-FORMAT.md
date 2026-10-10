# Cards Format

One file per lesson or reference sheet: `topics/<topic>/cards/<same-name-as-the-html>.toml`. Cards are scheduled for review per learner, so they are what makes a lesson last past the session.

```toml
from = "lessons/0001-what-a-commutator-measures.html"

[[card]]
id = "commutator-definition"
kind = "produce"
front = "Define the commutator $[X, Y]$ of two $n \\times n$ matrices."
back = "$[X, Y] = XY - YX$."
source = "hall-2015"
loc = "Def. 3.1"
nodes = ["lie-bracket"]

[[card]]
id = "commutator-of-commuting"
kind = "predict"
front = "If $X$ and $Y$ commute, what is $[X, Y]$, and why?"
back = "$0$: $XY = YX$, so $XY - YX = 0$. The bracket measures failure to commute."
source = "hall-2015"
loc = "§3.1"
nodes = ["lie-bracket"]
```

## Fields

- `id`: dash-case, unique within the file. A card's full id is `<topic>/<file>/<id>`; review history attaches to it, so once a card has been reviewed, keep its id when you edit it.
- `kind`: `produce` (write it out), `predict` (say what happens before checking), `explain` (say why), or `recall` (state it). Most cards should make the learner produce or predict.
- `front`, `back`: math in `$…$`. TOML basic strings need backslashes doubled (`\\times`); a literal string `'…'` avoids that.
- `source`, `loc`: required. The source id and where in it.
- `nodes`: the map nodes this card is evidence for.

## Rules

- **One fact or one move per card.** A card that tests two things gives a muddy result.
- **The answer is short.** If the back needs a paragraph, split the card.
- **Every card is answerable from its lesson.** No card tests what the lesson did not teach.
- **Five to ten cards per lesson** is typical; a reference sheet may carry more.
- **Rewrite** a card flagged as bad: fix it in place if the meaning holds, or give it a new id if it now tests something different.
