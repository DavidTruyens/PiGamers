# PiGamers

A Raspberry Pi that two kids can SSH into over Tailscale and play terminal games
together — same game, same screen, two keyboards, two different houses.

They get a real Linux shell, so they pick up `ls`, `cd`, `nano` and `git` along
the way instead of clicking buttons.

```text
   Sam's laptop  ──┐
                   ├── Tailscale ──▶  pigamers  ──▶  one shared tmux session
   Finn's laptop ──┘                  (Raspberry Pi)      running the game
```

Three games so far: **Space Invaders**, **Pong**, and **Pac-Man vs Ghost**.

The first kid to run a game starts it. The second one attaches to the same tmux
session and lands in the same match, controlling player 2.

---

## Contents

1. [What you need](#1-what-you-need)
2. [Flash the SD card](#2-flash-the-sd-card)
3. [First boot](#3-first-boot)
4. [Create the kids' accounts](#4-create-the-kids-accounts)
5. [Install PiGamers](#5-install-pigamers)
6. [The console interface](#6-the-console-interface)
7. [Write the tailnet policy](#7-write-the-tailnet-policy)
8. [Install Tailscale on the Pi](#8-install-tailscale-on-the-pi)
9. [Share the Pi with the friend](#9-share-the-pi-with-the-friend)
10. [Lock the Pi out of your home network](#10-lock-the-pi-out-of-your-home-network)
11. [Playing](#11-playing)
12. [Linux cheat sheet for the kids](#12-linux-cheat-sheet-for-the-kids)
13. [Troubleshooting](#13-troubleshooting)
14. [What this protects, and what it doesn't](#14-what-this-protects-and-what-it-doesnt)

Throughout, `sam` and `finn` are placeholders — swap in the real names. The Pi's
hostname is `pigamers` and your own admin account is `david`.

---

## 1. What you need

| Thing | Notes |
| --- | --- |
| Raspberry Pi 4 Model B | What this guide was written for. A Pi 5, Pi 3 or Zero 2 W works too — it's a text game, any RAM size is plenty |
| microSD card, 16 GB+ | Class 10 or better |
| Official USB-C power supply | The Pi 4B wants 5V/3A. Underpowered supplies cause random reboots |
| Ethernet cable *or* Wi-Fi details | Either is fine |
| A Tailscale account | Free tier is plenty |

No monitor, no keyboard, no mouse. The whole thing is set up headless over SSH.
Keep an HDMI cable and a USB keyboard within reach anyway — it's the fallback
that needs no network at all.

---

## 2. Flash the SD card

Install [Raspberry Pi Imager](https://www.raspberrypi.com/software/) on your Mac,
then:

1. **Choose Device** → **Raspberry Pi 4**.
2. **Choose OS** → *Raspberry Pi OS (other)* → **Raspberry Pi OS Lite (64-bit)**.
   Lite has no desktop, which is exactly what you want.
3. **Choose Storage** → your SD card.
4. Click **Next**, then **Edit Settings** when it offers OS customisation. This
   step is what makes the headless setup work — don't skip it:

   **General tab**
   - Hostname: `pigamers`
   - Username: `david`, and set a password
   - Configure wireless LAN: your SSID and password (skip if using Ethernet)
   - Set locale settings: your timezone and keyboard layout

   **Services tab**
   - ✅ Enable SSH → **Allow public-key authentication only**
   - Paste your public key, or click *Run SSH-keygen* if you don't have one.
     On your Mac, your key is usually at `~/.ssh/id_ed25519.pub`:

     ```bash
     cat ~/.ssh/id_ed25519.pub
     ```

5. **Save**, then **Yes** to apply settings, then **Yes** to erase the card.

Setting SSH up here means you never have to touch the old `ssh` file trick or
plug in a keyboard.

---

## 3. First boot

Put the card in the Pi, connect Ethernet if you're using it, and power it up.

**Be patient here.** First boot resizes the filesystem and reboots once, so give
it several minutes. If you try too early you'll get `Connection refused` — that
means the Pi is up and answering, but `sshd` hasn't started yet. Wait and retry;
it isn't a sign anything is wrong.

From your Mac:

```bash
ssh david@pigamers.local
```

If `pigamers.local` doesn't resolve, find the Pi's address in your router's
DHCP client list and use the IP instead.

Update everything and install what the games need:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y tmux git python3 nano htop
sudo reboot
```

`tmux` is what lets two SSH sessions share one screen. `python3` and its `curses`
module are already on Raspberry Pi OS, but installing explicitly costs nothing.

---

## 4. Create the kids' accounts

One Linux account each. They learn that accounts are real, and each gets their own
home directory and shell history.

```bash
# A group whose members are allowed to join a shared game session.
sudo groupadd gamers

# One account per kid. You'll be prompted for a password for each.
sudo adduser sam
sudo adduser finn

sudo usermod -aG gamers sam
sudo usermod -aG gamers finn

# Add yourself too, or you can't join their games -- the shared game
# socket is mode 770, owned by the 'gamers' group.
sudo usermod -aG gamers david
```

The kids are deliberately **not** added to the `sudo` group. They can break their
own account and nothing else.

Check it worked:

```bash
groups sam      # -> sam : sam gamers
groups david    # -> david : david adm sudo ... gamers
```

> **Group membership is only evaluated at login.** If you add someone to `gamers`
> while they're logged in, they must log out and back in. To pick it up in the
> session you're already in, run `newgrp gamers`.

---

## 5. Install PiGamers

Clone into `/opt` so it belongs to the machine rather than to any one account:

```bash
sudo git clone https://github.com/DavidTruyens/PiGamers.git /opt/pigamers
sudo chgrp -R gamers /opt/pigamers
sudo chmod -R g+rX /opt/pigamers
sudo chmod +x /opt/pigamers/*.sh /opt/pigamers/games
```

Put the commands on everyone's `PATH`:

```bash
sudo ln -sf /opt/pigamers/play-invaders.sh /usr/local/bin/play-invaders
sudo ln -sf /opt/pigamers/play-pong.sh     /usr/local/bin/play-pong
sudo ln -sf /opt/pigamers/play-pacman.sh   /usr/local/bin/play-pacman
sudo ln -sf /opt/pigamers/games            /usr/local/bin/games
```

Now `games`, `play-invaders`, `play-pong` and `play-pacman` work from
anywhere, for anyone.

To pick up new games later, anyone can run:

```bash
cd /opt/pigamers && sudo git pull
```

---

## 6. The console interface

A banner when they log in, so the shell isn't a blank intimidating prompt.

```bash
sudo tee /etc/motd > /dev/null <<'EOF'

   ▄▄▄· ▪   ▄▄ •  ▄▄▄· • ▌ ▄ ·. ▄▄▄ .▄▄▄  .▄▄ ·
  ▐█ ▄███ ▐█ ▀ ▪▐█ ▀█ ·██ ▐███▪▀▄.▀·▀▄ █·▐█ ▀.
   ██▀·▐█·▄█ ▀█▄▄█▀▀█ ▐█ ▌▐▌▐█·▐▀▀▪▄▐▀▀▄ ▄▀▀▀█▄
  ▐█▪·•▐█▌▐█▄▪▐█▐█ ▪▐▌██ ██▌▐█▌▐█▄▄▌▐█•█▌▐█▄▪▐█
  .▀   ▀▀▀·▀▀▀▀  ▀  ▀ ▀▀  █▪▀▀▀ ▀▀▀ .▀  ▀ ▀▀▀▀

  Type  games          to see what you can play
  Type  play-invaders  aliens are landing, shoot them
  Type  play-pong      first to 7 wins
  Type  play-pacman    one runs, one hunts
  Type  who            to see who else is logged in

EOF
```

Log out and back in to see it.

The `games` command ships in the repo, so `git pull` keeps it current as you add
games. Plain `bash` otherwise — they get a real prompt, which is the point.

---

## 7. Write the tailnet policy

Do this **before** the next step. Tailscale refuses to apply a tag that isn't
declared in the policy first.

Open the [Access Controls page](https://login.tailscale.com/admin/acls) in the
Tailscale admin console. A new tailnet ships wide open:

```json
{
  "grants": [
    { "src": ["*"], "dst": ["*"], "ip": ["*"] }
  ]
}
```

> **If your tailnet already has devices on it, merge rather than replace.**
> The stock policy also carries an `ssh` block allowing `autogroup:member` to
> reach `autogroup:self` — that is what lets you `tailscale ssh` into your own
> machines, and pasting over it will break them. Keep every rule you already
> have and add the `tag:pigamers` ones below.
>
> Before saving, check whether any existing device is **tagged**:
> a tagged device is not covered by `autogroup:self` and would lose access.
>
> ```bash
> tailscale status --json | grep -A2 '"Tags"'
> ```

Replace the whole file with this. Substitute the kids' real Tailscale emails:

```jsonc
{
  // tag:pigamers makes the Pi owned by the tailnet rather than by you.
  // Two reasons this matters:
  //   1. Tailscale will not let one user SSH into another *user's* device.
  //      Tagging is what makes shared-user access possible at all.
  //   2. Tagged devices don't expire, so the Pi won't drop off the tailnet
  //      in six months.
  "tagOwners": {
    "tag:pigamers": ["autogroup:admin"],
  },

  "grants": [
    // Your own devices can still reach each other, as before.
    { "src": ["autogroup:member"], "dst": ["autogroup:self"], "ip": ["*"] },

    // You keep full access to the Pi for admin.
    { "src": ["autogroup:admin"], "dst": ["tag:pigamers"], "ip": ["*"] },

    // Everyone the Pi is shared with reaches the Pi, on port 22, and
    // nothing else. No grant lists tag:pigamers as a *source*, so the Pi
    // cannot start connections to anything else on your tailnet either.
    { "src": ["autogroup:shared"], "dst": ["tag:pigamers"], "ip": ["22"] },
  ],

  "ssh": [
    // You, as any account on the Pi.
    {
      "action": "check",
      "src":    ["autogroup:member"],
      "dst":    ["tag:pigamers"],
      "users":  ["autogroup:nonroot", "root"],
    },

    // The kids, only as their own accounts. Never as root, never as you.
    //
    // These must be real Tailscale logins. autogroup:shared works in
    // grants (above) but is REJECTED here -- ssh rules accept only
    // individual users, groups, autogroup:member or autogroup:tagged.
    {
      "action": "accept",
      "src":    ["sams-login@example.com", "finns-login@example.com"],
      "dst":    ["tag:pigamers"],
      "users":  ["sam", "finn"],
    },
  ],
}
```

The Linux usernames in `users` must match the accounts you made in section 4
exactly. That pairing fails silently if it drifts.

Click **Save**. The console validates as you save, so a rejected selector shows
up immediately rather than silently doing nothing.

`grants` are default-deny: anything not listed is refused. That's why the Pi
appears only as a destination.

---

## 8. Install Tailscale on the Pi

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh --advertise-tags=tag:pigamers
```

Open the URL it prints and approve the machine. Then confirm:

```bash
tailscale status
tailscale ip -4
```

`--ssh` hands SSH to Tailscale, so the kids need no SSH keys and no passwords —
access is their tailnet identity, and you revoke it in the admin console.

Two flags deliberately **not** used: `--advertise-exit-node` and
`--advertise-routes`. Either would turn the Pi into a doorway onto your home
network, which is the opposite of what section 10 is for. `--accept-routes` is
off by default; leave it off.

**Test it from your Mac before going further:**

```bash
ssh david@pigamers
```

You want this working *before* the firewall step.

---

## 9. Share the Pi with the friend

The friend (or their parent) makes a free Tailscale account. Then, in your
[Machines](https://login.tailscale.com/admin/machines) list:

1. Click the `pigamers` machine → **Share…**
2. Enter their email, or copy the share link and send it over.

This is the strongest boundary in the whole setup, because it isn't a rule you
have to get right — it's how sharing works. Per Tailscale's docs, sharing "gives
the recipient access to only the shared machine in your tailnet, and nothing
else", and the Pi is quarantined so it can't initiate connections back into
*their* home network either.

Once they accept, from their machine:

```bash
ssh finn@pigamers
```

---

## 10. Lock the Pi out of your home network

The kids have a real shell on the Pi. Without this step, that shell can reach
your NAS, your router's admin page, your work laptop, and everything else on the
LAN. This blocks that.

### What the rules do

They filter **outbound** traffic only, and only *new* connections:

- You SSH in from your Mac → that's an **inbound** connection. The reply traffic
  matches `established,related`, the first rule, so it passes. **Admin access
  keeps working.**
- A kid runs `ssh david@192.168.1.50` or `nmap 192.168.1.0/24` → **outbound new**
  to a private address. Refused.

Nothing is dropped on input. That asymmetry is what makes this safe to apply
without locking yourself out.

### Fix DNS first

If the Pi's resolver is your router, these rules break name resolution. Check:

```bash
cat /etc/resolv.conf
```

If the nameserver is a `192.168.x.x` / `10.x.x.x` address, point it at a public
resolver instead. On Raspberry Pi OS Bookworm and newer (NetworkManager):

```bash
nmcli connection show                      # find your connection's name
sudo nmcli connection modify "<name>" ipv4.ignore-auto-dns yes ipv4.dns "1.1.1.1 9.9.9.9"
sudo nmcli connection up "<name>"
cat /etc/resolv.conf                       # should now show 1.1.1.1
```

A nameserver of `100.100.100.100` is Tailscale MagicDNS — that's inside the
allowed range, so it's fine as-is.

### Write the rules

```bash
sudo tee /etc/nftables.conf > /dev/null <<'EOF'
#!/usr/sbin/nft -f
# Keep the kids' shells off the home LAN.
flush ruleset

table inet pigamers {
    chain output {
        type filter hook output priority 0; policy accept;

        # Replies to connections that came IN — this is what keeps your
        # own admin SSH working. Must stay first.
        ct state established,related accept

        oifname "lo"         accept
        oifname "tailscale0" accept

        ip  daddr 100.64.0.0/10 accept    # the tailnet itself
        udp dport { 67, 68 }    accept    # DHCP lease renewal

        # New connections to any private network: refused.
        # "reject" rather than "drop" so it fails instantly with
        # "Network unreachable" instead of hanging for 30 seconds.
        ip  daddr 10.0.0.0/8     reject
        ip  daddr 172.16.0.0/12  reject
        ip  daddr 192.168.0.0/16 reject
        ip  daddr 169.254.0.0/16 reject
        ip6 daddr fc00::/7       reject
        ip6 daddr fe80::/10      reject
    }
}
EOF
```

### Apply with a safety net

For the first apply, use a dead-man's switch. If anything goes wrong, walk away
for ten minutes and the Pi undoes it by itself:

```bash
sudo sh -c 'nft -f /etc/nftables.conf; sleep 600; nft flush ruleset' &
```

Now, in a **second terminal**, check that everything you care about still works:

```bash
ssh david@pigamers.local    # LAN admin access
ssh david@pigamers          # tailnet access
```

and on the Pi:

```bash
ping -c2 1.1.1.1            # internet: works
sudo apt update             # DNS + internet: works
ping -c2 192.168.1.1        # your router: "Network unreachable" — correct
```

Happy with it? Make it permanent:

```bash
sudo systemctl enable --now nftables
```

**Rollback**, if you ever need it:

```bash
sudo systemctl disable --now nftables
sudo nft flush ruleset
```

### Optional: the strongest version

Everything above runs *on the box the kids have shells on*. If you want a
boundary they can't reach at all, put the Pi on your router's guest network or a
separate VLAN with client isolation enabled. Then the containment is enforced by
hardware they have no access to, and the nftables rules become a second layer
rather than the only one.

---

## 11. Playing

Each kid opens a terminal and runs:

```bash
ssh sam@pigamers      # or finn@pigamers
games                 # see what's available
play-pong             # ...or play-invaders, or play-pacman
```

Whoever runs a game first starts it. The second one joins the same session
and is player 2 automatically. Each game has its own session, so you can
leave a Pac-Man match running and go play Pong.

### Space Invaders

Aliens march down the screen; shoot them before they land. Both of you
share the wave and compete on score.

| | Move | Fire |
| --- | --- | --- |
| **Player 1** | `←` `→` | `SPACE` |
| **Player 2** | `A` `D` | `W` |

### Pong

The angle the ball leaves your bat depends on *where* it hits — middle
sends it flat, edges send it steep. Aiming beats hammering the keys. The
ball speeds up on every return. First to 7.

| | Move |
| --- | --- |
| **Player 1** (left bat) | `↑` `↓` |
| **Player 2** (right bat) | `W` `S` |

### Pac-Man vs Ghost

One of you is Pac-Man clearing the maze; the other drives the red ghost
hunting them, helped by three computer ghosts. Eat a big `o` and it flips
— for six seconds the ghosts are scared and Pac-Man can eat *them*.

Pac-Man wins by clearing three mazes. The ghost wins by catching Pac-Man
three times. Press `R` at the end to **swap roles** and go again, so
neither of them is stuck being the ghost.

| | Move |
| --- | --- |
| **Pac-Man** | `←` `→` `↑` `↓` |
| **Red ghost** | `W` `A` `S` `D` |

### In every game

`P` pauses · `R` restarts after game over · `Q` quits

Both need a terminal at least **80×24**. Smaller and the game refuses to
start.

To force a stuck game to end:

```bash
tmux -S /tmp/pigamers-pong.sock kill-server      # or -invaders, or -pacman
```

## 12. Linux cheat sheet for the kids

Stick this on the wall.

| Command | What it does |
| --- | --- |
| `games` | See what you can play |
| `play-invaders` | Start Space Invaders |
| `play-pong` | Start Pong |
| `play-pacman` | Start Pac-Man vs Ghost |
| `ls` | List the files here |
| `cd folder` | Go into a folder — `cd ..` goes back up |
| `pwd` | Where am I? |
| `cat file` | Show what's in a file |
| `nano file` | Edit a file — `Ctrl+O` saves, `Ctrl+X` quits |
| `who` | Who else is logged in right now |
| `whoami` | Who am I logged in as |
| `groups` | Which groups I'm in |
| `htop` | Live view of what the Pi is doing — `q` quits |
| `df -h` | How much disk space is left |
| `uptime` | How long the Pi has been running |
| `history` | Every command you've typed |
| `clear` | Clean up the screen |
| `exit` | Log out |

Something to try: open `invaders.py` in `nano`, find the block marked
**TUNING KNOBS** near the top, change `ALIEN_ROWS` to `6`, save, and play again.

```bash
cd /opt/pigamers
nano invaders.py
```

(They can't save changes in `/opt` — it's not theirs. Copy it into their home
directory first with `cp /opt/pigamers/invaders.py ~/` and run
`python3 ~/invaders.py`. That's a useful lesson in file permissions on its own.)

---

## 13. Troubleshooting

**"Connection refused" on the very first SSH.** Almost always means the Pi is
still booting, not that anything is misconfigured. `avahi` starts early, so
`pigamers.local` resolves before `sshd` is listening — the port is closed, the Pi
sends a RST, and you get *refused* rather than a timeout. Wait and retry; first
boot resizes the filesystem and reboots once, so it can take several minutes.

The distinction is worth knowing, because the two errors mean opposite things:

| Error | Meaning |
| --- | --- |
| `Connection refused` | Host is up and reachable, nothing listening on 22 — still booting, or SSH was never enabled |
| `Operation timed out` / `No route to host` | Host isn't reachable at all — wrong IP, not on the network, not powered |

If it's *still* refused after ten minutes, then SSH genuinely isn't enabled —
reflash and make sure the Imager **Services** tab has *Enable SSH* ticked.

**`pigamers.local` won't resolve.** mDNS is unreliable on some networks. Use the
Pi's LAN IP from your router's client list, or its tailnet name once Tailscale is
running.

**`"autogroup:shared" is not allowed in src` when saving the policy.** You put
it in an `ssh` rule. It is valid in `grants` but not in `ssh` — swap it for the
kids' actual Tailscale logins.

**`tailscale up` says the tag is not permitted.** `tag:pigamers` is not declared
in `tagOwners` yet. Section 7 has to be saved before section 8 runs.

**Your other tailnet devices stopped talking after saving the policy.**
Un-comment the `{"src": ["*"], "dst": ["*"], "ip": ["*"]}` grant to restore
everything instantly, then reintroduce the restrictions one rule at a time.

**The kids can't SSH in.** Check in order:

```bash
tailscale status                    # on the Pi: is it connected and tagged?
```

Then in the admin console, confirm the machine shows `tag:pigamers`, that the
share was accepted, and that the `ssh` rule lists the right email and usernames.

**The second player joins but sees a squashed playfield.** See *Known issues*
below.

**"Terminal is 74x22, need at least 60x20".** Make the terminal window bigger
before running `play-invaders`.

**`error connecting to /tmp/pigamers-*.sock (Permission denied)`.** You aren't in
the `gamers` group, or you are but haven't logged in again since being added. The
game socket is mode 770 owned by that group.

```bash
groups                          # is 'gamers' listed?
sudo usermod -aG gamers david   # if not
newgrp gamers                   # pick it up without logging out
```

**The game is stuck or nobody can join.** Kill that game's session:

```bash
tmux -S /tmp/pigamers-invaders.sock kill-server
tmux -S /tmp/pigamers-pong.sock kill-server
tmux -S /tmp/pigamers-pacman.sock kill-server
```

**"server exited unexpectedly" when starting a game.** tmux is reporting
that the game crashed the instant it launched. Run it directly to see the
real error instead of tmux's summary:

```bash
python3 /opt/pigamers/pong.py
```

**Rallies in Pong go on forever.** Two good players can out-last the ball.
Open `pong.py`, raise `BALL_MAX_SPEED` in the TUNING KNOBS block, and try
again — that's the knob that decides whether a bat can always catch up.

**`apt update` fails after the firewall step.** DNS. Re-read *Fix DNS first* in
section 10 — the Pi is almost certainly still pointed at your router.

**Locked out entirely.** HDMI cable, USB keyboard, log in at the console. No
network needed. Then `sudo nft flush ruleset`.

---

## 14. What this protects, and what it doesn't

Being straight about the boundaries, since that was the point of the design.

**Solid:**

- **The friend reaches only the Pi.** Enforced by Tailscale's sharing model, not
  by a rule you have to maintain correctly.
- **The Pi can't initiate connections to your other tailnet devices.** No grant
  lists it as a source, and `grants` are default-deny.
- **The kids have no `sudo`.** They can wreck their own home directory. That's it.
- **Nothing is exposed to the internet.** No port forwarding anywhere. The Pi is
  reachable over the tailnet or your LAN, and that's all.

**Weaker than it looks:**

- **The nftables rules run on the machine the kids control.** If either of them
  ever got root on the Pi, they could flush the rules. Realistically that means a
  Linux privilege-escalation exploit, and they're ten — but it's why the
  guest-VLAN option in section 10 is the version to reach for if you want a real
  boundary rather than a very effective speed bump.
- **Shared tmux means shared trust.** Whoever attaches second gets full control of
  a tmux session running as the *first* kid's user — including the ability to
  press `Ctrl-B` `c` and open a shell as them. Between two friends this is fine.
  If it ever isn't, the fix is to run the game as a dedicated `invaders` service
  user that owns the session, so neither kid's account is exposed to the other.
- **If the Pi is compromised, it's on your LAN.** The firewall stops it dialling
  out to your NAS, but it's still physically attached to your network. Guest VLAN
  solves this properly.

**If it all goes wrong:** reflash the SD card and run through this README again.
Twenty minutes, and nothing of value is lost. That's the intended disaster
recovery plan.

---

## Known issues

- **`play-invaders.sh:22` may not be doing anything.** It calls
  `tmux set-option -t "$SESSION" window-size manual`. The tmux manual confirms
  `window-size` is a **window** option (the `resize-window` entry notes it sets
  `window-size` to manual "in the window options"), while `-t "$SESSION"` targets
  a session. tmux 3.x may resolve this anyway, since `set-option` can look up
  window options by name — **untested on hardware either way**, and the trailing
  `|| true` swallows any error silently. The symptom would be the playfield
  shrinking to whoever has the smaller terminal when the second player joins.
  If you see that squash, try `set-window-option -t "$SESSION" window-size manual`
  and drop the `|| true` while you're debugging.
- **Direct LAN connections between Tailscale peers are blocked** by the firewall
  in section 10. If your Mac and the Pi are on the same network, Tailscale falls
  back to relaying through a DERP server instead of connecting directly. Adds a
  little latency; irrelevant for a text game.

---

## Adding another game

1. Drop `yourgame.py` in `/opt/pigamers/`.
2. Copy `play-pong.sh` to `play-yourgame.sh` and change the last word to
   `yourgame`. That's the whole wrapper — `play-game.sh` does the tmux work
   and gives every game its own socket.
3. Add a line to the `GAMES` list in the `games` script.
4. Symlink it: `sudo ln -sf /opt/pigamers/play-yourgame.sh /usr/local/bin/play-yourgame`
5. `git push`, then on the Pi: `cd /opt/pigamers && sudo git pull`.

Keep each game in one self-contained file. They deliberately don't share
code, so your son can break `pong.py` without stopping Pac-Man from working.

Run the tests before you push — they play whole matches with no terminal:

```bash
python3 test_games.py
```
