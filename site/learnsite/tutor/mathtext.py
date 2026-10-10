"""LaTeX to plain Unicode for Telegram, which cannot render math.

The tutor writes LaTeX; Telegram gets the closest Unicode. Anything that does
not survive the trip (matrices, multi-line displays) is flagged so the bot can
link to the same reply rendered properly on the website.
"""

from __future__ import annotations

import re

from pylatexenc.latex2text import LatexNodes2Text, MacroTextSpec, get_default_latex_context_db

# pylatexenc drops operator names it does not know, so `\det R = 1` would come
# out as `R = 1`. Every operator a lesson is likely to use is spelled out here.
_OPERATORS = ["det", "tr", "exp", "log", "ln", "sin", "cos", "tan", "dim", "ker", "rank", "span",
              "Ad", "ad", "diag", "im", "Im", "Re", "arg", "max", "min", "sup", "inf", "lim",
              "deg", "sgn", "Hom", "End", "Aut", "Lie", "SO", "SE", "GL", "SL", "SU", "id"]

_SUPER = str.maketrans("0123456789+-=()niT", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵀ")
_SUB = str.maketrans("0123456789+-=()aeijkmnopstx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑᵢⱼₖₘₙₒₚₛₜₓ")
_SUPER_OK = set("0123456789+-=()niT⊤")
_SUB_OK = set("0123456789+-=()aeijkmnopstx")


def _converter() -> LatexNodes2Text:
    db = get_default_latex_context_db()
    db = db.filter_context(keep_categories=None)
    db.add_context_category(
        "tutor-operators", prepend=True,
        macros=[MacroTextSpec(name, simplify_repl=name + " ") for name in _OPERATORS]
        + [MacroTextSpec("top", simplify_repl="⊤"),
           MacroTextSpec("intercal", simplify_repl="⊤")],
    )
    return LatexNodes2Text(latex_context=db, math_mode="text")


_CONVERT = _converter()


def _scripts(text: str) -> str:
    """x^2 → x², R^⊤ → Rᵀ, ω_3 → ω₃ where every character has a Unicode form."""
    def sup(match: re.Match) -> str:
        body = match.group(1)
        return body.replace("⊤", "T").translate(_SUPER) if set(body) <= _SUPER_OK else match.group(0)

    def sub(match: re.Match) -> str:
        body = match.group(1)
        return body.translate(_SUB) if set(body) <= _SUB_OK else match.group(0)

    text = re.sub(r"\^([0-9a-zA-Z+\-=()⊤]{1,3})(?![0-9a-zA-Z])", sup, text)
    return re.sub(r"_([0-9a-z+\-=()]{1,3})(?![0-9a-z])", sub, text)


def needs_rendering(latex: str) -> bool:
    """True when Unicode will mangle it: display blocks and environments."""
    return bool(re.search(r"\$\$|\\\[|\\begin\{", latex))


def to_unicode(text: str) -> str:
    text = re.sub(r"\\operatorname\*?\{([^{}]*)\}", r"\\mathrm{\1}\\,", text)
    out = _CONVERT.latex_to_text(text)
    out = re.sub(r"(?<=\S) {2,}", " ", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return _scripts(out).strip()
