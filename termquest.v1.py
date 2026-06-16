#!/usr/bin/env python3
# Copyright (c) 2026 eigamestudio. All rights reserved.
# File: termquest.v1.py (Client)
# Forbidden from being used for sexually explicit or illegal content.
# ============================================================
#  TermQuest RPG — client.py  v1.0 it might have some bug because
#                             this game is making in 2day
#
#  Singleplayer : python client.py
#  Multiplayer  : python client.py <ip> [port]
#
#  Pure Python stdlib — no pip needed
# can play on  Windows / Linux / Mac / Termux
# ============================================================

import os, sys, json, socket, threading, time, random, select

# ── Windows ANSI enable ──────────────────────────────────────
if sys.platform == "win32":
    import ctypes
    kernel = ctypes.windll.kernel32
    kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)

# ── Cross-platform raw input ─────────────────────────────────
#
#  Unix strategy: hold the terminal in cbreak mode for the whole
#  game loop so select.select() fires on every keypress without
#  waiting for Enter.  Temporarily restore cooked mode only for
#  blocking input() calls (world names, server IPs, etc.).
#
if sys.platform == "win32":
    import msvcrt

    def _term_init():    pass
    def _term_restore(): pass
    def _term_cooked():  pass   # context: run input() in cooked mode
    def _term_raw():     pass

    def _getch():
        c = msvcrt.getwch()
        if isinstance(c, bytes):
            c = c.decode("utf-8", "replace")
        return c

    def _kbhit():
        return msvcrt.kbhit()

else:
    import tty, termios, atexit

    _fd      = sys.stdin.fileno()
    _oldterm = termios.tcgetattr(_fd)

    def _term_init():
        """Enter cbreak mode — keys are delivered immediately."""
        tty.setcbreak(_fd)

    def _term_restore():
        """Restore original terminal settings (called on exit)."""
        try:
            termios.tcsetattr(_fd, termios.TCSADRAIN, _oldterm)
        except Exception:
            pass

    def _term_cooked():
        """Temporarily restore cooked mode for blocking input()."""
        try:
            termios.tcsetattr(_fd, termios.TCSADRAIN, _oldterm)
        except Exception:
            pass

    def _term_raw():
        """Re-enter cbreak mode after a blocking input() call."""
        try:
            tty.setcbreak(_fd)
        except Exception:
            pass

    def _getch():
        return sys.stdin.read(1)

    def _kbhit():
        return select.select([sys.stdin], [], [], 0)[0] != []

    atexit.register(_term_restore)

# ============================================================
#  SHARED CONSTANTS  (must match server.py)
# ============================================================

VERSION      = "1.0"
DEFAULT_PORT = 8080
MAX_MSG_LEN  = 65536

MOVE_COOLDOWN   = 0.15
ATTACK_COOLDOWN = 0.50
CHAT_COOLDOWN   = 1.00
ACTION_COOLDOWN = 0.30

WORLD_W = 120
WORLD_H = 120
SPAWN_X = 60
SPAWN_Y = 60

TILES = {
    "." : {"name":"Grass",    "walkable":True,  "mineable":False},
    "~" : {"name":"Water",    "walkable":False, "mineable":False, "swim":True},
    "T" : {"name":"Tree",     "walkable":False, "mineable":True,  "drop":"wood",     "qty":2},
    "#" : {"name":"Stone",    "walkable":False, "mineable":True,  "drop":"stone",    "qty":1},
    "^" : {"name":"Mountain", "walkable":False, "mineable":True,  "drop":"stone",    "qty":3},
    "*" : {"name":"Flower",   "walkable":True,  "mineable":True,  "drop":"flower",   "qty":1},
    "s" : {"name":"Sand",     "walkable":True,  "mineable":True,  "drop":"sand",     "qty":1},
    "c" : {"name":"Coal",     "walkable":False, "mineable":True,  "drop":"coal",     "qty":2},
    "i" : {"name":"Iron",     "walkable":False, "mineable":True,  "drop":"iron",     "qty":1},
    "g" : {"name":"Gold Ore", "walkable":False, "mineable":True,  "drop":"gold_ore", "qty":1},
    "w" : {"name":"Wood Blk", "walkable":False, "mineable":True,  "drop":"wood",     "qty":1},
    "b" : {"name":"Stone Blk","walkable":False, "mineable":True,  "drop":"stone",    "qty":1},
}

WEAPONS = {
    "fist":        {"dmg":3,  "price":0,   "desc":"Bare hands"},
    "dagger":      {"dmg":8,  "price":30,  "desc":"Fast blade"},
    "sword":       {"dmg":15, "price":80,  "desc":"Iron sword"},
    "axe":         {"dmg":20, "price":120, "desc":"Heavy axe"},
    "spear":       {"dmg":18, "price":100, "desc":"Long reach"},
    "warhammer":   {"dmg":25, "price":200, "desc":"Devastating"},
    "wood_sword":  {"dmg":6,  "price":0,   "desc":"Crafted"},
    "stone_sword": {"dmg":12, "price":0,   "desc":"Crafted"},
    "iron_sword":  {"dmg":22, "price":0,   "desc":"Crafted"},
}

ARMORS = {
    "none":         {"def":0,  "price":0,   "desc":"No armor"},
    "leather":      {"def":5,  "price":40,  "desc":"Light"},
    "chainmail":    {"def":10, "price":100, "desc":"Medium"},
    "iron_plate":   {"def":18, "price":180, "desc":"Heavy"},
    "dragon_scale": {"def":30, "price":500, "desc":"Ultimate"},
}

CONSUMABLES = {
    "health_potion":{"heal":30,   "price":20,  "desc":"Heals 30 HP"},
    "mega_potion":  {"heal":70,   "price":50,  "desc":"Heals 70 HP"},
    "elixir":       {"heal":9999, "price":120, "desc":"Full heal"},
}

CRAFTING = {
    "wood_sword":  {"wood":3},
    "stone_sword": {"stone":4},
    "iron_sword":  {"iron":3},
    "stone_block": {"stone":1},
    "wood_block":  {"wood":1},
}

LEVELS = {
    1: {"xp":0,    "hp":100,"atk":5, "def":0,  "title":"Novice"},
    2: {"xp":50,   "hp":120,"atk":7, "def":1,  "title":"Apprentice"},
    3: {"xp":120,  "hp":150,"atk":9, "def":2,  "title":"Warrior"},
    4: {"xp":250,  "hp":190,"atk":12,"def":3,  "title":"Knight"},
    5: {"xp":450,  "hp":240,"atk":15,"def":5,  "title":"Champion"},
    6: {"xp":700,  "hp":300,"atk":18,"def":7,  "title":"Hero"},
    7: {"xp":1000, "hp":370,"atk":22,"def":9,  "title":"Legend"},
    8: {"xp":1400, "hp":450,"atk":26,"def":12, "title":"Master"},
    9: {"xp":1900, "hp":540,"atk":31,"def":15, "title":"Grand Master"},
    10:{"xp":2500, "hp":650,"atk":36,"def":18, "title":"Immortal"},
}

ENEMIES = {
    "slime": {"hp":20, "atk":4, "def":0,"xp":10,"gold":5,  "char":"S","range":1,"speed":0.8},
    "goblin":{"hp":35, "atk":8, "def":2,"xp":20,"gold":12, "char":"G","range":1,"speed":0.6},
    "orc":   {"hp":60, "atk":14,"def":5,"xp":40,"gold":25, "char":"O","range":1,"speed":0.5},
    "troll": {"hp":90, "atk":20,"def":8,"xp":70,"gold":40, "char":"R","range":2,"speed":0.4},
    "dragon":{"hp":200,"atk":35,"def":15,"xp":150,"gold":100,"char":"D","range":2,"speed":0.3},
}

def net_encode(msg: dict) -> bytes:
    data = json.dumps(msg, separators=(",",":"))
    if len(data) > MAX_MSG_LEN:
        raise ValueError("Message too large")
    return (data + "\n").encode("utf-8")

def net_decode(line: str) -> dict:
    if len(line) > MAX_MSG_LEN:
        raise ValueError("Message too large")
    return json.loads(line.strip())

# ============================================================
#  ANSI HELPERS
# ============================================================

A = {
    "reset":"\033[0m", "bold":"\033[1m", "dim":"\033[2m",
    "black":"\033[30m","red":"\033[31m","green":"\033[32m",
    "yellow":"\033[33m","blue":"\033[34m","magenta":"\033[35m",
    "cyan":"\033[36m","white":"\033[37m",
    "bg_blue":"\033[44m","bg_red":"\033[41m","bg_black":"\033[40m",
    "blink":"\033[5m",
}

TILE_DISPLAY = {
    ".":("green",  "."), "~":("blue",  "~"), "T":("green","T"),
    "#":("white",  "#"), "^":("white", "^"), "*":("magenta","*"),
    "s":("yellow", "s"), "c":("dim",   "c"), "i":("cyan",  "i"),
    "g":("yellow", "g"), "w":("yellow","w"), "b":("white", "b"),
    " ":("dim",    " "),
}

