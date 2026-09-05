#!/usr/bin/env bash
#
# Start (or join) the shared Space Invaders session.
#
# Both kids just run:   play-invaders
# The first one to run it starts the game, the second one joins it.
#
set -euo pipefail

SOCKET="/tmp/invaders.sock"
SESSION="invaders"
COLS=80
ROWS=24
GAME_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! tmux -S "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    tmux -S "$SOCKET" new-session -d -s "$SESSION" -x "$COLS" -y "$ROWS" \
        "python3 '$GAME_DIR/invaders.py'"

    # Keep the playfield a fixed size, otherwise tmux shrinks the window
    # down to whoever has the smallest terminal.
    tmux -S "$SOCKET" set-option -t "$SESSION" window-size manual 2>/dev/null || true
    tmux -S "$SOCKET" set-option -t "$SESSION" status off

    # Let anyone in the 'gamers' group join this session.
    chgrp gamers "$SOCKET" 2>/dev/null || true
    chmod 770 "$SOCKET"
fi

exec tmux -S "$SOCKET" attach -t "$SESSION"
