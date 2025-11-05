#!/usr/bin/env python3
"""
DSPX - Data Store Pruner and Compressor
Clean up directories by removing OS residual files, finding and removing duplicate files,
and deleting empty directories.

VERSION 1.2
    Add ability to specify and save OS residual file matching patterns.  Nice.

VERSION 1.1
    Add stop button to cleanly stop all processes.

VERSION 1.0
    It works.

"""

import sys
import os
import hashlib
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Set, Tuple
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QFileDialog, QListWidget,
    QGroupBox, QProgressBar, QMessageBox, QTabWidget, QListWidgetItem,
    QCheckBox, QScrollArea, QSpinBox, QFormLayout
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QFont, QTextCursor


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
    
    async def compute_hash_async(filepath: Path, executor, chunk_size: int = 65536) -> tuple:
        """Async wrapper for hash computation."""
        loop = asyncio.get_event_loop()
        file_hash = await loop.run_in_executor(
            executor, compute_hash_sync, filepath, chunk_size
        )
        return filepath, file_hash
        
except ImportError:
    HASH_ALGO = "sha256"
    
    def compute_hash_sync(filepath: Path, chunk_size: int = 65536) -> str:
        """Synchronous hash computation for thread pool."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    async def compute_hash_async(filepath: Path, executor, chunk_size: int = 65536) -> tuple:
        """Async wrapper for hash computation."""
        loop = asyncio.get_event_loop()
        file_hash = await loop.run_in_executor(
            executor, compute_hash_sync, filepath, chunk_size
        )
        return filepath, file_hash


# OS residual files patterns
OS_RESIDUAL_PATTERNS = {
    # macOS
    # ... existing patterns ...
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


# Default settings
DEFAULT_SETTINGS = {
    'max_workers': min(32, multiprocessing.cpu_count() * 2),
    'chunk_size': 65536,  # 64 KB
}

# Settings file path
SETTINGS_FILE = Path('dspx_settings.json')


def load_settings() -> Dict:
    """Load settings from file or return defaults."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                # Merge with defaults to handle new settings
                return {**DEFAULT_SETTINGS, **settings}
        except Exception as e:
            logging.warning(f"Failed to load settings: {e}")
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict):
    """Save settings to file."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save settings: {e}")


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

    def __init__(self, directories: List[str], operation: str, max_workers: int = None, chunk_size: int = 65536):
        super().__init__()
        self.directories = directories
        self.operation = operation
        self.signals = WorkerSignals()
        self._is_cancelled = False
        # Use provided max_workers or default
        self.max_workers = max_workers or DEFAULT_SETTINGS['max_workers']
        self.chunk_size = chunk_size

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
        """Scan for duplicate files using hash signatures with parallel processing."""
        file_hashes = {}  # hash -> list of file paths
        file_info = {}    # file path -> (hash, size, name)
        total_scanned = 0
        files_to_hash = []

        self.signals.log.emit(f"Starting duplicate scan using {HASH_ALGO} hashing...")
        self.signals.log.emit(f"Using {self.max_workers} parallel workers")
        self.signals.log.emit(f"Chunk size: {self.chunk_size} bytes ({self.chunk_size // 1024} KB)")

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
                        if is_os_residual_file(file_path):
                            continue

                        if not file_path.is_file():
                            continue

                        try:
                            # Just collect file info, don't hash yet
                            file_size = file_path.stat().st_size
                            files_to_hash.append((file_path, file_size, filename))
                        except (OSError, PermissionError) as e:
                            self.signals.log.emit(f"Error accessing {file_path}: {str(e)}")

            except Exception as e:
                self.signals.log.emit(f"Error scanning {directory}: {str(e)}")

        if not files_to_hash:
            self.signals.log.emit("No files found to process")
            return {}
        
        # Second pass: parallel hashing using asyncio
        try:
            # Run the async hashing in the thread
            file_hashes, file_info, total_scanned = asyncio.run(
                self._hash_files_parallel(files_to_hash)
            )
        except Exception as e:
            self.signals.log.emit(f"Error during parallel hashing: {str(e)}")
            return {}

        if self._is_cancelled:
            return {}

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

    async def _hash_files_parallel(self, files_to_hash: List[tuple]) -> tuple:
        """Hash files in parallel using asyncio and thread pool."""
        file_hashes = {}
        file_info = {}
        total_scanned = 0
        
        # Create thread pool executor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Create tasks for all files
            tasks = []
            for file_path, file_size, filename in files_to_hash:
                if self._is_cancelled:
                    break
                task = compute_hash_async(file_path, executor, self.chunk_size)
                tasks.append((task, file_path, file_size, filename))
            
            # Process tasks as they complete
            for i, (task, file_path, file_size, filename) in enumerate(tasks):
                if self._is_cancelled:
                    break
                
                try:
                    # Wait for this specific task
                    _, file_hash = await task
                    
                    total_scanned += 1
                    
                    # Update progress every 50 files
                    if total_scanned % 50 == 0:
                        progress_msg = f"Hashed {total_scanned}/{len(tasks)} files..."
                        self.signals.progress.emit(
                            int((total_scanned / len(tasks)) * 100),
                            progress_msg
                        )
                    
                    # Store results in thread-safe manner
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

        # Load settings
        self.settings = load_settings()

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
        logs_dir = Path("../logs")
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

        # Tab 5: Settings
        self.settings_tab = self.create_settings_tab()
        def create_settings_tab(self) -> QWidget:
            """Create the settings tab."""
            widget = QWidget()
            layout = QVBoxLayout()

            # Performance settings group
            perf_group = QGroupBox("Performance Settings")
            perf_layout = QFormLayout()

            # Max workers setting
            self.max_workers_spinbox = QSpinBox()
            self.max_workers_spinbox.setMinimum(1)
            self.max_workers_spinbox.setMaximum(128)
            self.max_workers_spinbox.setValue(self.settings['max_workers'])
            self.max_workers_spinbox.setToolTip(
                "Number of parallel workers for file hashing.\n"
                f"Recommended: {multiprocessing.cpu_count() * 2} (CPU cores × 2)\n"
                "Higher values = faster scanning but more memory usage.\n"
                "SSD: Use 16-32 | HDD: Use 4-8"
            )
            
            workers_label = QLabel(f"Max Workers (CPU cores: {multiprocessing.cpu_count()})")
            perf_layout.addRow(workers_label, self.max_workers_spinbox)

            # Chunk size setting
            self.chunk_size_spinbox = QSpinBox()
            self.chunk_size_spinbox.setMinimum(4096)  # 4 KB minimum
            self.chunk_size_spinbox.setMaximum(1048576)  # 1 MB maximum
            self.chunk_size_spinbox.setSingleStep(4096)
            self.chunk_size_spinbox.setValue(self.settings['chunk_size'])
            self.chunk_size_spinbox.setToolTip(
                "Size of memory chunks when reading files (in bytes).\n"
                "Recommended: 65536 (64 KB)\n"
                "Larger values = faster for large files but more memory.\n"
                "Smaller values = less memory but slower."
            )
            
            chunk_label = QLabel("Chunk Size (bytes)")
            perf_layout.addRow(chunk_label, self.chunk_size_spinbox)

            # Display chunk size in KB/MB
            self.chunk_size_display = QLabel()
            self.update_chunk_size_display()
            self.chunk_size_spinbox.valueChanged.connect(self.update_chunk_size_display)
            perf_layout.addRow("", self.chunk_size_display)

            perf_group.setLayout(perf_layout)

            # Preset buttons
            preset_group = QGroupBox("Performance Presets")
            preset_layout = QVBoxLayout()

            preset_btn_layout = QHBoxLayout()
            
            conservative_btn = QPushButton("Conservative (Low Memory)")
            conservative_btn.clicked.connect(lambda: self.apply_preset('conservative'))
            conservative_btn.setToolTip("4 workers, 32 KB chunks - Best for old systems or HDDs")
            
            balanced_btn = QPushButton("Balanced (Recommended)")
            balanced_btn.clicked.connect(lambda: self.apply_preset('balanced'))
            balanced_btn.setToolTip("CPU×2 workers, 64 KB chunks - Good for most systems")
            
            aggressive_btn = QPushButton("Aggressive (High Performance)")
            aggressive_btn.clicked.connect(lambda: self.apply_preset('aggressive'))
            aggressive_btn.setToolTip("32 workers, 128 KB chunks - Best for SSDs with plenty of RAM")
            
            preset_btn_layout.addWidget(conservative_btn)
            preset_btn_layout.addWidget(balanced_btn)
            preset_btn_layout.addWidget(aggressive_btn)
            
            preset_layout.addLayout(preset_btn_layout)
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
                "• <b>Large files:</b> Increase chunk size (128-256 KB)<br>"
                f"• Current system: {multiprocessing.cpu_count()} CPU cores detected"
            )
            info_label.setWordWrap(True)
            info_label.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }")

            layout.addWidget(perf_group)
            layout.addWidget(preset_group)
            layout.addLayout(btn_layout)
            layout.addWidget(info_label)
            layout.addStretch()

            widget.setLayout(layout)
            return widget

        def update_chunk_size_display(self):
            """Update the chunk size display label."""
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
                self.chunk_size_spinbox.setValue(32768)  # 32 KB
            elif preset_name == 'balanced':
                self.max_workers_spinbox.setValue(min(32, multiprocessing.cpu_count() * 2))
                self.chunk_size_spinbox.setValue(65536)  # 64 KB
            elif preset_name == 'aggressive':
                self.max_workers_spinbox.setValue(32)
                self.chunk_size_spinbox.setValue(131072)  # 128 KB
            
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
        
        self.tabs.addTab(self.settings_tab, "⚙ Settings")

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

    def create_settings_tab(self) -> QWidget:
        """Create the settings tab."""
        widget = QWidget()
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Max Workers
        self.max_workers_spinbox = QSpinBox()
        self.max_workers_spinbox.setRange(1, multiprocessing.cpu_count() * 4)
        self.max_workers_spinbox.setValue(self.settings['max_workers'])
        form_layout.addRow("Max Workers:", self.max_workers_spinbox)

        # Chunk Size
        self.chunk_size_spinbox = QSpinBox()
        self.chunk_size_spinbox.setRange(4096, 1048576)  # 4KB to 1MB
        self.chunk_size_spinbox.setSingleStep(4096)       # Step by 4KB
        self.chunk_size_spinbox.setValue(self.settings['chunk_size'])
        form_layout.addRow("Chunk Size (bytes):", self.chunk_size_spinbox)

        # Save Button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)

        layout.addLayout(form_layout)
        layout.addWidget(save_btn)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def save_settings(self):
        """Save settings from the settings tab."""
        new_max_workers = self.max_workers_spinbox.value()
        new_chunk_size = self.chunk_size_spinbox.value()

        self.settings['max_workers'] = new_max_workers
        self.settings['chunk_size'] = new_chunk_size

        save_settings(self.settings)
        self.log("Settings saved.")
        QMessageBox.information(self, "Settings Saved", "Settings have been saved.")

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

    def scan_duplicates(self):
        """Start scanning for duplicate files."""
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
        selected_