PLAYER_COL = {
    "white":"\033[37m","red":"\033[31m","green":"\033[32m",
    "yellow":"\033[33m","blue":"\033[34m","magenta":"\033[35m","cyan":"\033[36m",
}

def c(text, *codes):
    return "".join(A.get(x,"") for x in codes) + text + A["reset"]

def render_tile(t):
    col, ch = TILE_DISPLAY.get(t, ("white", t))
    return A.get(col,"") + ch + A["reset"]

def term_size():
    try:
        import shutil
        s = shutil.get_terminal_size((80, 24))
        return s.columns, s.lines
    except Exception:
        return 80, 24

def clear():    print("\033[2J\033[H", end="", flush=True)
def mv(r, col): print(f"\033[{r};{col}H", end="", flush=True)
def hide_cur(): print("\033[?25l", end="", flush=True)
def show_cur(): print("\033[?25h", end="", flush=True)

def box(out, row, col, h, w, title=""):
    y = A["yellow"]+A["bold"]
    r = A["reset"]
    out.append(f"\033[{row};{col}H{y}+{'─'*(w-2)}+{r}")
    for i in range(1, h-1):
        out.append(f"\033[{row+i};{col}H{y}│{r}{' '*(w-2)}{y}│{r}")
    out.append(f"\033[{row+h-1};{col}H{y}+{'─'*(w-2)}+{r}")
    if title:
        t  = f" {title} "
        tc = col + (w - len(t)) // 2
        out.append(f"\033[{row};{tc}H{y}{t}{r}")

def put(out, row, col, text, *colors):
    cc = "".join(A.get(x,"") for x in colors)
    out.append(f"\033[{row};{col}H{cc}{text}{A['reset']}")

# ============================================================
#  SETTINGS / WORLDS / SERVERS
# ============================================================

SETTINGS_FILE = "settings.json"
SERVERS_FILE  = "servers.json"
WORLDS_DIR    = "worlds"

def load_settings():
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass

def load_servers():
    try:
        with open(SERVERS_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_servers(lst):
    try:
        with open(SERVERS_FILE, "w") as f:
            json.dump(lst, f, indent=2)
    except Exception:
        pass

def get_worlds():
    os.makedirs(WORLDS_DIR, exist_ok=True)
    worlds = []
    for name in sorted(os.listdir(WORLDS_DIR)):
        path = os.path.join(WORLDS_DIR, name)
        if not os.path.isdir(path):
            continue
        meta = {}
        mf = os.path.join(path, "meta.json")
        if os.path.exists(mf):
            try:
                with open(mf) as f:
                    meta = json.load(f)
            except Exception:
                pass
        worlds.append({"name": name, "path": path, **meta})
    return worlds

def save_world_meta(path):
    try:
        with open(os.path.join(path, "meta.json"), "w") as f:
            json.dump({"last_played": time.strftime("%Y-%m-%d %H:%M")}, f)
    except Exception:
        pass

def create_world_dir(name, seed=None):
    path = os.path.join(WORLDS_DIR, name)
    os.makedirs(path, exist_ok=True)
    if seed is None:
        seed = random.randint(0, 999_999_999)
    sf = os.path.join(path, "seed.json")
    if not os.path.exists(sf):
        with open(sf, "w") as f:
            json.dump({"seed": seed}, f)
    return path

# ============================================================
#  GAME STATE
# ============================================================

state = {
    "mode":    "menu",   # menu|sp_worlds|mp_list|mp_auth|game|dead|pause
    "sp":      False,
    "connected": False,
    "username": "",
    "op":      False,

    # player
    "x": SPAWN_X, "y": SPAWN_Y,
    "hp":100,"mhp":100,
    "lvl":1,"xp":0,"gold":50,
    "atk":5,"def":0,
    "weapon":"fist","armor":"none",
    "inv": {},
    "kills":0,"deaths":0,
    "char":"@","col":"white",

    # world
    "world":{},    # "x,y" -> tile
    "world_w":WORLD_W,"world_h":WORLD_H,

    # entities
    "players":{},  # name -> {x,y,hp,mhp,lvl,char,col}
    "enemies": {},  # eid  -> {type,x,y,hp,mhp,char}

    # UI
    "messages":   [],
    "input":      "",
    "input_mode": "cmd",
    "menu_sel":   0,
    "dead_sel":   0,
    "pause_sel":  0,
    "world_sel":  0,
    "srv_sel":    0,
    "worlds":     [],
    "servers":    [],

    # auth
    "auth_step":  "username",
    "auth_fields":["",""],
    "auth_error": "",
    "server_req_pw": False,

    # timing
    "last_move":  0.0,
    "last_attack":0.0,
    "last_action":0.0,
    "water_time": 0.0,
    "death_cause":"",
}

_lock = threading.Lock()

def add_msg(text: str):
    with _lock:
        for line in str(text).split("\n"):
            if line.strip():
                state["messages"].append(line)
        if len(state["messages"]) > 300:
            state["messages"] = state["messages"][-300:]

def get_tile(x, y):
    return state["world"].get(f"{x},{y}", ".")

# ============================================================
#  SINGLEPLAYER WORLD GENERATION
# ============================================================

def _sp_noise(wx, wy, seed, scale):
    def grad(gx, gy):
        r = random.Random(seed ^ (gx * 73856093) ^ (gy * 19349663))
        return r.uniform(-1.0, 1.0)
    gx, gy = wx/scale, wy/scale
    x0, y0 = int(gx), int(gy)
    tx, ty  = gx-x0, gy-y0
    sx = tx*tx*(3-2*tx)
    sy = ty*ty*(3-2*ty)
    v  = (1-sy)*((1-sx)*grad(x0,y0)   + sx*grad(x0+1,y0)) + \
            sy *((1-sx)*grad(x0,y0+1) + sx*grad(x0+1,y0+1))
    return (v+1)/2

# lazy tile generator — tiles generated on demand, never store full grid
_sp_cache  = {}
_sp_seed   = None

def sp_gen_tile(wx, wy):
    key = f"{wx},{wy}"
    if key in _sp_cache:
        return _sp_cache[key]
    if not (0 <= wx < WORLD_W and 0 <= wy < WORLD_H):
        return "#"
    h = _sp_noise(wx, wy, _sp_seed,    50)
    m = _sp_noise(wx, wy, _sp_seed+1,  25)
    t = _sp_noise(wx, wy, _sp_seed+2,  18)
    f = _sp_noise(wx, wy, _sp_seed+3,  9)
    o = _sp_noise(wx, wy, _sp_seed+4,  12)
    if   h < 0.25: tile = "~"
    elif h < 0.30: tile = "s"
    elif m > 0.80: tile = "^"
    elif m > 0.65: tile = "#"
    elif t > 0.68: tile = "T"
    elif f > 0.80: tile = "*"
    else:          tile = "."
    if tile in ("#","^"):
        if   o > 0.85: tile = "g"
        elif o > 0.72: tile = "i"
        elif o > 0.58: tile = "c"
    # protect spawn
    if abs(wx-SPAWN_X) <= 7 and abs(wy-SPAWN_Y) <= 7 and tile != "~":
        tile = "."
    _sp_cache[key] = tile
    return tile

def sp_set_tile(wx, wy, tile):
    key = f"{wx},{wy}"
    _sp_cache[key] = tile
    if tile == ".":
        state["world"].pop(key, None)
    else:
        state["world"][key] = tile

def sp_load_view():
    cx, cy = state["x"], state["y"]
    tiles  = {}
    for dy in range(-35, 36):
        for dx in range(-35, 36):
            wx, wy = cx+dx, cy+dy
            t = sp_gen_tile(wx, wy)
            if t != ".":
                tiles[f"{wx},{wy}"] = t
    state["world"]   = tiles
    state["world_w"] = WORLD_W
    state["world_h"] = WORLD_H

def sp_find_safe(cx, cy, radius=40):
    for r in range(radius):
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if abs(dx) != r and abs(dy) != r:
                    continue
                nx, ny = cx+dx, cy+dy
                if TILES.get(sp_gen_tile(nx, ny), {}).get("walkable"):
                    return nx, ny
    return cx, cy

# ============================================================
#  SINGLEPLAYER PLAYER SAVE / LOAD
# ============================================================

_sp_player_file = None
_sp_world_path  = None

def sp_save_player():
    if not _sp_player_file:
        return
    data = {k: state[k] for k in (
        "username","x","y","hp","mhp","lvl","xp","gold",
        "atk","def","weapon","armor","inv","kills","deaths","char","col"
    )}
    try:
        tmp = _sp_player_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _sp_player_file)
    except Exception:
        pass

