"""SQL-like WHERE conditions evaluated on a pandas DataFrame.

Supported syntax (keywords are case-insensitive)::

    pais = 'US' and continente = 'America'
      and (codigo like 'US%' or codigo in ('USA', 'USAID'))

* comparisons: ``=  ==  !=  <>  <  <=  >  >=``
* ``[NOT] LIKE`` (case-sensitive) / ``[NOT] ILIKE`` (case-insensitive)
  with ``%`` and ``_`` wildcards
* ``[NOT] IN (...)``, ``[NOT] BETWEEN a AND b``, ``IS [NOT] NULL``
* ``AND``, ``OR``, ``NOT`` and parentheses
* strings in single quotes (``''`` escapes a quote), numbers,
  ``TRUE``/``FALSE`` and ``NULL``
* column names as bare words, or quoted with "double quotes", `backticks`
  or [brackets] when they contain spaces or special characters

Conditions follow SQL's three-valued logic: a comparison involving NULL
is neither true nor false, so those rows are excluded (also under NOT).

Everything is evaluated with vectorized pandas / numpy operations, so it
scales to millions of rows.
"""

import operator
import re
from typing import Any, List, Optional, Tuple

import numpy as np
import pandas as pd


class QuerySyntaxError(ValueError):
    """The text is not a valid condition."""


class QueryError(ValueError):
    """The condition is valid but cannot be evaluated (e.g. unknown column)."""


# ---------------------------------------------------------------------------
#  Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"""
    (?P<ws>\s+)
  | (?P<str>'(?:[^']|'')*')
  | (?P<qid>"(?:[^"]|"")*"|`[^`]*`|\[[^\]]*\])
  | (?P<num>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<word>[^\W\d]\w*)
  | (?P<op><=|>=|<>|!=|==|=|<|>|\(|\)|,|-)
