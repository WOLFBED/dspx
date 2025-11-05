#!/usr/bin/env python3
"""dspx - Duplicate & residual file scanner (PySide6)

Features implemented:
- Residual file detection using editable CSV patterns (dspx_residuals_patterns.csv)
- File hashing using blake3 (if available) with sha256 fallback
- Asyncio + ThreadPoolExecutor parallel hashing with configurable max_workers & chunk_size
- Find duplicates by same filename+hash and by hash only
- Detect empty directories
- UI in PySide6 with tabs, Start/Stop, Settings, Patterns editor and log output
- Persistent settings (dspx_settings.json) and logs written to logs/

This is a complete single-file implementation intended to be saved as main.py and executed.
"""

from __future__ import annotations
import sys
import os
import csv
import json
import shutil
import asyncio
import platform
import multiprocessing
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from fnmatch import fnmatch

# Attempt to import blake3
try:
    import blake3
    HASH_ALGO = "blake3"
except Exception:
    import hashlib
    HASH_ALGO = "sha256"

# PySide6 imports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QFileDialog, QListWidget, QGroupBox, QProgressBar,
    QMessageBox, QTabWidget, QSpinBox, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QCheckBox, QComboBox
)
from PySide6.QtCore import Qt, QThread, Signal, QObject

APP_DIR = Path.cwd()
SETTINGS_FILE = APP_DIR / "dspx_settings.json"
PATTERNS_FILE = APP_DIR / "dspx_residuals_patterns.csv"
LOGS_DIR = APP_DIR / "logs"

# Default settings
DEFAULT_SETTINGS = {
    "max_workers": max(2, multiprocessing.cpu_count() * 2),
    "chunk_size": 64 * 1024,  # bytes
}

# Ensure logs dir exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class WorkerSignals(QObject):
    log = Signal(str)
    progress = Signal(int)  # percentage
    result = Signal(object)  # arbitrary data
    finished = Signal()