def sp_load_player():
    if not _sp_player_file or not os.path.exists(_sp_player_file):
        return
    try:
        with open(_sp_player_file) as f:
            d = json.load(f)
        for k in ("x","y","hp","mhp","lvl","xp","gold","atk","def",
                  "weapon","armor","inv","kills","deaths","char","col"):
            if k in d:
                state[k] = d[k]
        state["username"] = d.get("username", state["username"])
    except Exception:
        pass

# ============================================================
#  SINGLEPLAYER ENEMIES
# ============================================================

_sp_enemies   = {}   # eid -> dict
_sp_enemy_id  = [0]
_sp_last_spawn = [0.0]

def sp_spawn_enemy():
    etype = random.choice(list(ENEMIES.keys()))
    data  = ENEMIES[etype]
    cx, cy = state["x"], state["y"]
    for _ in range(40):
        ex = cx + random.randint(-18, 18)
        ey = cy + random.randint(-18, 18)
        if abs(ex-cx) < 6 and abs(ey-cy) < 6:
            continue
        if TILES.get(sp_gen_tile(ex, ey), {}).get("walkable"):
            _sp_enemy_id[0] += 1
            eid = _sp_enemy_id[0]
            _sp_enemies[eid] = {
                "id":eid,"type":etype,
                "x":ex,"y":ey,
                "hp":data["hp"],"mhp":data["hp"],
                "atk":data["atk"],"def":data["def"],
                "xp":data["xp"],"gold":data["gold"],
                "char":data["char"],
                "range":data["range"],"speed":data["speed"],
                "last_move":0.0,"last_attack":0.0,
                "wander_t":0.0,"wdx":0,"wdy":0,
            }
            return eid
    return None

def sp_enemy_tick():
    now = time.time()
    cx, cy = state["x"], state["y"]

    # spawn up to 10 nearby
    if now - _sp_last_spawn[0] > 3.0 and len(_sp_enemies) < 10:
        _sp_last_spawn[0] = now
        sp_spawn_enemy()

    dmg_taken = 0

    for eid, e in list(_sp_enemies.items()):
        dist = abs(e["x"]-cx) + abs(e["y"]-cy)

        # attack player
        if dist <= e["range"] and now - e["last_attack"] >= ATTACK_COOLDOWN:
            e["last_attack"] = now
            arm  = ARMORS.get(state["armor"], ARMORS["none"])
            dmg  = max(1, e["atk"] - arm["def"] - state["def"] + random.randint(-1, 2))
            dmg_taken += dmg

        # move
        if now - e["last_move"] < e["speed"]:
            continue
        e["last_move"] = now

        if dist <= 12:
            ddx = 0 if e["x"]==cx else (1 if cx>e["x"] else -1)
            ddy = 0 if e["y"]==cy else (1 if cy>e["y"] else -1)
            if random.random() < 0.5: ddy = 0
            else:                     ddx = 0
        else:
            if now - e["wander_t"] > 2.0:
                e["wander_t"] = now
                e["wdx"] = random.choice([-1,0,0,1])
                e["wdy"] = random.choice([-1,0,0,1])
            ddx, ddy = e["wdx"], e["wdy"]

        nx, ny = e["x"]+ddx, e["y"]+ddy
        if TILES.get(sp_gen_tile(nx,ny),{}).get("walkable") and not(nx==cx and ny==cy):
            e["x"], e["y"] = nx, ny

    if dmg_taken > 0:
        state["hp"] = max(0, state["hp"] - dmg_taken)
        add_msg(f"Enemies hit you for {dmg_taken}! HP:{state['hp']}/{state['mhp']}")
        if state["hp"] <= 0:
            state["mode"] = "dead"
            state["death_cause"] = "combat"
            state["deaths"] += 1
            sp_save_player()

    # update enemy display
    state["enemies"] = {str(eid): {
        "type":e["type"],"x":e["x"],"y":e["y"],
        "hp":e["hp"],"mhp":e["mhp"],"char":e["char"],
    } for eid,e in _sp_enemies.items()}

def sp_drown_tick():
    now = time.time()
    wt  = state.get("water_time", 0)
    if not wt or state["mode"] != "game":
        return
    secs = now - wt
    if secs > 5:
        dmg = max(1, int((secs-5)/2))
        state["hp"] = max(0, state["hp"] - dmg)
        state["water_time"] = now - 4
        add_msg(f"Drowning! -{dmg} HP! ({state['hp']}/{state['mhp']})")
        if state["hp"] <= 0:
            state["mode"]       = "dead"
            state["death_cause"] = "Drowning"
            state["deaths"] += 1
            state["water_time"] = 0
            sp_save_player()

# ============================================================
#  SINGLEPLAYER COMMAND HANDLER
# ============================================================

DIRS = {"w":(0,-1),"a":(-1,0),"s":(0,1),"d":(1,0)}

