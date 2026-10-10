// Behaviour for every lesson and reference sheet: math rendering, quizzes,
// and worked exercises. Loaded with `defer`; no inline script anywhere, so the
// site can serve lessons under `script-src 'self'`.
//
// Each answered quiz or self-graded exercise dispatches a `learning:result`
// event on document. Nothing listens yet; the website will, to save results.

(function () {
  "use strict";

  function emit(detail) {
    detail.lesson = document.querySelector('meta[name="lesson-id"]')?.content || null;
    document.dispatchEvent(new CustomEvent("learning:result", { detail: detail }));
  }

  function renderMath() {
    if (typeof renderMathInElement !== "function") return;
    renderMathInElement(document.body, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ],
      ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code"],
      throwOnError: false,
    });
  }

  // <div class="quiz" data-id="..."> with buttons.option, one carrying
  // data-correct. First choice counts; the explanation shows either way.
  function setUpQuiz(quiz) {
    var options = quiz.querySelectorAll("button.option");
    options.forEach(function (button) {
      button.addEventListener("click", function () {
        if (quiz.classList.contains("answered")) return;
        quiz.classList.add("answered");
        var right = button.hasAttribute("data-correct");
        button.classList.add(right ? "right" : "wrong");
        options.forEach(function (b) {
          if (b.hasAttribute("data-correct")) b.classList.add("right");
          b.disabled = true;
        });
        emit({ kind: "quiz", id: quiz.dataset.id || null, correct: right });
      });
    });
  }

  // <div class="exercise" data-id="..."> with a .answer block. The learner
  // works it, reveals, then grades themselves: math answers are not
  // machine-checkable in general.
  function setUpExercise(ex) {
    var actions = document.createElement("div");
    actions.className = "actions";
    var reveal = document.createElement("button");
    reveal.type = "button";
    reveal.textContent = "Show answer";
    actions.appendChild(reveal);

    var grade = document.createElement("div");
    grade.className = "selfgrade";
    [["got", "Got it"], ["partly", "Partly"], ["missed", "Missed it"]].forEach(function (pair) {
      var b = document.createElement("button");
      b.type = "button";
      b.textContent = pair[1];
      b.addEventListener("click", function () {
        grade.querySelectorAll("button").forEach(function (x) { x.classList.remove("chosen"); });
        b.classList.add("chosen");
        emit({ kind: "exercise", id: ex.dataset.id || null, grade: pair[0] });
      });
      grade.appendChild(b);
    });

    var answer = ex.querySelector(".answer");
    ex.insertBefore(actions, answer);
    ex.insertBefore(grade, answer.nextSibling);

    reveal.addEventListener("click", function () {
      ex.classList.add("revealed");
      reveal.remove();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderMath();
    document.querySelectorAll(".quiz").forEach(setUpQuiz);
    document.querySelectorAll(".exercise").forEach(setUpExercise);
  });
})();
