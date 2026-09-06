#!/usr/bin/env bash
#
# Start (or join) the shared Pac-Man vs Ghost session.
# Both kids just run:  play-pacman
#
exec "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/play-game.sh" pacman
