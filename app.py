import os
import sys
import json
import yaml
import pandas as pd
from datetime import datetime
from PyQt5 import QtWidgets, uic
from PyQt5.QtGui import QIcon

class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super(Main, self).__init__()
        uic.loadUi('assets/layout.ui', self)
        self.config = self.load_config()
        self.set_constants()

        self.init_gui()

    def load_config(self):
        conf_file = 'config/conf.yaml'
        with open(conf_file, 'r') as file:
            config = yaml.safe_load(file)
        return config
    
    def set_constants(self):
        self.file_auto_infer_types = self.config['app']['files']['txt-auto-infer-types']
        self.file_encodings = [enc.strip() for enc in self.config['app']['files']['txt-encodings'].split(',')]
        self.file_delimiter = self.config['app']['files']['txt-delimiter']
        self.file_has_header = True

    def init_gui(self):
        # Construct path relative to script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'assets/icon.png')
        if os.path.exists(icon_path):
            # Set icon window
            self.setWindowIcon(QIcon(icon_path))

        # Set window title
        self.title = "Application"
        self.title_add = " - Parquet Viewer Python"
        self.setWindowTitle(self.title + self.title_add)
        self.set_status("No records")
        self.path_file = None
        self.data_file_name = None
        self.data_file_ext = None
        self.dataframe = pd.DataFrame()
        self.dataindex = 0
        self.datarows = 0

        self.actionOpenParquetFile.triggered.connect(self.open_file_parquet)
        self.actionOpenCSVGZFile.triggered.connect(self.open_file_csv_gzip)
        self.actionOpenCSVFile.triggered.connect(self.open_file_csv)
        self.actionOpenTXTFile.triggered.connect(self.open_file_txt)

        self.actionCloseAndClean.triggered.connect(self.clear_data)

        self.actionExit.triggered.connect(self.close_window)

        self.btnShow.clicked.connect(self.on_re_show)
        self.btnPagPrevious.clicked.connect(self.on_page_previous)
        self.btnPagNext.clicked.connect(self.on_page_next)

        # Extract actions
        self.actionExtractExportData.triggered.connect(self.extract_export_data)
        self.actionExportParquet.triggered.connect(self.export_parquet_data)

        # Schema actions
        self.actionSchemaView.triggered.connect(self.extract_schema_view)
        self.actionSchemaToExcel.triggered.connect(self.extract_schema_to_excel)
        self.actionSchemaToJSON.triggered.connect(self.extract_schema_to_json)
        self.actionCompareJSONSchemas.triggered.connect(self.compare_json_schemas)

        self.actionAbout.triggered.connect(self.show_about)

    def close_window(self):
        reply = QtWidgets.QMessageBox.question(self, 'Message', "Are you sure to quit?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.close()
        
    def open_file_parquet(self):
        self.set_status("Select file...")
        path_file = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File', '', 'Parquet Files (*.parquet)')[0]
        if path_file:
            self.path_file = path_file
            self.dataframe = pd.read_parquet(path_file, engine='pyarrow')
            self.set_status_total_records()
            self.show_data()

    def open_file_text_plain(self, filter, compres = 'infer', sep_default = '|'):
        self.set_status("Select file...")
        path_file = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File', '', filter)[0]
        if path_file:
            # Create QMessageBox to select file options
            select_box = QtWidgets.QMessageBox()
            select_box.setWindowTitle("Select file options")
            select_box.setText("Select the file options")
            select_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
            select_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
            select_box.setModal(True)

            # Create the container and layout for the combobox
            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)

            # Create the first QComboBox (header)
            layout_header = QtWidgets.QHBoxLayout()
            label_header = QtWidgets.QLabel("Header:")
            layout_header.addWidget(label_header)
            option_header = QtWidgets.QComboBox()
            option_header.addItems(['True', 'False'])
            option_header.setCurrentText('True')
            option_header.setToolTip("Select if the file has header")
            layout_header.addWidget(option_header)
            layout.addLayout(layout_header)

            # Create the second QComboBox (separator)
            layout_sep = QtWidgets.QHBoxLayout()
            label_sep = QtWidgets.QLabel("Separator:")
            layout_sep.addWidget(label_sep)
            option_sep = QtWidgets.QComboBox()
            option_sep.addItems([';', ',', '|', '\t'])
            option_sep.setCurrentText(sep_default)
            option_sep.setToolTip("Select the column separator, the last one is tab")
            layout_sep.addWidget(option_sep)
            layout.addLayout(layout_sep)

            # Create the third QComboBox (encoding)
            layout_enc = QtWidgets.QHBoxLayout()
            label_enc = QtWidgets.QLabel("Encoding:")
            layout_enc.addWidget(label_enc)
            option_enc = QtWidgets.QComboBox()
            option_enc.addItems(self.file_encodings)
            option_enc.setCurrentText(self.file_encodings[0])
            option_enc.setToolTip("Select the file encoding")
            layout_enc.addWidget(option_enc)
            layout.addLayout(layout_enc)

            # Create the fourth QCheckBox (infer types)
            option_infer = QtWidgets.QCheckBox("Infer types")
            option_infer.setChecked(self.file_auto_infer_types)
            option_infer.setToolTip("Infer types from the file")
            layout.addWidget(option_infer)

            # Container layout
            select_box.layout().addWidget(container, 1, 0, 1, select_box.layout().columnCount())

            # Execute the QMessageBox and get results
            if select_box.exec_() == QtWidgets.QMessageBox.Ok:
                self.file_has_header = option_header.currentText() == 'True'
                self.file_delimiter = option_sep.currentText()
                self.file_encoding = option_enc.currentText()
                self.file_auto_infer_types = option_infer.isChecked()
                self.path_file = path_file
                self.dataframe = pd.read_csv(path_file, sep=self.file_delimiter, encoding=self.file_encoding, dtype=None if self.file_auto_infer_types else 'str', compression=compres, header=0 if self.file_has_header else None)

                self.set_status_total_records()
                self.show_data()

    def open_file_csv_gzip(self):
        compres = 'gzip'
        filter = 'CSV Gzip Files (*.csv.gz)'
        sep = ','
        self.open_file_text_plain(filter, compres, sep)    

    def open_file_csv(self):
        filter = 'CSV Files (*.csv)'
        compres = 'infer'
        sep = ','
        self.open_file_text_plain(filter, compres, sep)

    def open_file_txt(self):
        filter = 'Text Files (*.txt);;Text File (*.TXT)'
        compres = 'infer'
        sep = '|'
        self.open_file_text_plain(filter, compres, sep)

    def clear_data(self):
        self.dataframe = pd.DataFrame()
        self.tableWidget.clear()
        self.tableWidget.setColumnCount(0)
        self.tableWidget.setRowCount(0)
        self.set_status("No records")

    def set_data_file_info(self):
        self.data_file_ext = self.path_file.split('.')[-1]
        # get file name without path and extension
        if '/' in self.path_file:
            self.data_file_name = self.path_file.split('/')[-1]
        else:
            # if the os is Windows, use backslash
            if '\\' in self.path_file:
                self.data_file_name = self.path_file.split('\\')[-1]
            else:
                self.data_file_name = self.path_file.split('/')[-1]

        self.data_file_name = self.data_file_name.split('.')[0]
        
        # Set file name in the title
        self.setWindowTitle(self.data_file_name +'.'+ self.data_file_ext + self.title_add)

    def show_data(self):
        if self.dataframe.empty:
            self.set_status("No records")
            self.tableWidget.clear()
            self.tableWidget.setColumnCount(0)
            self.tableWidget.setRowCount(0)
            return
        
        self.set_data_file_info()
        # Set columns to col1, col2, col3, col4 if the dataframe has no columns
        if not self.file_has_header:
            self.dataframe.columns = ['col' + str(i) for i in range(1, self.dataframe.shape[1]+1)]

        # Clean tableWidget
        self.tableWidget.clear()

        limit_rows = self.spinLimit.value()

        self.tableWidget.setColumnCount(self.dataframe.shape[1])
        #self.tableWidget.setRowCount(self.dataframe.shape[0])
        self.tableWidget.setRowCount(limit_rows)
        self.tableWidget.setHorizontalHeaderLabels(self.dataframe.columns)

        self.progressBar.setValue(0)

        limit_grid = self.dataindex + limit_rows
        index_grid = 0

        while self.dataindex < self.datarows and self.dataindex < limit_grid:
            for j in range(self.dataframe.shape[1]):
                self.tableWidget.setItem(index_grid, j, QtWidgets.QTableWidgetItem(str(self.dataframe.iloc[self.dataindex, j])))
            
            self.dataindex += 1
            index_grid += 1
            self.progressBar.setValue(int((self.dataindex/self.datarows)*100))
            QtWidgets.QApplication.processEvents()
        self.tableWidget.setAlternatingRowColors(True)
        self.set_count_showing()

    def fill_table(self):
        limit_rows = self.spinLimit.value()
        limit_index = self.dataindex + limit_rows
        while self.dataindex < self.datarows and self.dataindex < limit_index:
            for j in range(self.dataframe.shape[1]):
                self.tableWidget.setItem(self.dataindex, j, QtWidgets.QTableWidgetItem(str(self.dataframe.iloc[self.dataindex, j])))
            
            self.dataindex += 1
            self.progressBar.setValue(int((self.dataindex/self.datarows)*100))
            QtWidgets.QApplication.processEvents()

    def on_page_previous(self):
        limit_rows = self.spinLimit.value()
        if self.datarows and self.dataindex > 0 and self.dataindex-limit_rows*2 >= 0:
            self.dataindex -= limit_rows*2
            self.show_data()
        elif self.datarows and self.dataindex > 0 and self.dataindex-(limit_rows+1) >= 0:
            self.dataindex = 0
            self.show_data()

    def on_page_next(self):
        limit_rows = self.spinLimit.value()
        if self.datarows and self.dataindex >= 0 and self.dataindex < self.datarows:
            self.show_data()

    def on_re_show(self):
        self.dataindex = 0
        self.show_data()

    def set_count_showing(self):
        # Showing # to ## of ### entries
        limit_rows = self.spinLimit.value()
        count_from = self.dataindex - limit_rows
        if count_from < 0:
            count_from = 0
        count_from += 1
        self.labelShowing.setText("Showing {:,} to {:,} of {:,} entries".format(count_from, self.dataindex, self.datarows))

    def set_status_total_records(self):
        if not hasattr(self, 'dataframe'):
            return
        # if the dataframe is empty, set status to "No records"
        if self.dataframe.empty:
            self.set_status("No records")
        else:
            # show total records in the status bar
            self.set_status("Total records: {:,}".format(self.dataframe.shape[0]))
            self.datarows = self.dataframe.shape[0]
            self.dataindex = 0

    def set_status(self, message):
        self.labelStatus.setText(message)

    def get_spark_type(self, dtype_str):
        # devolver el tipo de dato de spark equivalente para enteros, decimales, cadenas
        if dtype_str.lower().startswith('int') or dtype_str.lower() in ['int64', 'int32', 'int16', 'int8', 'uint8', 'uint16', 'uint32', 'uint64', 'integer', 'int']:
            return 'integer'
        elif dtype_str.lower().startswith('float') or dtype_str.lower() in ['float64', 'float32', 'float16', 'double']:
            return 'double'
        elif dtype_str.lower().startswith('str') or dtype_str.lower() in ['object', 'string']:
            return 'string'
        else:
            return 'string'
        
    def get_schema_df(self):
        # Set that first column is "column_name" and second column is "dtype"
        list_columns = []
        for col in self.dataframe.columns:
            type_pandas = self.dataframe[col].dtype.name
            type_spark = self.get_spark_type(type_pandas)
            list_columns.append({'Column Name': col, 'Pandas Type': type_pandas, 'Spark Type': type_spark})
        
        return pd.DataFrame(list_columns)
    
    # Extract functions
    def extract_export_data(self):
        if self.dataframe.empty:
            self.set_status("No records")
            QtWidgets.QMessageBox.information(self, 'Message', "No records to export", QtWidgets.QMessageBox.Ok)
            return
        
        export_box = QtWidgets.QMessageBox()
        export_box.setWindowTitle("Select export options")
        export_box.setText("Select extract and export options")
        export_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        export_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
        export_box.setModal(True)

        # create the container and layout for the comboboxes and inputs
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        layout_data = QtWidgets.QHBoxLayout()
        label_data = QtWidgets.QLabel("Extract:")
        layout_data.addWidget(label_data)
        section_data = QtWidgets.QComboBox()
        section_data.addItems(['Head', 'Tail', 'Random', 'All'])
        section_data.setCurrentText('Head')
        section_data.setToolTip("Select the type of extract")
        layout_data.addWidget(section_data)
        layout.addLayout(layout_data)

        layout_rows = QtWidgets.QHBoxLayout()
        label_rows = QtWidgets.QLabel("Rows:")
        layout_rows.addWidget(label_rows)
        input_rows = QtWidgets.QSpinBox()
        input_rows.setMinimum(1)
        input_rows.setMaximum(999000000)
        input_rows.setValue(50)
        input_rows.setToolTip("Select the number of rows to extract")
        layout_rows.addWidget(input_rows)
        layout.addLayout(layout_rows)

        layout_sep = QtWidgets.QHBoxLayout()
        label_sep = QtWidgets.QLabel("Separator:")
        layout_sep.addWidget(label_sep)
        sep_field = QtWidgets.QComboBox()
        sep_field.addItems([';', ',', '|', '\t'])
        sep_field.setCurrentText(self.file_delimiter)
        sep_field.setToolTip("Select the column separator, the last one is tab")
        layout_sep.addWidget(sep_field)
        layout.addLayout(layout_sep)

        text_except_fields = QtWidgets.QLineEdit()
        text_except_fields.setPlaceholderText("Columns to exclude, separated by commas")
        text_except_fields.setToolTip("Columns to exclude, separated by commas")
        layout.addWidget(text_except_fields)
        
        with_compress = QtWidgets.QCheckBox("Compress the file (*.csv.gz)")
        with_compress.setChecked(True)
        with_compress.setToolTip("Compress the file, if applicable")
        layout.addWidget(with_compress)

        # Container layout
        export_box.layout().addWidget(container, 1, 0, 1, export_box.layout().columnCount())

        # Execute the QMessageBox and get results
        if export_box.exec_() == QtWidgets.QMessageBox.Ok:
            option_data = section_data.currentText()
            option_rows = input_rows.value()
            option_sep = sep_field.currentText()
            option_except_fields = text_except_fields.text()
            option_compress = with_compress.isChecked()
            
            # Filter the dataframe based on the options
            if option_except_fields:
                list_except = [col.strip() for col in option_except_fields.split(',')]
                df_export = self.dataframe.drop(columns=list_except, errors='ignore').copy()
            else:
                df_export = self.dataframe.copy()
            # Get the number of rows to export
            if option_data in ['Head', 'Tail']:
                if option_data == 'Head':
                    df_export = df_export.head(option_rows)
                else:
                    df_export = df_export.tail(option_rows)
            elif option_data == 'Random':
                df_export = df_export.sample(n=option_rows)
            elif option_data == 'All':
                pass
            else:
                self.set_status("No records")
                return
            # Export the dataframe to CSV
            path_file = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', self.data_file_name + '_export.csv', 'CSV Files (*.csv)')[0]
            if path_file:
                # If checked compress, save as .csv.gz
                if option_compress:
                    df_export.to_csv(f'{path_file}.gz', sep=option_sep, index=False, compression='gzip')
                else:
                    df_export.to_csv(path_file, sep=option_sep, index=False)
                self.set_status("Data exported to {}".format(path_file))

    def export_parquet_data(self):
        if self.dataframe.empty:
            self.set_status("No records")
            QtWidgets.QMessageBox.information(self, 'Message', "No records to export", QtWidgets.QMessageBox.Ok)
            return
        # Suggest file name self.data_file_name + '_export.parquet'
        path_file = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', self.data_file_name + '_export.parquet', 'Parquet Files (*.parquet)')[0]
        if path_file:
            self.dataframe.to_parquet(path_file, index=False)
            self.set_status("Data exported to {}".format(path_file))

    # Schema functions
    def extract_schema_view(self):
        if self.dataframe.empty:
            self.set_status("No records")
            QtWidgets.QMessageBox.information(self, 'Message', "No records to show", QtWidgets.QMessageBox.Ok)
            return
        df_schema = self.get_schema_df()
        if df_schema.empty:
            self.set_status("No records")
            QtWidgets.QMessageBox.information(self, 'Message', "No records to show", QtWidgets.QMessageBox.Ok)
            return
        
        # Create a dialog to show the schema
        view_schema_box = QtWidgets.QDialog(self)
        view_schema_box.setWindowTitle("Schema View")
        view_schema_box.setModal(True)
        view_schema_box.setFixedSize(400, 400)

        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        table_schema = QtWidgets.QTableWidget()
        table_schema.setColumnCount(df_schema.shape[1])
        table_schema.setRowCount(df_schema.shape[0])
        table_schema.setHorizontalHeaderLabels(df_schema.columns)
        table_schema.setVerticalHeaderLabels([str(i) for i in range(1, df_schema.shape[0]+1)])
        table_schema.setColumnWidth(0, 200)
        table_schema.setColumnWidth(1, 80)
        table_schema.setColumnWidth(2, 80)
        table_schema.setHorizontalHeaderLabels(['Column Name', 'Pandas Type', 'Spark Type'])
        for i in range(df_schema.shape[0]):
            for j in range(df_schema.shape[1]):
                table_schema.setItem(i, j, QtWidgets.QTableWidgetItem(str(df_schema.iloc[i, j])))
        table_schema.resizeRowsToContents()
        table_schema.resizeColumnsToContents()
        table_schema.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        #table_schema.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        #table_schema.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        table_schema.setAlternatingRowColors(True)
        table_schema.setToolTip("Schema of the file")
        #table_schema.customContextMenuRequested.connect(lambda pos: self.show_context_menu(pos, table_schema))
        
        layout.addWidget(table_schema)

        layout_buttons = QtWidgets.QHBoxLayout()
        
        button_export_excel = QtWidgets.QPushButton("Export to Excel")
        button_export_excel.setToolTip("Export schema to Excel")
        button_export_excel.clicked.connect(self.extract_schema_to_excel)
        layout_buttons.addWidget(button_export_excel)

        button_export_json = QtWidgets.QPushButton("Export to JSON")
        button_export_json.setToolTip("Export schema to JSON")
        button_export_json.clicked.connect(self.extract_schema_to_json)
        layout_buttons.addWidget(button_export_json)

        layout.addLayout(layout_buttons)

        view_schema_box.setLayout(layout)
        view_schema_box.exec_()


    def extract_schema_to_excel(self):
        if self.dataframe.empty:
            self.set_status("No records")
            return
        # Suggest file name self.data_file_name + '_schema.xlsx'
        path_file = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', self.data_file_name + '_schema.xlsx', 'Excel Files (*.xlsx)')[0]
        if path_file:
            df_schema = self.get_schema_df()
            df_schema.to_excel(path_file, index=False)
            self.set_status("Schema extracted to Excel")

    def extract_schema_to_json(self):
        if self.dataframe.empty:
            self.set_status("No records")
            return
        
        path_file = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File', self.data_file_name + '_schema.json', 'JSON Files (*.json)')[0]
        if path_file:
            df_schema = self.get_schema_df()
            df_schema.columns = [col.lower().replace(' ', '_') for col in df_schema.columns]

            json_schema = {
                'schema': df_schema.to_dict(orient='records'),
                'total_columns': df_schema.shape[0],
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_file': f"{self.data_file_name}.{self.data_file_ext}"
            }
            with open(path_file, 'w') as file: 
                file.write(json.dumps(json_schema, indent=4))
            self.set_status("Schema extracted to JSON")

    def compare_json_schemas(self):
        # dialogs to select two JSON files to compare
        json_file_path1 = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File', '', 'JSON Files (*.json)')[0]
        json_file_path2 = QtWidgets.QFileDialog.getOpenFileName(self, 'Open File', '', 'JSON Files (*.json)')[0]

        if json_file_path1 and json_file_path2:
            with open(json_file_path1, 'r') as file:
                json1 = json.load(file)
            with open(json_file_path2, 'r') as file:
                json2 = json.load(file)
            
            cols_with_diff = []
            for col in json1['schema']:
                col_name = col['column_name']
                col_type = col['spark_type']
                col_found = False
                for col2 in json2['schema']:
                    if col2['column_name'] == col_name and col2['spark_type'] == col_type:
                        col_found = True
                        break
                if not col_found:
                    cols_with_diff.append(col_name)
            
            if len(cols_with_diff) == 0:
                # Alert that both JSON files have the same schema
                msg_box = f"Both JSON files have the same schema\n\nTotal columns: {json1['total_columns']}"
                QtWidgets.QMessageBox.information(self, 'Message', msg_box, QtWidgets.QMessageBox.Ok)
            else:
                error_box = f"Both JSON files have different schemas\n\nTotal columns file 1: {json1['total_columns']}\nTotal columns file 2: {json2['total_columns']}, \n\nColumns with differences:\n{len(cols_with_diff)}"
                # Show a message box with the error and the columns with differences
                msg_box = QtWidgets.QMessageBox()
                msg_box.setIcon(QtWidgets.QMessageBox.Critical)
                msg_box.setText("Error: " + error_box)
                msg_box.setInformativeText("Columns with differences:")
                msg_box.setDetailedText("\n".join(cols_with_diff))
                msg_box.setWindowTitle("Error")
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg_box.exec_()
    
    def show_about(self):
        about_box = QtWidgets.QMessageBox()
        about_box.setWindowTitle("About")
        about_box.setText("Parquet Viewer Python")
        text_about = "Desktop Version 1.0.0\n\nDeveloped by: edronald7@gmail.com\nWebsite: dataengi.net\n\n"+\
                    "This application is designed to facilitate the analysis of data lake files.\n\n"+\
                    "It enables you to open, view, and export data in multiple formats, including Parquet, CSV, and TXT.\n"+\
                    "Additionally, you can extract file schemas and export them to Excel or JSON formats.\n"+\
                    "The application also provides functionality to compare the structure and content of two files."
        about_box.setInformativeText(text_about)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'assets/icon.png')
        if os.path.exists(icon_path):
            about_box.setIconPixmap(QIcon(icon_path).pixmap(64, 64))
        else:
            about_box.setIcon(QtWidgets.QMessageBox.Information)
        about_box.setWindowIcon(QIcon(icon_path))
        about_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        about_box.exec_()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = Main()
    window.show()
    sys.exit(app.exec_())