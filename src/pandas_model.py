"""QAbstractTableModel backed by a pandas DataFrame, plus a pagination proxy.

Using a model instead of QTableWidget avoids copying every cell into a
Qt item object, resulting in dramatically better performance and lower
memory usage for large datasets.

Model chain
-----------
PandasModel  →  PaginationProxyModel  →  QTableView

Neither filtering nor pagination use QSortFilterProxyModel: it calls
Python code once per row (or per cell) and freezes the UI on large files.
Instead the matching row positions are computed with vectorized pandas on
a background thread and handed to :meth:`PandasModel.set_row_filter`, and
the pagination proxy maps the current page to source rows arithmetically.
"""

from typing import Any, List, Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import Qt, QAbstractProxyModel, QAbstractTableModel, QModelIndex

# Role returning the raw cell value, used for sorting.
SORT_ROLE = Qt.UserRole


class PandasModel(QAbstractTableModel):
    """Read-only table model that exposes a pandas DataFrame.

    The model keeps the full DataFrame and, optionally, a row filter. When a
    filter is active only the matching rows are exposed to the views, while
    :attr:`dataframe` still returns the complete data.
    """

    def __init__(self, dataframe: Optional[pd.DataFrame] = None, parent=None):
        super().__init__(parent)
        self._full_df: pd.DataFrame = dataframe if dataframe is not None else pd.DataFrame()
        self._df: pd.DataFrame = self._full_df
        # Original row positions of the visible rows (None = no filter)
        self._positions: Optional[np.ndarray] = None

    # --- required overrides --------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            value = self._df.iloc[index.row(), index.column()]
            return str(value)
        if role == SORT_ROLE:
            return self._df.iloc[index.row(), index.column()]
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        if self._positions is not None:
            return str(self._positions[section] + 1)
        return str(section + 1)

    # --- public helpers ------------------------------------------------------

    def update_dataframe(self, dataframe: pd.DataFrame) -> None:
        """Replace the backing DataFrame (dropping any filter) and notify all views."""
        self.beginResetModel()
        self._full_df = dataframe
        self._df = dataframe
        self._positions = None
        self.endResetModel()

    def set_row_filter(self, positions: np.ndarray) -> None:
        """Show only the rows at *positions* (0-based) of the full DataFrame."""
        self.beginResetModel()
        self._positions = positions
        self._df = self._full_df.iloc[positions]
        self.endResetModel()

    def clear_row_filter(self) -> None:
        """Show all rows again."""
        if self._positions is None:
            return
        self.beginResetModel()
        self._positions = None
        self._df = self._full_df
        self.endResetModel()

    @property
    def is_filtered(self) -> bool:
        return self._positions is not None

    def clear(self) -> None:
        self.update_dataframe(pd.DataFrame())

    @property
    def dataframe(self) -> pd.DataFrame:
        """The full (unfiltered) DataFrame."""
        return self._full_df


# ---------------------------------------------------------------------------
#  Pagination proxy
# ---------------------------------------------------------------------------

