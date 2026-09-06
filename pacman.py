#!/usr/bin/env python3
"""
Pac-Man vs Ghost -- a two-player chase for the terminal.

One of you is Pac-Man, trying to clear the maze. The other drives the
red ghost, trying to catch them. Three more ghosts help the hunter.

    Pac-Man:      arrow keys
    Red ghost:    W A S D

    Eat a big 'o' and the tables turn: for a few seconds the ghosts are
    scared and Pac-Man can eat THEM.

    P = pause     R = play again, swapping roles     Q = quit

Pac-Man wins by clearing LEVELS_TO_WIN mazes.
The ghost wins by catching Pac-Man PAC_LIVES times.

Both players share one screen. Run it inside tmux so two SSH sessions
can attach to the same game (see play-pacman.sh).
"""

import curses
import random
import time

# ---------------------------------------------------------------------
# TUNING KNOBS -- change these and see what happens!
# ---------------------------------------------------------------------
FPS = 20                   # game ticks per second

PAC_STEP_TICKS = 3         # ticks between Pac-Man moves (LOWER = FASTER)
GHOST_STEP_TICKS = 5       # ticks between ghost moves at level 1
GHOST_SPEEDUP = 1          # ghosts get this much faster each level
GHOST_MIN_STEP_TICKS = 2   # ... but never faster than this

FRIGHT_TICKS = FPS * 6     # how long a power pellet lasts
GHOST_RESPAWN_TICKS = FPS * 3   # how long an eaten ghost sits out
GHOST_RANDOMNESS = 0.15    # chance an AI ghost picks a random turn

PAC_LIVES = 3              # catches before the ghost wins
LEVELS_TO_WIN = 3          # mazes to clear before Pac-Man wins
RESPAWN_PAUSE = FPS        # freeze after a catch, so you see it happen

PELLET_POINTS = 10
POWER_POINTS = 50
GHOST_POINTS = 200

MIN_W, MIN_H = 31, 19      # smallest terminal the game will run in

# The maze. '#' wall, '.' pellet, 'o' power pellet, ' ' empty corridor.
# Every row must be the same length -- the tests check this.
MAZE = [
    "###########################",
    "#............#............#",
    "#o####.#####.#.#####.####o#",
    "#.####.#####.#.#####.####.#",
    "#.........................#",
    "#.####.#.#########.#.####.#",
    "#......#.....#.....#......#",
    "######.#####.#.#####.######",
    "#......#.....#.....#......#",
    "#.####.#.#########.#.####.#",
    "#.........................#",
    "#.####.#####.#.#####.####.#",
    "#o####.#####.#.#####.####o#",
    "#............#............#",
    "###########################",
]

PAC_START = (13, 6)
GHOST_STARTS = [(6, 12), (6, 14), (8, 12), (8, 14)]

UP, DOWN, LEFT, RIGHT = (-1, 0), (1, 0), (0, -1), (0, 1)
DIRS = [UP, DOWN, LEFT, RIGHT]

PAC_GLYPH = {UP: "V", DOWN: "^", LEFT: ">", RIGHT: "<"}

# Colour pair numbers
C_WALL, C_PELLET, C_PAC, C_HUNTER, C_GHOST, C_FRIGHT, C_DIM = 1, 2, 3, 4, 5, 6, 7


def opposite(d):
    return (-d[0], -d[1])


# ---------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------
class Mover:
    def __init__(self, y, x, direction):
        self.y = y
        self.x = x
        self.home = (y, x)
        self.dir = direction

    def go_home(self):
        self.y, self.x = self.home


class Ghost(Mover):
    def __init__(self, y, x, player_driven=False):
        super().__init__(y, x, random.choice(DIRS))
        self.player_driven = player_driven
        self.eaten = False
        self.eaten_timer = 0

    def reset(self):
        self.go_home()
        self.eaten = False
        self.eaten_timer = 0
        self.dir = random.choice(DIRS)


