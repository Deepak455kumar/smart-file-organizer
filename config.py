"""Configuration settings, constants, and category mappings for Smart File Organizer.
"""

from pathlib import Path
import os
import sys

# Application Metadata
APP_NAME = "Smart File Organizer"
APP_VERSION = "1.1.0"
AUTHOR = "Antigravity Engineer"

# Category Mapping (Extensions are lowercase, starting with dot)
EXTENSION_CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf"},
    "Spreadsheets": {".csv", ".xls", ".xlsx"},
    "Presentations": {".ppt", ".pptx"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov"},
    "Audio": {".mp3", ".wav", ".flac"},
    "Archives": {".zip", ".rar", ".7z"},
    "Code": {".py", ".js", ".html", ".css", ".java", ".cpp"},
}

DEFAULT_CATEGORY = "Other"

# Manifest filename for undo tracking
MANIFEST_FILENAME = ".smart_organizer_manifest.json"

# Default log file name (kept in the current working directory or designated app folder)
LOG_FILENAME = "smart_organizer.log"

# Internal application files to protect if workspace is chosen as target
INTERNAL_PROTECTED_FILES = {
    "main.py",
    "organizer.py",
    "gui.py",
    "config.py",
    "README.md",
    "LICENSE",
    ".gitignore",
    MANIFEST_FILENAME,
    LOG_FILENAME,
}

INTERNAL_PROTECTED_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "__pycache__",
    "tests",
    ".pytest_cache",
}

# Windows / OS Protected System Directory names (case-insensitive)
SYSTEM_PROTECTED_DIR_NAMES = {
    "windows",
    "system32",
    "syswow64",
    "program files",
    "program files (x86)",
    "programdata",
    "recovery",
    "system volume information",
    "$recycle.bin",
    "boot",
    "perflogs",
    "appdata",
}


def get_all_category_names() -> list[str]:
    """Return a sorted list of all supported category names including default."""
    categories = sorted(list(EXTENSION_CATEGORIES.keys()))
    categories.append(DEFAULT_CATEGORY)
    return categories
