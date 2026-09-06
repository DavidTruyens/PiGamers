#!/usr/bin/env bash
#
# Start (or join) the shared Space Invaders session.
# Both kids just run:  play-invaders
#
exec "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/play-game.sh" invaders