class Game:
    """All the rules live here. Nothing in this class touches curses,
    which is what lets the tests play whole games with no screen."""

    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.pac_is_p1 = True
        self.reset()

    def reset(self, swap_roles=False):
        if swap_roles:
            self.pac_is_p1 = not self.pac_is_p1
        self.state = "play"          # play | pause | over
        self.level = 1
        self.lives = PAC_LIVES
        self.score = 0
        self.caught = 0
        self.outcome = None          # "pac" | "ghost" once state == "over"
        self.build_level()

    def build_level(self):
        self.grid = [list(row) for row in MAZE]
        self.pellets = sum(row.count(".") + row.count("o") for row in MAZE)
        self.pac = Mover(PAC_START[0], PAC_START[1], LEFT)
        self.want_dir = LEFT
        self.ghosts = [
            Ghost(y, x, player_driven=(i == 0))
            for i, (y, x) in enumerate(GHOST_STARTS)
        ]
        self.fright = 0
        self.freeze = 0
        self.tick = 0

    # -- helpers -------------------------------------------------------
    def wall(self, y, x):
        if not (0 <= y < len(self.grid) and 0 <= x < len(self.grid[0])):
            return True
        return self.grid[y][x] == "#"

    def ghost_step_ticks(self):
        return max(GHOST_MIN_STEP_TICKS,
                   GHOST_STEP_TICKS - (self.level - 1) * GHOST_SPEEDUP)

    @property
    def hunter(self):
        """The ghost the second player drives."""
        return self.ghosts[0]

    # -- player actions ------------------------------------------------
    def steer_pac(self, direction):
        if self.state == "play":
            self.want_dir = direction

    def steer_hunter(self, direction):
        if self.state != "play":
            return
        g = self.hunter
        if not self.wall(g.y + direction[0], g.x + direction[1]):
            g.dir = direction

    # -- simulation ----------------------------------------------------
    def update(self):
        self.tick += 1

        if self.freeze > 0:
            self.freeze -= 1
            return

        if self.fright > 0:
            self.fright -= 1

        for g in self.ghosts:
            if g.eaten:
                g.eaten_timer -= 1
                if g.eaten_timer <= 0:
                    g.eaten = False

        if self.tick % PAC_STEP_TICKS == 0:
            self.move_pac()
            self.collide()

        if self.tick % self.ghost_step_ticks() == 0:
            self.move_ghosts()
            self.collide()

    def move_pac(self):
        # Turn if the way is clear, otherwise keep going.
        if not self.wall(self.pac.y + self.want_dir[0],
                         self.pac.x + self.want_dir[1]):
            self.pac.dir = self.want_dir
        ny = self.pac.y + self.pac.dir[0]
        nx = self.pac.x + self.pac.dir[1]
        if self.wall(ny, nx):
            return
        self.pac.y, self.pac.x = ny, nx
        self.eat(ny, nx)

    def eat(self, y, x):
        cell = self.grid[y][x]
        if cell == ".":
            self.grid[y][x] = " "
            self.pellets -= 1
            self.score += PELLET_POINTS
        elif cell == "o":
            self.grid[y][x] = " "
            self.pellets -= 1
            self.score += POWER_POINTS
            self.fright = FRIGHT_TICKS

        if self.pellets == 0:
            self.finish_level()

    def finish_level(self):
        if self.level >= LEVELS_TO_WIN:
            self.state = "over"
            self.outcome = "pac"
        else:
            self.level += 1
            self.build_level()

    def move_ghosts(self):
        for g in self.ghosts:
            if g.eaten:
                continue
            if g.player_driven:
                ny, nx = g.y + g.dir[0], g.x + g.dir[1]
                if not self.wall(ny, nx):
                    g.y, g.x = ny, nx
            else:
                g.dir = self.choose_dir(g)
                g.y += g.dir[0]
                g.x += g.dir[1]

    def choose_dir(self, g):
        """Head for Pac-Man, or away when scared. Never turn back on
        yourself unless it's the only way out of a dead end."""
        options = [d for d in DIRS
                   if not self.wall(g.y + d[0], g.x + d[1])
                   and d != opposite(g.dir)]
        if not options:
            back = opposite(g.dir)
            return back if not self.wall(g.y + back[0], g.x + back[1]) else g.dir

        if random.random() < GHOST_RANDOMNESS:
            return random.choice(options)

        def distance(d):
            dy = g.y + d[0] - self.pac.y
            dx = g.x + d[1] - self.pac.x
            return dy * dy + dx * dx

        return (max if self.fright > 0 else min)(options, key=distance)

    def collide(self):
        for g in self.ghosts:
            if g.eaten or (g.y, g.x) != (self.pac.y, self.pac.x):
                continue
            if self.fright > 0:
                g.eaten = True
                g.eaten_timer = GHOST_RESPAWN_TICKS
                g.go_home()
                self.score += GHOST_POINTS
            else:
                self.lose_life()
                return

    def lose_life(self):
        self.lives -= 1
        self.caught += 1
        self.fright = 0
        if self.lives <= 0:
            self.state = "over"
            self.outcome = "ghost"
            return
        self.pac.go_home()
        self.pac.dir = LEFT
        self.want_dir = LEFT
        for g in self.ghosts:
            g.reset()
        self.freeze = RESPAWN_PAUSE

    # -- naming --------------------------------------------------------
    def pac_name(self):
        return "P1" if self.pac_is_p1 else "P2"

    def hunter_name(self):
        return "P2" if self.pac_is_p1 else "P1"


# ---------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------
def put(win, y, x, text, attr=0):
    """addstr that never explodes at the screen edge."""
    try:
        win.addstr(int(y), int(x), text, attr)
    except curses.error:
        pass


def colour(n):
    return curses.color_pair(n) if curses.has_colors() else 0


