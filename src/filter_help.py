"""Floating help panel for the search / filter field.

Explains the two filter modes (plain text and SQL-like conditions), lists
the supported operators, offers clickable examples and shows the columns of
the currently loaded file. Clicking an example or a column inserts it into
the search field.
"""

import html
import re
from typing import Callable, List, Tuple

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QPalette

# (condition, explanation)
EXAMPLES: List[Tuple[str, str]] = [
    ("pais = 'US'",
     "Rows where the column equals a text value (case-sensitive)."),
    ("monto > 1000",
     "Numeric comparison."),
    ("pais = 'US' and continente = 'America'",
     "Both conditions must be true."),
    ("pais = 'US' or pais = 'MX'",
     "Either condition can be true."),
    ("codigo like 'US%'",
     "Starts with US. % = any text, _ = exactly one character."),
    ("nombre ilike '%garcia%'",
     "Contains garcia, ignoring upper/lower case."),
    ("codigo in ('USA', 'USAID')",
     "Equals any value of the list."),
    ("pais not in ('US', 'MX')",
     "Equals none of the values of the list."),
    ("monto between 100 and 500",
     "Range, both limits included."),
    ("fecha >= '2024-01-01' and fecha < '2024-02-01'",
     "Dates are written as quoted text."),
    ("email is null",
     "Empty values. Use <code>is not null</code> for the opposite."),
    ("not (estado = 'CANCELADO')",
     "Negates a condition."),
    ("pais = 'US' and continente = 'America' and "
     "(codigo like 'US%' or codigo in ('USA', 'USAID'))",
     "Parentheses group conditions; AND is evaluated before OR."),
    ("[fecha de alta] >= '2024-01-01'",
     "Column names with spaces go between [brackets], "
     "\"double quotes\" or `backticks`."),
]

OPERATORS: List[Tuple[str, str]] = [
    ("=  !=  &lt;&gt;", "equal / not equal"),
    ("&lt;  &lt;=  &gt;  &gt;=", "less / greater than"),
    ("LIKE, NOT LIKE", "pattern with % and _ (case-sensitive)"),
    ("ILIKE, NOT ILIKE", "same as LIKE, ignoring case"),
    ("IN (...), NOT IN (...)", "value in a list"),
    ("BETWEEN a AND b", "value in a range (limits included)"),
    ("IS NULL, IS NOT NULL", "empty / not empty value"),
    ("AND, OR, NOT, ( )", "combine conditions"),
]

_BARE_NAME_RE = re.compile(r"[^\W\d]\w*\Z")
_KEYWORDS = {'AND', 'OR', 'NOT', 'LIKE', 'ILIKE', 'IN', 'IS', 'NULL',
             'BETWEEN', 'TRUE', 'FALSE'}


def quote_column(name: str) -> str:
    """Return *name* as it must be written in a condition."""
    if _BARE_NAME_RE.match(name) and name.upper() not in _KEYWORDS:
        return name
    if ']' not in name:
        return f"[{name}]"
    return '"' + name.replace('"', '""') + '"'