def sp_handle(raw: str):
    raw   = raw.strip()
    if not raw:
        return
    parts = raw.split()
    cmd   = parts[0].lower()
    args  = parts[1:]
    now   = time.time()

    # ── MOVE / ATTACK ──
    if cmd in DIRS:
        if now - state["last_move"] < MOVE_COOLDOWN:
            return
        state["last_move"] = now
        dx, dy = DIRS[cmd]
        nx, ny = state["x"]+dx, state["y"]+dy

        # check enemy at target tile → attack
        hit = next((eid for eid,e in _sp_enemies.items()
                    if e["x"]==nx and e["y"]==ny), None)
        if hit is not None:
            if now - state["last_attack"] < ATTACK_COOLDOWN:
                return
            state["last_attack"] = now
            e   = _sp_enemies[hit]
            wpn = WEAPONS.get(state["weapon"], WEAPONS["fist"])
            arm = e["def"]
            dmg = max(1, wpn["dmg"] + state["atk"] - arm + random.randint(-2, 3))
            e["hp"] -= dmg
            add_msg(f"Hit {e['type']} for {dmg}! (HP:{max(0,e['hp'])}/{e['mhp']})")
            if e["hp"] <= 0:
                xp, gold, et = e["xp"], e["gold"], e["type"]
                del _sp_enemies[hit]
                state["xp"]    += xp
                state["gold"]  += gold
                state["kills"] += 1
                add_msg(f"Killed {et}! +{xp}XP +{gold}g")
                _sp_levelup()
                sp_save_player()
            return

        # move
        t = sp_gen_tile(nx, ny)
        if TILES.get(t, {}).get("walkable"):
            state["x"], state["y"] = nx, ny
            if TILES.get(t, {}).get("swim"):
                if not state["water_time"]:
                    state["water_time"] = now
                    add_msg("Swimming! Stay too long and you drown.")
            else:
                state["water_time"] = 0
            sp_load_view()
        else:
            add_msg(f"Blocked by {TILES.get(t,{}).get('name', t)}.")

    # ── MINE ──
    elif cmd == "mine":
        if not args or args[0] not in DIRS:
            add_msg("Usage: mine w/a/s/d"); return
        if now - state["last_action"] < ACTION_COOLDOWN:
            return
        state["last_action"] = now
        dx, dy = DIRS[args[0]]
        tx, ty = state["x"]+dx, state["y"]+dy
        t  = sp_gen_tile(tx, ty)
        td = TILES.get(t, {})
        if not td.get("mineable"):
            add_msg("Nothing to mine there."); return
        sp_set_tile(tx, ty, ".")
        inv = state["inv"]
        inv[td["drop"]] = inv.get(td["drop"], 0) + td["qty"]
        add_msg(f"Mined {td['name']}! Got {td['qty']}x {td['drop']}.")
        sp_load_view()

    # ── PLACE ──
    elif cmd == "place":
        if len(args) < 2 or args[0] not in DIRS:
            add_msg("Usage: place w/a/s/d wood|stone"); return
        if now - state["last_action"] < ACTION_COOLDOWN:
            return
        state["last_action"] = now
        dx, dy  = DIRS[args[0]]
        tx, ty  = state["x"]+dx, state["y"]+dy
        block   = args[1].lower()
        blk_map = {"wood":"w","stone":"b","wood_block":"w","stone_block":"b"}
        mat_map = {"wood":"wood","stone":"stone","wood_block":"wood","stone_block":"stone"}
        bc = blk_map.get(block)
        mn = mat_map.get(block)
        if not bc:
            add_msg("Use: wood or stone"); return
        if state["inv"].get(mn, 0) < 1:
            add_msg(f"Need {mn} to place."); return
        state["inv"][mn] -= 1
        if state["inv"][mn] <= 0:
            del state["inv"][mn]
        sp_set_tile(tx, ty, bc)
        add_msg(f"Placed {block}.")
        sp_load_view()

    # ── CRAFT ──
    elif cmd == "craft":
        if not args:
            lines = ["=== CRAFTING ==="]
            for item, recipe in CRAFTING.items():
                req = " + ".join(f"{v}x{k}" for k,v in recipe.items())
                lines.append(f"  {item:<15} needs: {req}")
            add_msg("\n".join(lines)); return
        item = "_".join(args).lower()
        if item not in CRAFTING:
            add_msg(f"Unknown recipe. Type 'craft' to list."); return
        inv = state["inv"]
        for mat, qty in CRAFTING[item].items():
            if inv.get(mat, 0) < qty:
                add_msg(f"Need {qty}x {mat}."); return
        for mat, qty in CRAFTING[item].items():
            inv[mat] -= qty
            if inv[mat] <= 0:
                del inv[mat]
        if item in WEAPONS:
            state["weapon"] = item
            add_msg(f"Crafted and equipped {item}!")
        else:
            inv[item] = inv.get(item, 0) + 1
            add_msg(f"Crafted {item}!")
        sp_save_player()

    # ── STATS ──
    elif cmd == "stats":
        lvl = state["lvl"]
        nxt = lvl + 1
        xp_next = LEVELS[nxt]["xp"] if nxt in LEVELS else "MAX"
        inv_str = ", ".join(f"{k}×{v}" for k,v in state["inv"].items()) or "empty"
        add_msg("\n".join([
            "=== STATS ===",
            f"Name  : {state['username']}",
            f"Level : {lvl} ({LEVELS[lvl]['title']})",
            f"HP    : {state['hp']}/{state['mhp']}",
            f"XP    : {state['xp']} / {xp_next}",
            f"Gold  : {state['gold']}",
            f"ATK   : {state['atk']}  DEF: {state['def']}",
            f"Weapon: {state['weapon']}",
            f"Armor : {state['armor']}",
            f"Items : {inv_str}",
            f"Pos   : ({state['x']},{state['y']})",
            f"Kills : {state['kills']}  Deaths: {state['deaths']}",
            "=============",
        ]))

    # ── INVENTORY ──
    elif cmd in ("inv", "inventory"):
        inv = state["inv"]
        if not inv:
            add_msg("Inventory is empty."); return
        lines = ["=== INVENTORY ==="]
        for item, qty in sorted(inv.items()):
            lines.append(f"  {item:<22} x{qty}")
        add_msg("\n".join(lines))

    # ── USE ──
    elif cmd == "use":
        if not args:
            add_msg("Usage: use <item>"); return
        item = "_".join(args).lower()
        if state["inv"].get(item, 0) < 1:
            add_msg(f"You don't have {item}."); return
        if item not in CONSUMABLES:
            add_msg(f"Can't use {item}."); return
        heal   = CONSUMABLES[item]["heal"]
        before = state["hp"]
        state["hp"] = min(state["mhp"], state["hp"] + heal)
        state["inv"][item] -= 1
        if state["inv"][item] <= 0:
            del state["inv"][item]
        add_msg(f"Used {item}. +{state['hp']-before} HP. ({state['hp']}/{state['mhp']})")
        sp_save_player()

    # ── SHOP ──
    elif cmd == "shop":
        lines = ["=== SHOP ===","--- Weapons ---"]
        for n, w in WEAPONS.items():
            if n == "fist": continue
            lines.append(f"  {n:<15} DMG:{w['dmg']:<4} {w['price']}g")
        lines.append("--- Armors ---")
        for n, a in ARMORS.items():
            if n == "none": continue
            lines.append(f"  {n:<15} DEF:{a['def']:<4} {a['price']}g")
        lines.append("--- Items ---")
        for n, cn in CONSUMABLES.items():
            lines.append(f"  {n:<15} {cn['desc']:<22} {cn['price']}g")
        lines.append("  Type: buy <item>")
        add_msg("\n".join(lines))

    # ── BUY ──
    elif cmd == "buy":
        if not args:
            add_msg("Usage: buy <item>"); return
        item = "_".join(args).lower()
        for store, key in [(WEAPONS,"weapon"),(ARMORS,"armor"),(CONSUMABLES,None)]:
            if item in store:
                cost = store[item]["price"]
                if state["gold"] < cost:
                    add_msg(f"Need {cost}g, have {state['gold']}g."); return
                state["gold"] -= cost
                if key:
                    state[key] = item
                    add_msg(f"Bought and equipped {item}!")
                else:
                    inv = state["inv"]
                    inv[item] = inv.get(item, 0) + 1
                    add_msg(f"Bought {item}!")
                sp_save_player(); return
        add_msg(f"Unknown item '{item}'.")

    # ── HELP ──
    elif cmd == "help":
        add_msg("\n".join([
            "=== COMMANDS ===",
            "  w/a/s/d  — move (walk into enemy = attack)",
            "  mine w/a/s/d   — mine block",
            "  place d wood   — place block",
            "  craft [item]   — craft item",
            "  stats          — your stats",
            "  inv            — inventory",
            "  use <item>     — use consumable",
            "  shop / buy     — shop",
            "  help           — this list",
            "  Esc            — pause menu",
            "================",
        ]))

    elif cmd in ("quit","exit"):
        state["mode"] = "pause"

    else:
        add_msg(f"Unknown command '{cmd}'. Type 'help'.")

def _sp_levelup():
    while True:
        nxt = state["lvl"] + 1
        if nxt not in LEVELS or state["xp"] < LEVELS[nxt]["xp"]:
            break
        state["lvl"]  = nxt
        state["mhp"]  = LEVELS[nxt]["hp"]
        state["hp"]   = state["mhp"]
        state["atk"]  = LEVELS[nxt]["atk"]
        state["def"]  = LEVELS[nxt]["def"]
        add_msg(f"LEVEL UP! Now level {nxt} — {LEVELS[nxt]['title']}!")

# ============================================================
#  START SINGLEPLAYER
# ============================================================

def start_sp(world_path: str):
    global _sp_player_file, _sp_world_path, _sp_seed
    global _sp_enemies, _sp_last_spawn

    _sp_world_path  = world_path
    _sp_player_file = os.path.join(world_path, "player.json")
    _sp_enemies     = {}
    _sp_last_spawn  = [0.0]
    _sp_cache.clear()

    # load seed
    sf = os.path.join(world_path, "seed.json")
    if os.path.exists(sf):
        try:
            with open(sf) as f:
                _sp_seed = json.load(f)["seed"]
        except Exception:
            _sp_seed = random.randint(0, 999_999_999)
    else:
        _sp_seed = random.randint(0, 999_999_999)

    # reset player state
    state.update({
        "sp": True, "op": True, "connected": False,
        "x": SPAWN_X, "y": SPAWN_Y,
        "hp":100,"mhp":100,"lvl":1,"xp":0,"gold":50,
        "atk":5,"def":0,"weapon":"fist","armor":"none",
        "inv":{},"kills":0,"deaths":0,
        "char":"@","col":"white","water_time":0.0,
        "players":{},"enemies":{},"messages":[],
        "input":"","input_mode":"cmd",
    })

    sp_load_player()

    sx, sy = sp_find_safe(SPAWN_X, SPAWN_Y)
    if not os.path.exists(_sp_player_file):
        state["x"], state["y"] = sx, sy

    state["players"][state["username"]] = {
        "x":state["x"],"y":state["y"],
        "hp":state["hp"],"mhp":state["mhp"],
        "lvl":state["lvl"],"char":"@","col":"white",
    }

    sp_load_view()
    save_world_meta(world_path)

    # seed starting enemies
    for _ in range(3):
        sp_spawn_enemy()

    state["mode"] = "game"
    name = os.path.basename(world_path)
    add_msg(f"Welcome to {name}, {state['username']}!")
    add_msg("wasd/arrows=move  mine <dir>=mine  craft=craft  help=commands  Esc=menu")

# ============================================================
#  MULTIPLAYER NETWORKING
# ============================================================

_conn     = None
_net_buf  = ""
_net_lock = threading.Lock()
_running  = True

def net_send(msg: dict):
    global _conn
    if _conn:
        try:
            _conn.sendall(net_encode(msg))
        except Exception:
            pass

def _net_recv_thread():
    global _net_buf, _conn
    while _running and _conn:
        try:
            chunk = _conn.recv(4096).decode("utf-8","replace")
            if not chunk:
                add_msg("*** Disconnected from server ***")
                state["connected"] = False
                break
            with _net_lock:
                _net_buf += chunk
            while True:
                with _net_lock:
                    if "\n" not in _net_buf:
                        break
                    line, _net_buf = _net_buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    _handle_server_msg(net_decode(line))
                except Exception:
                    pass
        except Exception as e:
            if _running:
                add_msg(f"Network error: {e}")
            break

