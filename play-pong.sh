#!/usr/bin/env bash
#
# Start (or join) the shared Pong session.
# Both kids just run:  play-pong
#
exec "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/play-game.sh" pong
