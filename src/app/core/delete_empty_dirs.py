#!/usr/bin/env python3
import os
import sys
import uuid
import errno
from pathlib import Path
from typing import List, Optional, Iterable

# ---------------------- ANSI color helpers ----------------------

CSI = "\033["
RESET = CSI + "0m"
BOLD = CSI + "1m"
GREEN = CSI + "32m"
YELLOW = CSI + "33m"
RED = CSI + "31m"
CYAN = CSI + "36m"

def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# ---------------------- Class Definition ------------------------

class AtomicEmptyDirPurger:
    """
    Atomic-ish purge of empty directories using:
      - Post-order traversal
      - Rename-to-quarantine
      - Optional fsync barriers (O_DIRECTORY)
      - Optional Btrfs-specific syncs
    """

    def __init__(
            self,
            root: Path,
            *,
            dry_run: bool = False,
            verbose: bool = False,
            btrfs: bool = False,
            sync_enabled: bool = True,
            lock_name: str = ".purge.lock"
    ):
        self.root = root.resolve()
        self.dry = dry_run
        self.verbose = verbose
        self.btrfs = btrfs
        self.sync_enabled = sync_enabled
        self.lock_name = lock_name
        self.lock_dir = self.root / lock_name

        self.renamed: List[Path] = []
        self.deleted: List[Path] = []

        if not self.root.exists() or not self.root.is_dir():
            raise ValueError(f"Root path does not exist or is not a directory: {self.root}")

    # ---------------------- Lock Mechanism ----------------------

    def acquire_lock(self):
        if self.dry:
            if self.verbose:
                eprint(f"DRY-RUN: would create lock directory {self.lock_dir}")
            return

        try:
            os.mkdir(str(self.lock_dir))
        except FileExistsError:
            raise RuntimeError(f"Lock exists: {self.lock_dir}")
        except PermissionError:
            raise RuntimeError(f"No permission to create lock: {self.lock_dir}")

    def release_lock(self):
        if self.dry:
            if self.verbose:
                eprint(f"DRY-RUN: would remove lock {self.lock_dir}")
            return

        try:
            if self.lock_dir.exists():
                self.lock_dir.rmdir()
        except Exception:
            pass

    # ---------------------- Low-level helpers ----------------------

    def _open_dir_fd(self, path: Path) -> Optional[int]:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        try:
            return os.open(str(path), flags)
        except Exception:
            return None

    def _fsync_fd(self, fd: int) -> bool:
        try:
            os.fsync(fd)
            return True
        except Exception:
            return False

    def _sync_path(self, path: Path):
        fd = self._open_dir_fd(path)
        if fd is None:
            if self.verbose:
                eprint("cannot open directory for fsync:", path)
            return
        ok = self._fsync_fd(fd)
        if self.verbose:
            eprint("fsync", "ok:" if ok else "failed:", path)
        try:
            os.close(fd)
        except Exception:
            pass

    # ---------------------- Phase 1: Rename ----------------------

    def phase1_rename_empty(self):
        """
        Post-order scan, rename empty directories to {name}.purge.<hex>.
        """
        for dirpath, dirnames, filenames in os.walk(str(self.root), topdown=False):
            p = Path(dirpath)

            if p.name == self.lock_name:
                continue
            if p == self.root:
                continue

            # empty?
            if not dirnames and not filenames:
                suffix = f".purge.{uuid.uuid4().hex[:8]}"
                new = p.with_name(p.name + suffix)

                if self.dry:
                    if self.verbose:
                        eprint("DRY: would rename", p, "->", new)
                    self.renamed.append(new)
                    continue

                # check emptiness just before rename
                try:
                    if os.listdir(str(p)):
                        continue
                except OSError:
                    continue

                try:
                    os.rename(str(p), str(new))
                    self.renamed.append(new)
                    if self.verbose:
                        eprint("renamed:", p, "->", new)
                except OSError:
                    if self.verbose:
                        eprint("failed to rename:", p)

    # ---------------------- Phase 2: Delete ----------------------

    def phase2_delete(self):
        """
        Delete renamed directories in deepest-first order.
        """
        ordered = sorted(self.renamed, key=lambda p: (-len(p.parts), str(p)))

        for d in ordered:
            if self.dry:
                if self.verbose:
                    eprint("DRY: would remove", d)
                self.deleted.append(d)
                continue

            try:
                d.rmdir()
                self.deleted.append(d)
                if self.verbose:
                    eprint("removed:", d)
            except OSError:
                if self.verbose:
                    eprint("failed to remove:", d)

    # ---------------------- Sync barriers ----------------------

    def sync_barriers(self):
        if self.dry or not self.sync_enabled:
            return

        if self.btrfs:
            if self.verbose:
                eprint("Btrfs: fsync quarantined dirs + global sync")
            for d in self.renamed:
                self._sync_path(d)
            try:
                os.sync()
            except Exception:
                pass
        else:
            parents = {d.parent for d in self.renamed}
            if self.verbose:
                eprint("syncing parent dirs of renamed items")
            for p in sorted(parents, key=lambda x: (len(x.parts), str(x))):
                self._sync_path(p)
            try:
                os.sync()
            except Exception:
                pass

    # ---------------------- Final sync ----------------------

    def final_sync(self):
        if self.dry or not self.sync_enabled:
            return
        try:
            if self.verbose:
                eprint("final os.sync()")
            os.sync()
        except Exception:
            pass

    # ---------------------- Reporting ----------------------

    def print_tree(self):
        if not self.renamed and not self.deleted:
            print(color("(nothing to do)", CYAN))
            return

        allp = set(self.renamed) | set(self.deleted)
        sorted_paths = sorted(allp, key=lambda p: (len(p.parts), str(p)))

        for p in sorted_paths:
            rel = p.relative_to(self.root)
            indent = "  " * (len(rel.parts) - 1)
            if p in self.deleted:
                print(f"{indent}{color('removed', GREEN)}: {rel}")
            elif p in self.renamed:
                print(f"{indent}{color('quarantined', YELLOW)}: {rel}")

    # ---------------------- Public API ----------------------

    def run(self):
        try:
            self.acquire_lock()
            self.phase1_rename_empty()
            self.sync_barriers()
            self.phase2_delete()
            self.final_sync()
        finally:
            self.release_lock()

        return self.renamed, self.deleted


