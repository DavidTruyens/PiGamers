#!/usr/bin/env python3
"""
Headless tests for the PiGamers games.

The rules of each game live in a Game class that never touches curses,
so a whole match can be played here with no terminal at all.

    python3 test_games.py
"""

import random
import sys
from collections import deque

import pacman
import pong

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}{' -- ' + detail if detail else ''}")
        FAILURES.append(name)


# ---------------------------------------------------------------------
# Maze integrity -- catches hand-drawing mistakes
# ---------------------------------------------------------------------
def test_maze():
    print("\nPac-Man maze")
    rows = pacman.MAZE
    widths = {len(r) for r in rows}
    check("every row is the same width", len(widths) == 1, f"widths={widths}")

    border_ok = (all(c == "#" for c in rows[0])
                 and all(c == "#" for c in rows[-1])
                 and all(r[0] == "#" and r[-1] == "#" for r in rows))
    check("maze is sealed by walls", border_ok)

    legal = set("#. o")
    strays = {c for r in rows for c in r} - legal
    check("no stray characters", not strays, f"found {strays}")

    py, px = pacman.PAC_START
    check("Pac-Man does not start inside a wall", rows[py][px] != "#")
    for gy, gx in pacman.GHOST_STARTS:
        check(f"ghost start ({gy},{gx}) is not a wall", rows[gy][gx] != "#")

    # Flood fill from Pac-Man's start: every pellet must be reachable.
    seen = {(py, px)}
    queue = deque([(py, px)])
    while queue:
        y, x = queue.popleft()
        for dy, dx in pacman.DIRS:
            ny, nx = y + dy, x + dx
            if (ny, nx) in seen:
                continue
            if 0 <= ny < len(rows) and 0 <= nx < len(rows[0]) \
                    and rows[ny][nx] != "#":
                seen.add((ny, nx))
                queue.append((ny, nx))

    pellets = {(y, x) for y, r in enumerate(rows)
               for x, c in enumerate(r) if c in ".o"}
    unreachable = pellets - seen
    check("every pellet is reachable", not unreachable,
          f"{len(unreachable)} stranded: {sorted(unreachable)[:5]}")

    open_cells = {(y, x) for y, r in enumerate(rows)
                  for x, c in enumerate(r) if c != "#"}
    check("no walled-off corridors", open_cells == seen,
          f"{len(open_cells - seen)} isolated cells")


# ---------------------------------------------------------------------
# Pac-Man simulation
# ---------------------------------------------------------------------
def test_pacman_runs():
    print("\nPac-Man simulation")
    random.seed(1)
    g = pacman.Game(80, 24)
    start_pellets = g.pellets

    for _ in range(20000):
        if random.random() < 0.1:
            g.steer_pac(random.choice(pacman.DIRS))
        if random.random() < 0.1:
            g.steer_hunter(random.choice(pacman.DIRS))
        g.update()
        if g.state == "over":
            break
        if g.grid[g.pac.y][g.pac.x] == "#":
            check("Pac-Man never walks into a wall", False,
                  f"at {(g.pac.y, g.pac.x)}")
            return
        for gh in g.ghosts:
            if not gh.eaten and g.grid[gh.y][gh.x] == "#":
                check("ghosts never walk into walls", False,
                      f"at {(gh.y, gh.x)}")
                return

    check("Pac-Man never walks into a wall", True)
    check("ghosts never walk into walls", True)
    check("random play reaches a result", g.state == "over",
          f"state={g.state} after 20000 ticks")
    check("something was eaten", g.pellets < start_pellets or g.level > 1)
    check("outcome is decided", g.outcome in ("pac", "ghost"),
          f"outcome={g.outcome}")


def test_pacman_ghost_wins():
    print("\nPac-Man: ghost catches Pac-Man")
    random.seed(2)
    g = pacman.Game(80, 24)
    for _ in range(pacman.PAC_LIVES):
        g.lose_life()
    check("ghost wins after PAC_LIVES catches", g.outcome == "ghost")
    check("game is over", g.state == "over")
    check("caught count matches", g.caught == pacman.PAC_LIVES)


def test_pacman_clearing_wins():
    print("\nPac-Man: clearing the mazes")
    random.seed(3)
    g = pacman.Game(80, 24)
    for expected in range(2, pacman.LEVELS_TO_WIN + 1):
        g.pellets = 1
        g.eat(*_find_pellet(g))
        check(f"level {expected} starts after a clear", g.level == expected,
              f"level={g.level}")
    g.pellets = 1
    g.eat(*_find_pellet(g))
    check("Pac-Man wins after the last maze", g.outcome == "pac")


def _find_pellet(g):
    for y, row in enumerate(g.grid):
        for x, c in enumerate(row):
            if c in ".o":
                return y, x
    raise AssertionError("no pellet left to eat")