class ScanWorker(QThread):
    """QThread that runs scan operations in an asyncio event loop.
    Modes: 'residuals', 'same_name', 'same_hash', 'empty_dirs'
    """

    def __init__(self, mode: str, directories: List[Path], settings: Dict[str, Any], patterns: List[Dict[str, str]] = None):
        super().__init__()
        self.mode = mode
        self.directories = [Path(d) for d in directories]
        self.settings = settings
        self.patterns = patterns or []
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True
        self.signals.log.emit("Cancellation requested.")

    def run(self):
        # create and run a fresh asyncio loop inside this thread
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_async())
        finally:
            try:
                loop.close()
            except Exception:
                pass
        self.signals.finished.emit()

    async def _run_async(self):
        try:
            if self.mode == 'residuals':
                await self._scan_residuals()
            elif self.mode in ('same_name', 'same_hash'):
                await self._scan_duplicates(group_by_name=(self.mode == 'same_name'))
            elif self.mode == 'empty_dirs':
                await self._scan_empty_dirs()
            else:
                self.signals.log.emit(f"Unknown mode: {self.mode}")
        except asyncio.CancelledError:
            self.signals.log.emit("Operation cancelled (asyncio CancelledError).")
        except Exception as e:
            self.signals.log.emit(f"Error in worker: {e}")

    async def _scan_residuals(self):
        """Walk directories and find files whose basenames match patterns from self.patterns."""
        found: List[Tuple[Path, Dict[str, str]]] = []
        total = 0
        for d in self.directories:
            for _ in d.rglob('*'):
                total += 1
        scanned = 0
        for root in self.directories:
            if self._is_cancelled:
                break
            for p in root.rglob('*'):
                if self._is_cancelled:
                    break
                scanned += 1
                if p.is_file():
                    for pat in self.patterns:
                        fp = pat.get('File_Pattern') or ''
                        # Only match against basename using fnmatch
                        if fp and fnmatch(p.name, fp):
                            found.append((p, pat))
                            self.signals.log.emit(f"Residual matched: {p} -> {fp}")
                            break
                # emit progress occasionally
                if total:
                    perc = int(scanned * 100 / total)
                    self.signals.progress.emit(perc)
                    await asyncio.sleep(0)  # yield to event loop
        self.signals.result.emit({'residuals': found})

    async def _hash_files_parallel(self, files: List[Path]) -> Dict[Path, str]:
        """Hash files in parallel using executor and asyncio.
        Returns dict Path->hexhash
        """
        # settings
        max_workers = int(self.settings.get('max_workers', DEFAULT_SETTINGS['max_workers']))
        chunk_size = int(self.settings.get('chunk_size', DEFAULT_SETTINGS['chunk_size']))

        loop = asyncio.get_event_loop()
        hashes: Dict[Path, str] = {}

        executor = ThreadPoolExecutor(max_workers=max_workers)

        async def hash_one(p: Path):
            if self._is_cancelled:
                return
            return await loop.run_in_executor(executor, compute_hash_sync, p, chunk_size)

        tasks = [asyncio.create_task(hash_one(p)) for p in files]

        for idx, t in enumerate(asyncio.as_completed(tasks), 1):
            if self._is_cancelled:
                break
            h = await t
            # find which file this was: we can't map directly, so we instead collect in order
            # to maintain mapping, we will run the tasks in sequence with indices
            # Simpler approach: run run_in_executor with mapping closure
        # Re-implement with mapping to file
        # Cancel previous executor tasks and recreate correctly
        executor.shutdown(wait=False)

        # Correct implementation: schedule named tasks
        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = {loop.run_in_executor(executor, compute_hash_sync, p, chunk_size): p for p in files}
        completed = 0
        total = len(files)
        for fut in asyncio.as_completed(list(futures.keys())):
            if self._is_cancelled:
                break
            res = await fut
            p = futures[fut]
            hashes[p] = res
            completed += 1
            if total:
                perc = int(completed * 100 / total)
                self.signals.progress.emit(perc)
            self.signals.log.emit(f"Hashed: {p} -> {res}")
            await asyncio.sleep(0)

        executor.shutdown(wait=False)
        return hashes

    async def _scan_duplicates(self, group_by_name: bool = False):
        # collect files
        files: List[Path] = []
        for d in self.directories:
            for p in d.rglob('*'):
                if self._is_cancelled:
                    break
                if p.is_file():
                    files.append(p)
        if not files:
            self.signals.log.emit("No files found for hashing.")
            self.signals.result.emit({'same_name': [], 'same_hash': []})
            return

        self.signals.log.emit(f"Hashing {len(files)} files with {self.settings.get('max_workers')} workers...")
        hashes = await self._hash_files_parallel(files)
        if self._is_cancelled:
            self.signals.log.emit("Cancelled after hashing.")
            self.signals.result.emit({'same_name': [], 'same_hash': []})
            return

        by_name_and_hash: Dict[Tuple[str, str], List[Path]] = defaultdict(list)
        by_hash: Dict[str, List[Path]] = defaultdict(list)
        for p, h in hashes.items():
            by_name_and_hash[(p.name, h)].append(p)
            by_hash[h].append(p)

        same_name_dups = [lst for lst in by_name_and_hash.values() if len(lst) > 1]
        same_hash_dups = [lst for lst in by_hash.values() if len(lst) > 1]

        # Optionally filter same_hash_dups to only those where names differ if group_by_name False
        self.signals.result.emit({'same_name': same_name_dups, 'same_hash': same_hash_dups})

    async def _scan_empty_dirs(self):
        empties: List[Path] = []
        for d in self.directories:
            if self._is_cancelled:
                break
            for root, dirs, files in os.walk(d):
                if self._is_cancelled:
                    break
                rp = Path(root)
                # An empty dir has no files and no subdirs
                if not files and not dirs:
                    empties.append(rp)
                    self.signals.log.emit(f"Empty dir: {rp}")
                await asyncio.sleep(0)
        self.signals.result.emit({'empties': empties})


# Hash compute sync
def compute_hash_sync(filepath: Path, chunk_size: int = 64 * 1024) -> str:
    try:
        if HASH_ALGO == 'blake3':
            hasher = blake3.blake3()
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        else:
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
    except Exception as e:
        return f"ERROR:{e}"


# Utilities for settings and patterns

