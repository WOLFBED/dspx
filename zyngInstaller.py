#!/usr/bin/env python3
"""
enhanced_python_installer_v3
Modified to:
 - Fetch latest GitHub release instead of git clone
 - Extract archive and continue with original workflow
 - zyngInstaller should exclude installing programs from repos, this should be in the install.sh script
"""

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
import json
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def eprint(*a, **k):
    """Print messages to standard error."""
    print(*a, file=sys.stderr, **k)


def run(cmd, check=True, capture=False, env=None):
    """
    Run a subprocess command with optional output capture.

    Parameters
    ----------
    cmd:
        Command to execute, either as a list/tuple of arguments or a shell-like string.
    check:
        If True, raise CalledProcessError on non-zero exit code.
    capture:
        If True, capture stdout and stderr and return them in the CompletedProcess.
    env:
        Optional environment dict to pass to subprocess.run().

    Returns
    -------
    subprocess.CompletedProcess
        The completed process object.
    """
    if isinstance(cmd, (list, tuple)):
        pass
    else:
        cmd = cmd.split()
    return subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        env=env
    )


def ensure_dir(p: Path, exist_ok=True):
    """
    Ensure that a directory exists, creating parent directories as needed.

    Parameters
    ----------
    p:
        Path of the directory to create.
    exist_ok:
        Passed through to Path.mkdir(); if False, raising on existing directory.

    Returns
    -------
    Path
        The expanded, ensured directory path.
    """
    p = Path(p).expanduser()
    p.mkdir(parents=True, exist_ok=exist_ok)
    return p


