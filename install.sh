#!/usr/bin/env bash
#
# AFM setup script
# -----------------
# - Creates a virtual environment at <project_root>/.venv (if missing)
# - Installs AFM (pip install -e .) into that venv
# - Registers an `afm-env` alias into your shell rc file (~/.bashrc or
#   ~/.zshrc) so you can activate the venv from ANY terminal / any directory
#   just by typing `afm-env`.
#
# Usage:
#   chmod +x install.sh
#   ./install.sh
#
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo "[AFM] Project dir : $PROJECT_DIR"
echo "[AFM] Venv dir     : $VENV_DIR"

# ------------------------------------------------------------------ #
# 1. Create venv if missing
# ------------------------------------------------------------------ #
if [ ! -d "$VENV_DIR" ]; then
    echo "[AFM] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "[AFM] Virtual environment already exists, reusing it."
fi

# ------------------------------------------------------------------ #
# 2. Install AFM into the venv
# ------------------------------------------------------------------ #
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -e "$PROJECT_DIR"
deactivate

echo "[AFM] Installed AFM into $VENV_DIR"

# ------------------------------------------------------------------ #
# 3. Register the 'afm-env' alias into the user's shell rc file(s)
# ------------------------------------------------------------------ #
ALIAS_LINE="alias afm-env='source \"$VENV_DIR/bin/activate\"'"

register_alias() {
    local rc_file="$1"
    [ -f "$rc_file" ] || touch "$rc_file"

    # Drop any previous afm-env alias (e.g. pointing at an old/moved venv)
    if grep -q '^alias afm-env=' "$rc_file" 2>/dev/null; then
        sed -i.afm-bak '/^alias afm-env=/d' "$rc_file"
    fi

    {
        echo ""
        echo "# AFM - activate the AFM virtual environment from anywhere"
        echo "$ALIAS_LINE"
    } >> "$rc_file"

    echo "[AFM] Registered 'afm-env' alias into $rc_file"
}

# Register into whichever rc file(s) are relevant. We check both bash and
# zsh rc files (if they exist) so the alias works regardless of which shell
# you open next, and also register into the rc matching $SHELL.
registered_any=false

if [ -f "$HOME/.bashrc" ] || [ "${SHELL##*/}" = "bash" ]; then
    register_alias "$HOME/.bashrc"
    registered_any=true
fi

if [ -f "$HOME/.zshrc" ] || [ "${SHELL##*/}" = "zsh" ]; then
    register_alias "$HOME/.zshrc"
    registered_any=true
fi

if [ "$registered_any" = false ]; then
    # Fallback: default to .bashrc even if it didn't exist before
    register_alias "$HOME/.bashrc"
fi

echo ""
echo "======================================================================"
echo " [AFM] Setup complete."
echo ""
echo " Open a NEW terminal (or run: source ~/.bashrc   /  source ~/.zshrc)"
echo " then, from ANY directory, type:"
echo ""
echo "     afm-env"
echo ""
echo " This activates the AFM virtual environment. After that, run:"
echo ""
echo "     afm --help"
echo "     afm -init"
echo "======================================================================"
