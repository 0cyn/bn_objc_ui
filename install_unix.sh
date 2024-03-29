#!/bin/bash

# This is a fairly simple example installation script for Darwin and Linux.

# Set these in your run configuration.
# PROJECT_NAME="SidebarExample"
# PLUGIN_INSTALL_DIR="$HOME/Library/Application Support/Binary Ninja/plugins"
# BINARYNINJA_PYTHON="/Applications/Binary Ninja.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"
# BINARYNINJA_PYTHON_LIBS="/Applications/Binary Ninja.app/Contents/Resources/bundled-python3/"
# USE_JETBRAINS_DEBUGGER = 1
# JETBRAINS_PYDEVD_VERSION = "223.8617.48"
# JETBRAINS_DEBUG_PORT = 12345
PROJECT_NAME="$(python3 project.py --get-project-name)"
PLUGIN_INSTALL_DIR="$(python3 project.py --find-plugin-install-dir)"
BINARYNINJA_PYTHON="$(python3 project.py --find-python-interpreter)"
BINARYNINJA_PYTHON_LIBS="$(python3 project.py --find-pythonhome)"

if [ ! -d "$PLUGIN_INSTALL_DIR" ]; then
    echo "Error: Plugin install directory does not exist: $PLUGIN_INSTALL_DIR"
    exit 1
fi
if [ -z "$PROJECT_NAME" ]; then
    echo "Must configure PROJECT_NAME via python3 project.py --setup"
    exit 1
fi
if [ ! -f "$BINARYNINJA_PYTHON" ]; then
    echo "Error: Binary Ninja Python executable does not exist: $BINARYNINJA_PYTHON"
    exit 1
fi
if [ "$USE_JETBRAINS_DEBUGGER" -eq 1 ]; then
    export PYTHONHOME="$BINARYNINJA_PYTHON_LIBS"
    "$BINARYNINJA_PYTHON" -m pip install pydevd-pycharm~="$JETBRAINS_PYDEVD_VERSION"
fi
if [ "$USE_VSCODE_DEBUGGER" -eq 1 ]; then
    export PYTHONHOME="$BINARYNINJA_PYTHON_LIBS"
    "$BINARYNINJA_PYTHON" -m pip install debugpy
fi

killall binaryninja
# Copy contents of src to folder named PROJECT_NAME in PLUGIN_INSTALL_DIR
mkdir -p "$PLUGIN_INSTALL_DIR/$PROJECT_NAME"
cp -r ./* "$PLUGIN_INSTALL_DIR/$PROJECT_NAME"
echo "Installed to " "$PLUGIN_INSTALL_DIR/$PROJECT_NAME"

