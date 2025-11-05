#!/usr/bin/env python3
"""
DSPX - Data Store Pruner and Compressor
Clean up directories by removing OS residual files, finding and removing duplicate files,
and deleting empty directories.

P.W.R. Marcoux 2025 :: aka WOLFBED

VERSION 1.0
    - CSV-based pattern matching for OS residual files
    - Pattern validation and testing
    - Stop button for clean cancellation
    - Settings persistence
    - Comprehensive logging
    - Async parallel file hashing
"""
import asyncio
import csv
import json
import multiprocessing
import os
import platform
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFileDialog, QListWidget,
    QGroupBox, QProgressBar, QMessageBox, QTabWidget, QSpinBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QAbstractItemView
)

# Try to use blake3 if available, otherwise fall back to sha256
try:
    import blake3
    HASH_ALGO = "blake3"

    def compute_hash_sync(filepath: Path, chunk_size: int = 65536) -> str:
        """Synchronous hash computation for thread pool."""
        hasher = blake3.blake3()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def compute_hash_async(filepath: Path, executor, chunk_size: int = 65536) -> Tuple[Path, str]:
        """Async wrapper for hash computation."""
        loop = asyncio.get_event_loop()
        file_hash = await loop.run_in_executor(
            executor, compute_hash_sync, filepath, chunk_size
        )
        return filepath, file_hash

