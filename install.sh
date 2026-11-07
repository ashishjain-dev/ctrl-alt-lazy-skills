#!/usr/bin/env bash
# Install one Ctrl Alt Lazy skill (or all of them) into your personal Claude Code skills folder.
# Usage:
#   ./install.sh summarize-changes       # install one skill
#   ./install.sh --all                   # install every skill in this repo
#   ./install.sh --agents review-squad   # install an agent pack into ~/.claude/agents
#   ./install.sh --list                  # show available skills and agent packs
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$REPO_DIR/skills"
AGENTS_SRC="$REPO_DIR/agents"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
DEST="${CLAUDE_SKILLS_DIR:-$CLAUDE_HOME/skills}"
AGENTS_DEST="${CLAUDE_AGENTS_DIR:-$CLAUDE_HOME/agents}"
# Backups live OUTSIDE the skills/agents folders, so Claude Code never loads a stale copy.
BACKUP_DIR="$CLAUDE_HOME/ctrl-alt-lazy-backup/$(date +%Y%m%d-%H%M%S)"

list() {
  echo "Skills:"; ls -1 "$SRC" | sed 's/^/  /'
  echo "Agent packs (--agents <name>):"; ls -1 "$AGENTS_SRC" | sed 's/^/  /'
}

backup() {  # backup <path> <kind>
  mkdir -p "$BACKUP_DIR/$2"
  mv "$1" "$BACKUP_DIR/$2/"
  echo "  old copy saved to $BACKUP_DIR/$2/$(basename "$1")"
}

install_one() {
  local name="$1"
  if [ ! -f "$SRC/$name/SKILL.md" ]; then
    echo "No skill called '$name'."; list; exit 1
  fi
  mkdir -p "$DEST"
  if [ -e "$DEST/$name" ]; then
    echo "Updating $name"; backup "$DEST/$name" skills
  fi
  cp -r "$SRC/$name" "$DEST/$name"
  echo "Installed /$name -> $DEST/$name"
}

install_agents() {
  local pack="$1" f base
  if [ ! -d "$AGENTS_SRC/$pack" ]; then
    echo "No agent pack called '$pack'."; list; exit 1
  fi
  mkdir -p "$AGENTS_DEST"
  for f in "$AGENTS_SRC/$pack"/*.md; do
    # Only real agent definitions (YAML frontmatter), never README.md or other docs.
    head -n 1 "$f" | grep -q '^---' || continue
    base="$(basename "$f")"
    if [ -e "$AGENTS_DEST/$base" ]; then backup "$AGENTS_DEST/$base" agents; fi
    cp "$f" "$AGENTS_DEST/$base"
    echo "Installed agent ${base%.md} -> $AGENTS_DEST/$base"
  done
}

case "${1:-}" in
  ""|-h|--help) sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'; echo; list ;;
  --list) list ;;
  --all) for d in "$SRC"/*/; do install_one "$(basename "$d")"; done
         echo "Done. Restart Claude Code if this is a brand-new skill folder." ;;
  --agents) [ -n "${2:-}" ] || { echo "Usage: ./install.sh --agents <pack>"; list; exit 1; }
            install_agents "$2"
            echo "Done. Restart Claude Code if $AGENTS_DEST did not exist before." ;;
  *) install_one "$1"
     echo "Done. Restart Claude Code if this is a brand-new skill folder." ;;
esac
