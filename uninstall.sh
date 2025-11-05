#!/bin/bash

# DSPX Uninstallation Script

echo "=========================================="
echo "DSPX Uninstallation Script"
echo "=========================================="

DESKTOP_FILE="$HOME/.local/share/applications/dspx.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor"

# Remove desktop entry
if [ -f "$DESKTOP_FILE" ]; then
    rm "$DESKTOP_FILE"
    echo "✓ Removed desktop shortcut"
fi

# Remove icons
echo "Removing application icons..."
for size in 16x16 32x32 48x48 64x64 128x128 256x256; do
    if [ -f "$ICON_DIR/$size/apps/dspx.png" ]; then
        rm "$ICON_DIR/$size/apps/dspx.png"
        echo "✓ Removed ${size} icon"
    fi
done

# Update caches
echo "Updating system caches..."
gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "=========================================="
echo "Uninstallation completed!"
echo "=========================================="
echo ""
echo "Note: Python dependencies (PySide6, blake3) were not removed."
echo "To remove them manually, run:"
echo "  pip uninstall PySide6 blake3"
echo ""