except ImportError:
    import hashlib
    HASH_ALGO = "sha256"

    def compute_hash_sync(filepath: Path, chunk_size: int = 65536) -> str:
        """Synchronous hash computation for thread pool."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def compute_hash_async(filepath: Path, executor, chunk_size: int = 65536) -> Tuple[Path, str]:
        """Async wrapper for hash computation."""
        loop = asyncio.get_event_loop()
        file_hash = await loop.run_in_executor(
            executor, compute_hash_sync, filepath, chunk_size
        )
        return filepath, file_hash


# Default settings
DEFAULT_SETTINGS = {
    'max_workers': min(32, multiprocessing.cpu_count() * 2),
    'chunk_size': 65536,  # 64 KB
}

# Determine the directory containing the current script
BASE_DIR = Path(__file__).resolve().parent

# Define paths relative to that directory
SETTINGS_FILE = BASE_DIR / 'dspx_settings.json'
PATTERNS_FILE = BASE_DIR / 'dspx_residuals_patterns.csv'


def load_settings() -> Dict:
    """Load settings from file or return defaults."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                return {**DEFAULT_SETTINGS, **settings}
        except Exception as e:
            print(f"Failed to load settings: {e}")
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict):
    """Save settings to file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Failed to save settings: {e}")


# def load_residual_patterns() -> List[Dict]:
#     """Load OS residual patterns from CSV file."""
#     patterns = []
#     if not PATTERNS_FILE.exists():
#         return []
#     try:
#         with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
#             reader = csv.DictReader(f)
#             for row in reader:
#                 # Validate required columns
#                 if row.get('OS') and row.get('File_Pattern'):
#                     patterns.append({
#                         'OS': row.get('OS', '').strip(),
#                         'File_Pattern': row.get('File_Pattern', '').strip(),
#                         'Path_Example': row.get('Path_Example', '').strip(),
#                         'Description': row.get('Description', '').strip(),
#                         'Safe_To_Delete': row.get('Safe_To_Delete', '').strip()
#                     })
#     except Exception as e:
#         print(f"Error loading patterns: {e}")
#     return patterns

def load_residual_patterns() -> List[Dict]:
    """Load OS residual patterns from CSV file."""
    patterns = []
    if not PATTERNS_FILE.exists():
        return []
    try:
        with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Validate required columns
                if row.get('OS') and row.get('File_Pattern'):
                    patterns.append({
                        'OS': row.get('OS', '').strip(),
                        'File_Pattern': row.get('File_Pattern', '').strip(),
                        'Path_Example': row.get('Path_Example', '').strip(),
                        'Description': row.get('Description', '').strip(),
                        'Safe_To_Delete': row.get('Safe_To_Delete', '').strip(),
                        'Enabled': row.get('Enabled', 'Yes').strip()  # Default to Yes if not present
                    })
    except Exception as e:
        print(f"Error loading patterns: {e}")
    return patterns


# def save_residual_patterns(patterns: List[Dict]):
#     """Save OS residual patterns to CSV file."""
#     try:
#         # Create backup
#         if PATTERNS_FILE.exists():
#             backup_file = PATTERNS_FILE.with_suffix('.csv_bak')
#             shutil.copy2(PATTERNS_FILE, backup_file)
#
#         with open(PATTERNS_FILE, 'w', encoding='utf-8', newline='') as f:
#             fieldnames = ['OS', 'File_Pattern', 'Path_Example', 'Description', 'Safe_To_Delete']
#             writer = csv.DictWriter(f, fieldnames=fieldnames)
#             writer.writeheader()
#             writer.writerows(patterns)
#     except Exception as e:
#         print(f"Error saving patterns: {e}")

def save_residual_patterns(patterns: List[Dict]):
    """Save OS residual patterns to CSV file."""
    try:
        # Create backup
        if PATTERNS_FILE.exists():
            backup_file = PATTERNS_FILE.with_suffix('.csv_bak')
            shutil.copy2(PATTERNS_FILE, backup_file)

        with open(PATTERNS_FILE, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['OS', 'File_Pattern', 'Path_Example', 'Description', 'Safe_To_Delete', 'Enabled']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(patterns)
    except Exception as e:
        print(f"Error saving patterns: {e}")


# def match_residual_pattern(filepath: Path, patterns: List[Dict]) -> Optional[Dict]:
#     """Check if a file matches any OS residual pattern."""
#     filename = filepath.name
#     for pattern in patterns:
#         file_pattern = pattern['File_Pattern']
#         # Handle wildcard patterns
#         if fnmatch(filename, file_pattern):
#             return pattern
#     return None

def match_residual_pattern(filepath: Path, patterns: List[Dict]) -> Optional[Dict]:
    """Check if a file matches any OS residual pattern."""
    filename = filepath.name
    for pattern in patterns:
        # Skip disabled patterns
        if pattern.get('Enabled', 'Yes').lower() not in ['yes', 'true', '1']:
            continue
        file_pattern = pattern['File_Pattern']
        # Handle wildcard patterns
        if fnmatch(filename, file_pattern):
            return pattern
    return None


class WorkerSignals(QObject):
    """Signals for worker threads."""
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)
    log = Signal(str)


class ScanWorker(QThread):
    """Worker thread for scanning directories."""
    def __init__(self, directories: List[str], operation: str,
                 max_workers: int = None, chunk_size: int = 65536,
                 patterns: List[Dict] = None):
        super().__init__()
        self.directories = directories
        self.operation = operation
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self.max_workers = max_workers or DEFAULT_SETTINGS['max_workers']
        self.chunk_size = chunk_size
        self.patterns = patterns or []


    def cancel(self):
        """Cancel the operation."""
        self._is_cancelled = True
        self.signals.log.emit("Cancellation requested...")


    def run(self):
        """Execute the scanning operation."""
        try:
            if self.operation == "scan_residual":
                result = self.scan_residual_files()
            elif self.operation == "scan_duplicates":
                result = self.scan_for_duplicates()
            elif self.operation == "scan_empty_dirs":
                result = self.scan_empty_directories()
            else:
                result = None
            if not self._is_cancelled:
                self.signals.finished.emit(result)
            else:
                self.signals.log.emit("Operation cancelled")
                self.signals.finished.emit(None)
        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            self.signals.error.emit(error_details)


    def scan_residual_files(self) -> List[Tuple[Path, Dict]]:
        """Scan for OS residual files using patterns from CSV."""
        residual_files = []
        total_scanned = 0
        self.signals.log.emit(f"Starting OS residual files scan with {len(self.patterns)} patterns...")
        for directory in self.directories:
            if self._is_cancelled:
                return []
            dir_path = Path(directory)
            if not dir_path.exists():
                self.signals.log.emit(f"Warning: Directory does not exist: {directory}")
                continue
            self.signals.log.emit(f"Scanning directory: {directory}")
            try:
                for root, dirs, files in os.walk(dir_path):
                    if self._is_cancelled:
                        return []
                    root_path = Path(root)
                    # Check directories
                    for dirname in dirs:
                        total_scanned += 1
                        if total_scanned % 100 == 0:
                            self.signals.progress.emit(0, f"Scanned {total_scanned} items...")
                        dir_full_path = root_path / dirname
                        matched_pattern = match_residual_pattern(dir_full_path, self.patterns)
                        if matched_pattern:
                            residual_files.append((dir_full_path, matched_pattern))
                    # Check files
                    for filename in files:
                        total_scanned += 1
                        if total_scanned % 100 == 0:
                            self.signals.progress.emit(0, f"Scanned {total_scanned} items...")
                        file_path = root_path / filename
                        matched_pattern = match_residual_pattern(file_path, self.patterns)
                        if matched_pattern:
                            residual_files.append((file_path, matched_pattern))
            except Exception as e:
                self.signals.log.emit(f"Error scanning {directory}: {str(e)}")
        self.signals.log.emit(f"Found {len(residual_files)} OS residual files/directories")
        return residual_files


    # def scan_for_duplicates(self) -> Dict:
    #     """Scan for duplicate files using hash signatures with parallel processing."""
    #     file_hashes = {}
    #     file_info = {}
    #     files_to_hash = []
    #     self.signals.log.emit(f"Starting duplicate scan using {HASH_ALGO} hashing...")
    #     self.signals.log.emit(f"Using {self.max_workers} parallel workers")
    #     self.signals.log.emit(f"Chunk size: {self.chunk_size} bytes ({self.chunk_size // 1024} KB)")
    #     # First pass: collect files
    #     for directory in self.directories:
    #         if self._is_cancelled:
    #             return {}
    #         dir_path = Path(directory)
    #         if not dir_path.exists():
    #             self.signals.log.emit(f"Warning: Directory does not exist: {directory}")
    #             continue
    #         self.signals.log.emit(f"Collecting files in: {directory}")
    #         try:
    #             for root, _, files in os.walk(dir_path):
    #                 if self._is_cancelled:
    #                     return {}
    #                 root_path = Path(root)
    #                 for filename in files:
    #                     file_path = root_path / filename
    #                     # Skip OS residual files
    #                     if match_residual_pattern(file_path, self.patterns):
    #                         continue
    #                     if not file_path.is_file():
    #                         continue
    #                     try:
    #                         file_size = file_path.stat().st_size
    #                         files_to_hash.append((file_path, file_size, filename))
    #                     except (OSError, PermissionError) as e:
    #                         self.signals.log.emit(f"Error accessing {file_path}: {str(e)}")
    #         except Exception as e:
    #             self.signals.log.emit(f"Error scanning {directory}: {str(e)}")
    #     if not files_to_hash:
    #         self.signals.log.emit("No files found to process")
    #         return {}
    #     # Second pass: parallel hashing
    #     try:
    #         file_hashes, file_info, total_scanned = asyncio.run(
    #             self._hash_files_parallel(files_to_hash)
    #         )
    #     except Exception as e:
    #         self.signals.log.emit(f"Error during parallel hashing: {str(e)}")
    #         return {}
    #     if self._is_cancelled:
    #         return {}
    #     # Find duplicates
    #     same_name_duplicates = defaultdict(list)
    #     all_duplicates = {}
    #     for file_hash, file_paths in file_hashes.items():
    #         if len(file_paths) > 1:
    #             # Group by name
    #             by_name = defaultdict(list)
    #             for fpath in file_paths:
    #                 fname = Path(fpath).name
    #                 by_name[fname].append(fpath)
    #             # Same name duplicates
    #             for fname, paths in by_name.items():
    #                 if len(paths) > 1:
    #                     same_name_duplicates[file_hash].extend(paths)
    #             # All duplicates
    #             all_duplicates[file_hash] = file_paths
    #     self.signals.log.emit(f"Scanned {total_scanned} files")
    #     self.signals.log.emit(f"Found {len(same_name_duplicates)} groups of same-name duplicates")
    #     self.signals.log.emit(f"Found {len(all_duplicates)} groups of all duplicates")
    #     return {
    #         'file_info': file_info,
    #         'same_name_duplicates': same_name_duplicates,
    #         'all_duplicates': all_duplicates
    #     }


    def scan_for_duplicates(self) -> Dict:
        """Scan for duplicate files using hash signatures with parallel processing."""
        file_hashes = {}
        file_info = {}
        files_to_hash = []
        self.signals.log.emit(f"Starting duplicate scan using {HASH_ALGO} hashing...")
        self.signals.log.emit(f"Using {self.max_workers} parallel workers")
        self.signals.log.emit(f"Chunk size: {self.chunk_size} bytes ({self.chunk_size // 1024} KB)")

        # First pass: collect files
        for directory in self.directories:
            if self._is_cancelled:
                return {}
            dir_path = Path(directory)
            if not dir_path.exists():
                self.signals.log.emit(f"Warning: Directory does not exist: {directory}")
                continue
            self.signals.log.emit(f"Collecting files in: {directory}")
            try:
                for root, _, files in os.walk(dir_path):
                    if self._is_cancelled:
                        return {}
                    root_path = Path(root)
                    for filename in files:
                        file_path = root_path / filename
                        # Skip OS residual files
                        if match_residual_pattern(file_path, self.patterns):
                            continue
                        if not file_path.is_file():
                            continue
                        try:
                            file_size = file_path.stat().st_size
                            files_to_hash.append((file_path, file_size, filename))
                        except (OSError, PermissionError) as e:
                            self.signals.log.emit(f"Error accessing {file_path}: {str(e)}")
            except Exception as e:
                self.signals.log.emit(f"Error scanning {directory}: {str(e)}")

        if not files_to_hash:
            self.signals.log.emit("No files found to process")
            return {}

        # Second pass: parallel hashing
        try:
            file_hashes, file_info, total_scanned = asyncio.run(
                self._hash_files_parallel(files_to_hash)
            )
        except Exception as e:
            self.signals.log.emit(f"Error during parallel hashing: {str(e)}")
            return {}

        if self._is_cancelled:
            return {}

        # Find all duplicates (files with same hash)
        all_duplicates = {}
        for file_hash, file_paths in file_hashes.items():
            if len(file_paths) > 1:
                all_duplicates[file_hash] = file_paths

        self.signals.log.emit(f"Scanned {total_scanned} files")
        self.signals.log.emit(f"Found {len(all_duplicates)} groups of duplicate files")

        return {
            'file_info': file_info,
            'duplicates': all_duplicates
        }


    async def _hash_files_parallel(self, files_to_hash: List[Tuple]) -> Tuple:
        """Hash files in parallel using asyncio and thread pool."""
        file_hashes = {}
        file_info = {}
        total_scanned = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            tasks = []
            for file_path, file_size, filename in files_to_hash:
                if self._is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                task = compute_hash_async(file_path, executor, self.chunk_size)
                tasks.append((task, file_path, file_size, filename))
            for i, (task, file_path, file_size, filename) in enumerate(tasks):
                if self._is_cancelled:
                    # Cancel remaining tasks
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    _, file_hash = await task
                    total_scanned += 1
                    if total_scanned % 50 == 0:
                        progress_msg = f"Hashed {total_scanned}/{len(tasks)} files..."
                        self.signals.progress.emit(
                            int((total_scanned / len(tasks)) * 100),
                            progress_msg
                        )
                    file_info[str(file_path)] = (file_hash, file_size, filename)
                    if file_hash not in file_hashes:
                        file_hashes[file_hash] = []
                    file_hashes[file_hash].append(str(file_path))
                except (OSError, PermissionError) as e:
                    self.signals.log.emit(f"Error processing {file_path}: {str(e)}")
                except Exception as e:
                    self.signals.log.emit(f"Unexpected error processing {file_path}: {str(e)}")
        return file_hashes, file_info, total_scanned


    def scan_empty_directories(self) -> List[Path]:
        """Scan for empty directories recursively."""
        empty_dirs = []
        self.signals.log.emit("Starting empty directories scan...")
        for directory in self.directories:
            if self._is_cancelled:
                return []
            dir_path = Path(directory)
            if not dir_path.exists():
                self.signals.log.emit(f"Warning: Directory does not exist: {directory}")
                continue
            self.signals.log.emit(f"Scanning for empty directories in: {directory}")
            try:
                # Collect all subdirectories first, then check them bottom-up
                all_dirs = []
                for root, dirs, files in os.walk(dir_path, topdown=False):
                    if self._is_cancelled:
                        return []
                    for dirname in dirs:
                        dir_full_path = Path(root) / dirname
                        all_dirs.append(dir_full_path)
                # Check each directory bottom-up
                for dir_full_path in all_dirs:
                    if self._is_cancelled:
                        return []
                    # Don't include the root directory itself
                    if dir_full_path == dir_path:
                        continue
                    try:
                        # Check if directory is empty (no files, no subdirectories)
                        if dir_full_path.exists() and dir_full_path.is_dir():
                            if not any(dir_full_path.iterdir()):
                                empty_dirs.append(dir_full_path)
                                self.signals.log.emit(f"Found empty: {dir_full_path}")
                    except (OSError, PermissionError) as e:
                        self.signals.log.emit(f"Error checking {dir_full_path}: {str(e)}")
            except Exception as e:
                self.signals.log.emit(f"Error scanning {directory}: {str(e)}")
        self.signals.log.emit(f"Found {len(empty_dirs)} empty directories")
        return empty_dirs


class DeletionWorker(QThread):
    """Worker thread for deleting files."""

    def __init__(self, items: List[str], item_type: str = "file"):
        super().__init__()
        self.items = items
        self.item_type = item_type
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self._is_cancelled = True
        self.signals.log.emit("Deletion cancellation requested...")

    def run(self):
        """Execute the deletion operation."""
        try:
            deleted_count = 0
            failed_items = []
            total = len(self.items)
            for i, item in enumerate(self.items):
                if self._is_cancelled:
                    break
                progress = int((i / total) * 100)
                self.signals.progress.emit(progress, f"Deleting {i+1}/{total}...")
                item_path = Path(item)
                try:
                    if item_path.is_file():
                        item_path.unlink()
                        deleted_count += 1
                        self.signals.log.emit(f"Deleted file: {item}")
                    elif item_path.is_dir():
                        shutil.rmtree(item_path)
                        deleted_count += 1
                        self.signals.log.emit(f"Deleted directory: {item}")
                except Exception as e:
                    failed_items.append((item, str(e)))
                    self.signals.log.emit(f"Failed to delete {item}: {str(e)}")
            result = {
                'deleted_count': deleted_count,
                'failed_items': failed_items,
                'cancelled': self._is_cancelled
            }
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        # Set application icon
        icon_path = Path(__file__).parent / "img" / "dspx_logo_01_128x128.png"
        if icon_path.exists():
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(str(icon_path)))

        self.directories = []
        self.worker = None
        self.deletion_worker = None

        # Load settings and patterns
        self.settings = load_settings()
        self.patterns = load_residual_patterns()

        # # Results storage
        # self.residual_files = []
        # self.duplicate_data = None
        # self.empty_dirs = []

        # Results storage
        self.residual_files = []
        self.duplicate_data = None
        self.empty_dirs = []

        # Setup logging
        self.setup_logging()

        self.init_ui()
        self.setWindowTitle("DSPX - Data Store Pruner and Compressor")
        self.resize(1200, 800)

    def setup_logging(self):
        """Setup logging to file."""
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = logs_dir / f"dspx_{timestamp}.log"
        self.log_handle = open(self.log_file, 'w', encoding='utf-8')
        self.write_log(f"DSPX Session Started - {datetime.now()}")
        self.write_log(f"Log file: {self.log_file}")
        self.write_log(f"Hash algorithm: {HASH_ALGO}")
        self.write_log(f"Platform: {platform.system()} {platform.release()}")
        self.write_log("="*60)

    def write_log(self, message: str):
        """Write to log file."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.log_handle.write(f"[{timestamp}] {message}\n")
            self.log_handle.flush()
        except:
            pass

    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Directory selection
        dir_group = QGroupBox("Directory Selection")
        dir_layout = QVBoxLayout()

        dir_btn_layout = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directory")
        add_dir_btn.clicked.connect(self.add_directory)
        clear_dirs_btn = QPushButton("Clear All")
        clear_dirs_btn.clicked.connect(self.clear_directories)

        # Stop button
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self.stop_operation)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #ff5555; color: white; font-weight: bold; }")

        dir_btn_layout.addWidget(add_dir_btn)
        dir_btn_layout.addWidget(clear_dirs_btn)
        dir_btn_layout.addStretch()
        dir_btn_layout.addWidget(self.stop_btn)

        self.dir_list = QListWidget()
        self.dir_list.setMaximumHeight(100)

        dir_layout.addLayout(dir_btn_layout)
        dir_layout.addWidget(self.dir_list)
        dir_group.setLayout(dir_layout)

        # # Tabs
        # self.tabs = QTabWidget()
        # self.tabs.addTab(self.create_residual_tab(), "1. OS Residual Files")
        # self.tabs.addTab(self.create_same_name_duplicates_tab(), "2. Same-Name Duplicates")
        # self.tabs.addTab(self.create_all_duplicates_tab(), "3. All Duplicates")
        # self.tabs.addTab(self.create_empty_dirs_tab(), "4. Empty Directories")
        # self.tabs.addTab(self.create_patterns_tab(), "📋 Patterns Editor")
        # self.tabs.addTab(self.create_settings_tab(), "⚙ Settings")

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_residual_tab(), "1. OS Residual Files")
        self.tabs.addTab(self.create_duplicates_tab(), "2. Duplicate Files")
        self.tabs.addTab(self.create_empty_dirs_tab(), "3. Empty Directories")
        self.tabs.addTab(self.create_patterns_tab(), "📋 Patterns Editor")
        self.tabs.addTab(self.create_settings_tab(), "⚙ Settings")

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.status_label = QLabel("Ready")

        # Log output
        log_group = QGroupBox("Log Output")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        font = QFont("Courier")
        font.setPointSize(9)
        self.log_text.setFont(font)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)

        # Add everything to main layout
        main_layout.addWidget(dir_group)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(log_group)

        self.log(f"Application started. Log file: {self.log_file}")
        self.log(f"Using {HASH_ALGO.upper()} hashing algorithm")
        self.log(f"Loaded {len(self.patterns)} OS residual patterns")

    def create_residual_tab(self) -> QWidget:
        """Create the OS residual files tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("Scan for OS Residual Files")
        scan_btn.clicked.connect(self.scan_residual_files)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_residual_files)
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        self.residual_list = QListWidget()
        self.residual_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        select_all_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.select_all_items(self.residual_list))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.residual_list))
        select_all_layout.addWidget(select_all_btn)
        select_all_layout.addWidget(deselect_all_btn)
        select_all_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("Found OS residual files (showing matched pattern):"))
        layout.addWidget(self.residual_list)
        layout.addLayout(select_all_layout)

        widget.setLayout(layout)
        return widget


    # def create_same_name_duplicates_tab(self) -> QWidget:
    #     """Create the same-name duplicates tab."""
    #     widget = QWidget()
    #     layout = QVBoxLayout()
    #
    #     btn_layout = QHBoxLayout()
    #     scan_btn = QPushButton("Scan for Duplicates")
    #     scan_btn.clicked.connect(self.scan_duplicates)
    #     delete_btn = QPushButton("Delete Selected")
    #     delete_btn.clicked.connect(self.delete_same_name_duplicates)
    #     btn_layout.addWidget(scan_btn)
    #     btn_layout.addWidget(delete_btn)
    #     btn_layout.addStretch()
    #
    #     self.same_name_dup_list = QListWidget()
    #     self.same_name_dup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    #
    #     select_all_layout = QHBoxLayout()
    #     select_all_btn = QPushButton("Select All Duplicates")
    #     select_all_btn.clicked.connect(lambda: self.select_all_duplicates(self.same_name_dup_list))
    #     deselect_all_btn = QPushButton("Deselect All")
    #     deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.same_name_dup_list))
    #     select_all_layout.addWidget(select_all_btn)
    #     select_all_layout.addWidget(deselect_all_btn)
    #     select_all_layout.addStretch()
    #
    #     layout.addLayout(btn_layout)
    #     layout.addWidget(QLabel("Same-name duplicate files (first kept, rest deletable):"))
    #     layout.addWidget(self.same_name_dup_list)
    #     layout.addLayout(select_all_layout)
    #
    #     widget.setLayout(layout)
    #     return widget
    #
    #
    # def create_all_duplicates_tab(self) -> QWidget:
    #     """Create the all duplicates tab."""
    #     widget = QWidget()
    #     layout = QVBoxLayout()
    #
    #     info_label = QLabel("All duplicate files regardless of name:")
    #     delete_btn = QPushButton("Delete Selected")
    #     delete_btn.clicked.connect(self.delete_all_duplicates)
    #
    #     btn_layout = QHBoxLayout()
    #     btn_layout.addWidget(delete_btn)
    #     btn_layout.addStretch()
    #
    #     self.all_dup_list = QListWidget()
    #     self.all_dup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
    #
    #     select_all_layout = QHBoxLayout()
    #     select_all_btn = QPushButton("Select All Duplicates")
    #     select_all_btn.clicked.connect(lambda: self.select_all_duplicates(self.all_dup_list))
    #     deselect_all_btn = QPushButton("Deselect All")
    #     deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.all_dup_list))
    #     select_all_layout.addWidget(select_all_btn)
    #     select_all_layout.addWidget(deselect_all_btn)
    #     select_all_layout.addStretch()
    #
    #     layout.addWidget(info_label)
    #     layout.addLayout(btn_layout)
    #     layout.addWidget(self.all_dup_list)
    #     layout.addLayout(select_all_layout)
    #
    #     widget.setLayout(layout)
    #     return widget

    def create_duplicates_tab(self) -> QWidget:
        """Create the duplicate files tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("Scan for Duplicate Files")
        scan_btn.clicked.connect(self.scan_duplicates)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_duplicates)
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        self.duplicates_list = QListWidget()
        self.duplicates_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        select_all_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All Duplicates")
        select_all_btn.clicked.connect(lambda: self.select_all_duplicates(self.duplicates_list))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.duplicates_list))
        select_all_layout.addWidget(select_all_btn)
        select_all_layout.addWidget(deselect_all_btn)
        select_all_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("Duplicate files (first occurrence kept, rest deletable):"))
        layout.addWidget(self.duplicates_list)
        layout.addLayout(select_all_layout)

        widget.setLayout(layout)
        return widget


    def create_empty_dirs_tab(self) -> QWidget:
        """Create the empty directories tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("Scan for Empty Directories")
        scan_btn.clicked.connect(self.scan_empty_dirs)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_empty_dirs)
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        self.empty_dirs_list = QListWidget()
        self.empty_dirs_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        select_all_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.select_all_items(self.empty_dirs_list))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.empty_dirs_list))
        select_all_layout.addWidget(select_all_btn)
        select_all_layout.addWidget(deselect_all_btn)
        select_all_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("Empty directories:"))
        layout.addWidget(self.empty_dirs_list)
        layout.addLayout(select_all_layout)

        widget.setLayout(layout)
        return widget


    # def create_patterns_tab(self) -> QWidget:
    #     """Create the patterns editor tab."""
    #     widget = QWidget()
    #     layout = QVBoxLayout()
    #
    #     info_label = QLabel(
    #         "<b>OS Residual File Patterns</b><br>"
    #         "Edit patterns used to identify OS residual files. "
    #         "Only OS and File_Pattern columns are required."
    #     )
    #     info_label.setWordWrap(True)
    #     layout.addWidget(info_label)
    #
    #     # Table for patterns
    #     self.patterns_table = QTableWidget()
    #     self.patterns_table.setColumnCount(5)
    #     self.patterns_table.setHorizontalHeaderLabels([
    #         "OS", "File_Pattern", "Path_Example", "Description", "Safe_To_Delete"
    #     ])
    #     self.patterns_table.horizontalHeader().setStretchLastSection(True)
    #     self.patterns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    #
    #     # Load patterns into table
    #     self.load_patterns_table()
    #
    #     # Buttons
    #     btn_layout = QHBoxLayout()
    #
    #     add_row_btn = QPushButton("Add Row")
    #     add_row_btn.clicked.connect(self.add_pattern_row)
    #
    #     delete_row_btn = QPushButton("Delete Selected Rows")
    #     delete_row_btn.clicked.connect(self.delete_pattern_rows)
    #
    #     save_patterns_btn = QPushButton("Save Patterns")
    #     save_patterns_btn.clicked.connect(self.save_patterns_from_table)
    #
    #     reload_patterns_btn = QPushButton("Reload from File")
    #     reload_patterns_btn.clicked.connect(self.reload_patterns)
    #
    #     btn_layout.addWidget(add_row_btn)
    #     btn_layout.addWidget(delete_row_btn)
    #     btn_layout.addWidget(save_patterns_btn)
    #     btn_layout.addWidget(reload_patterns_btn)
    #     btn_layout.addStretch()
    #
    #     layout.addWidget(self.patterns_table)
    #     layout.addLayout(btn_layout)
    #
    #     widget.setLayout(layout)
    #     return widget

    def create_patterns_tab(self) -> QWidget:
        """Create the patterns editor tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel(
            "<b>OS Residual File Patterns</b><br>"
            "Edit patterns used to identify OS residual files. "
            "Only OS and File_Pattern columns are required. Uncheck 'Enabled' to disable a pattern."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Table for patterns
        self.patterns_table = QTableWidget()
        self.patterns_table.setColumnCount(6)
        self.patterns_table.setHorizontalHeaderLabels([
            "Enabled", "OS", "File_Pattern", "Path_Example", "Description", "Safe_To_Delete"
        ])
        self.patterns_table.horizontalHeader().setStretchLastSection(True)
        self.patterns_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Load patterns into table
        self.load_patterns_table()

        # Buttons
        btn_layout = QHBoxLayout()

        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self.add_pattern_row)

        delete_row_btn = QPushButton("Delete Selected Rows")
        delete_row_btn.clicked.connect(self.delete_pattern_rows)

        save_patterns_btn = QPushButton("Save Patterns")
        save_patterns_btn.clicked.connect(self.save_patterns_from_table)

        reload_patterns_btn = QPushButton("Reload from File")
        reload_patterns_btn.clicked.connect(self.reload_patterns)

        btn_layout.addWidget(add_row_btn)
        btn_layout.addWidget(delete_row_btn)
        btn_layout.addWidget(save_patterns_btn)
        btn_layout.addWidget(reload_patterns_btn)
        btn_layout.addStretch()

        layout.addWidget(self.patterns_table)
        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget


    # def load_patterns_table(self):
    #     """Load patterns into the table widget."""
    #     self.patterns_table.setRowCount(len(self.patterns))
    #     for row, pattern in enumerate(self.patterns):
    #         self.patterns_table.setItem(row, 0, QTableWidgetItem(pattern.get('OS', '')))
    #         self.patterns_table.setItem(row, 1, QTableWidgetItem(pattern.get('File_Pattern', '')))
    #         self.patterns_table.setItem(row, 2, QTableWidgetItem(pattern.get('Path_Example', '')))
    #         self.patterns_table.setItem(row, 3, QTableWidgetItem(pattern.get('Description', '')))
    #         self.patterns_table.setItem(row, 4, QTableWidgetItem(pattern.get('Safe_To_Delete', '')))


    def load_patterns_table(self):
        """Load patterns into the table widget."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QCheckBox

        self.patterns_table.setRowCount(len(self.patterns))
        for row, pattern in enumerate(self.patterns):
            # Enabled checkbox
            enabled_val = pattern.get('Enabled', 'Yes').strip().lower()
            checkbox = QCheckBox()
            checkbox.setChecked(enabled_val in ['yes', 'true', '1'])
            checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
            self.patterns_table.setCellWidget(row, 0, checkbox)

            self.patterns_table.setItem(row, 1, QTableWidgetItem(pattern.get('OS', '')))
            self.patterns_table.setItem(row, 2, QTableWidgetItem(pattern.get('File_Pattern', '')))
            self.patterns_table.setItem(row, 3, QTableWidgetItem(pattern.get('Path_Example', '')))
            self.patterns_table.setItem(row, 4, QTableWidgetItem(pattern.get('Description', '')))
            self.patterns_table.setItem(row, 5, QTableWidgetItem(pattern.get('Safe_To_Delete', '')))

    # def add_pattern_row(self):
    #     """Add a new empty row to the patterns table."""
    #     row = self.patterns_table.rowCount()
    #     self.patterns_table.insertRow(row)
    #     for col in range(5):
    #         self.patterns_table.setItem(row, col, QTableWidgetItem(""))
    #     self.log("Added new pattern row")


    def add_pattern_row(self):
        """Add a new empty row to the patterns table."""
        from PySide6.QtWidgets import QCheckBox

        row = self.patterns_table.rowCount()
        self.patterns_table.insertRow(row)

        # Add enabled checkbox (default checked)
        checkbox = QCheckBox()
        checkbox.setChecked(True)
        checkbox.setStyleSheet("margin-left:50%; margin-right:50%;")
        self.patterns_table.setCellWidget(row, 0, checkbox)

        # Add empty items for other columns
        for col in range(1, 6):
            self.patterns_table.setItem(row, col, QTableWidgetItem(""))
        self.log("Added new pattern row")

    def delete_pattern_rows(self):
        """Delete selected rows from the patterns table."""
        selected_rows = set(item.row() for item in self.patterns_table.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.patterns_table.removeRow(row)
        self.log(f"Deleted {len(selected_rows)} pattern row(s)")


    # def save_patterns_from_table(self):
    #     """Save patterns from table to file."""
    #     patterns = []
    #     invalid_rows = []
    #     for row in range(self.patterns_table.rowCount()):
    #         os_val = self.patterns_table.item(row, 0)
    #         pattern_val = self.patterns_table.item(row, 1)
    #         os_text = os_val.text().strip() if os_val else ""
    #         pattern_text = pattern_val.text().strip() if pattern_val else ""
    #         # Validate required fields
    #         if not os_text or not pattern_text:
    #             invalid_rows.append(row + 1)
    #             continue
    #         pattern = {
    #             'OS': os_text,
    #             'File_Pattern': pattern_text,
    #             'Path_Example': self.patterns_table.item(row, 2).text() if self.patterns_table.item(row, 2) else "",
    #             'Description': self.patterns_table.item(row, 3).text() if self.patterns_table.item(row, 3) else "",
    #             'Safe_To_Delete': self.patterns_table.item(row, 4).text() if self.patterns_table.item(row, 4) else ""
    #         }
    #         patterns.append(pattern)
    #     if invalid_rows:
    #         QMessageBox.warning(
    #             self, "Invalid Patterns",
    #             f"Rows {', '.join(map(str, invalid_rows))} are missing required fields (OS and File_Pattern). "
    #             "These rows will not be saved."
    #         )
    #     save_residual_patterns(patterns)
    #     self.patterns = patterns
    #     self.log(f"Saved {len(patterns)} patterns to {PATTERNS_FILE}")
    #     QMessageBox.information(self, "Patterns Saved", f"Successfully saved {len(patterns)} patterns.")

    def save_patterns_from_table(self):
        """Save patterns from table to file."""
        patterns = []
        invalid_rows = []
        for row in range(self.patterns_table.rowCount()):
            # Get enabled checkbox
            checkbox = self.patterns_table.cellWidget(row, 0)
            enabled = "Yes" if checkbox and checkbox.isChecked() else "No"

            os_val = self.patterns_table.item(row, 1)
            pattern_val = self.patterns_table.item(row, 2)
            os_text = os_val.text().strip() if os_val else ""
            pattern_text = pattern_val.text().strip() if pattern_val else ""

            # Validate required fields
            if not os_text or not pattern_text:
                invalid_rows.append(row + 1)
                continue

            pattern = {
                'OS': os_text,
                'File_Pattern': pattern_text,
                'Path_Example': self.patterns_table.item(row, 3).text() if self.patterns_table.item(row, 3) else "",
                'Description': self.patterns_table.item(row, 4).text() if self.patterns_table.item(row, 4) else "",
                'Safe_To_Delete': self.patterns_table.item(row, 5).text() if self.patterns_table.item(row, 5) else "",
                'Enabled': enabled
            }
            patterns.append(pattern)

        if invalid_rows:
            QMessageBox.warning(
                self, "Invalid Patterns",
                f"Rows {', '.join(map(str, invalid_rows))} are missing required fields (OS and File_Pattern). "
                "These rows will not be saved."
            )

        save_residual_patterns(patterns)
        self.patterns = patterns

        # Count enabled patterns
        enabled_count = sum(1 for p in patterns if p.get('Enabled', 'Yes').lower() in ['yes', 'true', '1'])
        self.log(f"Saved {len(patterns)} patterns ({enabled_count} enabled) to {PATTERNS_FILE}")
        QMessageBox.information(self, "Patterns Saved", f"Successfully saved {len(patterns)} patterns ({enabled_count} enabled).")


    def reload_patterns(self):
        """Reload patterns from file."""
        self.patterns = load_residual_patterns()
        self.load_patterns_table()
        self.log(f"Reloaded {len(self.patterns)} patterns from {PATTERNS_FILE}")


    def create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        # Performance settings group
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout()

        # Max workers
        self.max_workers_spinbox = QSpinBox()
        self.max_workers_spinbox.setMinimum(1)
        self.max_workers_spinbox.setMaximum(128)
        self.max_workers_spinbox.setValue(self.settings['max_workers'])
        self.max_workers_spinbox.setToolTip(
            "Number of parallel workers for file hashing.\n"
            f"Recommended: {multiprocessing.cpu_count() * 2} (CPU cores × 2)"
        )
        workers_label = QLabel(f"Max Workers (CPU cores: {multiprocessing.cpu_count()})")
        perf_layout.addRow(workers_label, self.max_workers_spinbox)

        # Chunk size
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setMinimum(4096)
        self.chunk_size_spinbox.setMaximum(1048576)
        self.chunk_size_spinbox.setSingleStep(4096)
        self.chunk_size_spinbox.setValue(self.settings['chunk_size'])
        self.chunk_size_spinbox.setToolTip("Size of memory chunks when reading files (in bytes)")
        chunk_label = QLabel("Chunk Size (bytes)")
        perf_layout.addRow(chunk_label, self.chunk_size_spinbox)

        # Display chunk size
        self.chunk_size_display = QLabel()
        self.update_chunk_size_display()
        self.chunk_size_spinbox.valueChanged.connect(self.update_chunk_size_display)
        perf_layout.addRow("", self.chunk_size_display)

        perf_group.setLayout(perf_layout)

        # Preset buttons
        preset_group = QGroupBox("Performance Presets")
        preset_layout = QHBoxLayout()

        conservative_btn = QPushButton("Conservative")
        conservative_btn.clicked.connect(lambda: self.apply_preset('conservative'))
        conservative_btn.setToolTip("4 workers, 32 KB - For HDDs/older systems")

        balanced_btn = QPushButton("Balanced (Recommended)")
        balanced_btn.clicked.connect(lambda: self.apply_preset('balanced'))
        balanced_btn.setToolTip("CPU×2 workers, 64 KB - Recommended default")

        aggressive_btn = QPushButton("Aggressive")
        aggressive_btn.clicked.connect(lambda: self.apply_preset('aggressive'))
        aggressive_btn.setToolTip("32 workers, 128 KB - For SSDs with lots of RAM")

        preset_layout.addWidget(conservative_btn)
        preset_layout.addWidget(balanced_btn)
        preset_layout.addWidget(aggressive_btn)
        preset_group.setLayout(preset_layout)

        # Save/Reset buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings_clicked)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self.reset_settings)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()

        # Info label
        info_label = QLabel(
            "<b>Performance Tips:</b><br>"
            "• <b>SSDs:</b> Use 16-32 workers for maximum speed<br>"
            "• <b>HDDs:</b> Use 4-8 workers to avoid disk thrashing<br>"
            "• <b>Many small files:</b> Increase workers, decrease chunk size<br>"
            "• <b>Large files:</b> Increase chunk size (128-256 KB)"
        )
        info_label.setWordWrap(True)
        # info_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border-radius: 5px;")
        info_label.setStyleSheet("padding: 10px; border-radius: 5px;")

        layout.addWidget(perf_group)
        layout.addWidget(preset_group)
        layout.addLayout(btn_layout)
        layout.addWidget(info_label)
        layout.addStretch()

        widget.setLayout(layout)
        return widget


    def update_chunk_size_display(self):
        """Update chunk size display label."""
        chunk_size = self.chunk_size_spinbox.value()
        if chunk_size >= 1024:
            display = f"= {chunk_size / 1024:.1f} KB"
        else:
            display = f"= {chunk_size} bytes"
        self.chunk_size_display.setText(display)


    def apply_preset(self, preset_name: str):
        """Apply a performance preset."""
        if preset_name == 'conservative':
            self.max_workers_spinbox.setValue(4)
            self.chunk_size_spinbox.setValue(32768)
        elif preset_name == 'balanced':
            self.max_workers_spinbox.setValue(min(32, multiprocessing.cpu_count() * 2))
            self.chunk_size_spinbox.setValue(65536)
        elif preset_name == 'aggressive':
            self.max_workers_spinbox.setValue(32)
            self.chunk_size_spinbox.setValue(131072)
        self.log(f"Applied {preset_name} preset")


    def save_settings_clicked(self):
        """Save current settings."""
        self.settings['max_workers'] = self.max_workers_spinbox.value()
        self.settings['chunk_size'] = self.chunk_size_spinbox.value()
        save_settings(self.settings)
        self.log(f"Settings saved: {self.settings['max_workers']} workers, {self.settings['chunk_size']} byte chunks")
        QMessageBox.information(self, "Settings Saved", "Performance settings have been saved.")


    def reset_settings(self):
        """Reset settings to defaults."""
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings = DEFAULT_SETTINGS.copy()
            self.max_workers_spinbox.setValue(self.settings['max_workers'])
            self.chunk_size_spinbox.setValue(self.settings['chunk_size'])
            save_settings(self.settings)
            self.log("Settings reset to defaults")


    def select_all_items(self, list_widget: QListWidget):
        """Select all items in a list widget."""
        for i in range(list_widget.count()):
            list_widget.item(i).setSelected(True)


    def select_all_duplicates(self, list_widget: QListWidget):
        """Select all items labeled [DELETE] but not [KEEP] in a list widget."""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            text = item.text().strip()
            # Skip group headers (lines starting with '---')
            if text.startswith('---'):
                continue
            # Only select items marked with [DELETE]
            if '[DELETE]' in text:
                item.setSelected(True)
            elif '[KEEP]' in text:
                item.setSelected(False)


    def deselect_all_items(self, list_widget: QListWidget):
        """Deselect all items in a list widget."""
        list_widget.clearSelection()


    def add_directory(self):
        """Add a directory to scan."""
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            if directory not in self.directories:
                self.directories.append(directory)
                self.dir_list.addItem(directory)
                self.log(f"Added directory: {directory}")
                self.write_log(f"Added directory: {directory}")


    def clear_directories(self):
        """Clear all directories."""
        self.directories.clear()
        self.dir_list.clear()
        self.log("Cleared all directories")


    def log(self, message: str):
        """Add a message to the log output."""
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        self.write_log(message)


    def update_progress(self, value: int, message: str):
        """Update progress bar and status."""
        if value > 0:
            self.progress_bar.setValue(value)
        self.status_label.setText(message)


    def stop_operation(self):
        """Stop any running operation."""
        stopped_something = False
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.log("Cancelling scan operation...")
            stopped_something = True
        if self.deletion_worker and self.deletion_worker.isRunning():
            self.deletion_worker.cancel()
            self.log("Cancelling deletion operation...")
            stopped_something = True
        if stopped_something:
            self.status_label.setText("Cancellation requested...")
        # Reset UI state
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Operation stopped")


    def scan_residual_files(self):
        """Start scanning for OS residual files."""
        if not self.directories:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to scan.")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Operation in Progress", "An operation is already running.")
            return
        if not self.patterns:
            reply = QMessageBox.question(
                self, "No Patterns",
                "No residual file patterns loaded. Scan will find nothing. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.residual_list.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stop_btn.setEnabled(True)

        self.worker = ScanWorker(
            self.directories,
            "scan_residual",
            patterns=self.patterns
        )
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_residual_scan_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.log.connect(self.log)
        self.worker.start()


    def on_residual_scan_finished(self, result):
        """Handle residual files scan completion."""
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        if result is None:
            self.status_label.setText("Scan cancelled")
            return
        self.residual_files = result
        for file_path, matched_pattern in self.residual_files:
            pattern_str = matched_pattern.get('File_Pattern', 'Unknown')
            os_str = matched_pattern.get('OS', 'Unknown')
            item_text = f"{file_path}  [Pattern: {os_str}/{pattern_str}]"
            self.residual_list.addItem(item_text)
        self.status_label.setText(f"Found {len(self.residual_files)} OS residual files")
        self.log(f"Scan complete: {len(self.residual_files)} OS residual files found")


    def delete_residual_files(self):
        """Delete selected OS residual files."""
        selected_items = self.residual_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files to delete.")
            return
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete {len(selected_items)} selected residual file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        # Extract file paths from items
        items_to_delete = []
        for item in selected_items:
            text = item.text()
            # Extract path (before the [Pattern: ...] part)
            path = text.split('[Pattern:')[0].strip()
            items_to_delete.append(path)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stop_btn.setEnabled(True)

        self.deletion_worker = DeletionWorker(items_to_delete)
        self.deletion_worker.signals.progress.connect(self.update_progress)
        self.deletion_worker.signals.finished.connect(self.on_deletion_finished)
        self.deletion_worker.signals.error.connect(self.on_worker_error)
        self.deletion_worker.signals.log.connect(self.log)
        self.deletion_worker.start()


    # def scan_duplicates(self):
    #     """Start scanning for duplicate files."""
    #     if not self.directories:
    #         QMessageBox.warning(self, "No Directories", "Please add at least one directory to scan.")
    #         return
    #     if self.worker and self.worker.isRunning():
    #         QMessageBox.warning(self, "Operation in Progress", "An operation is already running.")
    #         return
    #
    #     self.same_name_dup_list.clear()
    #     self.all_dup_list.clear()
    #     self.progress_bar.setVisible(True)
    #     self.progress_bar.setValue(0)
    #     self.stop_btn.setEnabled(True)
    #
    #     self.worker = ScanWorker(
    #         self.directories,
    #         "scan_duplicates",
    #         max_workers=self.settings['max_workers'],
    #         chunk_size=self.settings['chunk_size'],
    #         patterns=self.patterns
    #     )
    #     self.worker.signals.progress.connect(self.update_progress)
    #     self.worker.signals.finished.connect(self.on_duplicate_scan_finished)
    #     self.worker.signals.error.connect(self.on_worker_error)
    #     self.worker.signals.log.connect(self.log)
    #     self.worker.start()

    def scan_duplicates(self):
        """Start scanning for duplicate files."""
        if not self.directories:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to scan.")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Operation in Progress", "An operation is already running.")
            return

        self.duplicates_list.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stop_btn.setEnabled(True)

        self.worker = ScanWorker(
            self.directories,
            "scan_duplicates",
            max_workers=self.settings['max_workers'],
            chunk_size=self.settings['chunk_size'],
            patterns=self.patterns
        )
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_duplicate_scan_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.log.connect(self.log)
        self.worker.start()


    # def on_duplicate_scan_finished(self, result):
    #     """Handle duplicate scan completion."""
    #     self.progress_bar.setVisible(False)
    #     self.stop_btn.setEnabled(False)
    #     if result is None or not result:
    #         self.status_label.setText("Scan cancelled or no duplicates found")
    #         return
    #     self.duplicate_data = result
    #
    #     # Populate same-name duplicates
    #     same_name_dups = result.get('same_name_duplicates', {})
    #     for file_hash, file_paths in same_name_dups.items():
    #         if len(file_paths) > 1:
    #             self.same_name_dup_list.addItem(f"--- Group (hash: {file_hash[:16]}...) ---")
    #             for i, fpath in enumerate(file_paths):
    #                 prefix = "[KEEP]" if i == 0 else "[DELETE]"
    #                 self.same_name_dup_list.addItem(f"  {prefix} {fpath}")
    #
    #     # Populate all duplicates
    #     all_dups = result.get('all_duplicates', {})
    #     for file_hash, file_paths in all_dups.items():
    #         if len(file_paths) > 1:
    #             self.all_dup_list.addItem(f"--- Group (hash: {file_hash[:16]}...) ---")
    #             for i, fpath in enumerate(file_paths):
    #                 prefix = "[KEEP]" if i == 0 else "[DELETE]"
    #                 self.all_dup_list.addItem(f"  {prefix} {fpath}")
    #     self.status_label.setText(
    #         f"Found {len(same_name_dups)} same-name duplicate groups, "
    #         f"{len(all_dups)} total duplicate groups"
    #     )
    #     self.log("Duplicate scan complete")

    def on_duplicate_scan_finished(self, result):
        """Handle duplicate scan completion."""
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        if result is None or not result:
            self.status_label.setText("Scan cancelled or no duplicates found")
            return

        self.duplicate_data = result
        duplicates = result.get('duplicates', {})

        # Populate duplicate files list
        for file_hash, file_paths in duplicates.items():
            if len(file_paths) > 1:
                self.duplicates_list.addItem(f"--- Group (hash: {file_hash[:16]}...) ---")
                for i, fpath in enumerate(file_paths):
                    prefix = "[KEEP]" if i == 0 else "[DELETE]"
                    self.duplicates_list.addItem(f"  {prefix} {fpath}")

        total_duplicates = sum(len(paths) - 1 for paths in duplicates.values())
        self.status_label.setText(
            f"Found {len(duplicates)} duplicate groups ({total_duplicates} duplicate files)"
        )


    # def delete_same_name_duplicates(self):
    #     """Delete selected same-name duplicates."""
    #     selected_items = self.same_name_dup_list.selectedItems()
    #     if not selected_items:
    #         QMessageBox.warning(self, "No Selection", "Please select files to delete.")
    #         return
    #     # Extract file paths (skip group headers)
    #     items_to_delete = []
    #     for item in selected_items:
    #         text = item.text().strip()
    #         if not text.startswith('---'):
    #             # Remove prefix
    #             if text.startswith('['):
    #                 text = text.split('] ', 1)[1] if '] ' in text else text
    #             items_to_delete.append(text.strip())
    #     if not items_to_delete:
    #         QMessageBox.warning(self, "No Files", "No valid files selected.")
    #         return
    #     reply = QMessageBox.question(
    #         self, "Confirm Deletion",
    #         f"Delete {len(items_to_delete)} selected duplicate file(s)?",
    #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    #     )
    #     if reply != QMessageBox.StandardButton.Yes:
    #         return
    #
    #     self.progress_bar.setVisible(True)
    #     self.progress_bar.setValue(0)
    #     self.stop_btn.setEnabled(True)
    #
    #     self.deletion_worker = DeletionWorker(items_to_delete)
    #     self.deletion_worker.signals.progress.connect(self.update_progress)
    #     self.deletion_worker.signals.finished.connect(self.on_deletion_finished)
    #     self.deletion_worker.signals.error.connect(self.on_worker_error)
    #     self.deletion_worker.signals.log.connect(self.log)
    #     self.deletion_worker.start()
    #
    #
    # def delete_all_duplicates(self):
    #     """Delete selected all duplicates."""
    #     selected_items = self.all_dup_list.selectedItems()
    #     if not selected_items:
    #         QMessageBox.warning(self, "No Selection", "Please select files to delete.")
    #         return
    #     items_to_delete = []
    #     for item in selected_items:
    #         text = item.text().strip()
    #         if not text.startswith('---'):
    #             items_to_delete.append(text.strip())
    #     if not items_to_delete:
    #         QMessageBox.warning(self, "No Files", "No valid files selected.")
    #         return
    #     reply = QMessageBox.question(
    #         self, "Confirm Deletion",
    #         f"Delete {len(items_to_delete)} selected duplicate file(s)?",
    #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    #     )
    #     if reply != QMessageBox.StandardButton.Yes:
    #         return
    #
    #     self.progress_bar.setVisible(True)
    #     self.progress_bar.setValue(0)
    #     self.stop_btn.setEnabled(True)
    #
    #     self.deletion_worker = DeletionWorker(items_to_delete)
    #     self.deletion_worker.signals.progress.connect(self.update_progress)
    #     self.deletion_worker.signals.finished.connect(self.on_deletion_finished)
    #     self.deletion_worker.signals.error.connect(self.on_worker_error)
    #     self.deletion_worker.signals.log.connect(self.log)
    #     self.deletion_worker.start()


    def delete_duplicates(self):
        """Delete selected duplicate files."""
        selected_items = self.duplicates_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files to delete.")
            return

        # Extract file paths (skip group headers)
        items_to_delete = []
        for item in selected_items:
            text = item.text().strip()
            if not text.startswith('---'):
                # Remove prefix
                if text.startswith('['):
                    text = text.split('] ', 1)[1] if '] ' in text else text
                items_to_delete.append(text.strip())

        if not items_to_delete:
            QMessageBox.warning(self, "No Files", "No valid files selected.")
            return

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete {len(items_to_delete)} selected duplicate file(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stop_btn.setEnabled(True)

        self.deletion_worker = DeletionWorker(items_to_delete)
        self.deletion_worker.signals.progress.connect(self.update_progress)
        self.deletion_worker.signals.finished.connect(self.on_deletion_finished)
        self.deletion_worker.signals.error.connect(self.on_worker_error)
        self.deletion_worker.signals.log.connect(self.log)

    def scan_empty_dirs(self):
        """Start scanning for empty directories."""
        if not self.directories:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to scan.")
            return
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Operation in Progress", "An operation is already running.")
            return

        self.empty_dirs_list.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stop_btn.setEnabled(True)

        self.worker = ScanWorker(self.directories, "scan_empty_dirs")
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_empty_dirs_scan_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.log.connect(self.log)
        self.worker.start()


    def on_empty_dirs_scan_finished(self, result):
        """Handle empty directories scan completion."""
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        if result is None:
            self.status_label.setText("Scan cancelled")
            return
        self.empty_dirs = result
        for dir_path in self.empty_dirs:
            self.empty_dirs_list.addItem(str(dir_path))

        self.status_label.setText(f"Found {len(self.empty_dirs)} empty directories")
        self.log(f"Scan complete: {len(self.empty_dirs)} empty directories found")


    def delete_empty_dirs(self):
        """Delete selected empty directories with iterative cleanup."""
        selected_items = self.empty_dirs_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select directories to delete.")
            return
        initial_items = [item.text() for item in selected_items]
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete {len(initial_items)} selected empty director(ies)?\n\n"
            "Note: This will repeatedly scan and delete empty directories\n"
            "until all nested empties are removed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        total_deleted = 0
        iteration = 0
        max_iterations = 100  # Safety limit to prevent infinite loops

        # Convert to Path objects and get all root directories to check
        root_dirs = set()
        for item in initial_items:
            item_path = Path(item)
            # Find which scan directory this belongs to
            for scan_dir in self.directories:
                scan_path = Path(scan_dir)
                try:
                    item_path.relative_to(scan_path)
                    root_dirs.add(scan_path)
                    break
                except ValueError:
                    continue

        self.log(f"Starting iterative empty directory deletion in {len(root_dirs)} root directories...")

        # Iteratively scan and delete until no more empty directories found
        while iteration < max_iterations:
            iteration += 1
            self.log(f"Iteration {iteration}: Scanning for empty directories...")

            # Collect all empty directories in the root directories
            empty_dirs = []
            for root_dir in root_dirs:
                for root, dirs, files in os.walk(root_dir, topdown=False):
                    root_path = Path(root)

                    # Don't include root scan directories
                    if root_path in root_dirs:
                        continue
                    try:
                        # Check if directory is empty
                        if root_path.exists() and root_path.is_dir():
                            if not any(root_path.iterdir()):
                                empty_dirs.append(root_path)
                    except (OSError, PermissionError) as e:
                        self.log(f"Error checking {root_path}: {str(e)}")

            if not empty_dirs:
                self.log(f"No more empty directories found after iteration {iteration}")
                break

            self.log(f"Found {len(empty_dirs)} empty directories in iteration {iteration}")

            # Delete them all
            deleted_this_round = 0
            failed_items = []

            # Sort by depth (deepest first) to minimize issues
            empty_dirs.sort(key=lambda p: len(p.parts), reverse=True)

            for i, dir_path in enumerate(empty_dirs):
                try:
                    if dir_path.exists() and dir_path.is_dir():
                        # Double-check it's still empty
                        if not any(dir_path.iterdir()):
                            import shutil
                            shutil.rmtree(dir_path)
                            deleted_this_round += 1
                            total_deleted += 1
                            self.log(f"Deleted: {dir_path}")
                except Exception as e:
                    failed_items.append((str(dir_path), str(e)))
                    self.log(f"Failed to delete {dir_path}: {str(e)}")

                # Update progress within iteration
                progress = int((iteration / max(10, max_iterations)) * 100)
                self.progress_bar.setValue(min(progress, 95))

            self.log(f"Iteration {iteration}: Deleted {deleted_this_round} directories")

            # If we deleted nothing, we're done
            if deleted_this_round == 0:
                self.log("No directories could be deleted this iteration, stopping.")
                break

        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)

        if iteration >= max_iterations:
            self.log(f"WARNING: Reached maximum iterations ({max_iterations})")

        self.log(f"Deletion complete: {total_deleted} total directories deleted across {iteration} iterations")

        self.status_label.setText(f"Deleted {total_deleted} directories in {iteration} iterations")

        QMessageBox.information(
            self, "Deletion Complete",
            f"Successfully deleted {total_deleted} director(ies)\n"
            f"across {iteration} iteration(s)."
        )

        # Refresh the list
        self.log("Refreshing empty directories list...")
        self.scan_empty_dirs()


    def on_deletion_finished(self, result):
        """Handle deletion completion."""
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        if result.get('cancelled'):
            self.log("Deletion cancelled by user")
            self.status_label.setText("Deletion cancelled")
            return
        deleted_count = result.get('deleted_count', 0)
        failed_items = result.get('failed_items', [])
        self.log(f"Deletion complete: {deleted_count} items deleted")
        if failed_items:
            self.log(f"Failed to delete {len(failed_items)} item(s)")
            for item, error in failed_items:
                self.log(f"  Failed: {item} - {error}")
        self.status_label.setText(f"Deleted {deleted_count} items")
        QMessageBox.information(
            self, "Deletion Complete",
            f"Successfully deleted {deleted_count} item(s).\n"
            f"Failed: {len(failed_items)} item(s)."
        )


    def on_worker_error(self, error_msg: str):
        """Handle worker errors."""
        self.progress_bar.setVisible(False)
        self.stop_btn.setEnabled(False)
        self.log(f"ERROR: {error_msg}")
        self.status_label.setText("Error occurred")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_msg}")


    def closeEvent(self, event):
        """Handle application close."""
        # Stop any running operations
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        if self.deletion_worker and self.deletion_worker.isRunning():
            self.deletion_worker.cancel()
            self.deletion_worker.wait()
        # Close log file
        self.write_log("="*60)
        self.write_log(f"DSPX Session Ended - {datetime.now()}")
        self.log_handle.close()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)

    # Set application-wide icon for taskbar
    icon_path = Path(__file__).parent / "img" / "dspx_logo_01_128x128.png"
    if icon_path.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()