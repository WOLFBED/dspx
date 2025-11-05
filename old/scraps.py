@staticmethod
    def get_dir_size1(dir_path: Path) -> int:
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


    @staticmethod
    def get_dir_size2(dir_path: Path) -> int:
        """
        Calculate total size of a directory using a generator-based approach with bounded memory usage.
        Uses os.scandir for performance while avoiding recursion.
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
        dirs_to_scan = collections.deque([dir_path])
        try:
            while dirs_to_scan:
                current_dir = dirs_to_scan.popleft()
                try:
                    # Process directory contents in chunks to limit memory usage
                    with os.scandir(current_dir) as it:
                        while True:
                            # Process entries in batches of 1000
                            chunk = list(itertools.islice(it, 1000))
                            if not chunk:
                                break
                            for entry in chunk:
                                try:
                                    if entry.is_symlink():
                                        continue
                                    if entry.is_file(follow_symlinks=False):
                                        total_size += entry.stat(follow_symlinks=False).st_size
                                    elif entry.is_dir(follow_symlinks=False):
                                        dirs_to_scan.append(Path(entry.path))
                                except (PermissionError, OSError) as e:
                                    print(f"Warning: Could not access {entry.path}: {e}",
                                          file=sys.stderr)
                                    continue
                except (PermissionError, OSError) as e:
                    print(f"Warning: Could not scan directory {current_dir}: {e}",
                          file=sys.stderr)
                    continue
        except Exception as e:
            raise ValueError(f"Error scanning directory structure: {e}")
        return total_size