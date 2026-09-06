#!/usr/bin/env python3
"""
Two-player Pong for the terminal.

    Player 1 (left bat):    UP / DOWN arrows
    Player 2 (right bat):   W / S

    P = pause      R = play again (after game over)      Q = quit

Both players share one screen. Run it inside tmux so two SSH sessions
can attach to the same game (see play-pong.sh).

Nothing to install -- Python 3 and its built-in curses module is all
you need.
"""

import curses
import random
import time

# ---------------------------------------------------------------------
# TUNING KNOBS -- change these and see what happens!
# ---------------------------------------------------------------------
FPS = 30                   # game ticks per second

PADDLE_H = 4               # how tall each bat is
PADDLE_SPEED = 1           # rows moved per key press
PADDLE_INSET = 2           # how far the bats sit from the side walls

BALL_START_SPEED = 0.30    # cells per tick at the start of a rally
BALL_SPEEDUP = 1.06        # ball gets this much faster on every hit
BALL_MAX_SPEED = 1.10      # ... but never faster than this
MAX_BOUNCE_ANGLE = 0.75    # how much edge-of-bat hits steer the ball

WIN_SCORE = 7              # first to this many points wins the match
SERVE_DELAY = FPS          # ticks to wait before each serve

PADDLE_CHAR = "|"
BALL_CHAR = "O"
NET_CHAR = ":"

MIN_W, MIN_H = 40, 14      # smallest terminal the game will run in

# Colour pair numbers
C_P1, C_P2, C_BALL, C_DIM = 1, 2, 3, 4


# ---------------------------------------------------------------------
# Game objects
# ---------------------------------------------------------------------
class Paddle:
    def __init__(self, pid, name, x):
        self.pid = pid
        self.name = name
        self.x = x
        self.y = 0
        self.score = 0


class Game:
    """All the rules live here. Nothing in this class touches curses,
    which is what lets the tests play a whole match with no screen."""

    def __init__(self, width, height):
        self.w = width
        self.h = height
        self.top = 1                # first row the ball may occupy
        self.bottom = height - 3    # last row the ball may occupy
        self.reset()

    def reset(self):
        self.state = "play"         # play | pause | over
        self.players = [
            Paddle(0, "P1", PADDLE_INSET),
            Paddle(1, "P2", self.w - 1 - PADDLE_INSET),
        ]
        middle = (self.top + self.bottom) // 2 - PADDLE_H // 2
        for p in self.players:
            p.y = middle
        self.serve(random.choice((-1, 1)))

    def serve(self, direction):
        """Put the ball back in the middle, heading `direction`."""
        self.bx = self.w / 2
        self.by = (self.top + self.bottom) / 2
        self.bvx = direction * BALL_START_SPEED
        self.bvy = random.uniform(-0.3, 0.3) * BALL_START_SPEED
        self.serve_timer = SERVE_DELAY
        self.rally = 0

    # -- player actions ------------------------------------------------
    def move_player(self, pid, dy):
        p = self.players[pid]
        lo, hi = self.top, self.bottom - PADDLE_H + 1
        p.y = max(lo, min(hi, p.y + dy * PADDLE_SPEED))

    # -- simulation ----------------------------------------------------
    def ball_speed(self):
        return (self.bvx ** 2 + self.bvy ** 2) ** 0.5

    def update(self):
        if self.serve_timer > 0:
            self.serve_timer -= 1
            return

        self.bx += self.bvx
        self.by += self.bvy

        # bounce off the top and bottom walls
        if self.by <= self.top:
            self.by = self.top
            self.bvy = abs(self.bvy)
        elif self.by >= self.bottom:
            self.by = self.bottom
            self.bvy = -abs(self.bvy)

        self.check_paddles()
        self.check_points()

    def check_paddles(self):
        for p in self.players:
            heading_at_me = (self.bvx < 0) if p.pid == 0 else (self.bvx > 0)
            if not heading_at_me:
                continue
            # Did the ball cross this bat's column on this tick?
            if abs(self.bx - p.x) > abs(self.bvx) + 0.5:
                continue
            if not (p.y <= self.by <= p.y + PADDLE_H - 1):
                continue
            self.bounce(p)

    def bounce(self, p):
        """Where the ball hits the bat decides the angle it leaves at,
        so aiming matters more than hammering the keys."""
        half = (PADDLE_H - 1) / 2
        centre = p.y + half
        offset = (self.by - centre) / half if half else 0.0
        offset = max(-1.0, min(1.0, offset))

        speed = min(BALL_MAX_SPEED, self.ball_speed() * BALL_SPEEDUP)
        self.bvy = offset * MAX_BOUNCE_ANGLE * speed
        sideways = max(0.15, (speed ** 2 - self.bvy ** 2) ** 0.5)
        self.bvx = sideways if p.pid == 0 else -sideways
        self.bx = p.x + (1 if p.pid == 0 else -1)
        self.rally += 1

    def check_points(self):
        if self.bx < 1:
            self.point_to(1, serve_towards=-1)
        elif self.bx > self.w - 2:
            self.point_to(0, serve_towards=1)

    def point_to(self, pid, serve_towards):
        self.players[pid].score += 1
        if self.players[pid].score >= WIN_SCORE:
            self.state = "over"
        else:
            self.serve(serve_towards)

    def winner(self):
        p1, p2 = self.players
        if p1.score > p2.score:
            return p1
        if p2.score > p1.score:
            return p2
        return None


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

    p1, p2 = g.players

    # scoreboard
    put(win, 0, 2, f"{p1.name}  {p1.score}", colour(C_P1) | curses.A_BOLD)
    right = f"{p2.score}  {p2.name}"
    put(win, 0, g.w - len(right) - 2, right, colour(C_P2) | curses.A_BOLD)
    put(win, 0, g.w // 2 - 3, f"to {WIN_SCORE}", colour(C_DIM))

    # the net
    for y in range(g.top, g.bottom + 1):
        if y % 2 == 0:
            put(win, y, g.w // 2, NET_CHAR, colour(C_DIM))

    # bats
    for p in g.players:
        for i in range(PADDLE_H):
            put(win, p.y + i, p.x, PADDLE_CHAR,
                colour(C_P1 if p.pid == 0 else C_P2) | curses.A_BOLD)

    # ball -- hidden during the pause before a serve, so you can see it coming
    if g.serve_timer == 0 or (g.serve_timer // 4) % 2 == 0:
        put(win, round(g.by), round(g.bx), BALL_CHAR,
            colour(C_BALL) | curses.A_BOLD)

    # bottom line
    if g.state == "pause":
        msg = "  PAUSED -- press P to carry on  "
        put(win, g.h - 1, (g.w - len(msg)) // 2, msg, curses.A_REVERSE)
    elif g.state == "over":
        win_p = g.winner()
        verdict = f"{win_p.name} WINS!" if win_p else "IT'S A DRAW!"
        msg = f"  GAME OVER -- {verdict}   R = again   Q = quit  "
        put(win, g.h - 1, max(0, (g.w - len(msg)) // 2), msg, curses.A_REVERSE)
    else:
        put(win, g.h - 1, 1,
            "P1: up/down arrows    P2: W/S    P pause   Q quit",
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

        if ch == curses.KEY_UP:
            g.move_player(0, -1)
        elif ch == curses.KEY_DOWN:
            g.move_player(0, 1)
        elif ch in (ord("w"), ord("W")):
            g.move_player(1, -1)
        elif ch in (ord("s"), ord("S")):
            g.move_player(1, 1)


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
        curses.init_pair(C_BALL, curses.COLOR_WHITE, bg)
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
