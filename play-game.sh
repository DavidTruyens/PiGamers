#!/usr/bin/env bash
#
# Shared session launcher for every PiGamers game.
#
#     play-game.sh <name>          # runs <name>.py from this directory
#
# The first player to run it starts the game; the second one joins the
# same tmux session and lands in the same match.
#
# Every game gets its own socket, so Pong and Pac-Man can be running at
# the same time without treading on each other.
#
set -euo pipefail

GAME="${1:?usage: play-game.sh <game-name>}"

SOCKET="/tmp/pigamers-$GAME.sock"
SESSION="$GAME"
COLS=80
ROWS=24

# readlink -f follows the symlink in /usr/local/bin back to the real file,
# so the game is found whether this is run by full path or by name.
GAME_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
GAME_PY="$GAME_DIR/$GAME.py"

if [ ! -f "$GAME_PY" ]; then
    echo "play-game: no such game: $GAME_PY" >&2
    exit 1
fi

if ! tmux -S "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    tmux -S "$SOCKET" new-session -d -s "$SESSION" -x "$COLS" -y "$ROWS" \
        "python3 '$GAME_PY'"

    # Keep the playfield a fixed size, otherwise tmux shrinks the window
    # down to whoever has the smallest terminal. window-size is a window
    # option, so try the window form first and fall back to the session one.
    tmux -S "$SOCKET" set-window-option -t "$SESSION" window-size manual 2>/dev/null \
        || tmux -S "$SOCKET" set-option -t "$SESSION" window-size manual 2>/dev/null \
        || true
    tmux -S "$SOCKET" set-option -t "$SESSION" status off

    # Let anyone in the 'gamers' group join this session.
    chgrp gamers "$SOCKET" 2>/dev/null || true
    chmod 770 "$SOCKET"
fi

exec tmux -S "$SOCKET" attach -t "$SESSION"
