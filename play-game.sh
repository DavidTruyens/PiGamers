#!/usr/bin/env bash
#
# Shared session launcher for every PiGamers game.
#
#     play-game.sh <name>          # runs <name>.py from this directory
#
# The first player to run it starts the game; the second one joins the
# same tmux session and lands in the same match.
#
# Every session runs as one dedicated account, GAME_USER, rather than as
# whoever happened to start it. Two things fall out of that:
#
#   * Nobody ends up with a shell as another player. Attaching to a tmux
#     session means full control of it, so a session owned by a child is
#     a session any other player can act as.
#   * tmux's own access list stops mattering. Since 3.3 the server
#     refuses clients whose UID differs from the owner's -- the "access
#     not allowed" message -- and here every client shares one UID.
#
# Each game gets its own socket, so Pong and Pac-Man can run at once.
#
set -euo pipefail

GAME_USER="pigames"

GAME="${1:?usage: play-game.sh <game-name>}"

# The name becomes part of a path, so keep it boring.
case "$GAME" in
    ""|*[!a-z0-9-]*)
        echo "play-game: bad game name: $GAME" >&2
        exit 1
        ;;
esac

# readlink -f follows the symlink in /usr/local/bin back to the real
# file, so this works whether it is run by full path or by name.
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
GAME_DIR="$(cd "$(dirname "$SELF")" && pwd)"
GAME_PY="$GAME_DIR/$GAME.py"

if [ ! -f "$GAME_PY" ]; then
    echo "play-game: no such game: $GAME_PY" >&2
    exit 1
fi

# Re-enter as the game user. sudo -n never prompts, so a missing rule
# fails fast with something a ten-year-old can act on instead of a
# password prompt they have no answer to.
#
# The check asks about THIS command specifically. Asking whether some
# other command is permitted -- 'true', say -- reports a denial whenever
# the rule is correctly scoped to just this script, which is precisely
# when everything is set up right.
if [ "$(id -un)" != "$GAME_USER" ]; then
    if ! sudo -n -l -u "$GAME_USER" "$SELF" "$GAME" >/dev/null 2>&1; then
        echo "play-game: not allowed to run games as '$GAME_USER'." >&2
        echo >&2
        echo "  Are you in the 'gamers' group?  Check with:  groups" >&2
        echo "  If it is missing, ask David to run:" >&2
        echo "      sudo usermod -aG gamers \$(id -un)" >&2
        echo "  Group membership only applies at login -- 'newgrp gamers'" >&2
        echo "  picks it up without logging out." >&2
        echo >&2
        echo "  If the group is there, the sudo rule is missing. David:" >&2
        echo "      sudo cat /etc/sudoers.d/pigamers" >&2
        echo "      sudo visudo -c -f /etc/sudoers.d/pigamers" >&2
        exit 1
    fi
    exec sudo -n -u "$GAME_USER" "$SELF" "$GAME"
fi

SOCKET="/tmp/pigamers-$GAME.sock"
SESSION="$GAME"
COLS=80
ROWS=24

if ! tmux -S "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    # A socket left behind by a dead server, or by the older version of
    # this script that ran as the player, would block the new session.
    if [ -S "$SOCKET" ] && [ -O "$SOCKET" ]; then
        rm -f "$SOCKET"
    fi

    tmux -S "$SOCKET" new-session -d -s "$SESSION" -x "$COLS" -y "$ROWS" \
        "python3 '$GAME_PY'"

    # Keep the playfield a fixed size, otherwise tmux shrinks the window
    # down to whoever has the smallest terminal. window-size is a window
    # option, so try that form first and fall back to the session one.
    tmux -S "$SOCKET" set-window-option -t "$SESSION" window-size manual 2>/dev/null \
        || tmux -S "$SOCKET" set-option -t "$SESSION" window-size manual 2>/dev/null \
        || true
    tmux -S "$SOCKET" set-option -t "$SESSION" status off
fi

exec tmux -S "$SOCKET" attach -t "$SESSION"
