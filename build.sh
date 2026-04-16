#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Download and install TinyTeX to the Render user directory
curl -sL "https://yihui.org/tinytex/install-bin-unix.sh" | sh