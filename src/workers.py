"""Background QThread workers for file I/O.

Running pandas read operations on a separate thread keeps the UI
responsive while large files are being loaded.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal

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
