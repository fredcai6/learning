# Lesson Format

A lesson is one HTML file: `topics/<topic>/lessons/NNNN-<dash-case-name>.html`, numbered per topic. Reference sheets use the same skeleton in `topics/<topic>/reference/<name>.html`.

Read on a phone as often as on a desk: one column, short paragraphs, display math for anything wider than a few symbols (it scrolls sideways on a narrow screen instead of breaking the page).

## Skeleton

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="lesson-id" content="lie-algebra/0001-what-a-commutator-measures">
  <meta name="nodes" content="lie-bracket">
  <title>What a commutator measures</title>
  <link rel="stylesheet" href="../../../assets/base/katex/katex.min.css">
  <link rel="stylesheet" href="../../../assets/base/lesson.css">
  <script defer src="../../../assets/base/katex/katex.min.js"></script>
  <script defer src="../../../assets/base/katex/auto-render.min.js"></script>
  <script defer src="../../../assets/base/lesson.js"></script>
</head>
<body>
<main>
  <p class="kicker">Lie algebra · Lesson 1</p>
  <h1>What a commutator measures</h1>

  <p class="goal-link">
    <strong>On the way to:</strong> {the goal, in a phrase}.
    {One or two sentences: where this sits on the route and why it matters to the goal.}
  </p>

  <p>Two matrices commute when $XY = YX$.<a class="cite" href="#src-1">1</a> …</p>

  <div class="definition">
    <p>The <em>commutator</em> of $X$ and $Y$ is $[X, Y] = XY - YX$.<a class="cite" href="#src-1">1</a></p>
  </div>

  <div class="quiz" data-id="commuting-bracket">
    <p class="q">If $XY = YX$, what is $[X, Y]$?</p>
    <ol class="options">
      <li><button class="option">The identity matrix $I$</button></li>
      <li><button class="option" data-correct>The zero matrix $0$</button></li>
      <li><button class="option">The product $2XY$</button></li>
    </ol>
    <p class="explain">$[X, Y] = XY - YX = XY - XY = 0$.</p>
  </div>

  <div class="exercise" data-id="bracket-2x2">
    <p class="q">Compute $[X, Y]$ for $X = \begin{pmatrix}0&1\\0&0\end{pmatrix}$, $Y = \begin{pmatrix}0&0\\1&0\end{pmatrix}$.</p>
    <details class="hint"><summary>Hint</summary><p>Compute $XY$ and $YX$ separately first.</p></details>
    <textarea aria-label="Your working" placeholder="Work it here or on paper"></textarea>
    <div class="answer"><p>$$[X, Y] = \begin{pmatrix}1&0\\0&-1\end{pmatrix}$$</p></div>
  </div>

  <p class="goal-link">
    <strong>This unlocks:</strong> {what the learner can now do or read, toward the goal}.
  </p>

  <div class="primary-source">
    <strong>Read next:</strong> Hall, <em>Lie Groups, Lie Algebras, and Representations</em>, §3.1.<a class="cite" href="#src-1">1</a>
  </div>

  <p class="ask-tutor">Anything unclear? Ask the tutor — send a photo of your working if it helps.</p>

  <h2>Sources</h2>
  <ol class="sources">
    <li id="src-1" data-source="hall-2015">
      Brian C. Hall, <a href="https://doi.org/10.1007/978-3-319-13467-3"><em>Lie Groups, Lie Algebras, and Representations</em></a>, 2nd ed., 2015.
      <span class="loc">Def. 3.1, §3.1.</span>
    </li>
  </ol>

  <nav class="lesson-nav">
    <span></span>
    <a href="0002-the-matrix-exponential.html">Next: the matrix exponential →</a>
  </nav>
</main>
</body>
</html>
```

## Rules the check enforces

- `lesson-id` is `<topic>/<file name without .html>`; `nodes` lists map node ids, comma-separated, each with a file in `map/`.
- Every `a.cite` points at an `li` in `ol.sources`, and every such `li` carries `data-source` naming a record in `sources/`.
- There is a `.primary-source` block, and both `.goal-link` paragraphs (opening and closing). Reference sheets need neither.
- Every relative link resolves to a file in the vault.
- No inline script: every `<script>` has a `src`. The site serves lessons with `script-src 'self'`, and inline script would not run there.
- Every lesson and reference sheet has a cards file of the same name in `../cards/`.
- Every `.quiz` has exactly one option with `data-correct`; every `.exercise` has an `.answer`.

## Components

- `.definition`, `.theorem`, `.example`: labelled panels.
- `.quiz`: multiple choice, first answer counts, explanation shown after.
- `.exercise`: the learner works it, reveals the answer, grades themselves (got it / partly / missed). Use for anything computed or proved.
- `details.hint`: optional, before the answer.

Give every quiz and exercise a `data-id` unique within the lesson; results attach to it.

New components go in `assets/` (vault-grown) with their own CSS and JS file, linked from the lesson; `assets/base/` belongs to the mechanism repo and is replaced on update.
