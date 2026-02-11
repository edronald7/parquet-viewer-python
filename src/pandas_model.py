"""QAbstractTableModel backed by a pandas DataFrame, plus a pagination proxy.

Using a model instead of QTableWidget avoids copying every cell into a
Qt item object, resulting in dramatically better performance and lower
memory usage for large datasets.

Model chain
-----------
PandasModel  →  QSortFilterProxyModel (search)  →  PaginationProxyModel  →  QTableView
"""

from typing import Any, Optional

import pandas as pd
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel


class PandasModel(QAbstractTableModel):
    """Read-only table model that exposes a pandas DataFrame."""

    def __init__(self, dataframe: Optional[pd.DataFrame] = None, parent=None):
        super().__init__(parent)
        self._df: pd.DataFrame = dataframe if dataframe is not None else pd.DataFrame()

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
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.DisplayRole) -> Any:
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    # --- public helpers ------------------------------------------------------

    def update_dataframe(self, dataframe: pd.DataFrame) -> None:
        """Replace the backing DataFrame and notify all views."""
        self.beginResetModel()
        self._df = dataframe
        self.endResetModel()

    def clear(self) -> None:
        self.update_dataframe(pd.DataFrame())

    @property
    def dataframe(self) -> pd.DataFrame:
        return self._df


# ---------------------------------------------------------------------------
#  Pagination proxy
# ---------------------------------------------------------------------------

class PaginationProxyModel(QSortFilterProxyModel):
    """Proxy that exposes only one *page* of rows from its source model.

    Sits on top of a search/filter proxy so that pagination applies to the
    **filtered** result set.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page: int = 0
        self._page_size: int = 50

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
        self.invalidateFilter()

    def go_to_page(self, page: int) -> None:
        max_page = max(0, self.page_count - 1)
        self._page = max(0, min(page, max_page))
        self.invalidateFilter()

    def first_page(self) -> None:
        self.go_to_page(0)

    def next_page(self) -> bool:
        if self._page < self.page_count - 1:
            self._page += 1
            self.invalidateFilter()
            return True
        return False

    def previous_page(self) -> bool:
        if self._page > 0:
            self._page -= 1
            self.invalidateFilter()
            return True
        return False

    # --- QSortFilterProxyModel override --------------------------------------

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        start = self._page * self._page_size
        end = start + self._page_size
        return start <= source_row < end
