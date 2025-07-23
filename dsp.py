from pathlib import Path
import sys
from rich import print as rprint
import os
import shutil
import platform
import subprocess
from datetime import datetime
import logging
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, BarColumn, TaskProgressColumn
import subprocess
from typing import Union, Tuple
import shutil
import collections
import itertools



class Utilities:
    _timestamp = None  # Class variable to hold the timestamp

    def __init__(self):
        # Only set the timestamp if it hasn't been set yet
        if Utilities._timestamp is None:
            Utilities._timestamp = self.ts_custom("%d%m%Y%H%M%S%f")

    @staticmethod
    def ts_custom(format):
        """
        Timestamp formatting utility
        """
        now = datetime.now()
        toim = now.strftime(format)
        return toim

    @staticmethod
    def logging(log_file=None, log_level=logging.DEBUG):
        """
        Configures logging with dynamic output modes.
        Parameters:
        - log_file (str): Path to the log file.
        - log_level (int): Logging level (e.g., logging.INFO, logging.ERROR).
        """
        if log_file is None:
            if Utilities._timestamp is None:
                raise RuntimeError("Utilities must be instantiated before using logging")
            log_file = f"dsp_{Utilities._timestamp}.log"
        logger = logging.getLogger()
        logger.setLevel(log_level)
        logger.handlers.clear()  # Clear existing handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    @staticmethod
    def printAscii(code, string):
        match code:
            case 7:
                art = rf"""[blue] ╺┳┓┏━┓┏━┓╖ ╓[/blue]   [deep_sky_blue1]╱[/deep_sky_blue1] 
 [blue] ┃┃┗━┓┣━┛ ▓   [/blue][deep_sky_blue1]╱[/deep_sky_blue1] [yellow]data-store pruner compressor ~ version {string}[/yellow]
[blue] ╺┻┛┗━┛╹  ╜ ╙ [/blue][deep_sky_blue1]╱[/deep_sky_blue1]
[orange1]▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔[/orange1]"""
        rprint(art)

    @staticmethod
    def bytes2nice(item):
        def sizeof_fmt(num, suffix="B"):
            for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
                if abs(num) < 1024.0:
                    return f"{num:3.1f} {unit}{suffix}"
                num /= 1024.0
            return f"{num:.1f}Yi{suffix}"
        siz = sizeof_fmt(item)
        return siz

    @staticmethod
    def bytes2nice2(size: int) -> str:
        """Convert size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0

    @staticmethod
    def check_program(program_name: str, *, verbose: bool = True) -> bool:
        """
        Checks if a program is available in PATH. If not, suggests installation commands
        based on detected package managers.

        :param program_name: Name of the executable to check.
        :param verbose: If True, prints installation instructions if program is missing.
        :return: True if found, False otherwise.
        """
        if shutil.which(program_name):
            # if verbose:
            #     print(f"✅ '{program_name}' is installed.")
            Utilities.logging()
            logging.info(f"Requirement: '{program_name}' is installed")
            return True
        os_info = Utilities._detect_os_info()
        pm = Utilities._detect_package_manager()
        if verbose:
            rprint(f"❌ '{program_name}' is not installed [chartreuse4]>>>[/chartreuse4] [orange_red1]but required[/orange_red1].")
            if pm:
                install_cmd = Utilities._suggest_install_command(pm, program_name)
                if install_cmd:
                    rprint(f"\n💡 Try installing it with:\n  {install_cmd}")
                else:
                    rprint("🤷 No install command found for this package manager.")
            else:
                rprint("🚫 No supported package manager detected.")
        return False

    @staticmethod
    def _detect_os_info():
        try:
            with open("/etc/os-release", "r") as f:
                return dict(
                    line.strip().split("=", 1)
                    for line in f if "=" in line
                )
        except Exception:
            return {}

    @staticmethod
    def _detect_package_manager():
        package_managers = {
            "apt": "Debian/Ubuntu",
            "dnf": "Fedora",
            "yum": "RHEL/CentOS",
            "pacman": "Arch Linux",
            "zypper": "openSUSE",
            "apk": "Alpine Linux",
            "brew": "macOS (Homebrew)",
            "port": "macOS (MacPorts)",
        }
        for pm in package_managers:
            if shutil.which(pm):
                return pm
        return None

    @staticmethod
    def _suggest_install_command(pm, program):
        commands = {
            "apt": f"sudo apt update && sudo apt install -y {program}",
            "dnf": f"sudo dnf install -y {program}",
            "yum": f"sudo yum install -y {program}",
            "pacman": f"sudo pacman -S --noconfirm {program}",
            "zypper": f"sudo zypper install -y {program}",
            "apk": f"sudo apk add {program}",
            "brew": f"brew install {program}",
            "port": f"sudo port install {program}",
        }
        return commands.get(pm)

    @staticmethod
    def validate_cli_directory() -> Path:
        """
        Validates command line argument for directory path.
        Returns:
            Path: Valid directory path as Path object
        Raises:
            SystemExit: If argument is missing or invalid
        """
        if len(sys.argv) < 2:
            rprint("[red]Error: Missing directory path argument[/red]")
            rprint("Usage: script.py <directory_path>")
            sys.exit(1)
        try:
            path = Path(sys.argv[1])
            if not path.exists():
                rprint(f"[red]Error: Directory does not exist: {path}[/red]")
                sys.exit(1)
            if not path.is_dir():
                rprint(f"[red]Error: Path exists but is not a directory: {path}[/red]")
                sys.exit(1)
            return path
        except Exception as e:
            rprint(f"[red]Error: Invalid directory path - {str(e)}[/red]")
            sys.exit(1)


class FileSystemOperations:
    """
    A class that provides utility methods for filesystem operations using Path objects.
    """
    @staticmethod
    def convert_path_string_to_object(path_string: str) -> Path:
        """
        Convert a string path to a Path object.
        Args:
            path_string: String representation of a file system path
        Returns:
            Path object representing the input path string
        Raises:
            ValueError: If the path string is empty or contains invalid characters
        """
        if isinstance(path_string, Path):
            return path_string
        if not path_string or not path_string.strip():
            raise ValueError("Path string cannot be empty")
        try:
            return Path(path_string)
        except OSError as e:
            raise ValueError(f"Invalid path string: {str(e)}")

    @staticmethod
    def ensure_valid_dir_path(path) -> bool:
        """
        Validate that the given path is a Path object and leads to a valid directory.
        Args:
            path: Object to validate as a directory path
        Returns:
        bool: True if the path is a valid directory, False if validation fails
        """
        try:
            if not isinstance(path, Path):
                rprint(f"Error: Expected pathlib.Path object, got {type(path).__name__}")
                return False
            if not path.exists():
                rprint(f"Error: Directory does not exist: {path}")
                return False
            if not path.is_dir():
                rprint(f"Error: Path exists but is not a directory: {path}")
                return False
            return True
        except Exception as e:
            rprint(f"Error: Unexpected error occurred - {str(e)}")
            return False

    @staticmethod
    def get_dir_size(dir_path: Path, use_du: bool = False) -> Union[int, Tuple[int, str]]:
        """
        Calculate total size of a directory using either Python or du command.
        For very large directories (>1TB), du is automatically used.
        Args:
            dir_path: Path object pointing to the directory
            use_du: Force using du command instead of Python implementation
        Returns:
            If using Python impl: total size in bytes
            If using du: tuple of (size in bytes, human readable size)
        """
        if not isinstance(dir_path, Path):
            raise ValueError(f"Expected Path object, got {type(dir_path).__name__}")
        if not dir_path.is_dir():
            raise ValueError(f"Path {dir_path} is not a directory")
        # Check if du is available
        if use_du or FileSystemOperations._should_use_du(dir_path):
            return FileSystemOperations._get_size_using_du(dir_path)
        return FileSystemOperations._get_size_using_python(dir_path)

    @staticmethod
    def _should_use_du(dir_path: Path) -> bool:
        """Determine if we should use du based on quick directory analysis"""
        try:
            # Get filesystem info
            stats = os.statvfs(dir_path)
            total_size = stats.f_blocks * stats.f_frsize
            # If filesystem is larger than 1TB, suggest using du
            return total_size > 1_099_511_627_776  # 1TB in bytes
        except Exception:
            return False

    @staticmethod
    def _get_size_using_du(dir_path: Path) -> Tuple[int, str]:
        """Use du command to get directory size"""
        try:
            # -b for bytes, -s for summary only
            result = subprocess.run(
                ['du', '-sb', str(dir_path)],
                capture_output=True,
                text=True,
                check=True
            )
            # du output format: "size_in_bytes path"
            size_in_bytes = int(result.stdout.split()[0])
            # Get human readable size with du -sh
            human_result = subprocess.run(
                ['du', '-sh', str(dir_path)],
                capture_output=True,
                text=True,
                check=True
            )
            return size_in_bytes, Utilities.bytes2nice(size_in_bytes)
        except subprocess.SubprocessError as e:
            raise ValueError(f"Error running du command: {e}")

    @staticmethod
    def _get_size_using_python(dir_path: Path) -> int:
        """Calculate directory size using Python with progress reporting"""
        total_size = 0
        dirs_to_scan = collections.deque([dir_path])
        processed_files = 0
        # First, count total files for progress bar
        total_files = sum(len(files) for _, _, files in os.walk(dir_path))
        with Progress(
                SpinnerColumn(),
                "[progress.description]{task.description}",
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("[cyan]Calculating size...", total=total_files)
            try:
                while dirs_to_scan:
                    current_dir = dirs_to_scan.popleft()
                    try:
                        with os.scandir(current_dir) as it:
                            while True:
                                chunk = list(itertools.islice(it, 1000))
                                if not chunk:
                                    break
                                for entry in chunk:
                                    try:
                                        if entry.is_symlink():
                                            continue
                                        if entry.is_file(follow_symlinks=False):
                                            size = entry.stat(follow_symlinks=False).st_size
                                            total_size += size
                                            processed_files += 1
                                            progress.update(task, advance=1)
                                        elif entry.is_dir(follow_symlinks=False):
                                            dirs_to_scan.append(Path(entry.path))
                                    except (PermissionError, OSError) as e:
                                        print(f"Warning: Could not access {entry.path}: {e}",
                                              file=sys.stderr)
                                        progress.update(task, advance=1)
                                        continue
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not scan directory {current_dir}: {e}",
                              file=sys.stderr)
                        continue
            except Exception as e:
                raise ValueError(f"Error scanning directory structure: {e}")
        return total_size

    @staticmethod
    def delete_files_by_patterns(directory, patterns):
        """
        1. only accepts path objects 
        2. doesn't move-on until all files are actually deleted, this is critical
        3. must be extremely fast, as will be dealing with hundreds of millions of files spanning over 500TB
        """
        if not isinstance(directory, Path):
            raise ValueError("Input directory must be a Path object")

        deleted_files = []

        with Progress() as progress:
            # Create progress bar
            task = progress.add_task("[cyan]Deleting files...", total=None)

            try:
                for pattern in patterns:
                    # Use rglob for recursive matching
                    matching_files = list(directory.rglob(pattern))

                    for file_path in matching_files:
                        try:
                            if file_path.is_file():
                                file_path.unlink()
                                deleted_files.append(file_path)
                                progress.update(task, advance=1)

                            # Verify file is actually deleted
                            if file_path.exists():
                                raise IOError(f"Failed to delete {file_path}")

                        except (PermissionError, OSError) as e:
                            logging.error(f"Error deleting {file_path}: {e}")
                            continue

            except Exception as e:
                logging.error(f"Error during file deletion: {e}")
                raise

        return deleted_files


from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import logging
from pathlib import Path
from rich.progress import Progress
import asyncio
import mmap
from typing import List, Iterator, Set


# class FastFileDeleter:
#     def __init__(self, directory: Path, batch_size: int = 1000):
#         self.directory = directory
#         self.batch_size = batch_size
#         self._seen_files: Set[Path] = set()
#
#     async def delete_files_by_patterns(self, patterns: List[str]) -> List[Path]:
#         if not isinstance(self.directory, Path):
#             raise ValueError("Input directory must be a Path object")
#
#         deleted_files = []
#
#         with Progress() as progress:
#             task = progress.add_task("[cyan]Deleting files...", total=None)
#
#             try:
#                 # Process patterns concurrently
#                 async with ProcessPoolExecutor() as pool:
#                     deletion_tasks = []
#
#                     for pattern in patterns:
#                         for batch in self._get_file_batches(pattern):
#                             deletion_tasks.append(
#                                 self._delete_batch(pool, batch)
#                             )
#
#                     # Wait for all deletions to complete
#                     results = await asyncio.gather(*deletion_tasks)
#                     for batch_deleted in results:
#                         deleted_files.extend(batch_deleted)
#                         progress.update(task, advance=len(batch_deleted))
#
#             except Exception as e:
#                 logging.error(f"Error during file deletion: {e}")
#                 raise
#
#         return deleted_files
#
#     def _get_file_batches(self, pattern: str) -> Iterator[List[Path]]:
#         """Get files in batches using efficient directory scanning"""
#         batch = []
#
#         for entry in os.scandir(self.directory):
#             if len(batch) >= self.batch_size:
#                 yield batch
#                 batch = []
#
#             try:
#                 file_path = Path(entry.path)
#                 if file_path in self._seen_files:
#                     continue
#
#                 if entry.is_file() and file_path.match(pattern):
#                     batch.append(file_path)
#                     self._seen_files.add(file_path)
#
#             except (PermissionError, OSError) as e:
#                 logging.error(f"Error accessing {entry.path}: {e}")
#
#         if batch:
#             yield batch
#
#     async def _delete_batch(self, pool, file_batch: List[Path]) -> List[Path]:
#         """Delete a batch of files using process pool"""
#         deleted = []
#
#         loop = asyncio.get_event_loop()
#         futures = []
#
#         for file_path in file_batch:
#             futures.append(
#                 loop.run_in_executor(
#                     pool, self._delete_single_file, file_path
#                 )
#             )
#
#         results = await asyncio.gather(*futures)
#         deleted.extend([f for f in results if f is not None])
#
#         return deleted
#
#     @staticmethod
#     def _delete_single_file(file_path: Path) -> Path:
#         """Delete a single file with verification"""
#         try:
#             file_path.unlink()
#             if not file_path.exists():
#                 return file_path
#         except (PermissionError, OSError) as e:
#             logging.error(f"Error deleting {file_path}: {e}")
#         return None


from concurrent.futures import ProcessPoolExecutor, as_completed
import os
import logging
from pathlib import Path
from rich.progress import Progress
from typing import List, Iterator, Set


class FastFileDeleter:
    def __init__(self, directory: Path, batch_size: int = 1000):
        self.directory = directory
        self.batch_size = batch_size
        self._seen_files: Set[Path] = set()

    def delete_files_by_patterns(self, patterns: List[str]) -> List[Path]:
        if not isinstance(self.directory, Path):
            raise ValueError("Input directory must be a Path object")

        deleted_files = []

        with Progress() as progress:
            task = progress.add_task("[cyan]Deleting files...", total=None)

            try:
                with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
                    futures = []

                    # Submit deletion tasks in batches
                    for pattern in patterns:
                        for batch in self._get_file_batches(pattern):
                            futures.append(
                                executor.submit(self._delete_batch, batch)
                            )

                    # Process results as they complete
                    for future in as_completed(futures):
                        batch_deleted = future.result()
                        deleted_files.extend(batch_deleted)
                        progress.update(task, advance=len(batch_deleted))

            except Exception as e:
                logging.error(f"Error during file deletion: {e}")
                raise

        return deleted_files

    def _get_file_batches(self, pattern: str) -> Iterator[List[Path]]:
        """Get files in batches using efficient directory scanning"""
        batch = []

        for entry in os.scandir(self.directory):
            if len(batch) >= self.batch_size:
                yield batch
                batch = []

            try:
                file_path = Path(entry.path)
                if file_path in self._seen_files:
                    continue

                if entry.is_file() and file_path.match(pattern):
                    batch.append(file_path)
                    self._seen_files.add(file_path)

            except (PermissionError, OSError) as e:
                logging.error(f"Error accessing {entry.path}: {e}")

        if batch:
            yield batch

    @staticmethod
    def _delete_batch(file_batch: List[Path]) -> List[Path]:
        """Delete a batch of files"""
        deleted = []

        for file_path in file_batch:
            try:
                file_path.unlink()
                if not file_path.exists():
                    deleted.append(file_path)
            except (PermissionError, OSError) as e:
                logging.error(f"Error deleting {file_path}: {e}")

        return deleted





async def ffd(directory):
    residuals_patterns = [
        ".Xauthority-*", "snap.*", "*.log", "*.swp", "*.swo", "*~", ".#*",
        ".kate-swp", "*.o", "*.out", "*.a", "*.class", "*.pyc", "*.pyo",
        "_*pycache*_*/*", "recently-used.xbel", ".goutputstream-*",
        "thumbcache_*.db", "Thumbs.db", "*.dmp", "*.mdmp", "*.hdmp", "*.msi",
        "*.mst", "*.cab", "*.old", "*.bak", "desktop.ini", "ehthumbs.db",
        ".DS_Store", ".Trash-*", "*.tmp", "*.autosave", "*.~*", "*.part",
        ".git/*", ".svn/*", ".hg/*"
    ]
    # patterns = ["*.tmp", "*.log", "*.bak"]

    deleter = FastFileDeleter(directory)
    deleted_files = await deleter.delete_files_by_patterns(residuals_patterns)
    print(f"Deleted {len(deleted_files)} files")


def delete_files_by_patterns(directory: Path, patterns: List[str]) -> List[Path]:
    """Main function to delete files matching patterns"""
    deleter = FastFileDeleter(directory)
    return deleter.delete_files_by_patterns(patterns)


def main():
    app_version = "1.0"
    residuals_patterns = [
        ".Xauthority-*", "snap.*", "*.log", "*.swp", "*.swo", "*~", ".#*",
        ".kate-swp", "*.o", "*.out", "*.a", "*.class", "*.pyc", "*.pyo",
        "_*pycache*_*/*", "recently-used.xbel", ".goutputstream-*",
        "thumbcache_*.db", "Thumbs.db", "*.dmp", "*.mdmp", "*.hdmp", "*.msi",
        "*.mst", "*.cab", "*.old", "*.bak", "desktop.ini", "ehthumbs.db",
        ".DS_Store", ".Trash-*", "*.tmp", "*.autosave", "*.~*", "*.part",
        ".git/*", ".svn/*", ".hg/*"
    ]

    # Create Utilities instance first to initialize timestamp, and then the rest of the classes...
    utility = Utilities()
    file_system = FileSystemOperations()

    # greeting
    utility.printAscii(7, app_version, )

    # handle input string
    input_path = utility.validate_cli_directory()

    # ensure fdupes is installed, if not suggest how to install, display result
    utility.check_program("fdupes")

    # take dir path input string and convert to path object
    path_obj = file_system.convert_path_string_to_object(input_path)

    # ensure path is indeed an existing dir path
    file_system.ensure_valid_dir_path(path_obj)

    # get validity of input dir, print result
    utility.logging()
    logging.info(f"Successfully validated directory: {input_path}")

    # display input dir size
    dir_name = path_obj.name
    # rprint(f"Directory '{dir_name}' size: {utility.bytes2nice(file_system.get_dir_size(path_obj))} bytes")

    try:
        # path = Path("/path/to/large/directory")
        result = FileSystemOperations.get_dir_size(path_obj)

        if isinstance(result, tuple):
            # du was used
            size_bytes, human_size = result
            print(f"Directory size (du): {human_size} ({size_bytes:,} bytes)")
        else:
            # Python implementation was used
            print(f"Directory size: {utility.bytes2nice(result)} ({result:,} bytes)")
    except ValueError as e:
        print(f"Error: {e}")

    # delete OS residual files
    # asyncio.run(ffd(path_obj))
    deleted_files = delete_files_by_patterns(path_obj, residuals_patterns)

    # deduplicate files


    # delete empty subdirs


if __name__ == "__main__":
    main()

