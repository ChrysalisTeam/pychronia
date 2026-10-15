"""
Wrapper around the pyscss CLI (``python -m scss``).

pyscss==1.4.0 (the latest release, abandoned since ~2018) embeds the regex
``((?i)opacity)`` for its OPACITY token. Python 3.11+ rejects inline flags
that aren't at the very start of the pattern ("global flags not at the
start of the expression"), which makes pyscss unusable as-is. We patch the
pattern in-memory (``(?i:opacity)`` is equivalent and Python 3.11+-safe)
before running the real CLI.
"""
import scss.grammar.expression as expression

_patterns = expression.SassExpressionScanner._patterns
for _i, (_name, _pattern) in enumerate(_patterns):
    if _name == "OPACITY":
        _patterns[_i] = (_name, "(?i:opacity)")
        break

import scss.tool

scss.tool.main()
