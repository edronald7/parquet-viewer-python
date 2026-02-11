"""Main application window.

Improvements over the original monolithic app.py
-------------------------------------------------
* QTableView + QAbstractTableModel (virtual scrolling, no pagination needed)
* QSortFilterProxyModel for instant search / filter
* QThread for background data loading (no UI freeze)
* Drag & drop file opening
* Recent files history
* Keyboard shortcuts
* Bidirectional schema comparison
* Robust error handling with user-friendly messages
* Proper path resolution (no fragile relative paths)
* Correct quoting constants (csv module)
* Type hints throughout
"""

import csv
import json
import logging
import os
from typing import Any, Dict, List, Optional

import pandas as pd
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtGui import QIcon, QKeySequence

from src import config
from src.pandas_model import PandasModel, PaginationProxyModel
from src.schema import compare_schemas, get_schema_df, schema_to_json_dict
from src.workers import DataLoaderWorker

logger = logging.getLogger(__name__)

APP_TITLE = "Parquet Viewer Python"
VERSION = "2.1.0"


# ---------------------------------------------------------------------------
#  Helper: file name / extension parsing
# ---------------------------------------------------------------------------

def _parse_file_info(file_path: str):
    """Return *(name_without_ext, full_extension)* handling compound exts."""
    basename = os.path.basename(file_path)
    lower = basename.lower()
    if lower.endswith('.csv.gz'):
        return basename[:-7], 'csv.gz'
    name, ext = os.path.splitext(basename)
    return name, ext.lstrip('.')


# ---------------------------------------------------------------------------
#  Options dialog for text / CSV files
# ---------------------------------------------------------------------------

class TextFileOptionsDialog(QtWidgets.QDialog):
    """Modal dialog that lets the user pick separator, encoding, etc."""

    def __init__(self, parent: QtWidgets.QWidget, *,
                 encodings: List[str],
                 default_sep: str = '|',
                 default_encoding: str = 'utf-8',
                 default_infer: bool = True,
                 default_header: bool = True):
        super().__init__(parent)
        self.setWindowTitle("File Options")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QtWidgets.QVBoxLayout(self)

        # Header
        row_header = QtWidgets.QHBoxLayout()
        row_header.addWidget(QtWidgets.QLabel("Header:"))
        self.combo_header = QtWidgets.QComboBox()
        self.combo_header.addItems(['True', 'False'])
        self.combo_header.setCurrentText('True' if default_header else 'False')
        row_header.addWidget(self.combo_header)
        layout.addLayout(row_header)

        # Separator
        row_sep = QtWidgets.QHBoxLayout()
        row_sep.addWidget(QtWidgets.QLabel("Separator:"))
        self.combo_sep = QtWidgets.QComboBox()
        self.combo_sep.addItems([';', ',', '|', '\\t (tab)'])
        # map display value -> real value
        self._sep_map = {';': ';', ',': ',', '|': '|', '\\t (tab)': '\t'}
        display_sep = default_sep if default_sep != '\t' else '\\t (tab)'
        self.combo_sep.setCurrentText(display_sep)
        row_sep.addWidget(self.combo_sep)
        layout.addLayout(row_sep)

        # Encoding
        row_enc = QtWidgets.QHBoxLayout()
        row_enc.addWidget(QtWidgets.QLabel("Encoding:"))
        self.combo_encoding = QtWidgets.QComboBox()
        self.combo_encoding.addItems(encodings)
        self.combo_encoding.setCurrentText(default_encoding)
        row_enc.addWidget(self.combo_encoding)
        layout.addLayout(row_enc)

        # Quoting
        row_quote = QtWidgets.QHBoxLayout()
        row_quote.addWidget(QtWidgets.QLabel("Quoting:"))
        self.combo_quoting = QtWidgets.QComboBox()
        self.combo_quoting.addItems(['Minimal', 'Quote All', 'None'])
        self.combo_quoting.setCurrentText('Minimal')
        self.combo_quoting.setToolTip(
            "Minimal: quote only when needed. "
            "Quote All: every field is quoted. "
            "None: no quoting at all."
        )
        row_quote.addWidget(self.combo_quoting)
        layout.addLayout(row_quote)

        # Infer types
        self.check_infer = QtWidgets.QCheckBox("Infer types")
        self.check_infer.setChecked(default_infer)
        layout.addWidget(self.check_infer)

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # --- public getters ------------------------------------------------------

    _QUOTING_MAP = {'Minimal': csv.QUOTE_MINIMAL,
                    'Quote All': csv.QUOTE_ALL,
                    'None': csv.QUOTE_NONE}

    def get_options(self) -> Dict[str, Any]:
        has_header = self.combo_header.currentText() == 'True'
        sep_display = self.combo_sep.currentText()
        return {
            'header': 0 if has_header else None,
            'has_header': has_header,
            'sep': self._sep_map.get(sep_display, sep_display),
            'encoding': self.combo_encoding.currentText(),
            'quoting': self._QUOTING_MAP.get(self.combo_quoting.currentText(),
                                             csv.QUOTE_MINIMAL),
            'dtype': None if self.check_infer.isChecked() else 'str',
        }


