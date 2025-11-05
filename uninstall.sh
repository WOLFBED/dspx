#!/bin/bash

# DSPX Uninstallation Script

echo "=========================================="
echo "DSPX Uninstallation Script"
echo "=========================================="

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DESKTOP_FILE="$HOME/.local/share/applications/dspx.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor"
VENV_DIR="$SCRIPT_DIR/venv"
LAUNCHER_SCRIPT="$SCRIPT_DIR/dspx-launcher.sh"

# Remove desktop entry
if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "✓ Removed desktop shortcut"
fi

# Remove launcher script
if [ -f "$LAUNCHER_SCRIPT" ]; then
    rm "$LAUNCHER_SCRIPT"
    echo "✓ Removed launcher script"
fi

# Remove icons
echo "Removing application icons..."
for size in 16x16 32x32 48x48 64x64 128x128 256x256; do
    if [ -f "$ICON_DIR/$size/apps/dspx.png" ]; then
        rm "$ICON_DIR/$size/apps/dspx.png"
        echo "✓ Removed ${size} icon"
    fi
done

# Remove virtual environment
if [ -d "$VENV_DIR" ]; then
    echo ""
    read -p "Remove virtual environment at $VENV_DIR? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
        echo "✓ Removed virtual environment"
    else
        echo "⊘ Kept virtual environment"
    fi
fi

# Update caches
echo ""
echo "Updating system caches..."
gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "=========================================="
echo "Uninstallation completed!"
echo "=========================================="
echo ""
echo "Note: Application data (settings, logs) were not removed:"
echo "  • $SCRIPT_DIR/dspx_settings.json"
echo "  • $SCRIPT_DIR/dspx_residuals_patterns.csv"
echo "  • $SCRIPT_DIR/logs/"
echo ""
echo "To remove all application data, delete the entire directory:"
echo "  rm -rf '$SCRIPT_DIR'"
echo ""