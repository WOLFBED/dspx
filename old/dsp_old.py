"""
dsp :: data-store pruner
v 1.0

USAGE [directory path]


VERSION NEWS

    v 1.0 ...... Everything seems to work good.
    v 0.03 ..... New: better progress for delete_files_by_patterns()
                 New: all options removed!

"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import glob
from subprocess import run, PIPE
from alive_progress import alive_bar
import shutil
import signal
import subprocess
from datetime import datetime
import logging


def printAscii(code, string):
    match code:
        case 4:
            art = rf""" ______  _______  _____ 
 |     \ |______ |_____]
 |_____/ ______| |                 
dsp ~ data-store pruner ~ version {string}
"""
    print(art)


def ts_custom(format):
    """
    Directive .... Example ...... Description
       %a .... Wed .......... Weekday, short version, usually three characters in length
       %A .... Wednesday .... Weekday, full version
       %w .... 3 ............ Weekday as a number 0-6, 0 is Sunday
       %d .... 31 ........... Day of month 01-31
       %b .... Dec .......... Month name, short version, usually three characters in length
       %B .... December ..... Month name, full version
       %m .... 12 ........... Month as a number 01-12, January is 01
       %y .... 21 ........... Year, short version, without century (2021)
       %Y .... 2021 ......... Year, full version
       %H .... 17 ........... Hour 00-23 (24 hour format)
       %I .... 05 ........... Hour 00-12 (12 hour format)
       %p .... PM ........... AM/PM
       %M .... 35 ........... Minute 00-59
       %S .... 14 ........... Second 00-59
       %f .... 638745 ....... Microsecond 000000-999999
       %z .... +0530 ........ UTC offset
       %Z .... CST .......... Timezone
       %j .... 182 .......... Day number of year 001-366 (366 for leap year, 365 otherwise)
       %U .... 47 ........... Week number of year, Sunday as the first day of week, 00-53
       %W .... 51 ........... Week number of year, Monday as the first day of week, 00-53
       %c .... Tue .......... Dec 10 17:41:00 2019	Local version of date and time
       %x .... 12/10/19 ..... Local version of date (mm/dd/yy)
       %X .... 17:41:00 ..... Local version of time (hh:mm:ss)
    """
    now = datetime.now()
    toim = now.strftime(format)
    return toim

# Custom timestamp function
ahora = ts_custom("%d%m%Y%H%M%S%f")

# Custom error codes
ERROR_DIRECTORY_NOT_FOUND = 2
ERROR_NOT_A_DIRECTORY = 3
ERROR_PERMISSION_DENIED = 4
ERROR_GENERAL = 5

def configure_logging(log_file=f"dsp_{ahora}.log", log_level=logging.DEBUG):
    """
    Configures logging with dynamic output modes.

    Parameters:
    - log_file (str): Path to the log file.
    - log_level (int): Logging level (e.g., logging.INFO, logging.ERROR).
    - output_mode (str): 'file', 'console', or 'both'.
    """
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


def deduplicate(timstimp, directory):
    """
    Handle fdupes deduplication with Ctrl+C interrupt handling

    -r --recurse
        For every directory given follow subdirectories encountered within.

    -1 --sameline
        List each set of matches on a single line.

    -m --summarize
        Summarize duplicate file information.

    -d --delete
        Prompt user for files to preserve, deleting all others (see CAVEATS below).

    -N --noprompt
        When used together with --delete, preserve the first file in each set of duplicates and delete the others without prompting the user.

    -l --log=LOGFILE
        Log file deletion choices to LOGFILE.
    """
    fdupes_log_file = f"dsp_fdupes_{timstimp}.log"
    command = [
        "fdupes",
        "-r",
        "-1",
        "-d",
        "-N",
        f"--log={fdupes_log_file}",
        f"{directory}"
    ]
    process = None
    print(f"Deduplication process...")
    try:
        # Start the process
        process = subprocess.Popen(command)
        # Wait for it to complete
        process.wait()
    except KeyboardInterrupt:
        # If Ctrl+C is pressed and process exists, terminate it
        if process and process.poll() is None:
            print("\nCtrl+C detected, terminating fdupes...")
            process.terminate()
            try:
                # Wait for process to terminate gracefully
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # If process doesn't terminate in time, kill it
                print("Force killing fdupes process...")
                process.kill()
        print("\nDeduplication interrupted by user")
    except Exception as e:
        print(f"Deduplication failed: {str(e)}")
        # If process is still running, terminate it
        if process and process.poll() is None:
            process.terminate()


def find_empty_subdirs(directory):
    empty_subdirs = []
    for root, dirs, files in os.walk(directory):
        # Check if the current directory is empty of files
        if not files:
            # Check if any subdirectory contains files, indicating the current directory is not truly empty
            subdir_empty = all(
                len(os.listdir(os.path.join(root, d))) == 0 for d in dirs
            )
            if subdir_empty:
                empty_subdirs.append(root)
    # Remove subdirectories already included in higher-level empty directories
    pruned_empty_subdirs = []
    for subdir in empty_subdirs:
        if not any(subdir.startswith(other + os.sep) for other in empty_subdirs if subdir != other):
            configure_logging()
            logging.info(f"Found empty directory: {subdir}")
            pruned_empty_subdirs.append(subdir)
    empty_dirs_count = len(pruned_empty_subdirs)
    return pruned_empty_subdirs, empty_dirs_count


def delete_empty_subdirs(directories_list):
    def do_the_thing(directories_list):
        for directory in directories_list:
            try:
                shutil.rmtree(directory)
                logging.info(f"Deleted empty directory: {directory}")
            except OSError as e:
                logging.error(f"Error deleting empty directory {directory}: {e}")
    while True:
        confirm = input("\nDo you want to delete these directories? (y/N): ").strip().lower()
        if confirm == 'y':
            do_the_thing(directories_list)
            break
        elif confirm == 'n':
            logging.error(f"Empty directories found >>> None deleted >>> Continuing...")
            break
        else:
            logging.error(f"Invalid input. Please enter 'y' or 'n'.")


def delete_files_by_patterns(directory, patterns):
    files_to_delete = set()  # Use set to avoid duplicates
    total_matches = 0
    print("Searching for OS residual files...")
    # Use ThreadPoolExecutor for parallel pattern matching
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        def find_matches(pattern):
            full_pattern = os.path.join(directory, '**', pattern)
            matches = [f for f in glob.glob(full_pattern, recursive=True) if os.path.isfile(f)]
            nonlocal total_matches
            total_matches += len(matches)
            return matches
        # Process patterns in parallel with a progress spinner
        with alive_bar(len(patterns), title='(Patience!)', spinner='dots_waves') as bar:
            pattern_matches = []
            for matches in executor.map(find_matches, patterns):
                pattern_matches.append(matches)
                bar()  # Update progress bar
        for matches in pattern_matches:
            files_to_delete.update(matches)
    if files_to_delete:
        print(f"\nFound {len(files_to_delete)} files to process:")
        for file_path in files_to_delete:
            print(file_path)
        confirm = input("\nDo you want to delete these files? (y/N): ").strip().lower()
        if confirm == 'y':
            # Delete files in parallel with progress bar
            with alive_bar(len(files_to_delete), title='Deleting files') as bar:
                def delete_file(file_path):
                    try:
                        os.remove(file_path)
                        bar()  # Update progress bar
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")
                list(executor.map(delete_file, files_to_delete))
        else:
            print("\nDeletion canceled.")
    else:
        print("No matching files found.  Quite clean!\n")


def validate_directory(path_str):
    path = Path(path_str)
    configure_logging()
    logging.info(f"Validating path: {path}")
    if not path.exists():
        configure_logging()
        logging.error(f"Directory not found: {path}")
        raise argparse.ArgumentTypeError(f"Error [{ERROR_DIRECTORY_NOT_FOUND}]: The path '{path}' does not exist.")
    if not path.is_dir():
        configure_logging()
        logging.error(f"Not a directory: {path}")
        raise argparse.ArgumentTypeError(f"Error [{ERROR_NOT_A_DIRECTORY}]: The path '{path}' is not a directory.")
    if not os.access(path, os.R_OK):
        configure_logging()
        logging.error(f"Permission denied: {path}")
        raise argparse.ArgumentTypeError(f"Error [{ERROR_PERMISSION_DENIED}]: The directory '{path}' is not accessible.")
    configure_logging()
    logging.info(f"Path validated: {path.resolve()}")
    return path.resolve()


def process_files(directory, keep_newer):
    files = sorted(directory.iterdir(), key=lambda x: x.stat().st_mtime, reverse=keep_newer)
    configure_logging()
    logging.info(f"Processing files in directory: {directory}, keep newer: {keep_newer}")
    # Example logic: Print or log the files based on the order
    for file in files:
        if file.is_file():
            configure_logging()
            logging.info(f"File: {file}, Last Modified: {time.ctime(file.stat().st_mtime)}")
            print(f"File: {file}, Last Modified: {time.ctime(file.stat().st_mtime)}")


def delete_empty_subdirs(directories_list):
    def do_the_thing(directories_list):
        for directory in directories_list:
            try:
                shutil.rmtree(directory)
                logging.info(f"Deleted empty directory: {directory}")
            except OSError as e:
                logging.error(f"Error deleting empty directory {directory}: {e}")
    while True:
        confirm = input("\nDo you want to delete these directories? (y/N): ").strip().lower()
        if confirm == 'y':
            do_the_thing(directories_list)
            break
        elif confirm == 'n':
            logging.error(f"Empty directories found >>> None deleted >>> Continuing...")
            break
        else:
            logging.error(f"Invalid input. Please enter 'y' or 'n'.")


def main(art_case, app_version, patterns):
    printAscii(art_case, app_version)

    parser = argparse.ArgumentParser(
        description="dsp ~ Data-Store Pruner :: deletes empty subdirs and residual OS files, and deduplicates everything else in the given dir.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "directory",
        type=validate_directory,
        help="Path to the directory to process."
    )

    args = parser.parse_args()

    configure_logging()
    logging.info(f"Successfully validated directory: {args.directory}")

    # delete OS residual files
    delete_files_by_patterns(args.directory, patterns)

    # deduplicate files
    deduplicate(ahora, args.directory)

    # delete empty subdirs
    print(f"Assessing empty subdirectories...")
    empty_dirs, empty_dirs_total_count = find_empty_subdirs(args.directory)
    configure_logging()
    logging.info(f"Found {empty_dirs_total_count} empty subdirectories")
    print(f"Empty subdirectories found: {empty_dirs}")
    delete_empty_subdirs(empty_dirs)


if __name__ == "__main__":
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
    try:
        main(4, f"{app_version}", residuals_patterns)
    except argparse.ArgumentTypeError as e:
        configure_logging()
        logging.critical(e)
        sys.exit(ERROR_GENERAL)
    except Exception as e:
        configure_logging()
        logging.critical(f"Unexpected error: {e}")
        sys.exit(ERROR_GENERAL)