class FilterHelpDialog(QtWidgets.QDialog):
    """Non-modal floating panel with the filter syntax and examples."""

    def __init__(self, parent: QtWidgets.QWidget,
                 insert_text: Callable[[str, bool], None]):
        """*insert_text(text, replace)* puts text into the search field."""
        super().__init__(parent, Qt.Tool)
        self.setWindowTitle("Search / Filter Help")
        self.resize(620, 640)
        self._insert_text = insert_text
        self._columns: List[Tuple[str, str]] = []

        layout = QtWidgets.QVBoxLayout(self)
        self._browser = QtWidgets.QTextBrowser()
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_link)
        layout.addWidget(self._browser)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btn_box.rejected.connect(self.close)
        layout.addWidget(btn_box)

        self._render()

    def set_columns(self, columns: List[Tuple[str, str]]) -> None:
        """Set the *(name, dtype)* columns of the loaded file."""
        self._columns = columns
        self._render()

    # --- links ---------------------------------------------------------------

    def _on_link(self, url: QUrl) -> None:
        kind, _, index = url.toString().partition(':')
        if kind == 'example':
            self._insert_text(EXAMPLES[int(index)][0], True)
        elif kind == 'column':
            self._insert_text(quote_column(self._columns[int(index)][0]), False)

    # --- content -------------------------------------------------------------

    def _render(self) -> None:
        scroll = self._browser.verticalScrollBar().value()
        self._browser.setHtml(self._build_html())
        self._browser.verticalScrollBar().setValue(scroll)

    def _build_html(self) -> str:
        pal = self.palette()
        code_bg = pal.color(QPalette.AlternateBase).name()
        # Secondary text: 70% text colour over the background, readable
        # in both light and dark themes.
        fg, bg = pal.color(QPalette.Text), pal.color(QPalette.Base)
        muted = QColor(*(int(0.7 * a + 0.3 * b) for a, b in
                         zip(fg.getRgb()[:3], bg.getRgb()[:3]))).name()
        link = pal.color(QPalette.Link).name()

        parts = [f"""
        <style>
          h3 {{ margin-top: 14px; margin-bottom: 4px; }}
          code {{ background-color: {code_bg}; font-family: monospace; }}
          td {{ padding: 2px 8px 2px 0; vertical-align: top; }}
          .muted {{ color: {muted}; }}
          a {{ color: {link}; text-decoration: none; }}
        </style>

        <p>Type in the search field and press <b>Enter</b> to filter.
        Clear the field (or click its &#x2715;) to show all rows again.
        The filter searches the <b>whole file</b>, not only the current page.</p>

        <h3>1. Plain text search</h3>
        <p>Any text that is not a condition shows the rows containing it in
        <b>any column</b>, ignoring upper/lower case.<br>
        Example: <code>usaid</code></p>

        <h3>2. SQL condition</h3>
        <p>Write a condition like the one after <code>WHERE</code> in SQL.
        The status bar shows <i>Filtered (SQL)</i> or <i>Filtered (text)</i>
        to tell which mode was used.</p>
        <table>"""]
        for op, desc in OPERATORS:
            parts.append(f"<tr><td><code>{op}</code></td>"
                         f"<td>{desc}</td></tr>")
        parts.append("""</table>
        <ul>
          <li>Text values go in <b>single quotes</b>: <code>'US'</code>.
              Write a quote inside as two: <code>'O''Brien'</code>.</li>
          <li><code>=</code> and <code>LIKE</code> are case-sensitive;
              use <code>ILIKE</code> to ignore case.</li>
          <li>Keywords (and, or, like…) and column names can be written in
              upper or lower case.</li>
          <li>Rows with an empty value (NULL) never match a comparison, not
              even with <code>!=</code> or <code>NOT</code>; use
              <code>IS NULL</code> to find them.</li>
          <li>Functions (<code>UPPER()</code>…) and arithmetic
              (<code>a + b</code>) are not supported.</li>
        </ul>

        <h3>Examples</h3>
        <p class="muted">Click an example to copy it into the search field,
        adapt the column names and press Enter.</p>
        <table>""")
        for i, (cond, desc) in enumerate(EXAMPLES):
            parts.append(
                f'<tr><td><a href="example:{i}"><code>{html.escape(cond)}'
                f'</code></a><br><span class="muted">{desc}</span></td></tr>')
        parts.append("</table>")

        parts.append("<h3>Columns of the current file</h3>")
        if self._columns:
            parts.append('<p class="muted">Click a column to insert its name '
                         'at the cursor.</p><table>')
            for i, (name, dtype) in enumerate(self._columns):
                parts.append(
                    f'<tr><td><a href="column:{i}"><code>'
                    f'{html.escape(quote_column(name))}</code></a></td>'
                    f'<td class="muted">{html.escape(dtype)}</td></tr>')
            parts.append("</table>")
        else:
            parts.append('<p class="muted">No file loaded.</p>')

        return "".join(parts)