# ---------------------------------------------------------------------------
#  Export options dialog
# ---------------------------------------------------------------------------

class ExportOptionsDialog(QtWidgets.QDialog):
    """Modal dialog for data export (Head / Tail / Random / All, etc.)."""

    def __init__(self, parent: QtWidgets.QWidget, *,
                 default_sep: str = ',',
                 total_rows: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Export Options")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QtWidgets.QVBoxLayout(self)

        # Extract type
        row_data = QtWidgets.QHBoxLayout()
        row_data.addWidget(QtWidgets.QLabel("Extract:"))
        self.combo_extract = QtWidgets.QComboBox()
        self.combo_extract.addItems(['Head', 'Tail', 'Random', 'All'])
        row_data.addWidget(self.combo_extract)
        layout.addLayout(row_data)

        # Number of rows
        row_rows = QtWidgets.QHBoxLayout()
        row_rows.addWidget(QtWidgets.QLabel("Rows:"))
        self.spin_rows = QtWidgets.QSpinBox()
        self.spin_rows.setMinimum(1)
        self.spin_rows.setMaximum(max(total_rows, 1))
        self.spin_rows.setValue(min(50, total_rows))
        row_rows.addWidget(self.spin_rows)
        layout.addLayout(row_rows)

        # Separator
        row_sep = QtWidgets.QHBoxLayout()
        row_sep.addWidget(QtWidgets.QLabel("Separator:"))
        self.combo_sep = QtWidgets.QComboBox()
        self.combo_sep.addItems([';', ',', '|', '\\t (tab)'])
        self._sep_map = {';': ';', ',': ',', '|': '|', '\\t (tab)': '\t'}
        display_sep = default_sep if default_sep != '\t' else '\\t (tab)'
        self.combo_sep.setCurrentText(display_sep)
        row_sep.addWidget(self.combo_sep)
        layout.addLayout(row_sep)

        # Exclude columns
        self.input_exclude = QtWidgets.QLineEdit()
        self.input_exclude.setPlaceholderText("Columns to exclude (comma-separated)")
        layout.addWidget(self.input_exclude)

        # Compress
        self.check_compress = QtWidgets.QCheckBox("Compress (*.csv.gz)")
        self.check_compress.setChecked(True)
        layout.addWidget(self.check_compress)

        # Buttons
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_options(self) -> Dict[str, Any]:
        sep_display = self.combo_sep.currentText()
        return {
            'extract': self.combo_extract.currentText(),
            'rows': self.spin_rows.value(),
            'sep': self._sep_map.get(sep_display, sep_display),
            'exclude': self.input_exclude.text(),
            'compress': self.check_compress.isChecked(),
        }


# ---------------------------------------------------------------------------
#  Main window
# ---------------------------------------------------------------------------

class MainWindow(QtWidgets.QMainWindow):
    """Application main window."""

    def __init__(self) -> None:
        super().__init__()

        # Load UI from file (absolute path)
        uic.loadUi(config.get_layout_path(), self)

        self._app_config = config.load_config()
        self._setup_constants()
        self._setup_ui()
        self._setup_table()
        self._setup_connections()
        self._setup_shortcuts()
        self._setup_drag_drop()
        self._setup_recent_files_menu()

        self._worker: Optional[DataLoaderWorker] = None
        self._current_load_settings: Dict[str, Any] = {}

    # =======================================================================
    #  SETUP
    # =======================================================================

    def _setup_constants(self) -> None:
        files_cfg = self._app_config.get('app', {}).get('files', {})
        self._auto_infer: bool = files_cfg.get('txt-auto-infer-types', True)
        self._encodings: List[str] = [
            e.strip()
            for e in files_cfg.get('txt-encodings', 'utf-8').split(',')
        ]
        self._delimiter: str = files_cfg.get('txt-delimiter', '|')
        self._has_header: bool = True

        self._path_file: Optional[str] = None
        self._file_name: Optional[str] = None
        self._file_ext: Optional[str] = None

    def _setup_ui(self) -> None:
        icon_path = config.get_icon_path()
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setWindowTitle(APP_TITLE)
        self._set_status("No records")

    def _setup_table(self) -> None:
        """Replace the QTableWidget from the .ui with a QTableView + model chain.

        Chain: PandasModel → search proxy → pagination proxy → QTableView
        """
        # 1. Base model backed by a DataFrame
        self._model = PandasModel()

        # 2. Search / filter proxy (operates on ALL rows)
        self._search_proxy = QSortFilterProxyModel()
        self._search_proxy.setSourceModel(self._model)
        self._search_proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._search_proxy.setFilterKeyColumn(-1)  # search all columns

        # 3. Pagination proxy (shows one page of filtered results)
        self._page_proxy = PaginationProxyModel()
        self._page_proxy.setSourceModel(self._search_proxy)
        self._page_proxy.set_page_size(self.spinLimit.value())

        # 4. QTableView
        self._table_view = QtWidgets.QTableView()
        self._table_view.setModel(self._page_proxy)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSortingEnabled(True)
        self._table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table_view.horizontalHeader().setStretchLastSection(True)

        # Swap widgets in the existing layout
        self.horizontalLayout.replaceWidget(self.tableWidget, self._table_view)
        self.tableWidget.hide()
        self.tableWidget.deleteLater()

        # Add search bar into the status area
        self._search_input = QtWidgets.QLineEdit()
        self._search_input.setPlaceholderText("Search / Filter...")
        self._search_input.setMaximumWidth(250)
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search_changed)
        self.horizontalStatus.insertWidget(2, self._search_input)

    def _setup_connections(self) -> None:
        # File menu
        self.actionOpenParquetFile.triggered.connect(self._open_file_parquet)
        self.actionOpenCSVGZFile.triggered.connect(self._open_file_csv_gzip)
        self.actionOpenCSVFile.triggered.connect(self._open_file_csv)
        self.actionOpenTXTFile.triggered.connect(self._open_file_txt)
        self.actionCloseAndClean.triggered.connect(self._clear_data)
        self.actionExit.triggered.connect(self._close_window)

        # Pagination / navigation
        self.btnShow.clicked.connect(self._on_show)
        self.btnPagPrevious.clicked.connect(self._on_page_previous)
        self.btnPagNext.clicked.connect(self._on_page_next)
        self.spinLimit.valueChanged.connect(self._on_page_size_changed)

        # Extract / Export
        self.actionExtractExportData.triggered.connect(self._extract_export_data)
        self.actionExportParquet.triggered.connect(self._export_parquet_data)

        # Schema
        self.actionSchemaView.triggered.connect(self._extract_schema_view)
        self.actionSchemaToExcel.triggered.connect(self._extract_schema_to_excel)
        self.actionSchemaToJSON.triggered.connect(self._extract_schema_to_json)
        self.actionCompareJSONSchemas.triggered.connect(self._compare_json_schemas)

        # Help
        self.actionAbout.triggered.connect(self._show_about)

    def _setup_shortcuts(self) -> None:
        self.actionOpenParquetFile.setShortcut(QKeySequence("Ctrl+O"))
        self.actionCloseAndClean.setShortcut(QKeySequence("Ctrl+W"))
        self.actionExit.setShortcut(QKeySequence("Ctrl+Q"))
        self.actionExtractExportData.setShortcut(QKeySequence("Ctrl+E"))
        self.actionExportParquet.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.actionSchemaView.setShortcut(QKeySequence("Ctrl+I"))

    def _setup_drag_drop(self) -> None:
        self.setAcceptDrops(True)

    def _setup_recent_files_menu(self) -> None:
        self._recent_menu = QtWidgets.QMenu("Recent Files", self)
        self.menuFile.insertMenu(self.actionCloseAndClean, self._recent_menu)
        self.menuFile.insertSeparator(self.actionCloseAndClean)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = config.load_recent_files()
        if not recent:
            action = self._recent_menu.addAction("(No recent files)")
            action.setEnabled(False)
        else:
            for fp in recent:
                act = self._recent_menu.addAction(os.path.basename(fp))
                act.setToolTip(fp)
                act.triggered.connect(lambda _checked, path=fp: self._open_recent_file(path))

    # =======================================================================
    #  FILE OPENING
    # =======================================================================

    def _open_file_parquet(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Parquet File', '', 'Parquet Files (*.parquet)')
        if path:
            self._has_header = True
            self._load_file(path, 'parquet')

    def _open_file_csv_gzip(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open CSV Gzip File', '', 'CSV Gzip Files (*.csv.gz)')
        if path:
            self._open_text_with_options(path, 'csv_gzip',
                                         default_sep=',', compression='gzip')

    def _open_file_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open CSV File', '', 'CSV Files (*.csv)')
        if path:
            self._open_text_with_options(path, 'csv', default_sep=',')

    def _open_file_txt(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Text File', '', 'Text Files (*.txt *.TXT)')
        if path:
            self._open_text_with_options(path, 'txt', default_sep='|')

    def _open_text_with_options(self, path: str, file_type: str, *,
                                default_sep: str = '|',
                                compression: str = 'infer') -> None:
        """Show options dialog and then load a text-based file."""
        dlg = TextFileOptionsDialog(
            self,
            encodings=self._encodings,
            default_sep=default_sep,
            default_encoding=self._encodings[0] if self._encodings else 'utf-8',
            default_infer=self._auto_infer,
            default_header=self._has_header,
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            opts = dlg.get_options()
            self._has_header = opts.pop('has_header', True)
            opts['compression'] = compression
            self._load_file(path, file_type, opts)

    def _open_recent_file(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            QtWidgets.QMessageBox.warning(
                self, 'Warning', f"File not found:\n{file_path}")
            return
        _, ext = _parse_file_info(file_path)
        ext_lower = ext.lower()
        if ext_lower == 'parquet':
            self._has_header = True
            self._load_file(file_path, 'parquet')
        elif ext_lower == 'csv.gz':
            self._load_file(file_path, 'csv_gzip',
                            {'sep': ',', 'compression': 'gzip'})
        elif ext_lower == 'csv':
            self._load_file(file_path, 'csv', {'sep': ','})
        elif ext_lower == 'txt':
            self._load_file(file_path, 'txt', {'sep': '|'})
        else:
            QtWidgets.QMessageBox.warning(
                self, 'Warning', f"Unsupported file format: .{ext}")

    # =======================================================================
    #  DATA LOADING (background thread)
    # =======================================================================

    def _load_file(self, path: str, file_type: str,
                   options: Optional[Dict[str, Any]] = None) -> None:
        """Start a background worker to load *path*."""
        # Store settings for potential refresh
        self._current_load_settings = {
            'path': path, 'file_type': file_type,
            'options': options or {},
        }

        self._path_file = path
        self._file_name, self._file_ext = _parse_file_info(path)

        self._set_status(f"Loading {os.path.basename(path)}...")
        self.progressBar.setRange(0, 0)  # indeterminate

        # Ensure any previous worker is finished
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait()

        self._worker = DataLoaderWorker(path, file_type, options, parent=self)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_data_loaded(self, df: pd.DataFrame) -> None:
        """Callback executed on the main thread when data is ready."""
        # Assign generic headers when the file has no header row
        if not self._has_header and not df.empty:
            df.columns = [f'col{i}' for i in range(1, len(df.columns) + 1)]

        self._model.update_dataframe(df)

        # Reset sort to original file order (no column sorted)
        self._table_view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self._search_proxy.sort(-1)

        # Reset pagination and show first page
        self._search_input.clear()
        self._page_proxy.first_page()
        self._table_view.resizeColumnsToContents()

        total = len(df)
        self._set_status(f"Total records: {total:,}")
        self._update_pagination_info()
        self.setWindowTitle(
            f"{self._file_name}.{self._file_ext} - {APP_TITLE}")

        # Reset header flag for next file
        self._has_header = True

        # Update recent files
        if self._path_file:
            config.add_recent_file(self._path_file)
            self._refresh_recent_menu()

    def _on_load_error(self, message: str) -> None:
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self._set_status("Error loading file")
        QtWidgets.QMessageBox.critical(
            self, 'Error', f"Could not load file:\n{message}")

    def _on_refresh(self) -> None:
        """Reload the current file from disk."""
        if self._current_load_settings:
            s = self._current_load_settings
            self._load_file(s['path'], s['file_type'], s.get('options'))
        else:
            self._set_status("No file to refresh")

    # =======================================================================
    #  PAGINATION
    # =======================================================================

    def _on_show(self) -> None:
        """Go back to first page and refresh the view."""
        self._page_proxy.first_page()
        self._update_pagination_info()

    def _on_page_previous(self) -> None:
        self._page_proxy.previous_page()
        self._update_pagination_info()

    def _on_page_next(self) -> None:
        self._page_proxy.next_page()
        self._update_pagination_info()

    def _on_page_size_changed(self, size: int) -> None:
        self._page_proxy.set_page_size(size)
        self._update_pagination_info()

    def _update_pagination_info(self) -> None:
        """Refresh the 'Showing X to Y of Z entries' label."""
        total = self._page_proxy.total_source_rows
        if total == 0:
            self.labelShowing.setText("")
            return
        frm = self._page_proxy.showing_from
        to = self._page_proxy.showing_to
        self.labelShowing.setText(
            f"Showing {frm:,} to {to:,} of {total:,} entries")
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(int(to / total * 100) if total else 0)

    # =======================================================================
    #  SEARCH / FILTER
    # =======================================================================

    def _on_search_changed(self, text: str) -> None:
        self._search_proxy.setFilterFixedString(text)
        # Reset to first page after filter change
        self._page_proxy.first_page()
        self._update_pagination_info()

    # =======================================================================
    #  CLEAR / CLOSE
    # =======================================================================

    def _clear_data(self) -> None:
        self._model.clear()
        self._search_input.clear()
        self._page_proxy.first_page()
        self._path_file = None
        self._file_name = None
        self._file_ext = None
        self._current_load_settings = {}
        self.progressBar.setValue(0)
        self.labelShowing.setText("")
        self.setWindowTitle(APP_TITLE)
        self._set_status("No records")

    def _close_window(self) -> None:
        reply = QtWidgets.QMessageBox.question(
            self, 'Confirm', "Are you sure you want to quit?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.close()

    # =======================================================================
    #  DRAG & DROP
    # =======================================================================

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].isLocalFile():
                ext = urls[0].toLocalFile().lower()
                if any(ext.endswith(e) for e in
                       ('.parquet', '.csv', '.csv.gz', '.txt')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if not urls:
            return
        file_path = urls[0].toLocalFile()
        _, ext = _parse_file_info(file_path)
        ext_lower = ext.lower()

        if ext_lower == 'parquet':
            self._has_header = True
            self._load_file(file_path, 'parquet')
        elif ext_lower == 'csv.gz':
            self._open_text_with_options(file_path, 'csv_gzip',
                                         default_sep=',', compression='gzip')
        elif ext_lower == 'csv':
            self._open_text_with_options(file_path, 'csv', default_sep=',')
        elif ext_lower == 'txt':
            self._open_text_with_options(file_path, 'txt', default_sep='|')

    # =======================================================================
    #  EXPORT DATA
    # =======================================================================

    def _require_data(self, action_label: str = "perform this action") -> bool:
        """Show a warning and return False if there is no data loaded."""
        if self._model.dataframe.empty:
            QtWidgets.QMessageBox.information(
                self, 'Info', f"No records to {action_label}.")
            return False
        return True

    def _extract_export_data(self) -> None:
        if not self._require_data("export"):
            return

        df = self._model.dataframe
        dlg = ExportOptionsDialog(self, default_sep=self._delimiter,
                                  total_rows=len(df))
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        opts = dlg.get_options()

        try:
            # Exclude columns
            df_export = df.copy()
            if opts['exclude']:
                cols = [c.strip() for c in opts['exclude'].split(',') if c.strip()]
                df_export = df_export.drop(columns=cols, errors='ignore')

            # Slice
            n_rows = opts['rows']
            extract = opts['extract']
            if extract == 'Head':
                df_export = df_export.head(n_rows)
            elif extract == 'Tail':
                df_export = df_export.tail(n_rows)
            elif extract == 'Random':
                n_rows = min(n_rows, len(df_export))
                df_export = df_export.sample(n=n_rows)
            # 'All' → no slicing

            suggested = f"{self._file_name or 'export'}_export.csv"
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, 'Save File', suggested, 'CSV Files (*.csv)')
            if not path:
                return

            sep = opts['sep']
            if opts['compress']:
                out_path = path if path.endswith('.gz') else f"{path}.gz"
                df_export.to_csv(out_path, sep=sep, index=False,
                                 compression='gzip')
            else:
                df_export.to_csv(path, sep=sep, index=False)

            self._set_status(f"Data exported to {os.path.basename(path)}")
        except Exception as exc:
            logger.error("Export error: %s", exc)
            QtWidgets.QMessageBox.critical(
                self, 'Error', f"Export failed:\n{exc}")

    def _export_parquet_data(self) -> None:
        if not self._require_data("export"):
            return
        suggested = f"{self._file_name or 'export'}_export.parquet"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save File', suggested, 'Parquet Files (*.parquet)')
        if path:
            try:
                self._model.dataframe.to_parquet(path, index=False)
                self._set_status(f"Data exported to {os.path.basename(path)}")
            except Exception as exc:
                logger.error("Parquet export error: %s", exc)
                QtWidgets.QMessageBox.critical(
                    self, 'Error', f"Export failed:\n{exc}")

    # =======================================================================
    #  SCHEMA
    # =======================================================================

    def _extract_schema_view(self) -> None:
        if not self._require_data("show schema"):
            return
        df_schema = get_schema_df(self._model.dataframe)

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Schema View")
        dlg.setModal(True)
        dlg.resize(520, 420)

        layout = QtWidgets.QVBoxLayout(dlg)

        table = QtWidgets.QTableWidget()
        table.setColumnCount(len(df_schema.columns))
        table.setRowCount(len(df_schema))
        table.setHorizontalHeaderLabels(list(df_schema.columns))
        table.setVerticalHeaderLabels(
            [str(i) for i in range(1, len(df_schema) + 1)])
        for i in range(len(df_schema)):
            for j in range(len(df_schema.columns)):
                table.setItem(
                    i, j,
                    QtWidgets.QTableWidgetItem(str(df_schema.iloc[i, j])))
        table.resizeColumnsToContents()
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_excel = QtWidgets.QPushButton("Export to Excel")
        btn_excel.clicked.connect(self._extract_schema_to_excel)
        btn_layout.addWidget(btn_excel)
        btn_json = QtWidgets.QPushButton("Export to JSON")
        btn_json.clicked.connect(self._extract_schema_to_json)
        btn_layout.addWidget(btn_json)
        layout.addLayout(btn_layout)

        dlg.exec_()

    def _extract_schema_to_excel(self) -> None:
        if not self._require_data("export schema"):
            return
        suggested = f"{self._file_name or 'schema'}_schema.xlsx"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save File', suggested, 'Excel Files (*.xlsx)')
        if path:
            try:
                get_schema_df(self._model.dataframe).to_excel(path, index=False)
                self._set_status("Schema exported to Excel")
            except Exception as exc:
                logger.error("Schema Excel export error: %s", exc)
                QtWidgets.QMessageBox.critical(
                    self, 'Error', f"Export failed:\n{exc}")

    def _extract_schema_to_json(self) -> None:
        if not self._require_data("export schema"):
            return
        suggested = f"{self._file_name or 'schema'}_schema.json"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save File', suggested, 'JSON Files (*.json)')
        if path:
            try:
                df_schema = get_schema_df(self._model.dataframe)
                payload = schema_to_json_dict(
                    df_schema, self._file_name or '', self._file_ext or '')
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump(payload, fh, indent=4)
                self._set_status("Schema exported to JSON")
            except Exception as exc:
                logger.error("Schema JSON export error: %s", exc)
                QtWidgets.QMessageBox.critical(
                    self, 'Error', f"Export failed:\n{exc}")

    def _compare_json_schemas(self) -> None:
        path1, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open first JSON schema', '', 'JSON Files (*.json)')
        if not path1:
            return
        path2, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open second JSON schema', '', 'JSON Files (*.json)')
        if not path2:
            return

        try:
            with open(path1, 'r', encoding='utf-8') as f:
                json1 = json.load(f)
            with open(path2, 'r', encoding='utf-8') as f:
                json2 = json.load(f)

            result = compare_schemas(json1, json2)

            if not result.has_differences:
                QtWidgets.QMessageBox.information(
                    self, 'Result',
                    f"Both schemas are identical "
                    f"(columns, types, and order match).\n\n"
                    f"Total columns: {json1['total_columns']}")
            else:
                details_parts: List[str] = []
                if result.only_in_first:
                    details_parts.append(
                        f"--- Only in first file ({len(result.only_in_first)}) ---\n"
                        + "\n".join(result.only_in_first))
                if result.only_in_second:
                    details_parts.append(
                        f"--- Only in second file ({len(result.only_in_second)}) ---\n"
                        + "\n".join(result.only_in_second))
                if result.type_mismatches:
                    details_parts.append(
                        f"--- Type mismatches ({len(result.type_mismatches)}) ---\n"
                        + "\n".join(result.type_mismatches))
                if result.order_mismatches:
                    details_parts.append(
                        f"--- Order mismatches ({len(result.order_mismatches)}) ---\n"
                        + "\n".join(result.order_mismatches))

                msg = QtWidgets.QMessageBox(self)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle("Schema Differences")
                msg.setText(
                    f"Schemas differ — {result.total_differences} "
                    f"difference(s) found.\n\n"
                    f"File 1 columns: {json1['total_columns']}\n"
                    f"File 2 columns: {json2['total_columns']}")
                msg.setDetailedText("\n\n".join(details_parts))
                msg.exec_()
        except Exception as exc:
            logger.error("Schema comparison error: %s", exc)
            QtWidgets.QMessageBox.critical(
                self, 'Error', f"Comparison failed:\n{exc}")

    # =======================================================================
    #  ABOUT
    # =======================================================================

    def _show_about(self) -> None:
        about = QtWidgets.QMessageBox(self)
        about.setWindowTitle("About")
        about.setText(APP_TITLE)
        about.setInformativeText(
            f"Desktop Version {VERSION}\n\n"
            "Developed by: edronald7@gmail.com\n\n"
            "This application facilitates the analysis of data lake files.\n"
            "Open, view, and export data in Parquet, CSV, and TXT formats.\n"
            "Extract schemas and export to Excel or JSON.\n"
            "Compare schemas to identify structural differences."
        )
        icon_path = config.get_icon_path()
        if os.path.exists(icon_path):
            about.setIconPixmap(QIcon(icon_path).pixmap(64, 64))
            about.setWindowIcon(QIcon(icon_path))
        else:
            about.setIcon(QtWidgets.QMessageBox.Information)
        about.setStandardButtons(QtWidgets.QMessageBox.Ok)
        about.exec_()

    # =======================================================================
    #  HELPERS
    # =======================================================================

    def _set_status(self, message: str) -> None:
        self.labelStatus.setText(message)