# EXAMPLE USAGE:

# from pathlib import Path
# from purge_class import AtomicEmptyDirPurger
#
# purger = AtomicEmptyDirPurger(
#     Path("/my/tree"),
#     dry_run=False,
#     verbose=True,
#     btrfs=True,
#     sync_enabled=True,
# )
#
# renamed, deleted = purger.run()
# purger.print_tree()



# OR CLI STYLE USAGE:

# if __name__ == "__main__":
#     import argparse
#
#     parser = argparse.ArgumentParser()
#     parser.add_argument("root", type=Path)
#     parser.add_argument("--dry-run", action="store_true")
#     parser.add_argument("--verbose", action="store_true")
#     parser.add_argument("--btrfs", action="store_true")
#     parser.add_argument("--no-sync", action="store_true")
#
#     args = parser.parse_args()
#
#     purger = AtomicEmptyDirPurger(
#         args.root,
#         dry_run=args.dry_run,
#         verbose=args.verbose,
#         btrfs=args.btrfs,
#         sync_enabled=not args.no_sync
#     )
#
#     purger.run()
#     purger.print_tree()















# //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



# #!/usr/bin/env python3
# """
# purge_empty_dirs.py
#
# Two-phase purge of empty subdirectories:
#   Phase 1: post-order scan, rename empty dirs -> {name}.purge.<hex>
#   Phase 2: after all renames succeed (and optionally fsync barriers),
#            remove the quarantined directories (they must be empty).
#
# Features:
#  - CLI with argparse
#  - Colored, hierarchical tree-printing
#  - File-descriptor-level sync (O_DIRECTORY + os.fsync) where available
#  - Optional Btrfs extra sync behavior (--btrfs)
#  - Dry-run mode and verbose logging
# """
#
# from __future__ import annotations
# import os
# import sys
# import argparse
# import uuid
# import errno
# from pathlib import Path
# from typing import List, Tuple, Optional
#
# # ANSI color helpers (no external deps)
# CSI = "\033["
# RESET = CSI + "0m"
# BOLD = CSI + "1m"
# GREEN = CSI + "32m"
# YELLOW = CSI + "33m"
# RED = CSI + "31m"
# CYAN = CSI + "36m"
#
# def color(text: str, code: str) -> str:
#     return f"{code}{text}{RESET}"
#
# def eprint(*args, **kwargs):
#     print(*args, file=sys.stderr, **kwargs)
#
# # --- Low-level helpers ----------------------------------------------------
#
# def open_dir_fd(path: Path):
#     """
#     Return an open file descriptor for the directory (O_DIRECTORY) if possible,
#     otherwise return None.
#     Caller must close(fd) after use.
#     """
#     flags = 0
#     if hasattr(os, "O_DIRECTORY"):
#         flags |= os.O_RDONLY | os.O_DIRECTORY
#     else:
#         # Fallback: open read-only file descriptor (may fail on Windows)
#         flags |= os.O_RDONLY
#     try:
#         return os.open(str(path), flags)
#     except Exception:
#         return None
#
# def fsync_dir_fd(fd: int) -> bool:
#     """
#     Call os.fsync(fd) on dir fd. Return True if succeeded.
#     """
#     try:
#         os.fsync(fd)
#         return True
#     except PermissionError:
#         # On some systems / mount combos, fsync on directory may be denied
#         return False
#     except OSError:
#         return False
#
# def safe_rename(src: Path, dst: Path) -> bool:
#     """
#     Atomic rename using os.rename; returns True on success.
#     """
#     try:
#         os.rename(str(src), str(dst))
#         return True
#     except OSError:
#         return False
#
# def safe_rmdir(path: Path) -> bool:
#     try:
#         path.rmdir()
#         return True
#     except OSError:
#         return False
#
# # --- Tree printing -------------------------------------------------------
#
# def print_tree_root(root: Path, renamed: List[Path], deleted: List[Path], dry_run: bool):
#     """
#     Print a small hierarchical view showing renamed and deleted directories.
#     For longer trees we print paths with indentation computed from depth.
#     """
#     # combine and sort
#     all_paths = set(renamed) | set(deleted)
#     if not all_paths:
#         print(color("(no empty subdirectories found)", CYAN))
#         return
#
#     # sort by depth then lexicographically
#     sorted_paths = sorted(all_paths, key=lambda p: (len(p.parts), str(p)))
#     for p in sorted_paths:
#         rel = p.relative_to(root)
#         indent = "  " * (len(rel.parts) - 1) if len(rel.parts) > 0 else ""
#         label = p.name
#         if p in deleted:
#             print(f"{indent}{color('removed', GREEN)}: {label}    {color(str(rel), BOLD)}")
#         elif p in renamed:
#             print(f"{indent}{color('quarantined', YELLOW)}: {label}    {color(str(rel), BOLD)}")
#         else:
#             print(f"{indent}{label}")
#
# # --- Main algorithm ------------------------------------------------------
#
# def find_and_rename_empty_dirs(root: Path, lock_name: str, dry_run: bool, verbose: bool) -> List[Path]:
#     """
#     Phase 1: post-order walk, rename empty directories to .purge.<hex> suffix.
#     Returns list of renamed Path objects (absolute).
#     """
#     renamed = []
#     root = root.resolve()
#
#     # Use os.walk topdown=False (post-order)
#     for dirpath, dirnames, filenames in os.walk(str(root), topdown=False):
#         p = Path(dirpath)
#         # Skip the lock directory itself
#         if p.name == lock_name:
#             continue
#
#         # Skip root itself if it is the lock or special
#         # If we want to avoid purging the root, we simply don't rename it even if empty
#         if p == root:
#             continue
#
#         # if directory is empty (no subdirs, no files), rename to quarantine
#         if not dirnames and not filenames:
#             suffix = f".purge.{uuid.uuid4().hex[:8]}"
#             new_name = p.with_name(p.name + suffix)
#             if dry_run:
#                 if verbose:
#                     eprint("DRY-RUN: would rename", p, "->", new_name)
#                 renamed.append(new_name)  # show intent, but path doesn't actually exist
#                 continue
#
#             # double-check emptiness immediately before rename:
#             try:
#                 # safest check using os.listdir which reads the directory contents
#                 if os.listdir(str(p)):
#                     # non-empty now
#                     continue
#             except OSError:
#                 # If cannot list, skip
#                 continue
#
#             ok = safe_rename(p, new_name)
#             if ok:
#                 renamed.append(new_name)
#                 if verbose:
#                     eprint("renamed:", p, "->", new_name)
#             else:
#                 if verbose:
#                     eprint("failed to rename (skipping):", p)
#
#     return renamed
#
# def purge_renamed(renamed: List[Path], dry_run: bool, verbose: bool) -> List[Path]:
#     """
#     Phase 2: delete the quarantined directories (they should be empty).
#     Return list of actually deleted directories.
#     """
#     deleted = []
#     # Delete in reverse order (deepest first) to be safe
#     for d in sorted(renamed, key=lambda p: (-len(p.parts), str(p))):
#         if dry_run:
#             if verbose:
#                 eprint("DRY-RUN: would remove", d)
#             deleted.append(d)
#             continue
#         ok = safe_rmdir(d)
#         if ok:
#             deleted.append(d)
#             if verbose:
#                 eprint("removed:", d)
#         else:
#             if verbose:
#                 eprint("failed to remove:", d)
#     return deleted
#
# def barrier_sync_dirs(dirs: List[Path], verbose: bool):
#     """
#     Given a list of directory Paths, attempt to open fd + fsync each one.
#     Close fds after sync. Best-effort.
#     """
#     for d in dirs:
#         fd = open_dir_fd(d)
#         if fd is None:
#             if verbose:
#                 eprint("could not open dir for fsync:", d)
#             continue
#         if fsync_dir_fd(fd):
#             if verbose:
#                 eprint("fsynced dir:", d)
#         else:
#             if verbose:
#                 eprint("fsync failed for dir:", d)
#         try:
#             os.close(fd)
#         except Exception:
#             pass
#
# # --- CLI / Orchestration -----------------------------------------------
#
# def main(argv=None):
#     parser = argparse.ArgumentParser(
#         description="Atomically purge empty subdirectories (rename-then-delete)."
#     )
#     parser.add_argument("root", type=Path, help="Root directory to scan (will not remove the root itself).")
#     parser.add_argument("--dry-run", action="store_true", help="Show what would be done, do not modify filesystem.")
#     parser.add_argument("--btrfs", action="store_true", help="Apply extra Btrfs-friendly sync barriers.")
#     parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging.")
#     parser.add_argument("--no-sync", action="store_true", help="Skip explicit fsync/os.sync barriers (faster, less durable).")
#     args = parser.parse_args(argv)
#
#     root: Path = args.root.resolve()
#     if not root.exists() or not root.is_dir():
#         eprint(color("Error:", RED), "root must be an existing directory")
#         sys.exit(2)
#
#     lock_name = ".purge.lock"
#     lock_dir = root / lock_name
#
#     # Acquire lock using mkdir (atomic)
#     try:
#         if args.dry_run:
#             if args.verbose:
#                 eprint("DRY-RUN: would create lock directory", lock_dir)
#         else:
#             os.mkdir(str(lock_dir))
#     except FileExistsError:
#         eprint(color("Error:", RED), f"Lock directory exists: {lock_dir} — another run may be active. Aborting.")
#         sys.exit(3)
#     except PermissionError:
#         eprint(color("Error:", RED), f"Permission denied creating lock: {lock_dir}")
#         sys.exit(4)
#
#     renamed = []
#     deleted = []
#     try:
#         # Phase 1: find & rename empties
#         renamed = find_and_rename_empty_dirs(root, lock_name, args.dry_run, args.verbose)
#
#         # If user requested Btrfs-specific durability steps, attempt to apply them
#         if not args.no_sync:
#             if args.btrfs:
#                 # Btrfs: fsync the directories we renamed (metadata), then os.sync()
#                 if args.verbose:
#                     eprint("Btrfs mode: issuing per-dir fsyncs, then os.sync()")
#                 barrier_sync_dirs(renamed, args.verbose)
#                 if not args.dry_run:
#                     try:
#                         os.sync()
#                     except Exception:
#                         if args.verbose:
#                             eprint("os.sync() failed or not supported")
#             else:
#                 # Generic path: fsync parent directories of the renamed dirs
#                 parents = sorted({d.parent for d in renamed}, key=lambda p: (len(p.parts), str(p)))
#                 barrier_sync_dirs(parents, args.verbose)
#                 if not args.dry_run:
#                     try:
#                         os.sync()
#                     except Exception:
#                         if args.verbose:
#                             eprint("os.sync() failed or not supported")
#
#         # Phase 2: delete quarantined directories
#         deleted = purge_renamed(renamed, args.dry_run, args.verbose)
#
#         # Final barrier for durability if requested
#         if not args.no_sync and not args.dry_run:
#             if args.verbose:
#                 eprint("final sync barrier (os.sync())")
#             try:
#                 os.sync()
#             except Exception:
#                 if args.verbose:
#                     eprint("os.sync() failed or not supported")
#
#         # Print summary tree
#         print_tree_root(root, renamed, deleted, args.dry_run)
#
#     finally:
#         # Release lock
#         try:
#             if args.dry_run:
#                 if args.verbose:
#                     eprint("DRY-RUN: would remove lock directory", lock_dir)
#             else:
#                 # lock_dir may be empty; remove if exists
#                 if lock_dir.exists() and lock_dir.is_dir():
#                     try:
#                         lock_dir.rmdir()
#                     except OSError:
#                         # if cannot remove (non-empty or changed) ignore
#                         pass
#         except Exception:
#             pass
#
# if __name__ == "__main__":
#     main()
