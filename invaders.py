#!/usr/bin/env python3
"""
Two-player Space Invaders for the terminal.

    Player 1:   <-  ->   move        SPACE   fire
    Player 2:   A   D    move        W       fire

    P = pause      R = restart (after game over)      Q = quit

Both players share one screen. Run it inside tmux so two SSH
sessions can attach to the same game (see play-invaders.sh).

Nothing to install -- Python 3 and its built-in curses module is all
you need.
"""

import curses
import random
import time

# ---------------------------------------------------------------------
# TUNING KNOBS -- change these and see what happens!
# ---------------------------------------------------------------------
FPS = 20                   # game ticks per second

ALIEN_ROWS = 4             # rows of aliens
ALIEN_COLS = 9             # aliens per row
ALIEN_SPACING_X = 5        # horizontal gap between aliens
ALIEN_SPACING_Y = 2        # vertical gap between rows
ALIEN_TOP = 3              # screen row where the top alien row starts

ALIEN_STEP_TICKS = 10      # ticks between alien moves (LOWER = FASTER)
ALIEN_MIN_STEP_TICKS = 2   # the fastest they are ever allowed to get
ALIEN_BOMB_CHANCE = 0.25   # chance of a bomb each time the aliens move
BOMB_STEP_TICKS = 3        # ticks between bomb moves (LOWER = FASTER)

PLAYER_SPEED = 1           # cells moved per key press
PLAYER_COOLDOWN = 5        # ticks you must wait between your own shots
MAX_BULLETS = 3            # bullets in the air at once, per player
START_LIVES = 3            # lives each player starts with

WAVE_SPEEDUP = 3           # aliens get this much faster each wave

# Points for each alien row, top row first.
ROW_POINTS = [30, 20, 20, 10]

# Two frames per alien row, so they wiggle as they march.
# All of them must be ALIEN_W characters wide.
ALIEN_W = 3
ALIEN_FRAMES = [
    ("{o}", "[o]"),
    ("/M\\", "\\M/"),
    ("<X>", ">X<"),
    ("(*)", ")*("),
]

SHIPS = ["/^\\", "[^]"]    # player 1 and player 2
SHIP_W = 3
BULLET_CHAR = "|"
BOMB_CHAR = "!"

MIN_W, MIN_H = 60, 20      # smallest terminal the game will run in

# Colour pair numbers
C_P1, C_P2, C_ALIEN, C_BOMB, C_DIM = 1, 2, 3, 4, 5


# ---------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------
class Alien:
    __slots__ = ("x", "y", "row", "alive")

    def __init__(self, x, y, row):
        self.x = x
        self.y = y
        self.row = row
        self.alive = True


class Player:
    def __init__(self, pid, name, x):
        self.pid = pid
        self.name = name
        self.x = x
        self.home_x = x
        self.score = 0
        self.lives = START_LIVES
        self.cooldown = 0
        self.blink = 0        # >0 = just respawned: flashing and safe

    @property
    def alive(self):
        return self.lives > 0


