#!/bin/bash

# DSPX Installation Script for Arch Linux with KDE
# This script installs dependencies and creates a desktop shortcut

set -e  # Exit on error

echo "=========================================="
echo "DSPX Installation Script"
echo "=========================================="

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="DSPX"
DESKTOP_FILE="$HOME/.local/share/applications/dspx.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor"

# Check if running on Arch Linux
if ! command -v pacman &> /dev/null; then
    echo "Warning: This script is designed for Arch Linux"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install system dependencies
echo ""
echo "Installing system dependencies..."
sudo pacman -S --needed python python-pip || {
    echo "Failed to install system dependencies"
    exit 1
}

# Install PySide6 (Qt for Python)
echo ""
echo "Installing PySide6..."
pip install --user PySide6

# Install optional blake3 for faster hashing
echo ""
echo "Installing optional blake3 (for faster file hashing)..."
pip install --user blake3 || {
    echo "Warning: blake3 installation failed. Will use sha256 instead."
}

# Install other Python dependencies if requirements.txt exists
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo ""
    echo "Installing additional Python dependencies..."
    pip install --user -r "$SCRIPT_DIR/requirements.txt"
fi

# Create .local directories if they don't exist
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.local/share/icons/hicolor/"{16x16,32x32,48x48,64x64,128x128,256x256}/apps

# Copy icons to system icon directories
echo ""
echo "Installing application icons..."
cp "$SCRIPT_DIR/img/dspx_logo_01_16x16.png" "$ICON_DIR/16x16/apps/dspx.png"
cp "$SCRIPT_DIR/img/dspx_logo_01_32x32.png" "$ICON_DIR/32x32/apps/dspx.png"
cp "$SCRIPT_DIR/img/dspx_logo_01_48x48.png" "$ICON_DIR/48x48/apps/dspx.png"
cp "$SCRIPT_DIR/img/dspx_logo_01_64x64.png" "$ICON_DIR/64x64/apps/dspx.png"
cp "$SCRIPT_DIR/img/dspx_logo_01_128x128.png" "$ICON_DIR/128x128/apps/dspx.png"
cp "$SCRIPT_DIR/img/dspx_logo_01_256x256.png" "$ICON_DIR/256x256/apps/dspx.png"

# Update icon cache
echo "Updating icon cache..."
gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true

# Create desktop entry
echo ""
echo "Creating desktop shortcut..."
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=DSPX
Comment=Data Store Pruner and Compressor - Clean duplicate files and residual OS files
Exec=python3 "$SCRIPT_DIR/main.py"
Icon=dspx
Terminal=false
Categories=Utility;System;FileTools;
Keywords=duplicate;cleanup;disk;storage;
StartupNotify=true
StartupWMClass=dspx
EOF

# Make the desktop file executable
chmod +x "$DESKTOP_FILE"

# Update desktop database
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

# Create logs directory
mkdir -p "$SCRIPT_DIR/logs"

echo ""
echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo ""
echo "You can now:"
echo "  1. Find DSPX in your application launcher (search for 'DSPX')"
echo "  2. Run it from terminal: cd '$SCRIPT_DIR' && python3 main.py"
echo ""
echo "The application icon will appear in:"
echo "  • Application launcher menu"
echo "  • KDE taskbar when running"
echo "  • Window title bar"
echo ""
echo "To uninstall, run: bash '$SCRIPT_DIR/uninstall.sh'"
echo ""