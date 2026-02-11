"""Configuration management module.

Handles loading application config, resolving asset paths,
and managing recent files history.
"""

import os
import json
import logging
from typing import Dict, List, Any

import yaml

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
RECENT_FILES_PATH = os.path.join(CONFIG_DIR, '.recent_files.json')
MAX_RECENT_FILES = 10

_DEFAULT_CONFIG: Dict[str, Any] = {
    'app': {
        'files': {
            'txt-auto-infer-types': True,
            'txt-encodings': 'utf-8, iso-8859-1, windows-1252, latin1, ascii',
            'txt-delimiter': '|',
        }
    }
}


def load_config() -> Dict[str, Any]:
    """Load application configuration from conf.yaml."""
    conf_file = os.path.join(CONFIG_DIR, 'conf.yaml')
    try:
        with open(conf_file, 'r', encoding='utf-8') as fh:
            config = yaml.safe_load(fh)
            return config if config else _DEFAULT_CONFIG
    except Exception as exc:
        logger.warning("Could not load config (%s), using defaults.", exc)
        return _DEFAULT_CONFIG


def get_icon_path() -> str:
    return os.path.join(ASSETS_DIR, 'icon.png')


def get_layout_path() -> str:
    return os.path.join(ASSETS_DIR, 'layout.ui')


# --- Recent files -----------------------------------------------------------

def load_recent_files() -> List[str]:
    """Return list of recently-opened file paths that still exist on disk."""
    try:
        if os.path.exists(RECENT_FILES_PATH):
            with open(RECENT_FILES_PATH, 'r', encoding='utf-8') as fh:
                files = json.load(fh)
            return [f for f in files if os.path.exists(f)]
    except Exception as exc:
        logger.warning("Could not load recent files: %s", exc)
    return []


def save_recent_files(files: List[str]) -> None:
    try:
        with open(RECENT_FILES_PATH, 'w', encoding='utf-8') as fh:
            json.dump(files[:MAX_RECENT_FILES], fh, indent=2)
    except Exception as exc:
        logger.warning("Could not save recent files: %s", exc)


def add_recent_file(file_path: str) -> List[str]:
    """Prepend *file_path* to the recent-files list and persist it."""
    files = load_recent_files()
    if file_path in files:
        files.remove(file_path)
    files.insert(0, file_path)
    files = files[:MAX_RECENT_FILES]
    save_recent_files(files)
    return files
