"""Background QThread workers for file I/O and search filtering.

Running pandas operations on a separate thread keeps the UI
responsive while large files are being loaded or filtered.
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

from src.query_filter import (QuerySyntaxError, evaluate,
                              looks_like_condition, parse_condition)

logger = logging.getLogger(__name__)


class DataLoaderWorker(QThread):
    """Load a file into a DataFrame on a background thread."""

    finished = pyqtSignal(object)   # emits pd.DataFrame
    error = pyqtSignal(str)         # emits error message

    def __init__(self, file_path: str, file_type: str,
                 options: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_type = file_type
        self.options: Dict[str, Any] = options or {}

    def run(self) -> None:
        try:
            if self.file_type == 'parquet':
                df = pd.read_parquet(self.file_path, engine='pyarrow')
            elif self.file_type in ('csv', 'csv_gzip', 'txt'):
                df = pd.read_csv(
                    self.file_path,
                    sep=self.options.get('sep', ','),
                    encoding=self.options.get('encoding', 'utf-8'),
                    dtype=self.options.get('dtype', None),
                    compression=self.options.get('compression', 'infer'),
                    header=self.options.get('header', 0),
                    quoting=self.options.get('quoting', 0),
                    on_bad_lines='skip',
                )
            else:
                self.error.emit(f"Unsupported file type: {self.file_type}")
                return

            self.finished.emit(df)
        except Exception as exc:
            logger.error("Error loading %s: %s", self.file_path, exc)
            self.error.emit(str(exc))


class FilterWorker(QThread):
    """Find the rows of a DataFrame matching *text* on a background thread.

    If *text* is a SQL WHERE-style condition (see :mod:`src.query_filter`)
    it is evaluated as such. Otherwise it is a case-insensitive substring
    search over every column, using the string representation the table
    displays.

    Rows are processed in chunks: between chunks the worker reports its
    progress, checks for cancellation and briefly releases the GIL, which
    pandas string operations otherwise hold for seconds at a time,
    starving the UI thread.
    """

    MODE_SQL = 'SQL'
    MODE_TEXT = 'text'

    # Cells (rows x columns) per chunk: well under 0.1 s of work, so the
    # UI stays fluid
    CHUNK_CELLS = 300_000

    # emits (generation, np.ndarray of row positions, mode)
    result = pyqtSignal(int, object, str)
    error = pyqtSignal(int, str)       # emits (generation, error message)
    progress = pyqtSignal(int, int)    # emits (generation, percent done)

    def __init__(self, dataframe: pd.DataFrame, text: str, generation: int,
                 parent=None):
        super().__init__(parent)
        self.dataframe = dataframe
        self.text = text
        self.generation = generation
        self._cancelled = False

    def cancel(self) -> None:
        """Stop at the next chunk; no result is emitted."""
        self._cancelled = True

    def run(self) -> None:
        try:
            try:
                condition = parse_condition(self.text)
            except QuerySyntaxError as exc:
                if looks_like_condition(self.text):
                    raise ValueError(f"Invalid condition: {exc}") from exc
                condition = None

            if condition is not None:
                positions = self._scan(lambda part: evaluate(condition, part))
                mode = self.MODE_SQL
            else:
                positions = self._scan(self._text_mask)
                mode = self.MODE_TEXT
            if positions is not None:
                self.result.emit(self.generation, positions, mode)
        except Exception as exc:
            logger.error("Error filtering data: %s", exc)
            self.error.emit(self.generation, str(exc))

    def _scan(self, row_mask) -> Optional[np.ndarray]:
        """Apply *row_mask* chunk by chunk; None if cancelled."""
        df = self.dataframe
        total = len(df)
        chunk = max(10_000, self.CHUNK_CELLS // max(1, len(df.columns)))
        found = []
        for start in range(0, total, chunk):
            if self._cancelled:
                return None
            mask = row_mask(df.iloc[start:start + chunk])
            found.append(np.flatnonzero(mask) + start)
            done = min(start + chunk, total)
            self.progress.emit(self.generation, done * 100 // total)
            self.msleep(1)  # release the GIL so the UI can repaint
        return np.concatenate(found) if found else np.array([], dtype=np.intp)

    def _text_mask(self, df: pd.DataFrame) -> np.ndarray:
        mask = np.zeros(len(df), dtype=bool)
        for i in range(len(df.columns)):
            col = df.iloc[:, i]
            if not (pd.api.types.is_string_dtype(col)
                    and not pd.api.types.is_object_dtype(col)):
                col = col.astype(str)
            matches = col.str.contains(self.text, case=False,
                                       regex=False, na=False)
            mask |= matches.to_numpy(dtype=bool, na_value=False)
        return mask
