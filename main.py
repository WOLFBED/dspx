#!/usr/bin/env python3
"""
DSPX - Data Store Pruner and Compressor
Clean up directories by removing OS residual files, finding and removing duplicate files,
and deleting empty directories.

VERSION 1.1
    Add ability to specify and save OS residual file matching patterns.  Nice.

VERSION 1.0
    It works.

"""

import sys
import os
import hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Set, Tuple
import logging

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFileDialog, QListWidget,
    QGroupBox, QProgressBar, QMessageBox, QTabWidget, QListWidgetItem,
    QCheckBox, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor


# Try to use blake3 if available, otherwise fall back to sha256
try:
    import blake3
    HASH_ALGO = "blake3"
    def compute_hash(filepath: Path) -> str:
        hasher = blake3.blake3()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
except ImportError:
    HASH_ALGO = "sha256"
    def compute_hash(filepath: Path) -> str:
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()


# OS residual files patterns
OS_RESIDUAL_PATTERNS = {
    # macOS
    '.DS_Store',
    '._*',
    '.Spotlight-V100',
    '.Trashes',
    '.fseventsd',
    '.TemporaryItems',
    '.VolumeIcon.icns',
    # Windows
    'Thumbs.db',
    'thumbs.db',
    'Desktop.ini',
    'desktop.ini',
    '$RECYCLE.BIN',
    'System Volume Information',
    # Linux
    '.directory',
    '.Trash-*',
    # General
    '.AppleDouble',
    '.LSOverride',
    '__MACOSX',
}


def is_os_residual_file(filepath: Path) -> bool:
    """Check if a file matches OS residual patterns."""
    name = filepath.name

    # Check exact matches
    if name in OS_RESIDUAL_PATTERNS:
        return True

    # Check wildcard patterns
    if name.startswith('._'):
        return True

    if name.startswith('.Trash-'):
        return True

    return False


class WorkerSignals(QObject):
    """Signals for worker threads."""
    progress = Signal(int, str)
    finished = Signal(object)
    error = Signal(str)
    log = Signal(str)