class PaginationProxyModel(QAbstractProxyModel):
    """Proxy that exposes only one *page* of rows from its source model.

    The page is mapped to source rows by position, so the cost of changing
    page does not depend on the total number of rows. Sorting (clicking a
    column header) orders the rows of the current page.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page: int = 0
        self._page_size: int = 50
        self._sort_column: int = -1
        self._sort_order: Qt.SortOrder = Qt.AscendingOrder
        self._rows: List[int] = []  # source rows of the page, in display order

    def setSourceModel(self, model) -> None:  # noqa: N802
        old = self.sourceModel()
        if old is not None:
            for signal in self._source_signals(old):
                signal.disconnect(self._on_source_changed)
        super().setSourceModel(model)
        if model is not None:
            for signal in self._source_signals(model):
                signal.connect(self._on_source_changed)
        self._reset()

    @staticmethod
    def _source_signals(model):
        return (model.modelReset, model.layoutChanged, model.rowsInserted,
                model.rowsRemoved, model.columnsInserted,
                model.columnsRemoved, model.dataChanged)

    def _on_source_changed(self, *_args) -> None:
        self._page = max(0, min(self._page, self.page_count - 1))
        self._reset()

    # --- properties ----------------------------------------------------------

    @property
    def page(self) -> int:
        return self._page

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def total_source_rows(self) -> int:
        """Row count in the source model (i.e. after search filtering)."""
        src = self.sourceModel()
        return src.rowCount() if src else 0

    @property
    def page_count(self) -> int:
        total = self.total_source_rows
        if total == 0:
            return 0
        return (total + self._page_size - 1) // self._page_size

    @property
    def showing_from(self) -> int:
        """1-based index of first visible row."""
        if self.total_source_rows == 0:
            return 0
        return self._page * self._page_size + 1

    @property
    def showing_to(self) -> int:
        """1-based index of last visible row."""
        return min((self._page + 1) * self._page_size,
                   self.total_source_rows)

    # --- navigation ----------------------------------------------------------

    def set_page_size(self, size: int) -> None:
        self._page_size = max(1, size)
        self._page = 0
        self._reset()

    def go_to_page(self, page: int) -> None:
        max_page = max(0, self.page_count - 1)
        self._page = max(0, min(page, max_page))
        self._reset()

    def first_page(self) -> None:
        self.go_to_page(0)

    def next_page(self) -> bool:
        if self._page < self.page_count - 1:
            self._page += 1
            self._reset()
            return True
        return False

    def previous_page(self) -> bool:
        if self._page > 0:
            self._page -= 1
            self._reset()
            return True
        return False

    # --- page building -------------------------------------------------------

    def _reset(self) -> None:
        self.beginResetModel()
        start = self._page * self._page_size
        self._rows = list(range(start, min(start + self._page_size,
                                           self.total_source_rows)))
        if self._sort_column >= 0 and self._rows:
            self._sort_rows()
        self.endResetModel()

    def _sort_rows(self) -> None:
        src = self.sourceModel()
        column = self._sort_column
        if column >= src.columnCount():
            return
        values = {row: src.data(src.index(row, column), SORT_ROLE)
                  for row in self._rows}
        nulls = [r for r in self._rows if _is_null(values[r])]
        rest = [r for r in self._rows if not _is_null(values[r])]
        reverse = self._sort_order == Qt.DescendingOrder
        try:
            rest.sort(key=values.__getitem__, reverse=reverse)
        except (TypeError, ValueError):  # mixed or non-comparable values
            rest.sort(key=lambda r: str(values[r]), reverse=reverse)
        self._rows = rest + nulls  # NULLs always last

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        self._sort_column = column
        self._sort_order = order
        self._reset()

    # --- QAbstractProxyModel overrides ---------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        src = self.sourceModel()
        return 0 if parent.isValid() or src is None else src.columnCount()

    def index(self, row: int, column: int,
              parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if (parent.isValid() or not 0 <= row < len(self._rows)
                or not 0 <= column < self.columnCount()):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(self, index: QModelIndex = QModelIndex()) -> QModelIndex:
        return QModelIndex()

    def hasChildren(self, parent: QModelIndex = QModelIndex()) -> bool:  # noqa: N802
        return not parent.isValid() and bool(self._rows)

    def mapToSource(self, proxy_index: QModelIndex) -> QModelIndex:  # noqa: N802
        if not proxy_index.isValid() or proxy_index.row() >= len(self._rows):
            return QModelIndex()
        return self.sourceModel().index(self._rows[proxy_index.row()],
                                        proxy_index.column())

    def mapFromSource(self, source_index: QModelIndex) -> QModelIndex:  # noqa: N802
        if not source_index.isValid():
            return QModelIndex()
        try:
            row = self._rows.index(source_index.row())
        except ValueError:
            return QModelIndex()
        return self.createIndex(row, source_index.column())

    def headerData(self, section: int, orientation: Qt.Orientation,  # noqa: N802
                   role: int = Qt.DisplayRole) -> Any:
        src = self.sourceModel()
        if src is None:
            return None
        if orientation == Qt.Vertical:
            if not 0 <= section < len(self._rows):
                return None
            section = self._rows[section]
        return src.headerData(section, orientation, role)


def _is_null(value: Any) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):  # arrays / lists are never NULL
        return False
