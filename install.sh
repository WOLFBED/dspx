#!/usr/bin/env bash
# this is for arch-based linuxes. tested with success on :: garuda, manjaro, cachyos, archcraft, endeavoros, rebornos.
# success is not expected for all other distros.
set -euo pipefail

installer_dir="dspx"

# --- Prepare workspace ---
# (Unecessary, github page command does this.)
# cd "$HOME/Desktop/"
# mkdir -p $installer_dir
# installer_dir = "$HOME/Desktop/$installer_dir"
# cd $installer_dir

# Path to the TOML file
TOML_FILE="app_config.toml"


echo "[+] Installing dependencies…"
sudo pacman -S --noconfirm \
    git curl unzip python python-pip python-virtualenv

# --- Run installer (auto-yes recommended to skip prompts) ---
echo "[+] Running Zyng installer…"
python zyngInstaller.py --config app_config.toml --skip-fonts

echo "[*] dspx installer finished."


# just frigging remove it
if [[ -d "$HOME/Desktop/$installer_dir" ]]; then
    echo "Removing temporary directory"
    rm -rf "$HOME/Desktop/$installer_dir"
    echo "[*] Cleanup complete."
fi