def _handle_server_msg(msg: dict):
    t = msg.get("t")

    if t == "auth_req":
        state["server_req_pw"] = msg.get("require_password", False)

    elif t == "auth_ok":
        state["username"]  = msg["username"]
        state["op"]        = msg.get("op", False)
        state["connected"] = True
        state["mode"]      = "game"
        add_msg(f"Welcome, {msg['username']}!")
        if msg.get("op"):
            add_msg("You are OP on this server.")

    elif t == "auth_fail":
        state["auth_error"] = msg.get("reason","Auth failed")

    elif t == "player":
        d = msg["data"]
        state.update({
            "x":d["x"],"y":d["y"],
            "hp":d["hp"],"mhp":d["mhp"],
            "lvl":d["lvl"],"xp":d["xp"],
            "gold":d["gold"],"atk":d["atk"],"def":d["def"],
            "weapon":d["weapon"],"armor":d["armor"],
            "inv":d.get("inv",{}),
            "kills":d.get("kills",0),"deaths":d.get("deaths",0),
            "char":d.get("char","@"),"col":d.get("col","white"),
        })

    elif t == "state":
        state["players"] = msg.get("players",{})
        me = state["players"].get(state["username"])
        if me:
            state["x"]   = me["x"]
            state["y"]   = me["y"]
            state["hp"]  = me["hp"]
            state["mhp"] = me["mhp"]
            state["lvl"] = me["lvl"]
            if state["hp"] <= 0:
                state["mode"]       = "dead"
                state["death_cause"] = "combat"

    elif t == "world":
        state["world"]   = msg.get("tiles",{})
        state["world_w"] = msg.get("w", WORLD_W)
        state["world_h"] = msg.get("h", WORLD_H)

    elif t == "tile":
        key = f"{msg['x']},{msg['y']}"
        if msg["tile"] == ".":
            state["world"].pop(key, None)
        else:
            state["world"][key] = msg["tile"]

    elif t == "enemies":
        state["enemies"] = msg.get("data",{})

    elif t == "msg":
        add_msg(msg.get("m",""))

    elif t == "chat":
        add_msg(f"[{msg.get('from','?')}] {msg.get('m','')}")

    elif t in ("teleport","pos"):
        state["x"] = msg["x"]
        state["y"] = msg["y"]

def mp_connect(ip: str, port: int):
    global _conn, _net_buf
    _net_buf = ""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        sock.settimeout(None)
        _conn = sock
    except Exception as e:
        return str(e)

    state.update({
        "sp":False,"connected":False,
        "players":{},"enemies":{},"world":{},
        "messages":[],"input":"","input_mode":"cmd","water_time":0.0,
    })

    threading.Thread(target=_net_recv_thread, daemon=True).start()

    # wait for auth_req (up to 5s)
    for _ in range(100):
        if "server_req_pw" in state:
            break
        time.sleep(0.05)

    return None  # success

# ============================================================
#  RENDERING
# ============================================================

def render():
    tw, th = term_size()
    out = ["\033[H"]   # move cursor home — no full clear = no flicker
    mode = state["mode"]
    if   mode == "menu":      _r_menu(out, tw, th)
    elif mode == "sp_worlds": _r_worlds(out, tw, th)
    elif mode == "mp_list":   _r_mp_list(out, tw, th)
    elif mode == "mp_auth":   _r_mp_auth(out, tw, th)
    elif mode == "game":      _r_game(out, tw, th)
    elif mode == "dead":      _r_dead(out, tw, th)
    elif mode == "pause":     _r_pause(out, tw, th)
    print("".join(out), end="", flush=True)

def _fill(out, tw, th, bg="\033[44m"):
    for r in range(1, th+1):
        out.append(f"\033[{r};1H{bg}{' '*tw}\033[0m")

