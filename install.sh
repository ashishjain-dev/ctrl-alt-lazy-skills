#!/usr/bin/env bash
# Install one Ctrl Alt Lazy skill (or all of them) into your personal Claude Code skills folder.
# Usage:
#   ./install.sh summarize-changes     # install one skill
#   ./install.sh --all                 # install every skill in this repo
#   ./install.sh --list                # show available skills
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/skills"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

list() { ls -1 "$SRC"; }

install_one() {
  local name="$1"
  if [ ! -f "$SRC/$name/SKILL.md" ]; then
    echo "No skill called '$name'. Available:"; list; exit 1
  fi
  mkdir -p "$DEST"
  if [ -e "$DEST/$name" ]; then
    echo "Updating $name (old copy saved as $DEST/$name.bak)"
    rm -rf "$DEST/$name.bak"; mv "$DEST/$name" "$DEST/$name.bak"
  fi
  cp -r "$SRC/$name" "$DEST/$name"
  echo "Installed /$name -> $DEST/$name"
}

case "${1:-}" in
  ""|-h|--help) sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'; echo; echo "Available skills:"; list ;;
  --list) list ;;
  --all) for d in "$SRC"/*/; do install_one "$(basename "$d")"; done
         echo "Done. Restart Claude Code if this is a brand-new skill folder." ;;
  *) install_one "$1"
     echo "Done. Restart Claude Code if this is a brand-new skill folder." ;;
esac