def sha256sum(path: Path):
    """
    Compute the SHA256 checksum of a file.

    Parameters
    ----------
    path:
        Path to the file to hash.

    Returns
    -------
    str
        Hex-encoded SHA256 digest of the file contents.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# -------------------------------------------------------------
# Installer Class
# -------------------------------------------------------------
class Installer:
    """High-level orchestrator for installing a Python application from a release archive."""

    def __init__(self, cfg_path: Path, args):
        """
        Initialize the installer from a TOML configuration file and CLI arguments.

        Parameters
        ----------
        cfg_path:
            Path to the TOML configuration file.
        args:
            Parsed argparse.Namespace containing CLI options.
        """
        self.args = args
        self.cfg_path = cfg_path.expanduser()
        self.load_config()
        self.tmpdir = Path(tempfile.mkdtemp(prefix="installer_"))
        self.appname = self.config["name"]
        self.version = self.config["version"]
        self.install_root = Path(
            self.config.get("default_install_root", "~/.local/share/" + self.appname + "-installs")
        ).expanduser()

        if args.install_root:
            self.install_root = Path(args.install_root).expanduser()

        ensure_dir(self.install_root)
        self.versioned_dir = self.install_root / f"{self.appname}-{self.version}"
        self.current_symlink = self.install_root / f"{self.appname}-current"
        self.archives_dir = self.install_root / "archives"
        ensure_dir(self.archives_dir)

        self.local_bin = Path("~/.local/bin").expanduser()
        ensure_dir(self.local_bin)

        self.source_root = None
        self.vpython = sys.executable

    def load_config(self):
        """
        Load and validate the installer configuration from disk.

        Raises
        ------
        SystemExit
            If the configuration file is missing or required keys are absent.
        """
        if not self.cfg_path.exists():
            raise SystemExit(f"Config file not found: {self.cfg_path}")
        with open(self.cfg_path, "rb") as f:
            self.config = tomllib.load(f)

        for key in ("name", "version", "source"):
            if key not in self.config:
                raise SystemExit(f"Missing required config key: {key}")

        self.source_cfg = self.config["source"]

    # -------------------------------------------------------------
    # Fetch Latest GitHub Release (NEW)
    # -------------------------------------------------------------
    def fetch_latest_github_release(self, repo: str) -> Path:
        """
        Download the newest GitHub release archive for a repository.

        Parameters
        ----------
        repo:
            Repository in the form ``'OWNER/REPO'``.

        Returns
        -------
        Path
            Local filesystem path to the downloaded archive.

        Raises
        ------
        SystemExit
            If the release has no assets or no suitable archive asset.
        """
        api = f"https://api.github.com/repos/{repo}/releases/latest"
        print(f"[+] querying GitHub releases: {api}")

        req = urllib.request.Request(api, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req) as r:
            meta = json.load(r)

        assets = meta.get("assets", [])
        if not assets:
            raise SystemExit("No assets found in the latest GitHub release.")

        # Choose an archive asset
        archive = None
        for a in assets:
            name = a["name"].lower()
            if name.endswith((".zip", ".tar.gz", ".tgz", ".tar.xz")):
                archive = a
                break

        if not archive:
            raise SystemExit("No installable archive asset found in the latest release.")

        url = archive["browser_download_url"]
        dest = self.tmpdir / archive["name"]

        print(f"[+] downloading release asset: {url}")
        urllib.request.urlretrieve(url, dest)

        print(f"[+] downloaded to: {dest}")
        return dest

    # -------------------------------------------------------------
    # Required App Logic (no package manager usage)
    # -------------------------------------------------------------
    def _get_required_apps(self) -> list[str]:
        """
        Resolve the list of required external applications from the config.

        Returns
        -------
        list[str]
            List of application names that must be present on PATH.
        """
        section = self.config.get("required_apps") or {}
        if not isinstance(section, dict):
            return []
        apps = section.get("apps") or section.get("name") or []
        if isinstance(apps, str):
            apps = [apps]
        return [a for a in apps if isinstance(a, str) and a.strip()]

    def ensure_required_apps(self):
        """
        Check that required external apps are present on PATH.

        NOTE: This does not install anything via a package manager.
        Any installation of system packages should be handled by
        install.sh or similar scripts.

        Raises
        ------
        SystemExit
            If required applications are missing.
        """
        required = self._get_required_apps()
        if not required:
            return

        print("[+] Checking required applications …")
        missing = [a for a in required if not shutil.which(a)]

        if not missing:
            print("  - all required applications are present")
            return

        eprint("[!] Missing required applications:")
        for app in missing:
            eprint(f"    - {app}")
        eprint("[!] Please install the missing applications using your system package manager")
        eprint("    (typically from install.sh) and re-run the installer.")
        raise SystemExit("Unmet required applications.")

    # -------------------------------------------------------------
    # Source Preparation (MODIFIED)
    # -------------------------------------------------------------
    def prepare_source(self):
        """
        Fetch and unpack the application source according to the configuration.

        For ``type="git"`` this downloads the latest GitHub release archive.
        For ``type="url"`` or ``"archive"`` this downloads or copies the given location,
        verifies the checksum if provided, and extracts the archive.

        Returns
        -------
        Path
            Path to the extracted source root directory.

        Raises
        ------
        SystemExit
            If the source type is unknown or checksum verification fails.
        """
        stype = self.source_cfg.get("type", "git")
        loc = self.source_cfg["location"]

        print(f"[+] preparing source (type={stype})")

        # if stype == "git":
        #     # Now: fetch latest GitHub release instead of git clone
        #     archive = self.fetch_latest_github_release(loc)
        #     return self.extract_archive(archive)
        if stype == "git":
            # old bit where it does git clone etc.
            return self.clone_git(loc, self.source_cfg.get("ref"))

        elif stype in ("url", "archive"):
            path = self.download_or_copy(loc)
            expected_sha = self.source_cfg.get("sha256")
            if expected_sha:
                print("  - verifying SHA256 …")
                actual = sha256sum(path)
                if actual.lower() != expected_sha.lower():
                    raise SystemExit("SHA256 mismatch")
                print("  - checksum OK")
            return self.extract_archive(path)

        else:
            raise SystemExit(f"Unknown source type: {stype}")

    def clone_git(self, url, ref=None):
        git_bin = shutil.which("git")
        if not git_bin:
            raise SystemExit("git not found; required for git source type.")
        clone_dir = self.tmpdir / "src"
        print(f"  - git clone {url} → {clone_dir}")
        run([git_bin, "clone", "--depth", "1", url, str(clone_dir)])
        if ref:
            try:
                run([git_bin, "-C", str(clone_dir), "fetch", "--depth", "1", "origin", ref])
                run([git_bin, "-C", str(clone_dir), "checkout", ref])
            except subprocess.CalledProcessError:
                eprint("Warning: failed to fetch/ref; using HEAD")
        self.source_root = clone_dir
        return clone_dir

    def update_git(self):
        """
        Update an existing git-based installation in-place and refresh dependencies.

        Assumes the initial install was done via clone_git() and that the installed
        directory is still a git checkout. If a virtualenv exists at <repo>/venv
        and requirements.txt is present, this will re-run:

            pip install -r requirements.txt

        inside that virtualenv.
        """
        if self.source_cfg.get("type") != "git":
            raise SystemExit("update-git is only valid when source.type = 'git' in the config")

        git_bin = shutil.which("git")
        if not git_bin:
            raise SystemExit("git not found; required for git source type.")

        # Prefer the current symlink if it exists, otherwise fall back
        # to the versioned install directory.
        if self.current_symlink.is_symlink() and self.current_symlink.exists():
            repo_dir = self.current_symlink.resolve()
        elif self.versioned_dir.exists():
            repo_dir = self.versioned_dir
        else:
            raise SystemExit("No existing installation found to update.")

        if not (repo_dir / ".git").exists():
            raise SystemExit(f"{repo_dir} is not a git checkout (missing .git directory).")

        print(f"[+] Updating git repo in {repo_dir}")
        run([git_bin, "-C", str(repo_dir), "fetch", "--all", "--tags"])

        ref = self.source_cfg.get("ref")
        try:
            if ref:
                print(f"  - checking out ref {ref}")
                run([git_bin, "-C", str(repo_dir), "checkout", ref])
                print("  - pulling latest changes for ref")
                run([git_bin, "-C", str(repo_dir), "pull", "--ff-only"])
            else:
                print("  - pulling latest changes on current branch")
                run([git_bin, "-C", str(repo_dir), "pull", "--ff-only"])
        except subprocess.CalledProcessError as exc:
            eprint(f"[!] git update failed: {exc}")
            raise SystemExit("Git update failed; installation left unchanged.")

        # --- Reuse existing venv and re-install requirements, if present ---
        venv_path = repo_dir / "venv"
        req = repo_dir / "requirements.txt"

        if not venv_path.exists():
            print("[*] No existing virtualenv found at:", venv_path)
            print("    Skipping dependency reinstall. If you changed requirements.txt,")
            print("    consider running a full install or creating a venv manually.")
            print("[+] Git update complete.")
            return

        if not req.exists():
            print("[*] No requirements.txt found at:", req)
            print("    Skipping dependency reinstall. Your code changes are in place,")
            print("    but dependencies were not modified.")
            print("[+] Git update complete.")
            return

        pip = venv_path / "bin" / "pip"
        if not pip.exists():
            print(f"[*] Expected pip at {pip}, but it does not exist.")
            print("    Skipping dependency reinstall. Your virtualenv might be broken;")
            print("    consider re-running a full install.")
            print("[+] Git update complete.")
            return

        print("[+] Reinstalling Python dependencies in existing virtualenv …")
        try:
            run([str(pip), "install", "--upgrade", "pip"])
            run([str(pip), "install", "-r", str(req)])
        except subprocess.CalledProcessError as exc:
            eprint(f"[!] Dependency reinstall failed: {exc}")
            raise SystemExit("Git update succeeded, but dependency installation failed.")

        print("[+] Git update and dependency refresh complete.")

    def download_or_copy(self, loc):
        """
        Download a remote file or copy a local file into the temporary directory.

        Parameters
        ----------
        loc:
            URL or local filesystem path to the archive.

        Returns
        -------
        Path
            Destination path of the downloaded or copied file.

        Raises
        ------
        SystemExit
            If a local source path does not exist.
        """
        dest = self.tmpdir / "download"
        if loc.startswith(("http://", "https://")):
            print(f"  - downloading {loc}")
            urllib.request.urlretrieve(loc, dest)
        else:
            src = Path(loc).expanduser()
            if not src.exists():
                raise SystemExit(f"Source not found: {src}")
            shutil.copy2(src, dest)
        return dest

    # -------------------------------------------------------------
    # Archive Extraction (unchanged)
    # -------------------------------------------------------------
    def extract_archive(self, pathobj):
        """
        Extract a supported archive into the temporary source directory.

        Parameters
        ----------
        pathobj:
            Path-like object pointing to the archive file.

        Returns
        -------
        Path
            The resolved source root directory inside the extraction directory.

        Raises
        ------
        SystemExit
            If the archive format is unsupported or the app structure is invalid.
        """
        path = Path(pathobj)
        print(f"  - extracting {path}")

        extract_dir = self.tmpdir / "src"
        ensure_dir(extract_dir)

        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as z:
                z.extractall(path=extract_dir)
        elif tarfile.is_tarfile(path):
            with tarfile.open(path, "r:*") as t:
                t.extractall(path=extract_dir)
        else:
            raise SystemExit(f"Unknown archive format: {path}")

        entries = [p for p in extract_dir.iterdir() if p.name != "__MACOSX"]
        root = entries[0] if len(entries) == 1 and entries[0].is_dir() else extract_dir

        self.validate_app_structure(root)
        self.source_root = root

        print(f"  - source root: {root}")
        return root

    def validate_app_structure(self, root: Path):
        """
        Validate that the extracted source tree has the expected layout.

        Parameters
        ----------
        root:
            Path to the extracted source root directory.

        Raises
        ------
        SystemExit
            If required directories are missing.
        """
        for r in ("src", "data"):
            if not (root / r).exists():
                raise SystemExit(f"Invalid app structure: missing {r}/")

        if not (root / "requirements.txt").exists():
            eprint("Warning: no requirements.txt found")

    # -------------------------------------------------------------
    # Installation (unchanged)
    # -------------------------------------------------------------
    def atomic_move_into_place(self):
        """
        Move the prepared source tree into the versioned install directory.

        Existing versions are archived into the ``archives`` directory and the
        ``-current`` symlink is updated to point to the new version.
        """
        if self.versioned_dir.exists():
            ts = time.strftime("%Y%m%d%H%M%S")
            archive_target = self.archives_dir / f"{self.appname}-{self.version}-{ts}"
            print(f"[!] existing version found; archiving → {archive_target}")
            shutil.move(str(self.versioned_dir), str(archive_target))

        print(f"[+] installing to {self.versioned_dir}")
        shutil.move(str(self.source_root), str(self.versioned_dir))

        if self.current_symlink.exists() or self.current_symlink.is_symlink():
            self.current_symlink.unlink(missing_ok=True)

        self.current_symlink.symlink_to(
            self.versioned_dir, target_is_directory=True
        )

    def setup_venv_and_requirements(self):
        """
        Optionally create a virtual environment and install Python dependencies.

        Returns
        -------
        Path | None
            Path to the created virtual environment, or None if disabled.
        """
        if not self.config.get("setup_venv", True):
            return None

        venv_path = self.versioned_dir / "venv"
        print(f"[+] creating venv: {venv_path}")
        run([self.vpython, "-m", "venv", str(venv_path)])

        req = self.versioned_dir / "requirements.txt"
        if req.exists():
            pip = venv_path / "bin" / "pip"
            print("[+] installing requirements …")
            run([pip, "install", "--upgrade", "pip"])
            run([pip, "install", "-r", str(req)])

        return venv_path

    def install_fonts(self):
        """
        Optionally install bundled fonts into the user's font directory.

        Fonts are copied under ``~/.local/share/fonts/<appname>-<version>`` and
        the font cache is refreshed.
        """
        # Allow CLI to fully skip font installation
        if getattr(self.args, "skip_fonts", False):
            return

        fonts_dir = self.versioned_dir / "data" / "fonts"
        if not fonts_dir.exists():
            return
        if not self.prompt_yesno("Install included fonts to user font dir?", True):
            return

        target = Path("~/.local/share/fonts").expanduser() / f"{self.appname}-{self.version}"
        ensure_dir(target)

        print(f"[+] copying fonts → {target}")
        for root, _, files in os.walk(fonts_dir):
            for f in files:
                src = Path(root) / f
                rel = Path(root).relative_to(fonts_dir)
                dst = target / rel
                ensure_dir(dst)
                shutil.copy2(src, dst / f)

        run(["fc-cache", "-f", str(target)], check=False)

    def create_launcher(self, venv_path=None):
        """
        Create a launcher script in ``~/.local/bin`` for the installed application.

        Parameters
        ----------
        venv_path:
            Optional path to a virtual environment whose activation should be
            sourced before running the app.

        Returns
        -------
        Path
            Path to the created launcher script.
        """
        entry = self.config.get("entrypoint", "src/app/zyngInstaller.py")
        launcher = self.local_bin / self.appname

        with open(launcher, "w") as f:
            f.write("#!/usr/bin/env bash\nset -euo pipefail\n")
            f.write(f"APP_DIR=\"{self.current_symlink}\"\n")
            if venv_path:
                f.write("source \"$APP_DIR/venv/bin/activate\"\n")
            f.write("cd \"$APP_DIR\"\n")
            f.write(f"exec python3 {entry} \"$@\"\n")

        launcher.chmod(0o755)
        print(f"[+] launcher created: {launcher}")
        return launcher

    def create_desktop_entry(self, launcher):
        """
        Create a ``.desktop`` entry for the application in the user's applications directory.

        Parameters
        ----------
        launcher:
            Path to the launcher script that should be invoked by the desktop entry.
        """
        desktop_dir = Path("~/.local/share/applications").expanduser()
        ensure_dir(desktop_dir)

        desktop = desktop_dir / f"{self.appname}-{self.version}.desktop"

        icon_path = self.config.get("icon", "")
        if icon_path:
            icon_abs = self.versioned_dir / icon_path
            if not icon_abs.exists():
                eprint(f"[!] icon not found: {icon_abs}")
                icon_abs = ""
        else:
            icon_abs = ""

        with open(desktop, "w") as f:
            f.write("[Desktop Entry]\n")
            f.write("Type=Application\n")
            f.write("Comment=Download a/v media from the net!\n")
            f.write(f"Name={self.appname} v{self.version}\n")
            f.write(f"Exec={launcher} %U\n")
            f.write(f"Icon={icon_abs}\n")
            f.write("Terminal=false\n")
            f.write("Categories=Network;Internet;WebBrowser;Application;\n")

        desktop.chmod(0o644)
        print(f"[+] desktop entry: {desktop}")

        # Refresh KDE application cache so the new entry appears immediately
        self.refresh_kde_app_cache()


    def refresh_kde_app_cache(self):
        """
        Ask KDE Plasma (if present) to rebuild its application menu cache so
        newly installed or removed .desktop entries take effect immediately.
        """
        for cmd in ("kbuildsycoca6", "kbuildsycoca5", "kbuildsycoca"):
            bin_path = shutil.which(cmd)
            if bin_path:
                try:
                    print(f"[+] Refreshing KDE application cache via {cmd} …")
                    run([bin_path], check=False)
                    break
                except Exception as exc:
                    eprint(f"[!] Failed to run {cmd}: {exc}")
        # If no kbuildsycoca is present, we silently do nothing.


    def uninstall(self, remove_all=False):
        """
        Uninstall the application.

        Parameters
        ----------
        remove_all:
            If True, remove the entire install root; otherwise only the configured version.
        """
        # Remove installation directories
        if remove_all:
            shutil.rmtree(self.install_root, ignore_errors=True)
        else:
            if self.versioned_dir.exists():
                shutil.rmtree(self.versioned_dir, ignore_errors=True)

            # Also remove launcher from ~/.local/bin
            launcher = self.local_bin / self.appname
            if launcher.exists():
                try:
                    launcher.unlink()
                    print(f"[+] Removed launcher: {launcher}")
                except OSError as exc:
                    eprint(f"[!] Failed to remove launcher {launcher}: {exc}")

            # Remove any .desktop entries for this app from ~/.local/share/applications
            desktop_dir = Path("~/.local/share/applications").expanduser()
            pattern = f"{self.appname}-*.desktop"
            if desktop_dir.exists():
                for desktop_file in desktop_dir.glob(pattern):
                    try:
                        desktop_file.unlink()
                        print(f"[+] Removed desktop entry: {desktop_file}")
                    except OSError as exc:
                        eprint(f"[!] Failed to remove desktop entry {desktop_file}: {exc}")

            # Refresh KDE cache after removal so entries disappear immediately
            self.refresh_kde_app_cache()

            print("[+] Uninstall complete.")

    # -------------------------------------------------------------
    # Cleanup & Rollback (unchanged)
    # -------------------------------------------------------------
    def clean_old_archives(self, keep):
        """
        Remove old archived versions, keeping only the newest ``keep`` entries.

        Parameters
        ----------
        keep:
            Number of archives to retain.
        """
        entries = sorted(self.archives_dir.glob(f"{self.appname}-*"),
                         key=os.path.getmtime,
                         reverse=True)

        if len(entries) <= keep:
            return

        for old in entries[keep:]:
            print(f"[-] removing old archive: {old}")
            shutil.rmtree(old, ignore_errors=True)

    def rollback(self):
        print("[+] Rollback mode active")

        archives = sorted(
            self.archives_dir.glob(f"{self.appname}-*"),
            key=os.path.getmtime,
            reverse=True
        )

        if not archives:
            raise SystemExit("No archived versions exist.")

        print("Available versions:")
        for i, arch in enumerate(archives):
            print(f"  [{i}] {arch.name}")

        choice = int(input("Select index: ").strip())
        if choice < 0 or choice >= len(archives):
            raise SystemExit("Invalid selection.")

        target = archives[choice]
        print(f"[+] Rolling back to {target}")

        if self.current_symlink.exists() and self.current_symlink.is_symlink():
            curr = self.current_symlink.resolve()
            ts = time.strftime("%Y%m%d%H%M%S")
            failed = self.archives_dir / f"{curr.name}-failed-{ts}"
            shutil.move(str(curr), str(failed))

        if self.current_symlink.exists():
            self.current_symlink.unlink(missing_ok=True)

        self.current_symlink.symlink_to(target, target_is_directory=True)

        print("[+] Rollback complete.")

    # -------------------------------------------------------------
    # Installation Orchestration
    # -------------------------------------------------------------
    def install(self):
        """
        Perform a full installation run using the current configuration.

        Steps:
          1. Prepare and extract the source.
          2. Move it into place as the new version.
          3. Optionally create a virtualenv and install requirements.
          4. Optionally install fonts.
          5. Create launcher and desktop entry.
          6. Optionally prune old archives.
        """
        self.prepare_source()
        self.atomic_move_into_place()
        venv = self.setup_venv_and_requirements()
        self.install_fonts()
        launcher = self.create_launcher(venv)
        self.create_desktop_entry(launcher)
        print("[+] Installation successful.")

        if self.args.auto_clean_archives:
            self.clean_old_archives(self.args.keep)

    def uninstall(self, remove_all=False):
        """
        Uninstall the application.

        Parameters
        ----------
        remove_all:
            If True, remove the entire install root; otherwise only the configured version.
        """
        # Remove installation directories
        if remove_all:
            shutil.rmtree(self.install_root, ignore_errors=True)
        else:
            if self.versioned_dir.exists():
                shutil.rmtree(self.versioned_dir, ignore_errors=True)

            # Also remove launcher from ~/.local/bin
            launcher = self.local_bin / self.appname
            if launcher.exists():
                try:
                    launcher.unlink()
                    print(f"[+] Removed launcher: {launcher}")
                except OSError as exc:
                    eprint(f"[!] Failed to remove launcher {launcher}: {exc}")

            # Remove any .desktop entries for this app from ~/.local/share/applications
            desktop_dir = Path("~/.local/share/applications").expanduser()
            pattern = f"{self.appname}-*.desktop"
            if desktop_dir.exists():
                for desktop_file in desktop_dir.glob(pattern):
                    try:
                        desktop_file.unlink()
                        print(f"[+] Removed desktop entry: {desktop_file}")
                    except OSError as exc:
                        eprint(f"[!] Failed to remove desktop entry {desktop_file}: {exc}")

            # Ask KDE Plasma to rebuild its application menu cache so entries disappear immediately
            for cmd in ("kbuildsycoca6", "kbuildsycoca5", "kbuildsycoca"):
                bin_path = shutil.which(cmd)
                if bin_path:
                    try:
                        print(f"[+] Refreshing KDE application cache via {cmd} …")
                        run([bin_path], check=False)
                        break
                    except Exception as exc:
                        eprint(f"[!] Failed to run {cmd}: {exc}")

            print("[+] Uninstall complete.")

    def prompt_yesno(self, q, default=True):
        """
        Prompt the user with a yes/no question, honoring the ``--yes`` flag.

        Parameters
        ----------
        q:
            Question to display.
        default:
            Default answer if the user just presses Enter.

        Returns
        -------
        bool
            True for yes, False for no.
        """
        if self.args.yes:
            return default
        while True:
            yn = input(f"{q} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
            if yn == "":
                return default
            if yn in ("y", "yes"):
                return True
            if yn in ("n", "no"):
                return False


# -------------------------------------------------------------
# Main
# -------------------------------------------------------------
def main():
    """
    Command-line entry point for the installer script.

    Parses arguments, constructs an Installer, and dispatches to install,
    uninstall, or rollback operations.
    """
    ap = argparse.ArgumentParser(description="Installer for Python apps with GitHub-release fetch")
    ap.add_argument("--config", "-c", required=True)
    ap.add_argument("--install-root")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--remove-all", action="store_true")
    ap.add_argument("--auto-clean-archives", action="store_true")
    ap.add_argument("--keep", type=int, default=3)
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--skip-fonts", action="store_true", help="Skip installation of bundled fonts")
    ap.add_argument(
        "--update-git",
        action="store_true",
        help="Update an existing git-based installation in-place (uses the existing clone)"
    )
    args = ap.parse_args()

    inst = Installer(Path(args.config), args)

    if args.rollback:
        inst.rollback()
    elif args.uninstall:
        inst.uninstall(remove_all=args.remove_all)
    elif args.update_git:
        inst.update_git()
    else:
        if not args.yes:
            print(f"Default install root: {inst.install_root}")
            custom = input("Install here? (enter to accept or specify another): ").strip()
            if custom:
                inst.install_root = Path(custom).expanduser()
                ensure_dir(inst.install_root)

        # Only *checks* required apps; does not install via a package manager.
        # inst.ensure_required_apps()  # <-- this is now handled by the installer.py script -- actuly, just not doing this
        inst.install()


if __name__ == "__main__":
    main()