""", re.VERBOSE)

_KEYWORDS = {'AND', 'OR', 'NOT', 'LIKE', 'ILIKE', 'IN', 'IS', 'NULL',
             'BETWEEN', 'TRUE', 'FALSE'}
_CMP_OPS = {'=', '==', '!=', '<>', '<', '<=', '>', '>='}

# Token: (kind, value, position). Kinds: str, num, ident, kw, op, end.
_Token = Tuple[str, Any, int]


def _tokenize(text: str) -> List[_Token]:
    tokens: List[_Token] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise QuerySyntaxError(f"Unexpected character at position {pos + 1}")
        kind, raw = m.lastgroup, m.group()
        if kind == 'str':
            tokens.append(('str', raw[1:-1].replace("''", "'"), pos))
        elif kind == 'qid':
            # Double-quoted names remember it: if no such column exists
            # they are taken as a string literal (a common habit).
            name = raw[1:-1].replace('""', '"') if raw[0] == '"' else raw[1:-1]
            tokens.append(('ident', (name, raw[0] == '"'), pos))
        elif kind == 'num':
            value = float(raw) if any(c in raw for c in '.eE') else int(raw)
            tokens.append(('num', value, pos))
        elif kind == 'word':
            if raw.upper() in _KEYWORDS:
                tokens.append(('kw', raw.upper(), pos))
            else:
                tokens.append(('ident', (raw, False), pos))
        elif kind == 'op':
            tokens.append(('op', raw, pos))
        pos = m.end()
    tokens.append(('end', None, len(text)))
    return tokens


# ---------------------------------------------------------------------------
#  Parser (recursive descent) → AST of tuples
# ---------------------------------------------------------------------------
#
#  expr      := and_expr (OR and_expr)*
#  and_expr  := not_expr (AND not_expr)*
#  not_expr  := NOT not_expr | '(' expr ')' | predicate
#  predicate := operand ( cmp_op operand
#                       | [NOT] (LIKE | ILIKE) string
#                       | [NOT] IN '(' literal (',' literal)* ')'
#                       | [NOT] BETWEEN operand AND operand
#                       | IS [NOT] NULL )
#  operand   := column | literal

class _Parser:
    def __init__(self, text: str):
        self._tokens = _tokenize(text)
        self._i = 0

    # --- token helpers -------------------------------------------------------

    def _peek(self) -> _Token:
        return self._tokens[self._i]

    def _next(self) -> _Token:
        tok = self._tokens[self._i]
        self._i += 1
        return tok

    def _accept(self, kind: str, value: Any = None) -> bool:
        tok = self._peek()
        if tok[0] == kind and (value is None or tok[1] == value):
            self._i += 1
            return True
        return False

    def _expect(self, kind: str, value: Any = None) -> _Token:
        tok = self._peek()
        if tok[0] != kind or (value is not None and tok[1] != value):
            self._fail(f"Expected {value or kind}")
        return self._next()

    def _fail(self, message: str):
        tok = self._peek()
        where = "end of text" if tok[0] == 'end' else f"position {tok[2] + 1}"
        raise QuerySyntaxError(f"{message} at {where}")

    # --- grammar -------------------------------------------------------------

    def parse(self):
        node = self._or()
        if self._peek()[0] != 'end':
            self._fail("Unexpected token")
        return node

    def _or(self):
        node = self._and()
        while self._accept('kw', 'OR'):
            node = ('or', node, self._and())
        return node

    def _and(self):
        node = self._not()
        while self._accept('kw', 'AND'):
            node = ('and', node, self._not())
        return node

    def _not(self):
        if self._accept('kw', 'NOT'):
            return ('not', self._not())
        if self._accept('op', '('):
            node = self._or()
            self._expect('op', ')')
            return node
        return self._predicate()

    def _predicate(self):
        left = self._operand()
        tok = self._peek()

        if tok[0] == 'op' and tok[1] in _CMP_OPS:
            self._next()
            return ('cmp', tok[1], left, self._operand())

        if self._accept('kw', 'IS'):
            negated = self._accept('kw', 'NOT')
            self._expect('kw', 'NULL')
            return ('isnull', left, negated)

        negated = self._accept('kw', 'NOT')
        tok = self._peek()
        if tok[0] == 'kw' and tok[1] in ('LIKE', 'ILIKE'):
            self._next()
            pattern = self._expect('str')[1]
            return ('like', left, pattern, tok[1] == 'LIKE', negated)
        if self._accept('kw', 'IN'):
            self._expect('op', '(')
            values = [self._literal()]
            while self._accept('op', ','):
                values.append(self._literal())
            self._expect('op', ')')
            return ('in', left, values, negated)
        if self._accept('kw', 'BETWEEN'):
            low = self._operand()
            self._expect('kw', 'AND')
            return ('between', left, low, self._operand(), negated)

        self._fail("Expected a comparison operator")

    def _operand(self):
        tok = self._peek()
        if tok[0] == 'ident':
            self._next()
            name, double_quoted = tok[1]
            return ('col', name, double_quoted)
        return ('lit', self._literal())

    def _literal(self):
        tok = self._next()
        if tok[0] in ('str', 'num'):
            return tok[1]
        if tok[0] == 'op' and tok[1] == '-' and self._peek()[0] == 'num':
            return -self._next()[1]
        if tok[0] == 'kw' and tok[1] in ('TRUE', 'FALSE'):
            return tok[1] == 'TRUE'
        if tok[0] == 'kw' and tok[1] == 'NULL':
            return None
        self._i -= 1
        self._fail("Expected a column or value")


def parse_condition(text: str):
    """Parse *text* into an AST, raising :class:`QuerySyntaxError`."""
    return _Parser(text).parse()


def looks_like_condition(text: str) -> bool:
    """Heuristic: does the user seem to be writing a condition?

    Used to report a syntax error instead of silently falling back to a
    plain text search.
    """
    return bool(re.search(r"[=<>]", text))


# ---------------------------------------------------------------------------
#  Evaluation with three-valued logic: each node yields (true, false) masks;
#  rows in neither mask are "unknown" (NULL).
# ---------------------------------------------------------------------------

_OPS = {'=': operator.eq, '==': operator.eq, '!=': operator.ne,
        '<>': operator.ne, '<': operator.lt, '<=': operator.le,
        '>': operator.gt, '>=': operator.ge}
_FLIPPED = {'<': '>', '<=': '>=', '>': '<', '>=': '<='}

_Masks = Tuple[np.ndarray, np.ndarray]


def evaluate(node, df: pd.DataFrame) -> np.ndarray:
    """Return a boolean mask of the rows of *df* where *node* is TRUE."""
    return _Evaluator(df).eval(node)[0]


def filter_positions(text: str, df: pd.DataFrame) -> np.ndarray:
    """Parse and evaluate *text*, returning the matching row positions."""
    return np.flatnonzero(evaluate(parse_condition(text), df))


class _Evaluator:
    def __init__(self, df: pd.DataFrame):
        self._df = df
        self._n = len(df)

    def eval(self, node) -> _Masks:
        kind = node[0]
        if kind == 'and':
            (at, af), (bt, bf) = self.eval(node[1]), self.eval(node[2])
            return at & bt, af | bf
        if kind == 'or':
            (at, af), (bt, bf) = self.eval(node[1]), self.eval(node[2])
            return at | bt, af & bf
        if kind == 'not':
            t, f = self.eval(node[1])
            return f, t
        if kind == 'cmp':
            return self._compare(node[1], self._operand(node[2]),
                                 self._operand(node[3]))
        if kind == 'isnull':
            return self._is_null(self._operand(node[1]), node[2])
        if kind == 'like':
            return self._like(self._operand(node[1]), node[2], node[3], node[4])
        if kind == 'in':
            return self._in(self._operand(node[1]), node[2], node[3])
        if kind == 'between':
            value = self._operand(node[1])
            t1, f1 = self._compare('>=', value, self._operand(node[2]))
            t2, f2 = self._compare('<=', value, self._operand(node[3]))
            t, f = t1 & t2, f1 | f2
            return (f, t) if node[4] else (t, f)
        raise QueryError(f"Unknown node: {kind}")

    # --- operands ------------------------------------------------------------

    def _operand(self, node):
        """Return a pd.Series (column) or a Python scalar (literal)."""
        if node[0] == 'lit':
            return node[1]
        name, double_quoted = node[1], node[2]
        columns = [str(c) for c in self._df.columns]
        if name in columns:
            return self._df.iloc[:, columns.index(name)]
        lowered = [c.lower() for c in columns]
        if lowered.count(name.lower()) == 1:
            return self._df.iloc[:, lowered.index(name.lower())]
        if double_quoted:
            return name  # "US" meant as a string value
        raise QueryError(f"Unknown column: {name}")

    def _full(self, value: bool) -> np.ndarray:
        return np.full(self._n, value, dtype=bool)

    def _from_bool(self, value: Optional[bool]) -> _Masks:
        if value is None:
            return self._full(False), self._full(False)
        return self._full(value), self._full(not value)

    # --- predicates ----------------------------------------------------------

    def _compare(self, op: str, left, right) -> _Masks:
        left_col = isinstance(left, pd.Series)
        right_col = isinstance(right, pd.Series)

        if not left_col and not right_col:
            if left is None or right is None:
                return self._from_bool(None)
            try:
                return self._from_bool(bool(_OPS[op](left, right)))
            except TypeError as exc:
                raise QueryError(f"Cannot compare {left!r} and {right!r}") from exc

        if not left_col:
            left, right, op = right, left, _FLIPPED.get(op, op)

        if right_col:
            null = (left.isna() | right.isna()).to_numpy()
            a, b = _align_columns(left, right)
        else:
            if right is None:
                return self._from_bool(None)
            null = left.isna().to_numpy()
            a, b = _coerce(left, right)

        try:
            result = _to_bool(_OPS[op](a, b))
        except TypeError as exc:
            raise QueryError(
                f"Cannot compare column {left.name!r} with {right!r}") from exc
        return result & ~null, ~result & ~null

    def _is_null(self, value, negated: bool) -> _Masks:
        if isinstance(value, pd.Series):
            isnull = value.isna().to_numpy()
        else:
            isnull = self._full(value is None)
        return (~isnull, isnull) if negated else (isnull, ~isnull)

    def _like(self, value, pattern: str, case_sensitive: bool,
              negated: bool) -> _Masks:
        if not isinstance(value, pd.Series):
            if value is None:
                return self._from_bool(None)
            value = pd.Series([value] * self._n)
        null = value.isna().to_numpy()
        result = _to_bool(_like(_as_str(value), pattern, case_sensitive))
        t, f = result & ~null, ~result & ~null
        return (f, t) if negated else (t, f)

    def _in(self, value, items: list, negated: bool) -> _Masks:
        t, f = self._full(False), self._full(True)
        for item in items:
            it, itf = self._compare('=', value, item)
            t, f = t | it, f & itf
        return (f, t) if negated else (t, f)


# ---------------------------------------------------------------------------
#  Type helpers
# ---------------------------------------------------------------------------

def _to_bool(result) -> np.ndarray:
    if isinstance(result, pd.Series):
        return result.to_numpy(dtype=bool, na_value=False)
    return np.asarray(result, dtype=bool)


def _as_str(s: pd.Series) -> pd.Series:
    if isinstance(s.dtype, pd.StringDtype):
        return s
    return s.astype(str)


def _coerce(s: pd.Series, value) -> Tuple[pd.Series, Any]:
    """Make a column and a literal comparable, SQL-style."""
    dtype = s.dtype
    if pd.api.types.is_bool_dtype(dtype):
        if isinstance(value, str) and value.lower() in ('true', 'false'):
            return s, value.lower() == 'true'
        return s, value
    if pd.api.types.is_numeric_dtype(dtype):
        if isinstance(value, str):
            try:
                return s, float(value)
            except ValueError:
                return _as_str(s), value
        return s, value
    if pd.api.types.is_datetime64_any_dtype(dtype):
        if not isinstance(value, str):
            raise QueryError(
                f"Compare date column {s.name!r} with a quoted date, "
                f"e.g. '2024-01-31'")
        try:
            ts = pd.Timestamp(value)
        except ValueError as exc:
            raise QueryError(f"Invalid date: {value!r}") from exc
        tz = getattr(dtype, 'tz', None)
        if tz is not None and ts.tzinfo is None:
            ts = ts.tz_localize(tz)
        return s, ts
    # Text / object / categorical columns
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return pd.to_numeric(s, errors='coerce'), value
    if isinstance(value, str):
        return _as_str(s), value
    return s, value


def _align_columns(a: pd.Series, b: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """Make two columns comparable (fall back to comparing as text)."""
    for check in (pd.api.types.is_numeric_dtype,
                  pd.api.types.is_datetime64_any_dtype):
        if check(a.dtype) and check(b.dtype):
            return a, b
    return _as_str(a), _as_str(b)


def _like(s: pd.Series, pattern: str, case_sensitive: bool) -> pd.Series:
    """Vectorized SQL LIKE, with fast paths for the common patterns."""
    if '_' not in pattern:
        inner = pattern.strip('%')
        if '%' not in inner:
            if not inner:
                return pd.Series(True, index=s.index)
            if not case_sensitive:
                s, inner = s.str.lower(), inner.lower()
            starts, ends = pattern.startswith('%'), pattern.endswith('%')
            if starts and ends:
                return s.str.contains(inner, regex=False)
            if ends:
                return s.str.startswith(inner)
            if starts:
                return s.str.endswith(inner)
            return s == inner
    regex = ''.join('.*' if c == '%' else '.' if c == '_' else re.escape(c)
                    for c in pattern)
    return s.str.fullmatch(regex, case=case_sensitive, flags=re.DOTALL)