def load_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
                # validate
                if 'max_workers' not in data or 'chunk_size' not in data:
                    return DEFAULT_SETTINGS.copy()
                return data
        except Exception:
            return DEFAULT_SETTINGS.copy()
    else:
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]):
    with SETTINGS_FILE.open('w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)


def load_patterns() -> List[Dict[str, str]]:
    patterns: List[Dict[str, str]] = []
    if not PATTERNS_FILE.exists():
        # write default minimal file
        with PATTERNS_FILE.open('w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['OS', 'File_Pattern', 'Path_Example', 'Description', 'Safe_To_Delete'])
        return patterns
    try:
        with PATTERNS_FILE.open('r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # validation: must have OS and File_Pattern
                if (row.get('OS') or '').strip() and (row.get('File_Pattern') or '').strip():
                    patterns.append(row)
        return patterns
    except Exception:
        return []


def save_patterns(patterns: List[Dict[str, str]]):
    fields = ['OS', 'File_Pattern', 'Path_Example', 'Description', 'Safe_To_Delete']
    with PATTERNS_FILE.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in patterns:
            writer.writerow({k: row.get(k, '') for k in fields})


# Logging helper that writes both to a QTextEdit and to a file
class Logger:
    def __init__(self, text_widget: QTextEdit):
        self.text_widget = text_widget
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        logfile = LOGS_DIR / f'dspx_{ts}.log'
        self.logfile = logfile
        try:
            self.handle = logfile.open('a', encoding='utf-8')
        except Exception:
            self.handle = None

    def write(self, msg: str):
        ts = datetime.now().isoformat(sep=' ', timespec='seconds')
        line = f"[{ts}] {msg}"
        # append to text widget
        self.text_widget.append(line)
        # also write to file
        if self.handle:
            try:
                self.handle.write(line + '\n')
                self.handle.flush()
            except Exception:
                pass

    def close(self):
        if self.handle:
            try:
                self.handle.close()
            except Exception:
                pass


# MainWindow UI
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('dspx - Duplicate & residual file scanner')
        self.resize(1000, 700)

        self.settings = load_settings()
        self.patterns = load_patterns()

        self.current_worker: Optional[ScanWorker] = None

        self._build_ui()

    def _build_ui(self):
        tabs = QTabWidget()

        # Tab: Directories & Residuals
        self.tab_scan = QWidget()
        self._build_scan_tab()
        tabs.addTab(self.tab_scan, 'Residuals')

        # Tab: Duplicates
        self.tab_dups = QWidget()
        self._build_dups_tab()
        tabs.addTab(self.tab_dups, 'Duplicates')

        # Tab: Empty dirs
        self.tab_empty = QWidget()
        self._build_empty_tab()
        tabs.addTab(self.tab_empty, 'Empty Dirs')

        # Tab: Patterns editor
        self.tab_patterns = QWidget()
        self._build_patterns_tab()
        tabs.addTab(self.tab_patterns, 'Residual Patterns')

        # Tab: Settings
        self.tab_settings = QWidget()
        self._build_settings_tab()
        tabs.addTab(self.tab_settings, 'Settings')

        # Tab: Logs
        self.tab_logs = QWidget()
        self._build_logs_tab()
        tabs.addTab(self.tab_logs, 'Logs')

        self.setCentralWidget(tabs)

    # --- Build tabs ---
    def _build_scan_tab(self):
        v = QVBoxLayout()
        top_row = QHBoxLayout()
        self.dir_list = QListWidget()
        top_controls = QVBoxLayout()
        add_dir_btn = QPushButton('Add Directory')
        add_dir_btn.clicked.connect(self.add_directory)
        remove_dir_btn = QPushButton('Remove Selected')
        remove_dir_btn.clicked.connect(lambda: self.dir_list.takeItem(self.dir_list.currentRow()))
        scan_btn = QPushButton('Scan Residuals')
        scan_btn.clicked.connect(self.start_residual_scan)
        stop_btn = QPushButton('Stop')
        stop_btn.clicked.connect(self.stop_current_worker)

        top_controls.addWidget(add_dir_btn)
        top_controls.addWidget(remove_dir_btn)
        top_controls.addWidget(scan_btn)
        top_controls.addWidget(stop_btn)
        top_controls.addStretch()

        top_row.addWidget(self.dir_list)
        top_row.addLayout(top_controls)

        v.addLayout(top_row)

        self.residuals_list = QListWidget()
        v.addWidget(QLabel('Residual files found:'))
        v.addWidget(self.residuals_list)

        delete_sel_btn = QPushButton('Delete Selected File(s)')
        delete_sel_btn.clicked.connect(self.delete_selected_residuals)
        delete_all_btn = QPushButton('Delete All Listed')
        delete_all_btn.clicked.connect(self.delete_all_residuals)
        h = QHBoxLayout()
        h.addWidget(delete_sel_btn)
        h.addWidget(delete_all_btn)
        v.addLayout(h)

        self.tab_scan.setLayout(v)

    def _build_dups_tab(self):
        v = QVBoxLayout()
        top = QHBoxLayout()
        scan_name_btn = QPushButton('Find Same-name+hash Duplicates')
        scan_name_btn.clicked.connect(lambda: self.start_duplicates_scan(group_by_name=True))
        scan_hash_btn = QPushButton('Find Same-hash Duplicates')
        scan_hash_btn.clicked.connect(lambda: self.start_duplicates_scan(group_by_name=False))
        stop_btn = QPushButton('Stop')
        stop_btn.clicked.connect(self.stop_current_worker)
        top.addWidget(scan_name_btn)
        top.addWidget(scan_hash_btn)
        top.addWidget(stop_btn)
        v.addLayout(top)

        self.dups_list = QListWidget()
        self.dups_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        v.addWidget(self.dups_list)

        del_sel = QPushButton('Delete Selected')
        del_sel.clicked.connect(self.delete_selected_dups)
        del_all = QPushButton('Delete All Groups Shown')
        del_all.clicked.connect(self.delete_all_dups)
        h = QHBoxLayout()
        h.addWidget(del_sel)
        h.addWidget(del_all)
        v.addLayout(h)

        self.tab_dups.setLayout(v)

    def _build_empty_tab(self):
        v = QVBoxLayout()
        scan_btn = QPushButton('Find Empty Directories')
        scan_btn.clicked.connect(self.start_empty_dirs_scan)
        stop_btn = QPushButton('Stop')
        stop_btn.clicked.connect(self.stop_current_worker)
        h = QHBoxLayout()
        h.addWidget(scan_btn)
        h.addWidget(stop_btn)
        v.addLayout(h)

        self.empty_list = QListWidget()
        v.addWidget(self.empty_list)

        del_sel = QPushButton('Delete Selected')
        del_sel.clicked.connect(self.delete_selected_empty)
        del_all = QPushButton('Delete All Listed')
        del_all.clicked.connect(self.delete_all_empty)
        h2 = QHBoxLayout()
        h2.addWidget(del_sel)
        h2.addWidget(del_all)
        v.addLayout(h2)

        self.tab_empty.setLayout(v)

    def _build_patterns_tab(self):
        v = QVBoxLayout()
        self.patterns_table = QTableWidget()
        self.patterns_table.setColumnCount(5)
        self.patterns_table.setHorizontalHeaderLabels(['OS', 'File_Pattern', 'Path_Example', 'Description', 'Safe_To_Delete'])
        self.patterns_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        v.addWidget(self.patterns_table)

        load_btn = QPushButton('Reload Patterns from CSV')
        load_btn.clicked.connect(self.reload_patterns_to_table)
        save_btn = QPushButton('Save Patterns to CSV')
        save_btn.clicked.connect(self.save_patterns_from_table)
        h = QHBoxLayout()
        h.addWidget(load_btn)
        h.addWidget(save_btn)
        v.addLayout(h)

        self.tab_patterns.setLayout(v)
        self.reload_patterns_to_table()

    def _build_settings_tab(self):
        v = QVBoxLayout()
        form = QFormLayout()
        self.workers_spin = QSpinBox()
        self.workers_spin.setMinimum(1)
        self.workers_spin.setMaximum(512)
        self.workers_spin.setValue(int(self.settings.get('max_workers', DEFAULT_SETTINGS['max_workers'])))
        self.chunk_edit = QLineEdit(str(int(self.settings.get('chunk_size', DEFAULT_SETTINGS['chunk_size']))))
        form.addRow('Max workers:', self.workers_spin)
        form.addRow('Chunk size (bytes):', self.chunk_edit)

        presets = QHBoxLayout()
        cons = QPushButton('Conservative')
        cons.clicked.connect(lambda: self.apply_preset('conservative'))
        bal = QPushButton('Balanced')
        bal.clicked.connect(lambda: self.apply_preset('balanced'))
        agg = QPushButton('Aggressive')
        agg.clicked.connect(lambda: self.apply_preset('aggressive'))
        presets.addWidget(cons)
        presets.addWidget(bal)
        presets.addWidget(agg)

        save_btn = QPushButton('Save Settings')
        save_btn.clicked.connect(self.save_settings_from_ui)

        v.addLayout(form)
        v.addLayout(presets)
        v.addWidget(save_btn)
        self.tab_settings.setLayout(v)

    def _build_logs_tab(self):
        v = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        v.addWidget(self.log_text)
        self.logger = Logger(self.log_text)
        self.tab_logs.setLayout(v)

    # --- Actions ---
    def add_directory(self):
        dirpath = QFileDialog.getExistingDirectory(self, 'Select directory')
        if dirpath:
            self.dir_list.addItem(dirpath)

    def start_residual_scan(self):
        dirs = [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
        if not dirs:
            QMessageBox.warning(self, 'No directories', 'Please add at least one directory to scan.')
            return
        # start worker
        self._start_worker('residuals', dirs)

    def start_duplicates_scan(self, group_by_name: bool = False):
        dirs = [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
        if not dirs:
            QMessageBox.warning(self, 'No directories', 'Please add at least one directory to scan.')
            return
        mode = 'same_name' if group_by_name else 'same_hash'
        self._start_worker(mode, dirs)

    def start_empty_dirs_scan(self):
        dirs = [self.dir_list.item(i).text() for i in range(self.dir_list.count())]
        if not dirs:
            QMessageBox.warning(self, 'No directories', 'Please add at least one directory to scan.')
            return
        self._start_worker('empty_dirs', dirs)

    def stop_current_worker(self):
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel()
            self.logger.write('Stop requested by user.')
        else:
            self.logger.write('No active worker to stop.')

    def _start_worker(self, mode: str, directories: List[str]):
        # ensure any previous worker cancelled
        if self.current_worker and self.current_worker.isRunning():
            QMessageBox.information(self, 'Worker running', 'A worker is already running. Stop it first.')
            return
        # refresh settings and patterns
        self.settings['max_workers'] = int(self.workers_spin.value())
        try:
            self.settings['chunk_size'] = int(self.chunk_edit.text())
        except ValueError:
            QMessageBox.warning(self, 'Invalid chunk size', 'Chunk size must be an integer (bytes).')
            return
        save_settings(self.settings)
        self.patterns = load_patterns()

        self.current_worker = ScanWorker(mode=mode, directories=[Path(d) for d in directories], settings=self.settings, patterns=self.patterns)
        self.current_worker.signals.log.connect(self.logger.write)
        self.current_worker.signals.progress.connect(lambda p: self.logger.write(f"Progress: {p}%"))
        self.current_worker.signals.result.connect(self._handle_worker_result)
        self.current_worker.signals.finished.connect(lambda: self.logger.write('Worker finished.'))
        self.current_worker.start()
        self.logger.write(f'Started worker: {mode} on {len(directories)} directories')

    def _handle_worker_result(self, data: Dict[str, Any]):
        # flush UI lists depending on content
        if 'residuals' in data:
            self.residuals_list.clear()
            for p, pat in data['residuals']:
                display = f"{p}    [pattern: {pat.get('File_Pattern')} | {pat.get('Description')}]"
                self.residuals_list.addItem(display)
            self.logger.write(f"Residuals listed: {len(data['residuals'])}")
        if 'same_name' in data or 'same_hash' in data:
            self.dups_list.clear()
            groups = []
            if data.get('same_name'):
                groups.extend(data['same_name'])
            if data.get('same_hash'):
                groups.extend(data['same_hash'])
            for grp in groups:
                # show group header and items
                header = ' | '.join(str(p) for p in grp)
                self.dups_list.addItem(header)
            self.logger.write(f"Duplicate groups shown: {len(groups)}")
        if 'empties' in data:
            self.empty_list.clear()
            for p in data['empties']:
                self.empty_list.addItem(str(p))
            self.logger.write(f"Empty directories found: {len(data['empties'])}")

    # --- Delete actions ---
    def delete_selected_residuals(self):
        items = self.residuals_list.selectedItems()
        if not items:
            return
        to_delete = []
        for it in items:
            text = it.text()
            path = text.split('    ')[0]
            to_delete.append(Path(path))
        self._confirm_and_delete_files(to_delete)

    def delete_all_residuals(self):
        items = [self.residuals_list.item(i).text() for i in range(self.residuals_list.count())]
        to_delete = [Path(t.split('    ')[0]) for t in items]
        self._confirm_and_delete_files(to_delete)

    def delete_selected_dups(self):
        items = self.dups_list.selectedItems()
        if not items:
            return
        to_delete = []
        for it in items:
            # header contains paths separated by ' | '
            parts = it.text().split(' | ')
            # Ask user which among group to delete? For simplicity delete all but first
            for p in parts[1:]:
                to_delete.append(Path(p))
        self._confirm_and_delete_files(to_delete)

    def delete_all_dups(self):
        items = [self.dups_list.item(i).text() for i in range(self.dups_list.count())]
        to_delete = []
        for it in items:
            parts = it.split(' | ')
            for p in parts[1:]:
                to_delete.append(Path(p))
        self._confirm_and_delete_files(to_delete)

    def delete_selected_empty(self):
        items = self.empty_list.selectedItems()
        if not items:
            return
        dirs = [Path(it.text()) for it in items]
        self._confirm_and_delete_dirs(dirs)

    def delete_all_empty(self):
        dirs = [Path(self.empty_list.item(i).text()) for i in range(self.empty_list.count())]
        self._confirm_and_delete_dirs(dirs)

    def _confirm_and_delete_files(self, files: List[Path]):
        if not files:
            return
        msg = '\n'.join(str(p) for p in files[:50])
        if len(files) > 50:
            msg += '\n...'
        reply = QMessageBox.question(self, 'Confirm delete', f'Delete {len(files)} files?\n{msg}')
        if reply != QMessageBox.StandardButton.Yes:
            return
        for p in files:
            try:
                if p.exists():
                    p.unlink()
                    self.logger.write(f'Deleted file: {p}')
                else:
                    self.logger.write(f'File not found: {p}')
            except Exception as e:
                self.logger.write(f'Failed to delete {p}: {e}')

    def _confirm_and_delete_dirs(self, dirs: List[Path]):
        if not dirs:
            return
        msg = '\n'.join(str(d) for d in dirs[:50])
        if len(dirs) > 50:
            msg += '\n...'
        reply = QMessageBox.question(self, 'Confirm delete', f'Delete {len(dirs)} directories?\n{msg}')
        if reply != QMessageBox.StandardButton.Yes:
            return
        for d in dirs:
            try:
                if d.exists() and d.is_dir():
                    shutil.rmtree(d)
                    self.logger.write(f'Deleted directory: {d}')
                else:
                    self.logger.write(f'Directory not found: {d}')
            except Exception as e:
                self.logger.write(f'Failed to delete directory {d}: {e}')

    # --- Patterns table management ---
    def reload_patterns_to_table(self):
        self.patterns = load_patterns()
        self.patterns_table.setRowCount(0)
        for row in self.patterns:
            r = self.patterns_table.rowCount()
            self.patterns_table.insertRow(r)
            self.patterns_table.setItem(r, 0, QTableWidgetItem(row.get('OS', '')))
            self.patterns_table.setItem(r, 1, QTableWidgetItem(row.get('File_Pattern', '')))
            self.patterns_table.setItem(r, 2, QTableWidgetItem(row.get('Path_Example', '')))
            self.patterns_table.setItem(r, 3, QTableWidgetItem(row.get('Description', '')))
            self.patterns_table.setItem(r, 4, QTableWidgetItem(row.get('Safe_To_Delete', '')))

    def save_patterns_from_table(self):
        rows = []
        for r in range(self.patterns_table.rowCount()):
            row = {
                'OS': self._get_table_text(r, 0),
                'File_Pattern': self._get_table_text(r, 1),
                'Path_Example': self._get_table_text(r, 2),
                'Description': self._get_table_text(r, 3),
                'Safe_To_Delete': self._get_table_text(r, 4),
            }
            # validate
            if not row['OS'].strip() or not row['File_Pattern'].strip():
                QMessageBox.warning(self, 'Invalid row', f'Row {r+1} missing OS or File_Pattern; please fix.')
                return
            rows.append(row)
        save_patterns(rows)
        self.patterns = rows
        self.logger.write(f'Saved {len(rows)} patterns to {PATTERNS_FILE}')
        QMessageBox.information(self, 'Saved', 'Patterns saved.')

    def _get_table_text(self, r: int, c: int) -> str:
        it = self.patterns_table.item(r, c)
        return it.text() if it else ''

    # --- Settings management ---
    def apply_preset(self, name: str):
        cpu = multiprocessing.cpu_count()
        if name == 'conservative':
            self.workers_spin.setValue(4)
            self.chunk_edit.setText(str(32 * 1024))
        elif name == 'balanced':
            self.workers_spin.setValue(max(1, cpu * 2))
            self.chunk_edit.setText(str(64 * 1024))
        elif name == 'aggressive':
            self.workers_spin.setValue(32)
            self.chunk_edit.setText(str(128 * 1024))

    def save_settings_from_ui(self):
        try:
            self.settings['max_workers'] = int(self.workers_spin.value())
            self.settings['chunk_size'] = int(self.chunk_edit.text())
        except ValueError:
            QMessageBox.warning(self, 'Invalid', 'Max workers and chunk size must be integers.')
            return
        save_settings(self.settings)
        QMessageBox.information(self, 'Saved', 'Settings saved.')
        self.logger.write('Settings saved.')

    def closeEvent(self, event):
        try:
            self.logger.close()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