def _r_menu(out, tw, th):
    _fill(out, tw, th)
    cy = th//2 - 6
    cx = tw//2
    title = "T E R M Q U E S T   R P G"
    put(out, cy,   cx-len(title)//2, title, "yellow","bold")
    put(out, cy+1, cx-len(title)//2, "─"*len(title), "yellow")
    put(out, cy+2, cx-12, f"v{VERSION}  | make by mengei", "dim")

    bw, bh = 38, 11
    bx = cx-bw//2
    by = cy+4
    box(out, by, bx, bh, bw, "Select Mode")
    sel  = state["menu_sel"]
    opts = [
        ("Singleplayer", "Play alone — your world, your rules"),
        ("Multiplayer",  "Join a server (run server.py to host)"),
        ("Quit",         ""),
    ]
    for i, (label, desc) in enumerate(opts):
        r      = by+2+i*2
        marker = "(*)" if i==sel else "( )"
        col    = "\033[32m" if i==0 else ("\033[36m" if i==1 else "\033[31m")
        inv    = "\033[7m" if i==sel else ""
        out.append(f"\033[{r};{bx+2}H{inv}{col}{marker} {label}\033[0m")
        if desc:
            put(out, r+1, bx+6, desc, "dim")
    put(out, by+bh-2, bx+2, "up=W/down=S=>select  Enter=confirm  q=quit", "dim")

def _r_worlds(out, tw, th):
    _fill(out, tw, th)
    worlds = state["worlds"]
    sel    = state["world_sel"]
    bw = min(tw-4, 56)
    bh = min(th-4, 22)
    bx = tw//2-bw//2
    by = th//2-bh//2
    box(out, by, bx, bh, bw, "Singleplayer Worlds")
    if not worlds:
        put(out, by+2, bx+2, "No worlds found.  Press N to create one.", "yellow")
    else:
        put(out, by+1, bx+2, "World Name             Last Played", "dim")
        vis   = bh-6
        start = max(0, sel-vis//2)
        for i, w in enumerate(worlds[start:start+vis]):
            idx = start+i
            nm  = w["name"][:22]
            lp  = w.get("last_played","never")[:16]
            r   = by+2+i
            if idx == sel:
                out.append(f"\033[{r};{bx+2}H\033[7m\033[32m  {nm:<22} {lp}\033[0m")
            else:
                put(out, r, bx+2, f"  {nm:<22} {lp}")
    put(out, by+bh-3, bx+2, "up/down=select", "dim")
    put(out, by+bh-2, bx+2,  "Enter=Play", "green","bold")
    put(out, by+bh-2, bx+14, "  N=New", "cyan")
    put(out, by+bh-2, bx+22, "  X=Delete", "red")
    put(out, by+bh-2, bx+33, "  Esc=Back", "yellow")

def _r_mp_list(out, tw, th):
    _fill(out, tw, th)
    servers = state["servers"]
    sel     = state["srv_sel"]
    bw = min(tw-4, 58)
    bh = min(th-4, 22)
    bx = tw//2-bw//2
    by = th//2-bh//2
    box(out, by, bx, bh, bw, "Multiplayer Servers")
    if not servers:
        put(out, by+2, bx+2, "No servers saved.  Press A to add one.", "yellow")
        put(out, by+3, bx+2, "Host your own: python server.py", "dim")
    else:
        put(out, by+1, bx+2, "Name               Address", "dim")
        vis   = bh-7
        start = max(0, sel-vis//2)
        for i, srv in enumerate(servers[start:start+vis]):
            idx  = start+i
            nm   = srv.get("name","Server")[:18]
            addr = f"{srv.get('ip','')}:{srv.get('port', DEFAULT_PORT)}"
            r    = by+2+i
            if idx == sel:
                out.append(f"\033[{r};{bx+2}H\033[7m\033[36m  {nm:<18} {addr}\033[0m")
            else:
                put(out, r, bx+2, f"  {nm:<18} {addr}")
    put(out, by+bh-4, bx+2, "up=W/down=S=>select", "dim")
    put(out, by+bh-3, bx+2,  "Enter=Join", "green","bold")
    put(out, by+bh-3, bx+14, "  A=Add", "cyan")
    put(out, by+bh-3, bx+22, "  E=Edit", "yellow")
    put(out, by+bh-3, bx+31, "  D=Del", "red")
    put(out, by+bh-2, bx+2,  "I=Direct IP", "cyan")
    put(out, by+bh-2, bx+15, "  Esc=Back", "yellow")

def _r_mp_auth(out, tw, th):
    _fill(out, tw, th)
    step = state["auth_step"]
    bw   = min(tw-4, 48)
    bh   = 14
    bx   = tw//2-bw//2
    by   = th//2-bh//2

    if step == "username":
        box(out, by, bx, bh, bw, "Join Server")
        put(out, by+1, bx+2, "Enter your username:", "white")
        val = state["auth_fields"][0]
        out.append(f"\033[{by+3};{bx+4}H\033[7m{(val+'_').ljust(32)}\033[0m")
        if state.get("server_req_pw"):
            put(out, by+5, bx+2, "Password required on this server.", "yellow")
        else:
            put(out, by+5, bx+2, "Open server — no password needed!", "green")
        if state["auth_error"]:
            put(out, by+7, bx+2, state["auth_error"][:bw-4], "red","bold")
        saved = load_settings().get("username","")
        if saved:
            put(out, by+9, bx+2, f"Saved name: {saved}  (Enter to use)", "dim")
        put(out, by+bh-2, bx+2, "Enter=join  Esc=back  Backspace=clear", "dim")

    elif step == "password":
        box(out, by, bx, bh, bw, "Password")
        put(out, by+1, bx+2, f"Username: {state['auth_fields'][0]}", "yellow","bold")
        put(out, by+3, bx+2, "Password:", "white")
        pw_disp = "*" * len(state["auth_fields"][1])
        out.append(f"\033[{by+4};{bx+4}H\033[7m{(pw_disp+'_').ljust(32)}\033[0m")
        put(out, by+6, bx+2, "First join = sets your password", "dim")
        if state["auth_error"]:
            put(out, by+8, bx+2, state["auth_error"][:bw-4], "red","bold")
        put(out, by+bh-2, bx+2, "Enter=confirm  Esc=change name", "dim")

    elif step == "waiting":
        box(out, by, bx, bh, bw, "Connecting…")
        put(out, by+2, bx+2, "Joining server…", "cyan","bold")
        put(out, by+4, bx+2, f"Username: {state['auth_fields'][0]}", "yellow")
        if state["auth_error"]:
            is_err = any(w in state["auth_error"].lower()
                        for w in ("fail","wrong","ban","not","taken","error","timeout"))
            put(out, by+6, bx+2, state["auth_error"][:bw-4],
                "red" if is_err else "cyan", "bold")
        put(out, by+bh-2, bx+2, "Esc=cancel", "dim")

def _r_game(out, tw, th):
    sb_w   = min(28, tw//4)
    map_w  = tw - sb_w - 1
    chat_h = max(4, th//5)
    map_h  = th - chat_h - 2

    cx, cy = state["x"], state["y"]
    hw, hh = map_w//2, map_h//2

    # ── map tiles ──
    for sy in range(map_h):
        wy = cy - hh + sy
        out.append(f"\033[{sy+1};1H")
        row = []
        for sx in range(map_w):
            wx = cx - hw + sx
            if wx<0 or wy<0 or wx>=state["world_w"] or wy>=state["world_h"]:
                row.append(A["dim"]+"░"+A["reset"])
            else:
                row.append(render_tile(get_tile(wx, wy)))
        out.append("".join(row))

    # ── enemies ──
    for eid, e in state["enemies"].items():
        sx2 = e["x"] - cx + hw
        sy2 = e["y"] - cy + hh
        if 0<=sx2<map_w and 0<=sy2<map_h:
            out.append(f"\033[{sy2+1};{sx2+1}H\033[31m\033[1m{e['char']}\033[0m")

    # ── other players ──
    for pname, pd in state["players"].items():
        if pname == state["username"]:
            continue
        sx2 = pd["x"] - cx + hw
        sy2 = pd["y"] - cy + hh
        if 0<=sx2<map_w and 0<=sy2<map_h:
            pc = PLAYER_COL.get(pd.get("col","white"), "\033[37m")
            out.append(f"\033[{sy2+1};{sx2+1}H{pc}\033[1m{pd.get('char','@')}\033[0m")

    # ── self (blinking @ in centre) ──
    out.append(f"\033[{hh+1};{hw+1}H\033[32m\033[1m\033[5m{state['char']}\033[0m")

    # ── divider ──
    for r in range(1, th):
        out.append(f"\033[{r};{map_w+1}H\033[33m│\033[0m")

    # ── sidebar ──
    sx0 = map_w + 2

    def sl(row, text, *cols):
        cc = "".join(A.get(x,"") for x in cols)
        out.append(f"\033[{row};{sx0}H{cc}{text[:sb_w-1]}\033[0m")

    hp   = state["hp"]
    mhp  = state["mhp"]
    pct  = hp/mhp if mhp > 0 else 0
    hc   = "green" if pct>0.5 else ("yellow" if pct>0.25 else "red")
    bw2  = max(2, sb_w-4)
    fill = int(pct*bw2)
    bar  = "[" + "█"*fill + "░"*(bw2-fill) + "]"
    lvl  = state["lvl"]
    nxt  = lvl+1
    xp_n = LEVELS[nxt]["xp"] if nxt in LEVELS else None
    xp_pct = ((state["xp"] - LEVELS[lvl]["xp"]) /
               (LEVELS[nxt]["xp"] - LEVELS[lvl]["xp"])
               if xp_n else 1.0)
    xfill  = int(xp_pct * bw2)
    xbar   = "[" + "▓"*xfill + "░"*(bw2-xfill) + "]"

    r = 1
    sl(r, "┌─ STATS ──────────┐","yellow","bold"); r+=1
    sl(r, f" {state['username'][:sb_w-3]}","yellow","bold"); r+=1
    sl(r, f" HP:{hp}/{mhp}", hc,"bold"); r+=1
    sl(r, " "+bar, hc); r+=1
    sl(r, f" Lv:{lvl} XP:{state['xp']}", "white"); r+=1
    sl(r, " "+xbar, "magenta"); r+=1
    sl(r, f" Gold: {state['gold']}g","yellow"); r+=1
    sl(r, f" ATK:{state['atk']} DEF:{state['def']}","cyan"); r+=1
    sl(r, f" WP: {state['weapon'][:sb_w-6]}","white"); r+=1
    sl(r, f" AR: {state['armor'][:sb_w-6]}","white"); r+=1
    sl(r, f" Pos:({state['x']},{state['y']})","dim"); r+=1
    sl(r, f" K:{state['kills']} D:{state['deaths']}","dim"); r+=1
    if state.get("op"):
        sl(r,"[OP]","red","bold"); r+=1

    # nearby enemies in sidebar
    near = [(eid,e) for eid,e in state["enemies"].items()
            if abs(e["x"]-cx)+abs(e["y"]-cy) <= 8]
    if near:
        sl(r,"├─ NEARBY ─────────┤","yellow","bold"); r+=1
        for eid, e in near[:4]:
            ep = max(0, e["hp"]) / max(1, e["mhp"])
            ec = "red" if ep<0.4 else ("yellow" if ep<0.7 else "green")
            sl(r, f" {e['char']} {e['type']:<8} {e['hp']}/{e['mhp']}", ec); r+=1
            if r >= map_h:
                break

    # online players
    if not state["sp"] and state["players"]:
        sl(r,"├─ ONLINE ─────────┤","yellow","bold"); r+=1
        for pname, pd in list(state["players"].items())[:4]:
            marker = ">" if pname==state["username"] else " "
            pc     = PLAYER_COL.get(pd.get("col","white"),"\033[37m")
            out.append(f"\033[{r};{sx0}H{pc}\033[1m {marker}{pname[:10]} L{pd.get('lvl',1)}\033[0m")
            r += 1
            if r >= map_h: break

    sl(r,"├─ KEYS ───────────┤","yellow","bold"); r+=1
    sl(r," wasd/arrows=move","dim"); r+=1
    sl(r," mine <dir>=mine","dim"); r+=1
    sl(r," Enter=cmd  Esc=menu","dim"); r+=1

    # ── chat/message area ──
    out.append(f"\033[{map_h+1};1H\033[33m{'─'*map_w}\033[0m")
    msgs = state["messages"][-(chat_h):]
    for i, msg in enumerate(msgs):
        rr = map_h+2+i
        if rr >= th:
            break
        col = "\033[36m"
        if msg.startswith("***"):       col = "\033[33m\033[1m"
        elif msg.startswith("["):        col = "\033[32m"
        elif "error" in msg.lower() or "drown" in msg.lower(): col = "\033[31m"
        elif "level" in msg.lower():     col = "\033[35m\033[1m"
        elif "killed" in msg.lower() or "+xp" in msg.lower(): col = "\033[33m"
        out.append(f"\033[{rr};1H\033[K{col}{msg[:map_w-1]}\033[0m")

    # ── input line ──
    prefix = "[chat] " if state["input_mode"]=="chat" else "> "
    inp    = prefix + state["input"] + "_"
    out.append(f"\033[{th};1H\033[K\033[7m{inp[:tw-1]}\033[0m")

def _r_dead(out, tw, th):
    _fill(out, tw, th, "\033[41m")
    bw, bh = 38, 12
    bx = tw//2-bw//2
    by = th//2-bh//2
    box(out, by, bx, bh, bw)
    put(out, by+2, tw//2-5, "YOU DIED", "red","bold","blink")
    cause = state.get("death_cause","")
    if cause:
        put(out, by+3, bx+2, f"Cause: {cause}", "white")
    sel  = state["dead_sel"]
    opts = ["Respawn at spawn","Quit to menu"]
    for i, label in enumerate(opts):
        r = by+5+i*2
        if i == sel:
            out.append(f"\033[{r};{bx+2}H\033[7m(*) {label}\033[0m")
        else:
            put(out, r, bx+2, f"( ) {label}", "white")
    put(out, by+bh-2, bx+2, "up=W/down=S=>select  Enter=confirm", "dim")

def _r_pause(out, tw, th):
    _fill(out, tw, th, "\033[40m")
    opts = ["Resume","Stats","Inventory","Shop","Craft","Logout","Quit to Menu","Quit Game"]
    bw   = 36
    bh   = len(opts)+5
    bx   = tw//2-bw//2
    by   = th//2-bh//2
    box(out, by, bx, bh, bw, "Game Menu")
    sel = state["pause_sel"]
    for i, label in enumerate(opts):
        r   = by+2+i
        col = ("\033[31m" if "Quit" in label
               else "\033[32m" if label=="Resume"
               else "\033[37m")
        if i == sel:
            out.append(f"\033[{r};{bx+2}H\033[7m{col}> {label}\033[0m")
        else:
            out.append(f"\033[{r};{bx+2}H{col}  {label}\033[0m")
    put(out, by+bh-2, bx+2, "up=W/down=S=>select  Enter=confirm  Esc=resume","dim")

# ============================================================
#  INPUT READING
# ============================================================

def read_key():
    """Returns (key, is_esc, is_enter, is_backspace) or (None,…) if no key."""
    if not _kbhit():
        return None, False, False, False
    ch = _getch()
    if not ch:
        return None, False, False, False
    code = ord(ch) if len(ch)==1 else 0

    if ch == "\x1b":
        if _kbhit():
            ch2 = _getch()
            if ch2 == "[" and _kbhit():
                ch3 = _getch()
                if ch3 == "A": return "UP",    False,False,False
                if ch3 == "B": return "DOWN",  False,False,False
                if ch3 == "C": return "RIGHT", False,False,False
                if ch3 == "D": return "LEFT",  False,False,False
            return ch2, False,False,False
        return None, True,False,False   # bare ESC

    if ch in ("\r","\n"):  return ch,    False,True, False
    if ch in ("\x7f","\x08"): return ch, False,False,True
    return ch, False,False,False

# ============================================================
#  INPUT HANDLERS
# ============================================================

def _inp_menu(ch, esc, enter, bs):
    global _running
    sel = state["menu_sel"]
    if ch in ("UP","w"):   state["menu_sel"] = (sel-1)%3
    elif ch in ("DOWN","s"): state["menu_sel"] = (sel+1)%3
    elif enter:
        s = state["menu_sel"]
        if s == 0:
            state["worlds"]    = get_worlds()
            state["world_sel"] = 0
            state["mode"]      = "sp_worlds"
        elif s == 1:
            state["servers"]  = load_servers()
            state["srv_sel"]  = 0
            state["mode"]     = "mp_list"
        elif s == 2:
            _running = False
    elif ch in ("q","Q"):
        _running = False

def _inp_worlds(ch, esc, enter, bs):
    worlds = state["worlds"]
    sel    = state["world_sel"]
    if esc:
        state["mode"] = "menu"; return
    if ch == "UP":    state["world_sel"] = max(0, sel-1)
    elif ch == "DOWN":state["world_sel"] = min(max(0,len(worlds)-1), sel+1)
    elif enter and worlds:
        w = worlds[sel]
        _pick_username()
        start_sp(w["path"])
    elif ch in ("n","N"):
        _create_world()
        state["worlds"] = get_worlds()
    elif ch in ("x","X") and worlds:
        _delete_world(worlds[sel])
        state["worlds"]    = get_worlds()
        state["world_sel"] = max(0, sel-1)

def _pick_username():
    settings   = load_settings()
    saved_name = settings.get("username","")
    if saved_name:
        state["username"] = saved_name
        return
    _term_cooked(); clear(); show_cur()
    try:
        name = input("Enter your name: ").strip() or "Hero"
    except (KeyboardInterrupt, EOFError):
        name = "Hero"
    finally:
        hide_cur(); _term_raw()
    settings["username"] = name
    save_settings(settings)
    state["username"] = name

def _create_world():
    _term_cooked(); clear(); show_cur()
    try:
        name = input("World name (letters/numbers/underscore): ").strip()
        name = "".join(c for c in name if c.isalnum() or c=="_") or "NewWorld"
        s    = input("Seed (blank=random): ").strip()
        seed = (int(s) if s.isdigit()
                else abs(hash(s))%999_999_999 if s
                else None)
    except (KeyboardInterrupt, EOFError):
        name = None
    finally:
        hide_cur(); _term_raw()
    if name:
        create_world_dir(name, seed)

def _delete_world(w):
    _term_cooked(); clear(); show_cur()
    try:
        confirm = input(f"Delete '{w['name']}'? (y/N): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        confirm = ""
    finally:
        hide_cur(); _term_raw()
    if confirm == "y":
        import shutil
        shutil.rmtree(w["path"], ignore_errors=True)

def _inp_mp_list(ch, esc, enter, bs):
    servers = state["servers"]
    sel     = state["srv_sel"]
    if esc:
        state["mode"] = "menu"; return
    if ch == "UP":    state["srv_sel"] = max(0, sel-1)
    elif ch == "DOWN":state["srv_sel"] = min(max(0,len(servers)-1), sel+1)
    elif enter and servers:
        srv = servers[sel]
        _do_connect(srv["ip"], srv.get("port", DEFAULT_PORT))
    elif ch in ("a","A"): _add_server();  state["servers"] = load_servers()
    elif ch in ("e","E") and servers: _edit_server(sel); state["servers"] = load_servers()
    elif ch in ("d","D") and servers: _del_server(sel);  state["servers"] = load_servers(); state["srv_sel"]=max(0,sel-1)
    elif ch in ("i","I"): _direct_ip()

def _add_server():
    _term_cooked(); clear(); show_cur()
    ip = None
    try:
        name = input("Server name: ").strip() or "My Server"
        ip   = input("IP address: ").strip()
        ps   = input("Port (blank=8080): ").strip()
        port = int(ps) if ps.isdigit() else DEFAULT_PORT
    except (KeyboardInterrupt, EOFError):
        ip = None
    finally:
        hide_cur(); _term_raw()
    if ip:
        lst = load_servers()
        lst.append({"name":name,"ip":ip,"port":port})
        save_servers(lst)

def _edit_server(idx):
    lst = load_servers()
    if idx >= len(lst): return
    srv = lst[idx]
    _term_cooked(); clear(); show_cur()
    ok = True
    try:
        name = input(f"Name [{srv['name']}]: ").strip() or srv["name"]
        ip   = input(f"IP   [{srv['ip']}]: ").strip()   or srv["ip"]
        ps   = input(f"Port [{srv.get('port',DEFAULT_PORT)}]: ").strip()
        port = int(ps) if ps.isdigit() else srv.get("port", DEFAULT_PORT)
    except (KeyboardInterrupt, EOFError):
        ok = False
    finally:
        hide_cur(); _term_raw()
    if ok:
        lst[idx] = {"name":name,"ip":ip,"port":port}
        save_servers(lst)

def _del_server(idx):
    lst = load_servers()
    if idx < len(lst):
        lst.pop(idx)
        save_servers(lst)

def _direct_ip():
    _term_cooked(); clear(); show_cur()
    ip = None
    try:
        ip   = input("Server IP (blank=localhost): ").strip() or "127.0.0.1"
        ps   = input("Port (blank=8080): ").strip()
        port = int(ps) if ps.isdigit() else DEFAULT_PORT
    except (KeyboardInterrupt, EOFError):
        ip = None
    finally:
        hide_cur(); _term_raw()
    if ip:
        _do_connect(ip, port)

def _do_connect(ip: str, port: int):
    global _conn
    clear()
    print(f"\033[33mConnecting to {ip}:{port}…\033[0m", flush=True)
    err = mp_connect(ip, port)
    if err:
        _term_cooked(); show_cur()
        print(f"\033[31mConnection failed: {err}\033[0m")
        input("Press Enter to go back…")
        hide_cur(); _term_raw()
        return

    # wait for auth_req (auth_step already set)
    settings   = load_settings()
    saved_user = settings.get("username","")

    state.update({
        "mode":       "mp_auth",
        "auth_step":  "username",
        "auth_fields":[saved_user, ""],
        "auth_error": "",
    })
    hide_cur()

def _inp_mp_auth(ch, esc, enter, bs):
    global _conn
    step   = state["auth_step"]
    req_pw = state.get("server_req_pw", False)

    if step == "username":
        if esc:
            state["mode"] = "mp_list"
            if _conn:
                try: _conn.close()
                except: pass
                _conn = None
            return
        if bs:
            state["auth_fields"][0] = state["auth_fields"][0][:-1]
        elif enter:
            uname = state["auth_fields"][0].strip()
            if not uname:
                uname = load_settings().get("username","")
            if not uname:
                state["auth_error"] = "Enter a username."; return
            if len(uname) < 2 or len(uname) > 16:
                state["auth_error"] = "Username must be 2-16 characters."; return
            if not uname.replace("_","").isalnum():
                state["auth_error"] = "Letters, numbers, underscore only."; return
            state["auth_fields"][0] = uname
            s = load_settings(); s["username"] = uname; save_settings(s)
            if req_pw:
                state["auth_step"] = "password"
                state["auth_fields"][1] = ""
                state["auth_error"] = ""
            else:
                state["auth_step"]  = "waiting"
                state["auth_error"] = "Joining…"
                net_send({"t":"auth","username":uname,"password":""})
                _wait_auth()
        elif ch and ch not in ("UP","DOWN","LEFT","RIGHT","TAB"):
            if len(state["auth_fields"][0]) < 16:
                state["auth_fields"][0] += ch
                state["auth_error"] = ""

    elif step == "password":
        if esc:
            state["auth_step"] = "username"; state["auth_error"] = ""; return
        if bs:
            state["auth_fields"][1] = state["auth_fields"][1][:-1]
        elif enter:
            pw = state["auth_fields"][1]
            if not pw:
                state["auth_error"] = "Enter a password."; return
            uname = state["auth_fields"][0]
            state["auth_step"]  = "waiting"
            state["auth_error"] = "Joining…"
            net_send({"t":"auth","username":uname,"password":pw})
            _wait_auth()
        elif ch and ch not in ("UP","DOWN","LEFT","RIGHT","TAB"):
            if len(state["auth_fields"][1]) < 64:
                state["auth_fields"][1] += ch
                state["auth_error"] = ""

    elif step == "waiting":
        if esc:
            state["mode"] = "mp_list"
            if _conn:
                try: _conn.close()
                except: pass
                _conn = None

def _wait_auth():
    deadline = time.time() + 10
    while time.time() < deadline:
        if state.get("connected"):
            return
        err = state.get("auth_error","")
        if err and err not in ("Joining…","Connecting…"):
            req_pw = state.get("server_req_pw", False)
            state["auth_step"] = "password" if req_pw else "username"
            return
        time.sleep(0.05)
    state["auth_error"] = "Timeout — server not responding."
    state["auth_step"]  = "username"

def _inp_game(ch, esc, enter, bs):
    now = time.time()

    if esc and not state["input"]:
        state["pause_sel"] = 0
        state["mode"]      = "pause"
        return

    imode = state["input_mode"]

    # movement / hotkeys when input line empty
    if not state["input"] and imode == "cmd":
        move_map = {"w":"w","a":"a","s":"s","d":"d",
                    "W":"w","A":"a","S":"s","D":"d",
                    "UP":"w","DOWN":"s","LEFT":"a","RIGHT":"d"}
        if ch in move_map:
            if state["sp"]:
                sp_handle(move_map[ch])
            else:
                net_send({"t":"cmd","c":move_map[ch]})
            return
        if ch == "e":   state["input"] = "mine "; return
        if ch == "E":   state["input"] = "mine "; return
        if ch == "f":   state["input"] = "place "; return
        if ch == "i":   # quick inventory
            if state["sp"]: sp_handle("inv")
            else:           net_send({"t":"cmd","c":"inv"})
            return
        if ch == "t":   state["input_mode"] = "chat"; return

    # backspace
    if bs:
        state["input"] = state["input"][:-1]
        return

    # enter = submit
    if enter:
        text = state["input"].strip()
        state["input"]     = ""
        state["input_mode"]= "cmd"
        if text:
            if state["input_mode"] == "chat" or (
                    state["sp"] and imode == "chat"):
                if state["sp"]:
                    add_msg(f"[{state['username']}] {text}")
                else:
                    net_send({"t":"cmd","c":f"chat {text}"})
            else:
                if state["sp"]:
                    sp_handle(text)
                else:
                    net_send({"t":"cmd","c":text})
        return

    # typing
    if ch and ch not in ("UP","DOWN","LEFT","RIGHT","TAB") and not esc:
        if len(state["input"]) < 120:
            state["input"] += ch

def _inp_dead(ch, esc, enter, bs):
    sel = state["dead_sel"]
    if ch in ("UP","w"):    state["dead_sel"] = (sel-1)%2
    elif ch in ("DOWN","s"):state["dead_sel"] = (sel+1)%2
    elif enter:
        if sel == 0:
            if state["sp"]:
                sx, sy = sp_find_safe(SPAWN_X, SPAWN_Y)
                state["x"], state["y"] = sx, sy
                state["hp"] = state["mhp"]
                state["water_time"] = 0
                _sp_enemies.clear()
                sp_load_view()
                sp_save_player()
            else:
                net_send({"t":"cmd","c":"respawn"})
            state["mode"] = "game"
        else:
            if state["sp"]:
                sp_save_player()
            state.update({"mode":"menu","sp":False,"connected":False,
                          "players":{},"enemies":{},"world":{},"messages":[]})

def _inp_pause(ch, esc, enter, bs):
    global _running, _conn
    opts = ["Resume","Stats","Inventory","Shop","Craft","Logout","Quit to Menu","Quit Game"]
    sel  = state["pause_sel"]

    if esc or ch in ("r","R"):
        state["mode"] = "game"; return
    if ch in ("UP","w"):    state["pause_sel"] = (sel-1)%len(opts)
    elif ch in ("DOWN","s"):state["pause_sel"] = (sel+1)%len(opts)
    elif enter:
        choice = opts[sel]
        if choice == "Resume":
            state["mode"] = "game"
        elif choice == "Stats":
            if state["sp"]: sp_handle("stats")
            else:           net_send({"t":"cmd","c":"stats"})
            state["mode"] = "game"
        elif choice == "Inventory":
            if state["sp"]: sp_handle("inv")
            else:           net_send({"t":"cmd","c":"inv"})
            state["mode"] = "game"
        elif choice == "Shop":
            if state["sp"]: sp_handle("shop")
            else:           net_send({"t":"cmd","c":"shop"})
            state["mode"] = "game"
        elif choice == "Craft":
            if state["sp"]: sp_handle("craft")
            else:           net_send({"t":"cmd","c":"craft"})
            state["mode"] = "game"
        elif choice == "Logout":
            if state["sp"]:
                sp_save_player()
            else:
                if _conn:
                    try: _conn.close()
                    except: pass
                    _conn = None
            settings = load_settings()
            settings.pop("username", None)
            save_settings(settings)
            state.update({"mode":"menu","sp":False,"connected":False,
                          "username":"","players":{},"enemies":{},
                          "world":{},"messages":[]})
        elif choice == "Quit to Menu":
            if state["sp"]:
                sp_save_player()
            else:
                if _conn:
                    try: _conn.close()
                    except: pass
                    _conn = None
            state.update({"mode":"menu","sp":False,"connected":False,
                          "players":{},"enemies":{},"world":{},"messages":[]})
        elif choice == "Quit Game":
            if state["sp"]:
                sp_save_player()
            _running = False

# ============================================================
#  MAIN LOOP
# ============================================================

def main():
    global _running, _conn

    # direct connect from command line
    direct_ip   = sys.argv[1] if len(sys.argv) >= 2 else None
    direct_port = int(sys.argv[2]) if len(sys.argv) >= 3 else DEFAULT_PORT

    _term_init()   # ← put terminal in cbreak so every keypress fires immediately
    hide_cur()
    clear()

    if direct_ip:
        _do_connect(direct_ip, direct_port)

    last_render   = 0.0
    last_sp_tick  = 0.0
    last_drown    = 0.0
    last_save     = 0.0

    try:
        while _running:
            now = time.time()

            # render at ~20 fps
            if now - last_render > 0.05:
                render()
                last_render = now

            # singleplayer ticks
            if state["sp"] and state["mode"] == "game":
                if now - last_sp_tick > 0.25:
                    sp_enemy_tick()
                    last_sp_tick = now
                if now - last_drown > 1.0:
                    sp_drown_tick()
                    last_drown = now
                if now - last_save > 30.0:
                    sp_save_player()
                    last_save = now

            # input
            ch, esc, enter, bs = read_key()
            if ch is not None or esc or enter or bs:
                mode = state["mode"]
                if   mode == "menu":      _inp_menu(ch,esc,enter,bs)
                elif mode == "sp_worlds": _inp_worlds(ch,esc,enter,bs)
                elif mode == "mp_list":   _inp_mp_list(ch,esc,enter,bs)
                elif mode == "mp_auth":   _inp_mp_auth(ch,esc,enter,bs)
                elif mode == "game":      _inp_game(ch,esc,enter,bs)
                elif mode == "dead":      _inp_dead(ch,esc,enter,bs)
                elif mode == "pause":     _inp_pause(ch,esc,enter,bs)

            time.sleep(0.008)

    except KeyboardInterrupt:
        pass
    finally:
        _term_restore()   # ← restore cooked mode so the shell works normally
        show_cur()
        clear()
        if state["sp"]:
            sp_save_player()
        if _conn:
            try: _conn.close()
            except: pass
        print("Thanks for playing TermQuest RPG!")
        print(f"Kills: {state['kills']}  Deaths: {state['deaths']}  Level: {state['lvl']}")

if __name__ == "__main__":
    main()