class Game:
    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.left = 1
        self.right = width - 2
        self.ship_row = height - 3
        self.reset()

    def reset(self):
        self.wave = 1
        self.state = "play"          # play | pause | over
        self.players = [
            Player(0, "P1", self.w // 3 - 1),
            Player(1, "P2", 2 * self.w // 3 - 1),
        ]
        self.build_wave()

    def build_wave(self):
        self.aliens = []
        grid_w = (ALIEN_COLS - 1) * ALIEN_SPACING_X + ALIEN_W
        x0 = max(self.left + 1, (self.w - grid_w) // 2)
        for r in range(ALIEN_ROWS):
            for c in range(ALIEN_COLS):
                self.aliens.append(
                    Alien(x0 + c * ALIEN_SPACING_X,
                          ALIEN_TOP + r * ALIEN_SPACING_Y, r))
        self.direction = 1
        self.bullets = []            # [x, y, pid, dead]
        self.bombs = []              # [x, y, dead]
        self.tick = 0
        self.frame = 0

    # -- player actions ------------------------------------------------
    def move_player(self, pid, dx):
        p = self.players[pid]
        if not p.alive:
            return
        lo, hi = self.left, self.right - SHIP_W + 1
        p.x = max(lo, min(hi, p.x + dx * PLAYER_SPEED))

    def fire(self, pid):
        p = self.players[pid]
        if not p.alive or p.cooldown:
            return
        if sum(1 for b in self.bullets if b[2] == pid) >= MAX_BULLETS:
            return
        self.bullets.append([p.x + 1, self.ship_row - 1, pid, False])
        p.cooldown = PLAYER_COOLDOWN

    # -- simulation ----------------------------------------------------
    def alien_step_ticks(self):
        """Aliens speed up as their friends get shot, and each wave."""
        base = max(ALIEN_MIN_STEP_TICKS,
                   ALIEN_STEP_TICKS - (self.wave - 1) * WAVE_SPEEDUP)
        total = len(self.aliens)
        left = sum(1 for a in self.aliens if a.alive)
        if not total:
            return base
        return max(ALIEN_MIN_STEP_TICKS, int(base * left / total))

    def update(self):
        self.tick += 1

        for p in self.players:
            if p.cooldown:
                p.cooldown -= 1
            if p.blink:
                p.blink -= 1

        for b in self.bullets:
            b[1] -= 1
        self.bullets = [b for b in self.bullets if b[1] > 0 and not b[3]]

        if self.tick % BOMB_STEP_TICKS == 0:
            for m in self.bombs:
                m[1] += 1

        self.collide()

        if self.tick % self.alien_step_ticks() == 0:
            self.move_aliens()
            self.collide()

        self.bullets = [b for b in self.bullets if not b[3]]
        self.bombs = [m for m in self.bombs
                      if not m[2] and m[1] <= self.ship_row]

        if self.state == "play" and not any(a.alive for a in self.aliens):
            self.wave += 1
            self.build_wave()

    def move_aliens(self):
        self.frame ^= 1
        alive = [a for a in self.aliens if a.alive]
        if not alive:
            return

        xs = [a.x for a in alive]
        turning = ((self.direction > 0 and
                    max(xs) + ALIEN_W > self.right) or
                   (self.direction < 0 and min(xs) - 1 < self.left))
        if turning:
            self.direction *= -1
            for a in alive:
                a.y += 1
        else:
            for a in alive:
                a.x += self.direction

        if max(a.y for a in alive) >= self.ship_row:
            self.state = "over"        # they landed -- everyone loses
            return

        # Only the lowest alien in each column can drop a bomb.
        lowest = {}
        for a in alive:
            if a.x not in lowest or a.y > lowest[a.x].y:
                lowest[a.x] = a
        if lowest and random.random() < ALIEN_BOMB_CHANCE:
            shooter = random.choice(list(lowest.values()))
            self.bombs.append([shooter.x + ALIEN_W // 2, shooter.y + 1, False])

    def collide(self):
        # bullets vs aliens
        for b in self.bullets:
            if b[3]:
                continue
            for a in self.aliens:
                if (a.alive and a.y == b[1] and
                        a.x <= b[0] <= a.x + ALIEN_W - 1):
                    a.alive = False
                    b[3] = True
                    pts = ROW_POINTS[a.row % len(ROW_POINTS)]
                    self.players[b[2]].score += pts
                    break

        # bullets vs bombs -- you can shoot bombs out of the sky
        for b in self.bullets:
            if b[3]:
                continue
            for m in self.bombs:
                if not m[2] and m[0] == b[0] and abs(m[1] - b[1]) <= 1:
                    m[2] = True
                    b[3] = True
                    break

        # bombs vs ships
        for m in self.bombs:
            if m[2] or m[1] != self.ship_row:
                continue
            for p in self.players:
                if not p.alive or p.blink:
                    continue
                if p.x <= m[0] <= p.x + SHIP_W - 1:
                    m[2] = True
                    p.lives -= 1
                    p.blink = FPS       # about one second of safety
                    p.x = p.home_x
                    break

        if all(not p.alive for p in self.players):
            self.state = "over"


# ---------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------
def put(win, y, x, text, attr=0):
    """addstr that never explodes at the screen edge."""
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def colour(n):
    return curses.color_pair(n) if curses.has_colors() else 0


def draw(win, g):
    win.erase()

    # HUD
    p1, p2 = g.players
    put(win, 0, 1, f"{p1.name} {p1.score:05d} {'#' * p1.lives:<3}",
        colour(C_P1) | curses.A_BOLD)
    put(win, 0, g.w // 2 - 4, f"WAVE {g.wave}", colour(C_DIM))
    right = f"{'#' * p2.lives:>3} {p2.score:05d} {p2.name}"
    put(win, 0, g.w - len(right) - 1, right, colour(C_P2) | curses.A_BOLD)

    # aliens
    for a in g.aliens:
        if a.alive:
            glyph = ALIEN_FRAMES[a.row % len(ALIEN_FRAMES)][g.frame]
            put(win, a.y, a.x, glyph, colour(C_ALIEN) | curses.A_BOLD)

    # bullets and bombs
    for b in g.bullets:
        put(win, b[1], b[0], BULLET_CHAR,
            colour(C_P1 if b[2] == 0 else C_P2))
    for m in g.bombs:
        put(win, m[1], m[0], BOMB_CHAR, colour(C_BOMB) | curses.A_BOLD)

    # ships
    for p in g.players:
        if not p.alive:
            continue
        if p.blink and (g.tick // 2) % 2:
            continue                      # flash while respawning
        put(win, g.ship_row, p.x, SHIPS[p.pid],
            colour(C_P1 if p.pid == 0 else C_P2) | curses.A_BOLD)

    put(win, g.ship_row + 1, 1, "=" * (g.w - 2), colour(C_DIM))

    # bottom line
    if g.state == "pause":
        msg = "  PAUSED -- press P to carry on  "
        put(win, g.h - 1, (g.w - len(msg)) // 2, msg, curses.A_REVERSE)
    elif g.state == "over":
        if p1.score > p2.score:
            verdict = "P1 WINS!"
        elif p2.score > p1.score:
            verdict = "P2 WINS!"
        else:
            verdict = "IT'S A DRAW!"
        msg = f"  GAME OVER -- {verdict}   R = again   Q = quit  "
        put(win, g.h - 1, max(0, (g.w - len(msg)) // 2), msg, curses.A_REVERSE)
    else:
        put(win, g.h - 1, 1,
            "P1: arrows + space    P2: A/D + W    P pause   Q quit",
            colour(C_DIM))

    win.noutrefresh()
    curses.doupdate()


# ---------------------------------------------------------------------
# Input and main loop
# ---------------------------------------------------------------------
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
            g.reset()
            continue
        if g.state != "play":
            continue

        if ch == curses.KEY_LEFT:
            g.move_player(0, -1)
        elif ch == curses.KEY_RIGHT:
            g.move_player(0, 1)
        elif ch == ord(" "):
            g.fire(0)
        elif ch in (ord("a"), ord("A")):
            g.move_player(1, -1)
        elif ch in (ord("d"), ord("D")):
            g.move_player(1, 1)
        elif ch in (ord("w"), ord("W")):
            g.fire(1)


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
        curses.init_pair(C_P1, curses.COLOR_CYAN, bg)
        curses.init_pair(C_P2, curses.COLOR_YELLOW, bg)
        curses.init_pair(C_ALIEN, curses.COLOR_GREEN, bg)
        curses.init_pair(C_BOMB, curses.COLOR_RED, bg)
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
