#!/bin/bash

# DSPX Universal Installation Script
# Auto-detects Linux distribution and runs appropriate installer

set -e

echo "=========================================="
echo "DSPX Universal Installer"
echo "=========================================="
echo ""

# Detect distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "Cannot detect Linux distribution"
    exit 1
fi

echo "Detected distribution: $DISTRO ($NAME)"
echo ""

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

case $DISTRO in
    arch|manjaro|endeavouros|artix)
        echo "Using Arch Linux installer..."
        bash "$SCRIPT_DIR/install-arch.sh"
        ;;
    ubuntu|debian|linuxmint|pop|elementary|zorin|mx|tuxedo)
        echo "Using Ubuntu/Debian installer..."
        bash "$SCRIPT_DIR/install-ubuntu.sh"
        ;;
    fedora|rhel|centos|rocky|almalinux)
        echo "Fedora/RHEL family detected."
        echo "Please use: pip3 install --user -r requirements.txt"
        echo "Then manually create desktop shortcut or run: python3 main.py"
        exit 1
        ;;
    *)
        echo "Unsupported distribution: $DISTRO"
        echo ""
        echo "You can manually install by running:"
        echo "  pip3 install --user -r requirements.txt"
        echo "  python3 main.py"
        exit 1
        ;;
esac