class ScanWorker(QThread):
    """Worker thread for scanning directories."""

    def __init__(self, directories: List[str], operation: str):
        super().__init__()
        self.directories = directories
        self.operation = operation
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self._is_cancelled = True

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
        except Exception as e:
            self.signals.error.emit(str(e))

    def scan_residual_files(self) -> List[Path]:
        """Scan for OS residual files."""
        residual_files = []
        total_scanned = 0

        self.signals.log.emit("Starting OS residual files scan...")

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
                        if is_os_residual_file(dir_full_path):
                            residual_files.append(dir_full_path)

                    # Check files
                    for filename in files:
                        total_scanned += 1
                        if total_scanned % 100 == 0:
                            self.signals.progress.emit(0, f"Scanned {total_scanned} items...")

                        file_path = root_path / filename
                        if is_os_residual_file(file_path):
                            residual_files.append(file_path)

            except Exception as e:
                self.signals.log.emit(f"Error scanning {directory}: {str(e)}")

        self.signals.log.emit(f"Found {len(residual_files)} OS residual files/directories")
        return residual_files

    def scan_for_duplicates(self) -> Dict[str, any]:
        """Scan for duplicate files using hash signatures."""
        file_hashes = {}  # hash -> list of file paths
        file_info = {}    # file path -> (hash, size, name)
        total_scanned = 0

        self.signals.log.emit(f"Starting duplicate scan using {HASH_ALGO} hashing...")

        # First pass: collect all files and compute hashes
        for directory in self.directories:
            if self._is_cancelled:
                return {}

            dir_path = Path(directory)
            if not dir_path.exists():
                self.signals.log.emit(f"Warning: Directory does not exist: {directory}")
                continue

            self.signals.log.emit(f"Computing hashes for files in: {directory}")

            try:
                for root, _, files in os.walk(dir_path):
                    if self._is_cancelled:
                        return {}

                    root_path = Path(root)

                    for filename in files:
                        file_path = root_path / filename

                        # Skip OS residual files
                        if is_os_residual_file(file_path):
                            continue

                        if not file_path.is_file():
                            continue

                        try:
                            total_scanned += 1
                            if total_scanned % 50 == 0:
                                self.signals.progress.emit(0, f"Hashed {total_scanned} files...")

                            file_size = file_path.stat().st_size
                            file_hash = compute_hash(file_path)

                            file_info[str(file_path)] = (file_hash, file_size, filename)

                            if file_hash not in file_hashes:
                                file_hashes[file_hash] = []
                            file_hashes[file_hash].append(str(file_path))

                        except (OSError, PermissionError) as e:
                            self.signals.log.emit(f"Error processing {file_path}: {str(e)}")

            except Exception as e:
                self.signals.log.emit(f"Error scanning {directory}: {str(e)}")

        # Find duplicates with same names
        same_name_duplicates = defaultdict(list)

        # Find all duplicates (same hash, regardless of name)
        all_duplicates = {}

        for file_hash, file_paths in file_hashes.items():
            if len(file_paths) > 1:
                # Group by name
                by_name = defaultdict(list)
                for fpath in file_paths:
                    fname = Path(fpath).name
                    by_name[fname].append(fpath)

                # Same name duplicates
                for fname, paths in by_name.items():
                    if len(paths) > 1:
                        same_name_duplicates[file_hash].extend(paths)

                # All duplicates
                all_duplicates[file_hash] = file_paths

        self.signals.log.emit(f"Scanned {total_scanned} files")
        self.signals.log.emit(f"Found {len(same_name_duplicates)} groups of same-name duplicates")
        self.signals.log.emit(f"Found {len(all_duplicates)} groups of all duplicates")

        return {
            'file_info': file_info,
            'same_name_duplicates': same_name_duplicates,
            'all_duplicates': all_duplicates
        }

    def scan_empty_directories(self) -> List[Path]:
        """Scan for empty directories."""
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
                # Walk bottom-up to catch nested empty directories
                for root, dirs, files in os.walk(dir_path, topdown=False):
                    if self._is_cancelled:
                        return []

                    root_path = Path(root)

                    # Don't include the root directory itself
                    if root_path == dir_path:
                        continue

                    try:
                        # Check if directory is empty
                        if not any(root_path.iterdir()):
                            empty_dirs.append(root_path)
                    except (OSError, PermissionError) as e:
                        self.signals.log.emit(f"Error checking {root_path}: {str(e)}")

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
                        # For directories, try to remove recursively
                        import shutil
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
        self.directories = []
        self.worker = None
        self.deletion_worker = None

        # Results storage
        self.residual_files = []
        self.duplicate_data = None
        self.empty_dirs = []

        # Setup logging
        self.setup_logging()

        self.init_ui()
        self.setWindowTitle("DSPX - Data Store Pruner and Compressor")
        self.resize(1000, 700)

    def setup_logging(self):
        """Setup logging to file."""
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_dir / f"dspx_{timestamp}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
            ]
        )

        self.logger = logging.getLogger(__name__)
        self.log_file = log_file
        self.logger.info("="*60)
        self.logger.info("DSPX Session Started")
        self.logger.info(f"Log file: {log_file}")
        self.logger.info(f"Hash algorithm: {HASH_ALGO}")
        self.logger.info("="*60)

    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Directory selection section
        dir_group = QGroupBox("Directory Selection")
        dir_layout = QVBoxLayout()

        dir_btn_layout = QHBoxLayout()
        add_dir_btn = QPushButton("Add Directory")
        add_dir_btn.clicked.connect(self.add_directory)
        clear_dirs_btn = QPushButton("Clear All")
        clear_dirs_btn.clicked.connect(self.clear_directories)
        dir_btn_layout.addWidget(add_dir_btn)
        dir_btn_layout.addWidget(clear_dirs_btn)
        dir_btn_layout.addStretch()

        self.dir_list = QListWidget()
        self.dir_list.setMaximumHeight(100)

        dir_layout.addLayout(dir_btn_layout)
        dir_layout.addWidget(self.dir_list)
        dir_group.setLayout(dir_layout)

        # Operations section with tabs
        self.tabs = QTabWidget()

        # Tab 1: OS Residual Files
        self.residual_tab = self.create_residual_tab()
        self.tabs.addTab(self.residual_tab, "1. OS Residual Files")

        # Tab 2: Same-name Duplicates
        self.same_name_dup_tab = self.create_same_name_duplicates_tab()
        self.tabs.addTab(self.same_name_dup_tab, "2. Same-Name Duplicates")

        # Tab 3: All Duplicates
        self.all_dup_tab = self.create_all_duplicates_tab()
        self.tabs.addTab(self.all_dup_tab, "3. All Duplicates")

        # Tab 4: Empty Directories
        self.empty_dirs_tab = self.create_empty_dirs_tab()
        self.tabs.addTab(self.empty_dirs_tab, "4. Empty Directories")

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
        layout.addWidget(QLabel("Found OS residual files:"))
        layout.addWidget(self.residual_list)
        layout.addLayout(select_all_layout)

        widget.setLayout(layout)
        return widget

    def create_same_name_duplicates_tab(self) -> QWidget:
        """Create the same-name duplicates tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        scan_btn = QPushButton("Scan for Duplicates")
        scan_btn.clicked.connect(self.scan_duplicates)
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_same_name_duplicates)
        btn_layout.addWidget(scan_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        self.same_name_dup_list = QListWidget()
        self.same_name_dup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        select_all_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.select_all_items(self.same_name_dup_list))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.same_name_dup_list))
        select_all_layout.addWidget(select_all_btn)
        select_all_layout.addWidget(deselect_all_btn)
        select_all_layout.addStretch()

        layout.addLayout(btn_layout)
        layout.addWidget(QLabel("Same-name duplicate files (keep first, delete rest):"))
        layout.addWidget(self.same_name_dup_list)
        layout.addLayout(select_all_layout)

        widget.setLayout(layout)
        return widget

    def create_all_duplicates_tab(self) -> QWidget:
        """Create the all duplicates tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel("All duplicate files regardless of name:")
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_all_duplicates)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()

        self.all_dup_list = QListWidget()
        self.all_dup_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        select_all_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda: self.select_all_items(self.all_dup_list))
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(lambda: self.deselect_all_items(self.all_dup_list))
        select_all_layout.addWidget(select_all_btn)
        select_all_layout.addWidget(deselect_all_btn)
        select_all_layout.addStretch()

        layout.addWidget(info_label)
        layout.addLayout(btn_layout)
        layout.addWidget(self.all_dup_list)
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

    def select_all_items(self, list_widget: QListWidget):
        """Select all items in a list widget."""
        for i in range(list_widget.count()):
            list_widget.item(i).setSelected(True)

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
                self.logger.info(f"Added directory: {directory}")

    def clear_directories(self):
        """Clear all directories."""
        self.directories.clear()
        self.dir_list.clear()
        self.log("Cleared all directories")

    def log(self, message: str):
        """Add a message to the log output."""
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        self.logger.info(message)

    def update_progress(self, value: int, message: str):
        """Update progress bar and status."""
        if value > 0:
            self.progress_bar.setValue(value)
        self.status_label.setText(message)

    def scan_residual_files(self):
        """Start scanning for OS residual files."""
        if not self.directories:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to scan.")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Operation in Progress", "An operation is already running.")
            return

        self.residual_list.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = ScanWorker(self.directories, "scan_residual")
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_residual_scan_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.log.connect(self.log)
        self.worker.start()

    def on_residual_scan_finished(self, result):
        """Handle residual files scan completion."""
        self.progress_bar.setVisible(False)
        self.residual_files = result

        for file_path in self.residual_files:
            self.residual_list.addItem(str(file_path))

        self.status_label.setText(f"Found {len(self.residual_files)} OS residual files")
        self.log(f"Scan complete: {len(self.residual_files)} OS residual files found")

    def delete_residual_files(self):
        """Delete selected OS residual files."""
        selected_items = self.residual_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files to delete.")
            return

        selected_paths = [item.text() for item in selected_items]

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_paths)} items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_deletion(selected_paths, "OS residual files")

    def scan_duplicates(self):
        """Start scanning for duplicate files."""
        if not self.directories:
            QMessageBox.warning(self, "No Directories", "Please add at least one directory to scan.")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Operation in Progress", "An operation is already running.")
            return

        self.same_name_dup_list.clear()
        self.all_dup_list.clear()
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = ScanWorker(self.directories, "scan_duplicates")
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_duplicates_scan_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.log.connect(self.log)
        self.worker.start()

    def on_duplicates_scan_finished(self, result):
        """Handle duplicates scan completion."""
        self.progress_bar.setVisible(False)
        self.duplicate_data = result

        if not result:
            self.status_label.setText("No duplicates found")
            return

        # Populate same-name duplicates
        same_name_dups = result['same_name_duplicates']
        for file_hash, file_paths in same_name_dups.items():
            # Sort by path to keep first one
            sorted_paths = sorted(file_paths)

            # Add group header
            item = QListWidgetItem(f"--- Group ({len(sorted_paths)} files with same name and hash) ---")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.same_name_dup_list.addItem(item)

            # Add first file (to keep) - not selectable
            keep_item = QListWidgetItem(f"✓ KEEP: {sorted_paths[0]}")
            keep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.same_name_dup_list.addItem(keep_item)

            # Add rest (to potentially delete)
            for fpath in sorted_paths[1:]:
                dup_item = QListWidgetItem(f"✗ DELETE: {fpath}")
                dup_item.setData(Qt.ItemDataRole.UserRole, fpath)
                self.same_name_dup_list.addItem(dup_item)

        # Populate all duplicates
        all_dups = result['all_duplicates']
        for file_hash, file_paths in all_dups.items():
            if len(file_paths) > 1:
                sorted_paths = sorted(file_paths)

                # Add group header
                item = QListWidgetItem(f"--- Group ({len(sorted_paths)} files with same hash) ---")
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.all_dup_list.addItem(item)

                # Add first file (to keep) - not selectable
                keep_item = QListWidgetItem(f"✓ KEEP: {sorted_paths[0]}")
                keep_item.setFlags(Qt.ItemFlag.NoItemFlags)
                self.all_dup_list.addItem(keep_item)

                # Add rest (to potentially delete)
                for fpath in sorted_paths[1:]:
                    dup_item = QListWidgetItem(f"✗ DELETE: {fpath}")
                    dup_item.setData(Qt.ItemDataRole.UserRole, fpath)
                    self.all_dup_list.addItem(dup_item)

        same_name_count = len(same_name_dups)
        all_dup_count = len(all_dups)
        self.status_label.setText(
            f"Found {same_name_count} same-name duplicate groups, "
            f"{all_dup_count} total duplicate groups"
        )
        self.log(f"Duplicate scan complete")

    def delete_same_name_duplicates(self):
        """Delete selected same-name duplicates."""
        selected_items = [
            item for item in self.same_name_dup_list.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole) is not None
        ]

        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files to delete.")
            return

        selected_paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_paths)} duplicate files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_deletion(selected_paths, "same-name duplicates")

    def delete_all_duplicates(self):
        """Delete selected duplicates from all duplicates list."""
        selected_items = [
            item for item in self.all_dup_list.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole) is not None
        ]

        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select files to delete.")
            return

        selected_paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_paths)} duplicate files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_deletion(selected_paths, "all duplicates")

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

        self.worker = ScanWorker(self.directories, "scan_empty_dirs")
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.on_empty_dirs_scan_finished)
        self.worker.signals.error.connect(self.on_worker_error)
        self.worker.signals.log.connect(self.log)
        self.worker.start()

    def on_empty_dirs_scan_finished(self, result):
        """Handle empty directories scan completion."""
        self.progress_bar.setVisible(False)
        self.empty_dirs = result

        for dir_path in self.empty_dirs:
            self.empty_dirs_list.addItem(str(dir_path))

        self.status_label.setText(f"Found {len(self.empty_dirs)} empty directories")
        self.log(f"Scan complete: {len(self.empty_dirs)} empty directories found")

    def delete_empty_dirs(self):
        """Delete selected empty directories."""
        selected_items = self.empty_dirs_list.selectedItems()

        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select directories to delete.")
            return

        selected_paths = [item.text() for item in selected_items]

        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete {len(selected_paths)} empty directories?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_deletion(selected_paths, "empty directories")

    def start_deletion(self, paths: List[str], item_type: str):
        """Start deletion worker thread."""
        if self.deletion_worker and self.deletion_worker.isRunning():
            QMessageBox.warning(self, "Operation in Progress", "A deletion is already running.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.deletion_worker = DeletionWorker(paths, item_type)
        self.deletion_worker.signals.progress.connect(self.update_progress)
        self.deletion_worker.signals.finished.connect(
            lambda result: self.on_deletion_finished(result, item_type)
        )
        self.deletion_worker.signals.error.connect(self.on_worker_error)
        self.deletion_worker.signals.log.connect(self.log)
        self.deletion_worker.start()

    def on_deletion_finished(self, result, item_type: str):
        """Handle deletion completion."""
        self.progress_bar.setVisible(False)

        deleted_count = result['deleted_count']
        failed_count = len(result['failed_items'])

        self.log(f"Deletion complete: {deleted_count} {item_type} deleted, {failed_count} failed")

        if failed_count > 0:
            self.log("Failed items:")
            for item, error in result['failed_items']:
                self.log(f"  - {item}: {error}")

        self.status_label.setText(
            f"Deleted {deleted_count} {item_type}, {failed_count} failed"
        )

        # Refresh the appropriate list
        if "residual" in item_type:
            self.scan_residual_files()
        elif "empty" in item_type:
            self.scan_empty_dirs()
        elif "duplicate" in item_type:
            self.scan_duplicates()

    def on_worker_error(self, error_msg: str):
        """Handle worker thread errors."""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error occurred")
        self.log(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Error", f"An error occurred: {error_msg}")

    def closeEvent(self, event):
        """Handle window close event."""
        self.logger.info("="*60)
        self.logger.info("DSPX Session Ended")
        self.logger.info("="*60)
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()