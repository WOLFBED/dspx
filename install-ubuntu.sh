#!/bin/bash

# DSPX Installation Script for Ubuntu/Debian with GNOME/KDE
# This script installs dependencies in a venv and creates a desktop shortcut

set -e  # Exit on error

echo "=========================================="
echo "DSPX Installation Script (Ubuntu/Debian)"
echo "=========================================="

# Get the absolute path of the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="DSPX"
VENV_DIR="$SCRIPT_DIR/venv"
DESKTOP_FILE="$HOME/.local/share/applications/dspx.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor"

# Detect if running on Ubuntu/Debian
if ! command -v apt &> /dev/null; then
    echo "Warning: This script is designed for Ubuntu/Debian systems"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update package lists
echo ""
echo "Updating package lists..."
sudo apt update

# Install system dependencies
echo ""
echo "Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv || {
    echo "Failed to install system dependencies"
    exit 1
}

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "Virtual environment already exists, removing old one..."
    rm -rf "$VENV_DIR"
fi
python3 -m venv "$VENV_DIR"

# Activate virtual environment and install dependencies
echo ""
echo "Installing Python dependencies in virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install PySide6 (Qt for Python)
echo "Installing PySide6..."
pip install PySide6

# Install optional blake3 for faster hashing
echo "Installing blake3 (for faster file hashing)..."
pip install blake3 || {
    echo "Warning: blake3 installation failed. Will use sha256 instead."
}

# Install other dependencies from requirements.txt if it exists
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Installing additional dependencies from requirements.txt..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

deactivate

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
# Also try xdg-icon-resource if available
command -v xdg-icon-resource &> /dev/null && xdg-icon-resource forceupdate || true

# Create launcher script
echo ""
echo "Creating launcher script..."
cat > "$SCRIPT_DIR/dspx-launcher.sh" << 'EOF'
#!/bin/bash
# DSPX Launcher - Activates venv and runs main.py
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/main.py" "$@"
EOF

chmod +x "$SCRIPT_DIR/dspx-launcher.sh"

# Create desktop entry
echo "Creating desktop shortcut..."
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=DSPX
Comment=Data Store Pruner and Compressor - Clean duplicate files and residual OS files
Exec=$SCRIPT_DIR/dspx-launcher.sh
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
echo "Virtual environment created at: $VENV_DIR"
echo ""
echo "You can now:"
echo "  1. Find DSPX in your application launcher (search for 'DSPX')"
echo "  2. Run it from terminal: $SCRIPT_DIR/dspx-launcher.sh"
echo "  3. Or activate venv manually: source $VENV_DIR/bin/activate && python $SCRIPT_DIR/main.py"
echo ""
echo "The application icon will appear in:"
echo "  • Application launcher menu"
echo "  • Taskbar/panel when running"
echo "  • Window title bar"
echo ""
echo "Desktop Environment: $(echo $XDG_CURRENT_DESKTOP)"
echo ""
echo "To uninstall, run: bash '$SCRIPT_DIR/uninstall.sh'"
echo ""