def test_pacman_power_pellet():
    print("\nPac-Man: power pellet flips the chase")
    random.seed(4)
    g = pacman.Game(80, 24)
    py, px = next((y, x) for y, r in enumerate(g.grid)
                  for x, c in enumerate(r) if c == "o")
    g.pac.y, g.pac.x = py, px
    g.eat(py, px)
    check("power pellet starts fright mode", g.fright > 0)

    ghost = g.ghosts[0]
    ghost.y, ghost.x = g.pac.y, g.pac.x
    lives_before = g.lives
    g.collide()
    check("frightened ghost is eaten, not Pac-Man", ghost.eaten)
    check("Pac-Man keeps his life", g.lives == lives_before)

    # and it comes back rather than sitting out forever
    for _ in range(pacman.GHOST_RESPAWN_TICKS + 5):
        g.update()
    check("eaten ghost respawns", not ghost.eaten)


def test_pacman_role_swap():
    print("\nPac-Man: roles swap on restart")
    g = pacman.Game(80, 24)
    first = g.pac_is_p1
    g.reset(swap_roles=True)
    check("R swaps who is Pac-Man", g.pac_is_p1 is not first)
    check("names follow the swap", g.pac_name() != g.hunter_name())


# ---------------------------------------------------------------------
# Pong simulation
# ---------------------------------------------------------------------
def test_pong_full_match():
    """Two players with human-like reaction lag. Perfect trackers would
    rally forever -- that is correct physics, not a bug -- so the bats
    here only re-aim every REACTION ticks, like someone actually playing."""
    print("\nPong: a full match")
    random.seed(5)
    g = pong.Game(80, 24)
    REACTION = 5
    max_rally = 0
    aim = {0: g.players[0].y, 1: g.players[1].y}

    for tick in range(200000):
        for p in g.players:
            if tick % REACTION == 0:
                aim[p.pid] = g.by
            centre = p.y + (pong.PADDLE_H - 1) / 2
            if aim[p.pid] < centre - 0.5:
                g.move_player(p.pid, -1)
            elif aim[p.pid] > centre + 0.5:
                g.move_player(p.pid, 1)
        g.update()
        max_rally = max(max_rally, g.rally)

        if not (g.top - 1 <= g.by <= g.bottom + 1):
            check("ball stays between the walls", False, f"by={g.by}")
            return
        if g.ball_speed() > pong.BALL_MAX_SPEED + 0.01:
            check("ball never exceeds BALL_MAX_SPEED", False,
                  f"speed={g.ball_speed():.3f}")
            return
        if g.state == "over":
            break

    check("ball stays between the walls", True)
    check("ball never exceeds BALL_MAX_SPEED", True)
    check("match reaches a winner", g.state == "over", f"state={g.state}")
    check("bats can return the ball", max_rally > 0, f"max rally={max_rally}")
    winner = g.winner()
    check("a winner is named", winner is not None)
    check("winner reached WIN_SCORE",
          winner is not None and winner.score >= pong.WIN_SCORE)


def test_pong_ball_can_get_past_a_bat():
    """If nobody moves, points must still happen -- otherwise the game
    could never end."""
    print("\nPong: a still bat concedes")
    random.seed(6)
    g = pong.Game(80, 24)
    for _ in range(100000):
        g.update()
        if g.state == "over":
            break
    check("a match between two motionless bats ends", g.state == "over",
          f"state={g.state}")


def test_pong_bats_stay_on_court():
    print("\nPong: bats stay on the court")
    g = pong.Game(80, 24)
    for _ in range(200):
        g.move_player(0, -1)
        g.move_player(1, 1)
    check("top bat stops at the wall", g.players[0].y >= g.top,
          f"y={g.players[0].y}")
    check("bottom bat stops at the wall",
          g.players[1].y + pong.PADDLE_H - 1 <= g.bottom,
          f"y={g.players[1].y}")


def test_pong_scoring():
    print("\nPong: scoring")
    g = pong.Game(80, 24)
    g.serve_timer = 0
    g.bx, g.bvx, g.bvy = 0.5, -0.5, 0.0
    g.by = (g.top + g.bottom) / 2
    before = g.players[1].score
    g.update()
    check("ball past the left wall scores for P2",
          g.players[1].score == before + 1)
    check("ball is re-served to the middle", abs(g.bx - g.w / 2) < 1.0)


# ---------------------------------------------------------------------
def main():
    test_maze()
    test_pacman_runs()
    test_pacman_ghost_wins()
    test_pacman_clearing_wins()
    test_pacman_power_pellet()
    test_pacman_role_swap()
    test_pong_full_match()
    test_pong_ball_can_get_past_a_bat()
    test_pong_bats_stay_on_court()
    test_pong_scoring()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
