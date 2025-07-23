from pathlib import Path
import sys
from rich import print as rprint
import os
import shutil
import platform
import subprocess
from datetime import datetime
import logging


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
                art = rf"""[blue] ╺┳┓┏━┓┏━┓[/blue]  [deep_sky_blue1]╱[/deep_sky_blue1] 
 [blue] ┃┃┗━┓┣━┛[/blue] [deep_sky_blue1]╱[/deep_sky_blue1] [yellow]dsp ~ data-store pruner ~ version {string}[/yellow]
[blue] ╺┻┛┗━┛╹[/blue]  [deep_sky_blue1]╱[/deep_sky_blue1]
[orange1]▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔[/orange1]"""
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
    def get_dir_size(dir_path: Path) -> int:
        """
        Calculate total size of a directory recursively, excluding symlinks.
        Uses os.scandir for maximum performance.
        Args:
            dir_path: Path object pointing to the directory
        Returns:
            Total size in bytes
        Raises:
            ValueError: If the path is not a valid directory
        """
        if not isinstance(dir_path, Path):
            raise ValueError(f"Expected Path object, got {type(dir_path).__name__}")
        if not dir_path.is_dir():
            raise ValueError(f"Path {dir_path} is not a directory")
        total_size = 0
        try:
            # Using os.scandir which is significantly faster than os.walk or Path.rglob
            with os.scandir(dir_path) as entries:
                for entry in entries:
                    try:
                        # Skip symlinks to avoid infinite loops
                        if entry.is_symlink():
                            continue
                        # For files, add size
                        if entry.is_file(follow_symlinks=False):
                            total_size += entry.stat(follow_symlinks=False).st_size
                        # For directories, recurse
                        elif entry.is_dir(follow_symlinks=False):
                            total_size += FileSystemOperations.get_dir_size(Path(entry.path))
                    except (PermissionError, OSError) as e:
                        print(f"Warning: Could not access {entry.path}: {e}", file=sys.stderr)
                        continue
        except (PermissionError, OSError) as e:
            raise ValueError(f"Could not scan directory {dir_path}: {e}")
        return total_size



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

    # take dir path input string and convert to path object
    path_obj = file_system.convert_path_string_to_object(input_path)

    # ensure path is indeed an existing dir path
    file_system.ensure_valid_dir_path(path_obj)

    # get validity of input dir, print result
    utility.logging()
    logging.info(f"Successfully validated directory: {input_path}")

    # display input dir size
    dir_name = path_obj.name
    rprint(f"Directory '{dir_name}' size: {utility.bytes2nice(file_system.get_dir_size(path_obj))} bytes")

    # ensure fdupes is installed, if not suggest how to install, display result
    utility.check_program("fdupes")

    # delete OS residual files


    # deduplicate files


    # delete empty subdirs


if __name__ == "__main__":
    main()