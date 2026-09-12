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

    # Let anyone in the 'gamers' group join this session. Two separate
    # gates have to be opened:
    #
    #   1. The socket itself, via group ownership and mode 770.
    #   2. tmux's own access list. Since tmux 3.3 the server refuses any
    #      client whose UID differs from the one that started it, no
    #      matter what the socket permissions say -- that refusal is the
    #      "access not allowed" message. Everyone who may attach has to
    #      be added here, by the user who owns the server, at the moment
    #      the session is created.
    chgrp gamers "$SOCKET" 2>/dev/null || true
    chmod 770 "$SOCKET"

    me="$(id -un)"
    for player in $(getent group gamers | cut -d: -f4 | tr ',' ' '); do
        [ "$player" = "$me" ] && continue
        # -w gives write access, so the second player can actually play
        # rather than just watch. Older tmux has no server-access at all
        # and does not need it, hence the fallback.
        tmux -S "$SOCKET" server-access -aw "$player" 2>/dev/null || true
    done
fi

exec tmux -S "$SOCKET" attach -t "$SESSION"
