# Parquet Viewer Python

A desktop utility for data engineers and analysts to efficiently explore data lake files, analyze and compare schemas, and convert/export data to various formats—all from your local machine.

![Application Parquet Viewer](assets/images/parquet-viewer-python.png)


## Features
**Version 2.1.0**  
This release provides the following capabilities:
- **File Exploration**: Open and visualize Parquet, CSV, CSV.GZ (Gzip) and TXT files to inspect data content and structure.
- **Virtual Scrolling**: Efficiently browse large datasets without pagination — powered by a high-performance table model.
- **Search & Filter**: Instantly filter rows across all columns using the built-in search bar.
- **Drag & Drop**: Drop files directly into the window to open them.
- **Recent Files**: Quickly reopen recently viewed files from the *Data File* menu.
- **Data Export**: Export data samples in CSV, Gzip, or Parquet formats — extract head, tail, random, or all records.
- **Schema Management**: View data schemas, export them to Excel or JSON, and compare two JSON schemas bidirectionally — ideal for tables with hundreds or thousands of columns.
- **Keyboard Shortcuts**: `Ctrl+O` open, `Ctrl+W` close, `Ctrl+Q` quit, `Ctrl+E` export, `Ctrl+I` schema view.

![Schema Viewer](assets/images/parquet-viewer-schema.png)


## Installation

### Prerequisites
- Python 3.9+ installed on your system.
- Basic familiarity with command-line interfaces.

### Option 1: Add Dependencies to an Existing Environment
Install the required libraries by running:
```bash
pip install -r requirements.txt
```

### Option 2: Create a Dedicated Python Virtual Environment
Run the provided `setup.py` script to set up a virtual environment and install dependencies automatically:
1. Ensure Python 3 is installed.
2. Execute the following command:
   ```bash
   python setup.py
   ```
   This will:
   - Create a virtual environment in the `venv/` folder within the project directory.
   - Install all dependencies listed in `requirements.txt`.
   - Generate a launcher script (`.bat` for Windows or `.sh` for Unix-based systems) for easy application startup.

## Usage
To launch the application: simply double-click `run.bat` or `run.sh`.

Or run it manually:
1. Activate the virtual environment (if using Option 2):
   - On Windows: `venv\Scripts\activate`
   - On Unix/Linux/Mac: `source venv/bin/activate`
2. Run the main script:
   ```bash
   python app.py
   ```
3. Follow the on-screen instructions to explore files, export data, or compare schemas.

## Project Structure
```
app.py                  # Entry point
src/
  main_window.py        # Main UI window
  pandas_model.py       # QAbstractTableModel for DataFrames
  workers.py            # QThread background data loading
  schema.py             # Schema extraction & comparison
  config.py             # Configuration management
config/
  conf.yaml             # Application settings
assets/
  layout.ui             # Qt Designer UI layout
  icon.png              # Application icon
```

## Contributing
Contributions are welcome! Please submit issues or pull requests to help improve the project. For major changes, please open an issue first to discuss your ideas.

## About us
Github: https://github.com/edronald7

## License
[MIT License](LICENSE)  
See the `LICENSE` file in the repository for details.