def draw(win, g):
    win.erase()

    oy = 1
    ox = max(0, (g.w - len(g.grid[0])) // 2)

    # HUD
    put(win, 0, 2, f"{g.pac_name()} PAC {g.score:05d}  {'C' * g.lives}",
        colour(C_PAC) | curses.A_BOLD)
    put(win, 0, g.w // 2 - 4, f"LEVEL {g.level}/{LEVELS_TO_WIN}", colour(C_DIM))
    right = f"caught {g.caught}  GHOST {g.hunter_name()}"
    put(win, 0, g.w - len(right) - 2, right, colour(C_HUNTER) | curses.A_BOLD)

    # maze
    for y, row in enumerate(g.grid):
        for x, cell in enumerate(row):
            if cell == "#":
                put(win, oy + y, ox + x, "#", colour(C_WALL))
            elif cell == ".":
                put(win, oy + y, ox + x, ".", colour(C_PELLET))
            elif cell == "o":
                put(win, oy + y, ox + x, "o",
                    colour(C_PELLET) | curses.A_BOLD)

    # ghosts
    for gh in g.ghosts:
        if gh.eaten:
            continue
        if g.fright > 0:
            # flash when the power pellet is about to run out
            if g.fright < FPS and (g.tick // 3) % 2:
                pair, glyph = (C_HUNTER if gh.player_driven else C_GHOST), "M"
            else:
                pair, glyph = C_FRIGHT, "w"
        else:
            pair = C_HUNTER if gh.player_driven else C_GHOST
            glyph = "M"
        put(win, oy + gh.y, ox + gh.x, glyph, colour(pair) | curses.A_BOLD)

    # Pac-Man -- flashes while frozen after being caught
    if g.freeze == 0 or (g.tick // 2) % 2:
        put(win, oy + g.pac.y, ox + g.pac.x, PAC_GLYPH[g.pac.dir],
            colour(C_PAC) | curses.A_BOLD)

    # bottom line
    pac_keys = "arrows" if g.pac_is_p1 else "WASD"
    hunt_keys = "WASD" if g.pac_is_p1 else "arrows"
    if g.state == "pause":
        msg = "  PAUSED -- press P to carry on  "
        put(win, g.h - 1, (g.w - len(msg)) // 2, msg, curses.A_REVERSE)
    elif g.state == "over":
        verdict = ("PAC-MAN WINS!" if g.outcome == "pac"
                   else "THE GHOST WINS!")
        msg = f"  {verdict}   R = swap roles and play again   Q = quit  "
        put(win, g.h - 1, max(0, (g.w - len(msg)) // 2), msg, curses.A_REVERSE)
    else:
        put(win, g.h - 1, 1,
            f"Pac-Man ({g.pac_name()}): {pac_keys}   "
            f"Ghost ({g.hunter_name()}): {hunt_keys}   P pause  Q quit",
            colour(C_DIM))

    win.noutrefresh()
    curses.doupdate()


# ---------------------------------------------------------------------
# Input and main loop
# ---------------------------------------------------------------------
ARROWS = {curses.KEY_UP: UP, curses.KEY_DOWN: DOWN,
          curses.KEY_LEFT: LEFT, curses.KEY_RIGHT: RIGHT}
WASD = {ord("w"): UP, ord("W"): UP, ord("s"): DOWN, ord("S"): DOWN,
        ord("a"): LEFT, ord("A"): LEFT, ord("d"): RIGHT, ord("D"): RIGHT}


def handle_input(win, g):
    """Drain every pending keystroke -- two people are typing at once."""
    while True:
        ch = win.getch()
        if ch == -1:
            return False
        if ch in (ord("q"), ord("Q")):
            return True
        if ch in (ord("p"), ord("P")) and g.state in ("play", "pause"):
            g.state = "pause" if g.state == "play" else "play"
            continue
        if g.state == "over" and ch in (ord("r"), ord("R")):
            g.reset(swap_roles=True)
            continue
        if g.state != "play":
            continue

        # Whoever is Pac-Man this round gets the arrows.
        if ch in ARROWS:
            (g.steer_pac if g.pac_is_p1 else g.steer_hunter)(ARROWS[ch])
        elif ch in WASD:
            (g.steer_hunter if g.pac_is_p1 else g.steer_pac)(WASD[ch])


def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        curses.init_pair(C_WALL, curses.COLOR_BLUE, bg)
        curses.init_pair(C_PELLET, curses.COLOR_WHITE, bg)
        curses.init_pair(C_PAC, curses.COLOR_YELLOW, bg)
        curses.init_pair(C_HUNTER, curses.COLOR_RED, bg)
        curses.init_pair(C_GHOST, curses.COLOR_MAGENTA, bg)
        curses.init_pair(C_FRIGHT, curses.COLOR_CYAN, bg)
        curses.init_pair(C_DIM, curses.COLOR_BLUE, bg)

    h, w = stdscr.getmaxyx()
    if w < MIN_W or h < MIN_H:
        stdscr.nodelay(False)
        put(stdscr, 0, 0, f"Terminal is {w}x{h}, need at least "
                          f"{MIN_W}x{MIN_H}.")
        put(stdscr, 1, 0, "Make the window bigger, then press any key.")
        stdscr.refresh()
        stdscr.getch()
        return

    game = Game(w, h)
    frame_time = 1.0 / FPS
    next_frame = time.monotonic()

    while True:
        if handle_input(stdscr, game):
            break
        if game.state == "play":
            game.update()
        draw(stdscr, game)

        next_frame += frame_time
        delay = next_frame - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        else:
            next_frame = time.monotonic()


if __name__ == "__main__":
    curses.wrapper(main)
