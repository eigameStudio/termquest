#!/usr/bin/env python3
# Copyright (c) 2026 eigamestudio. All rights reserved.
# File: termquestserver.v1.py (Server)
# Forbidden from being used for sexually explicit or illegal content.
# ============================================================
#  TermQuest RPG — server.py  v1.0
#  Run: python server.py [port]
#  Pure Python stdlib — no pip needed
#  Windows / Linux / Mac / Termux
# ============================================================

import os, sys, json, socket, threading, time, hashlib, random, queue

# ============================================================
#  SHARED CONSTANTS  (must match client.py)
# ============================================================

VERSION       = "1.0"
DEFAULT_HOST  = "0.0.0.0"
DEFAULT_PORT  = 8080
MAX_MSG_LEN   = 65536   # bytes
TICK_RATE     = 0.10    # seconds per game tick (10 Hz)

# Rate limits — seconds between actions (enforced server-side)
MOVE_COOLDOWN   = 0.15
ATTACK_COOLDOWN = 0.50
CHAT_COOLDOWN   = 1.00
ACTION_COOLDOWN = 0.30

# World
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

MATERIALS = {"wood","stone","coal","iron","gold_ore","sand","flower"}

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
#  SERVER SETTINGS
# ============================================================

SAVE_FILE        = "world.json"
PLAYERS_FILE     = "players.json"
WHITELIST_FILE   = "whitelist.json"
SAVE_INTERVAL    = 30       # seconds
MAX_PLAYERS      = 50
ENEMY_TICK_RATE  = 0.5      # seconds per enemy AI tick
MAX_ENEMIES      = 25
SPAWN_ENEMIES    = True
REQUIRE_PASSWORD = True     # False = open server (no password)
USE_WHITELIST    = False

# ============================================================
#  LOGGING
# ============================================================

def log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ============================================================
#  WORLD GENERATION
# ============================================================

def _grad(gx: int, gy: int, seed: int) -> float:
    r = random.Random(seed ^ (gx * 73856093) ^ (gy * 19349663))
    return r.uniform(-1.0, 1.0)

def _noise(wx: float, wy: float, seed: int, scale: float) -> float:
    gx, gy = wx / scale, wy / scale
    x0, y0 = int(gx), int(gy)
    tx, ty = gx - x0, gy - y0
    sx = tx * tx * (3 - 2 * tx)
    sy = ty * ty * (3 - 2 * ty)
    v = (1-sy)*((1-sx)*_grad(x0,y0,seed)   + sx*_grad(x0+1,y0,seed)) + \
           sy *((1-sx)*_grad(x0,y0+1,seed) + sx*_grad(x0+1,y0+1,seed))
    return (v + 1) / 2

def generate_world(seed=None):
    if seed is None:
        seed = random.randint(0, 999_999_999)
    log(f"Generating world (seed={seed}, {WORLD_W}x{WORLD_H})…")
    grid = []
    for wy in range(WORLD_H):
        row = []
        for wx in range(WORLD_W):
            h = _noise(wx, wy, seed,   50)
            m = _noise(wx, wy, seed+1, 25)
            t = _noise(wx, wy, seed+2, 18)
            f = _noise(wx, wy, seed+3, 9)
            o = _noise(wx, wy, seed+4, 12)
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
            row.append(tile)
        grid.append(row)
    # clear spawn area
    for dy in range(-7, 8):
        for dx in range(-7, 8):
            nx, ny = SPAWN_X+dx, SPAWN_Y+dy
            if 0 <= nx < WORLD_W and 0 <= ny < WORLD_H:
                if grid[ny][nx] != "~":
                    grid[ny][nx] = "."
    log("World ready.")
    return {"seed": seed, "grid": grid}

def find_safe_tile(grid, cx, cy, radius=40):
    for r in range(radius):
        for dy in range(-r, r+1):
            for dx in range(-r, r+1):
                if abs(dx) != r and abs(dy) != r:
                    continue
                nx, ny = cx+dx, cy+dy
                if 0 <= nx < WORLD_W and 0 <= ny < WORLD_H:
                    if TILES.get(grid[ny][nx], {}).get("walkable"):
                        return nx, ny
    return cx, cy

# ============================================================
#  SERVER STATE
# ============================================================

world      = None           # {"seed":int,"grid":[[char]]}
world_lock = threading.Lock()
dirty      = False

players_db = {}             # username -> player dict
online     = {}             # username -> Client
db_lock    = threading.Lock()

enemies     = {}            # eid -> enemy dict
enemy_lock  = threading.Lock()
_enemy_id   = [0]

battle_requests = {}        # challenger -> {"target":str,"time":float}
save_queue  = queue.Queue() # async save requests

server_running = True

# ============================================================
#  SAVE / LOAD  (async saves — never block game loop)
# ============================================================

def _save_worker():
    while server_running:
        try:
            task = save_queue.get(timeout=1)
        except queue.Empty:
            continue
        kind = task.get("kind")
        try:
            if kind == "players":
                tmp = PLAYERS_FILE + ".tmp"
                with open(tmp, "w") as f:
                    json.dump(players_db, f, indent=2)
                os.replace(tmp, PLAYERS_FILE)
            elif kind == "world":
                if dirty:
                    tmp = SAVE_FILE + ".tmp"
                    with open(tmp, "w") as f:
                        json.dump({"seed":world["seed"],"grid":world["grid"]},
                                  f, separators=(",",":"))
                    os.replace(tmp, SAVE_FILE)
                    globals()["dirty"] = False
        except Exception as e:
            log(f"Save error ({kind}): {e}")

def save_db():
    save_queue.put({"kind":"players"})

def save_world():
    save_queue.put({"kind":"world"})

def load_db():
    global players_db
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE) as f:
                players_db = json.load(f)
            log(f"Loaded {len(players_db)} player(s).")
        except Exception as e:
            log(f"Load players error: {e}")

def load_world_file():
    global world
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE) as f:
                data = json.load(f)
            world = data
            log(f"Loaded world (seed={world['seed']}).")
            return True
        except Exception as e:
            log(f"Load world error: {e}")
    return False

# ============================================================
#  WORLD HELPERS
# ============================================================

def get_tile(x, y):
    if 0 <= x < WORLD_W and 0 <= y < WORLD_H:
        return world["grid"][y][x]
    return "#"

def set_tile(x, y, tile):
    global dirty
    if 0 <= x < WORLD_W and 0 <= y < WORLD_H:
        with world_lock:
            world["grid"][y][x] = tile
            dirty = True

def is_walkable(x, y):
    return TILES.get(get_tile(x, y), {}).get("walkable", False)

# ============================================================
#  PLAYER HELPERS
# ============================================================

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def new_player(username: str) -> dict:
    sx, sy = find_safe_tile(world["grid"], SPAWN_X, SPAWN_Y)
    return {
        "username": username, "password": "",
        "x": sx, "y": sy,
        "hp": 100, "max_hp": 100,
        "level": 1, "xp": 0, "gold": 50,
        "atk": 5, "def": 0,
        "weapon": "fist", "armor": "none",
        "inventory": {},
        "kills": 0, "deaths": 0,
        "char": "@", "color": "white",
        "op": False, "banned": False,
        "last_move": 0.0, "last_attack": 0.0,
        "last_chat": 0.0, "last_action": 0.0,
        "water_time": 0.0,
    }

def inv_add(p, item, qty=1):
    p.setdefault("inventory", {})[item] = \
        p["inventory"].get(item, 0) + qty

def inv_remove(p, item, qty=1) -> bool:
    inv = p.get("inventory", {})
    if inv.get(item, 0) < qty:
        return False
    inv[item] -= qty
    if inv[item] <= 0:
        del inv[item]
    return True

def inv_has(p, item, qty=1) -> bool:
    return p.get("inventory", {}).get(item, 0) >= qty

def check_levelup(p) -> list:
    msgs = []
    while True:
        nxt = p["level"] + 1
        if nxt not in LEVELS or p["xp"] < LEVELS[nxt]["xp"]:
            break
        p["level"]  = nxt
        p["max_hp"] = LEVELS[nxt]["hp"]
        p["hp"]     = p["max_hp"]
        p["atk"]    = LEVELS[nxt]["atk"]
        p["def"]    = LEVELS[nxt]["def"]
        msgs.append(f"LEVEL UP! Now level {nxt} — {LEVELS[nxt]['title']}!")
    return msgs

# ============================================================
#  COMBAT
# ============================================================

def calc_atk(p) -> int:
    wpn = WEAPONS.get(p.get("weapon","fist"), WEAPONS["fist"])
    return wpn["dmg"] + p.get("atk", 5)

def calc_def(p) -> int:
    arm = ARMORS.get(p.get("armor","none"), ARMORS["none"])
    return arm["def"] + p.get("def", 0)

def do_pvp(atk_name, def_name):
    now = time.time()
    a   = players_db[atk_name]
    d   = players_db[def_name]
    if now - a.get("last_attack", 0) < ATTACK_COOLDOWN:
        return
    a["last_attack"] = now
    dmg = max(1, calc_atk(a) - calc_def(d) + random.randint(-2, 3))
    d["hp"] -= dmg
    send_to(atk_name, {"t":"msg","m":f"You hit {def_name} for {dmg} dmg!"})
    send_to(def_name, {"t":"msg","m":f"{atk_name} hit you for {dmg} dmg! HP:{max(0,d['hp'])}/{d['max_hp']}"})
    broadcast_state()
    if d["hp"] <= 0:
        kill_player(def_name, atk_name)

def kill_player(dead, killer=None):
    d = players_db[dead]
    d["hp"]     = d["max_hp"]
    d["deaths"] += 1
    sx, sy      = find_safe_tile(world["grid"], SPAWN_X, SPAWN_Y)
    d["x"], d["y"] = sx, sy
    d["water_time"] = 0
    send_to(dead, {"t":"msg","m":"You died and respawned at spawn."})
    send_to(dead, {"t":"teleport","x":sx,"y":sy})
    if killer and killer in players_db:
        k = players_db[killer]
        k["kills"] += 1
        k["xp"]    += 50
        k["gold"]  += 30
        for m in check_levelup(k):
            send_to(killer, {"t":"msg","m":m})
        send_to(killer, {"t":"msg","m":f"Defeated {dead}! +50XP +30g"})
    broadcast({"t":"msg","m":f"*** {dead} was defeated! ***"})
    send_world_view(dead)
    broadcast_state()
    save_db()

# ============================================================
#  ENEMIES
# ============================================================

def spawn_enemy(etype=None, x=None, y=None):
    if not online:
        return None
    if etype is None:
        etype = random.choice(list(ENEMIES.keys()))
    if not (etype in ENEMIES):
        return None
    data = ENEMIES[etype]
    if x is None or y is None:
        ref = players_db.get(random.choice(list(online.keys())))
        bx, by = (ref["x"], ref["y"]) if ref else (SPAWN_X, SPAWN_Y)
        for _ in range(50):
            ex = bx + random.randint(-20, 20)
            ey = by + random.randint(-20, 20)
            if is_walkable(ex, ey):
                x, y = ex, ey
                break
        else:
            return None
    with enemy_lock:
        _enemy_id[0] += 1
        eid = _enemy_id[0]
        enemies[eid] = {
            "id": eid, "type": etype,
            "x": x, "y": y,
            "hp": data["hp"], "max_hp": data["hp"],
            "atk": data["atk"], "def": data["def"],
            "xp": data["xp"], "gold": data["gold"],
            "char": data["char"],
            "range": data["range"], "speed": data["speed"],
            "last_move": 0.0, "last_attack": 0.0,
            "wander_t": 0.0, "wander_dx": 0, "wander_dy": 0,
        }
    return eid

def enemy_ai_tick():
    now = time.time()
    with enemy_lock:
        eids = list(enemies.keys())

    for eid in eids:
        with enemy_lock:
            e = enemies.get(eid)
            if not e:
                continue

        # find nearest online player
        nearest, nearest_dist = None, 9999
        for uname in list(online):
            p = players_db.get(uname)
            if not p:
                continue
            d = abs(p["x"]-e["x"]) + abs(p["y"]-e["y"])
            if d < nearest_dist:
                nearest_dist, nearest = d, uname

        # attack
        if nearest and nearest_dist <= e["range"]:
            if now - e["last_attack"] >= ATTACK_COOLDOWN:
                e["last_attack"] = now
                p   = players_db[nearest]
                dmg = max(1, e["atk"] - calc_def(p) + random.randint(-1, 2))
                p["hp"] -= dmg
                send_to(nearest, {"t":"msg","m":
                    f"{e['type'].title()} hits you for {dmg}! HP:{max(0,p['hp'])}/{p['max_hp']}"})
                broadcast_state()
                if p["hp"] <= 0:
                    kill_player(nearest)

        # move
        if now - e["last_move"] < e["speed"]:
            continue
        e["last_move"] = now

        if nearest and nearest_dist <= 10:
            p  = players_db[nearest]
            dx = 0 if e["x"]==p["x"] else (1 if p["x"]>e["x"] else -1)
            dy = 0 if e["y"]==p["y"] else (1 if p["y"]>e["y"] else -1)
            if random.random() < 0.5: dy = 0
            else:                     dx = 0
        else:
            if now - e["wander_t"] > 2.0:
                e["wander_t"]  = now
                e["wander_dx"] = random.choice([-1,0,0,1])
                e["wander_dy"] = random.choice([-1,0,0,1])
            dx, dy = e["wander_dx"], e["wander_dy"]

        nx, ny = e["x"]+dx, e["y"]+dy
        if is_walkable(nx, ny):
            occupied = any(
                players_db.get(u,{}).get("x")==nx and
                players_db.get(u,{}).get("y")==ny
                for u in online
            )
            if not occupied:
                e["x"], e["y"] = nx, ny

    broadcast_enemies()

def _enemy_loop():
    while server_running:
        try:
            if online:
                enemy_ai_tick()
                with enemy_lock:
                    cnt = len(enemies)
                if SPAWN_ENEMIES and cnt < MAX_ENEMIES:
                    if random.random() < 0.12:
                        spawn_enemy()
        except Exception as ex:
            log(f"Enemy loop error: {ex}")
        time.sleep(ENEMY_TICK_RATE)

# ============================================================
#  BROADCAST / SEND
# ============================================================

def send_to(username: str, msg: dict):
    c = online.get(username)
    if c:
        c.send(msg)

def broadcast(msg: dict, exclude=()):
    for name, c in list(online.items()):
        if name not in exclude:
            c.send(msg)

def broadcast_state():
    pdata = {}
    for name in list(online):
        p = players_db.get(name)
        if p:
            pdata[name] = {
                "x":p["x"],"y":p["y"],
                "hp":p["hp"],"mhp":p["max_hp"],
                "lvl":p["level"],
                "char":p.get("char","@"),
                "col":p.get("color","white"),
            }
    broadcast({"t":"state","players":pdata})

def broadcast_enemies():
    with enemy_lock:
        data = {str(eid): {
            "type":e["type"],"x":e["x"],"y":e["y"],
            "hp":e["hp"],"mhp":e["max_hp"],"char":e["char"],
        } for eid,e in enemies.items()}
    broadcast({"t":"enemies","data":data})

def send_world_view(username: str):
    p  = players_db[username]
    cx, cy = p["x"], p["y"]
    r  = 35
    tiles = {}
    for dy in range(-r, r+1):
        for dx in range(-r, r+1):
            wx, wy = cx+dx, cy+dy
            if 0 <= wx < WORLD_W and 0 <= wy < WORLD_H:
                t = world["grid"][wy][wx]
                if t != ".":
                    tiles[f"{wx},{wy}"] = t
    send_to(username, {"t":"world","tiles":tiles,"w":WORLD_W,"h":WORLD_H})

# ============================================================
#  COMMAND HANDLER  (called from client thread)
# ============================================================

DIRS = {"w":(0,-1),"a":(-1,0),"s":(0,1),"d":(1,0)}

def handle_cmd(username: str, raw: str):
    raw = raw.strip()[:256]
    if not raw:
        return
    parts = raw.split()
    cmd   = parts[0].lower()
    args  = parts[1:]
    now   = time.time()

    with db_lock:
        if username not in players_db:
            return
        p = players_db[username]

    # ── MOVE ──
    if cmd in DIRS:
        if now - p.get("last_move",0) < MOVE_COOLDOWN:
            return
        p["last_move"] = now
        dx, dy = DIRS[cmd]
        nx, ny = p["x"]+dx, p["y"]+dy

        # bounds check
        if not (0 <= nx < WORLD_W and 0 <= ny < WORLD_H):
            return

        # enemy collision → attack
        with enemy_lock:
            hit = next((eid for eid,e in enemies.items()
                        if e["x"]==nx and e["y"]==ny), None)
        if hit:
            _attack_enemy(username, hit)
            return

        # pvp collision → attack
        victim = next((u for u in online if u != username and
                       players_db.get(u,{}).get("x")==nx and
                       players_db.get(u,{}).get("y")==ny), None)
        if victim:
            do_pvp(username, victim)
            return

        if is_walkable(nx, ny):
            p["x"], p["y"] = nx, ny
            t = get_tile(nx, ny)
            if TILES.get(t,{}).get("swim"):
                if not p.get("water_time"):
                    p["water_time"] = now
                    send_to(username,{"t":"msg","m":"Swimming! Don't linger or you'll drown."})
            else:
                p["water_time"] = 0
            send_to(username, {"t":"pos","x":nx,"y":ny})
            broadcast_state()
        else:
            send_to(username,{"t":"msg","m":f"Blocked by {TILES.get(get_tile(nx,ny),{}).get('name','?')}."})

    # ── MINE ──
    elif cmd == "mine":
        if not args or args[0] not in DIRS:
            send_to(username,{"t":"msg","m":"Usage: mine w/a/s/d"}); return
        if now - p.get("last_action",0) < ACTION_COOLDOWN:
            return
        p["last_action"] = now
        dx, dy = DIRS[args[0]]
        tx, ty = p["x"]+dx, p["y"]+dy
        if not (0 <= tx < WORLD_W and 0 <= ty < WORLD_H):
            return
        t    = get_tile(tx, ty)
        td   = TILES.get(t,{})
        if not td.get("mineable"):
            send_to(username,{"t":"msg","m":"Nothing to mine there."}); return
        set_tile(tx, ty, ".")
        inv_add(p, td["drop"], td["qty"])
        send_to(username,{"t":"msg","m":f"Mined {td['name']}! Got {td['qty']}x {td['drop']}."})
        broadcast({"t":"tile","x":tx,"y":ty,"tile":"."})
        save_db()

    # ── PLACE ──
    elif cmd == "place":
        if len(args) < 2 or args[0] not in DIRS:
            send_to(username,{"t":"msg","m":"Usage: place w/a/s/d wood|stone"}); return
        if now - p.get("last_action",0) < ACTION_COOLDOWN:
            return
        p["last_action"] = now
        dx, dy   = DIRS[args[0]]
        tx, ty   = p["x"]+dx, p["y"]+dy
        block    = args[1].lower()
        blk_map  = {"wood":"w","stone":"b","wood_block":"w","stone_block":"b"}
        mat_map  = {"wood":"wood","stone":"stone","wood_block":"wood","stone_block":"stone"}
        bc = blk_map.get(block)
        mn = mat_map.get(block)
        if not bc:
            send_to(username,{"t":"msg","m":"Use: wood or stone"}); return
        if not inv_has(p, mn):
            send_to(username,{"t":"msg","m":f"Need {mn} to place."}); return
        cur = get_tile(tx, ty)
        if not (TILES.get(cur,{}).get("walkable") or cur == "."):
            send_to(username,{"t":"msg","m":"Can't place there."}); return
        inv_remove(p, mn)
        set_tile(tx, ty, bc)
        broadcast({"t":"tile","x":tx,"y":ty,"tile":bc})
        save_db()

    # ── CRAFT ──
    elif cmd == "craft":
        if not args:
            lines = ["=== CRAFTING ==="]
            for item, recipe in CRAFTING.items():
                req = " + ".join(f"{v}x{k}" for k,v in recipe.items())
                lines.append(f"  {item:<15} needs: {req}")
            send_to(username,{"t":"msg","m":"\n".join(lines)}); return
        item = "_".join(args).lower()
        if item not in CRAFTING:
            send_to(username,{"t":"msg","m":f"Unknown recipe. Type 'craft' to list."}); return
        for mat, qty in CRAFTING[item].items():
            if not inv_has(p, mat, qty):
                send_to(username,{"t":"msg","m":f"Need {qty}x {mat}."}); return
        for mat, qty in CRAFTING[item].items():
            inv_remove(p, mat, qty)
        if item in WEAPONS:
            p["weapon"] = item
            send_to(username,{"t":"msg","m":f"Crafted and equipped {item}!"})
        else:
            inv_add(p, item)
            send_to(username,{"t":"msg","m":f"Crafted {item}!"})
        save_db()

    # ── STATS ──
    elif cmd == "stats":
        lvl     = p["level"]
        nxt     = lvl + 1
        xp_next = LEVELS[nxt]["xp"] if nxt in LEVELS else "MAX"
        inv_str = ", ".join(f"{k}×{v}" for k,v in p.get("inventory",{}).items()) or "empty"
        send_to(username,{"t":"msg","m":"\n".join([
            "=== YOUR STATS ===",
            f"Name  : {p['username']}",
            f"Level : {lvl} ({LEVELS[lvl]['title']})",
            f"HP    : {p['hp']}/{p['max_hp']}",
            f"XP    : {p['xp']} / {xp_next}",
            f"Gold  : {p['gold']}",
            f"ATK   : {p['atk']}  DEF: {p['def']}",
            f"Weapon: {p['weapon']}",
            f"Armor : {p['armor']}",
            f"Items : {inv_str}",
            f"Pos   : ({p['x']},{p['y']})",
            f"Kills : {p['kills']}  Deaths: {p['deaths']}",
            "==================",
        ])})

    # ── INVENTORY ──
    elif cmd in ("inv","inventory"):
        inv = p.get("inventory", {})
        if not inv:
            send_to(username,{"t":"msg","m":"Inventory is empty."}); return
        lines = ["=== INVENTORY ==="]
        for item, qty in inv.items():
            lines.append(f"  {item:<20} x{qty}")
        send_to(username,{"t":"msg","m":"\n".join(lines)})

    # ── USE ──
    elif cmd == "use":
        if not args:
            send_to(username,{"t":"msg","m":"Usage: use <item>"}); return
        item = "_".join(args).lower()
        if not inv_has(p, item):
            send_to(username,{"t":"msg","m":f"You don't have {item}."}); return
        if item not in CONSUMABLES:
            send_to(username,{"t":"msg","m":f"Can't use {item}."}); return
        heal = CONSUMABLES[item]["heal"]
        before = p["hp"]
        p["hp"] = min(p["max_hp"], p["hp"] + heal)
        inv_remove(p, item)
        healed = p["hp"] - before
        send_to(username,{"t":"msg","m":f"Used {item}. +{healed} HP. ({p['hp']}/{p['max_hp']})"})
        broadcast_state()
        save_db()

    # ── SHOP ──
    elif cmd == "shop":
        lines = ["=== SHOP ===","--- Weapons ---"]
        for n,w in WEAPONS.items():
            if n == "fist": continue
            lines.append(f"  {n:<15} DMG:{w['dmg']:<4} {w['price']}g")
        lines.append("--- Armors ---")
        for n,a in ARMORS.items():
            if n == "none": continue
            lines.append(f"  {n:<15} DEF:{a['def']:<4} {a['price']}g")
        lines.append("--- Items ---")
        for n,c in CONSUMABLES.items():
            lines.append(f"  {n:<15} {c['desc']:<22} {c['price']}g")
        lines.append("  Type: buy <item>")
        send_to(username,{"t":"msg","m":"\n".join(lines)})

    # ── BUY ──
    elif cmd == "buy":
        if not args:
            send_to(username,{"t":"msg","m":"Usage: buy <item>"}); return
        item = "_".join(args).lower()
        for store, key in [(WEAPONS,"weapon"),(ARMORS,"armor"),(CONSUMABLES,None)]:
            if item in store:
                cost = store[item]["price"]
                if p["gold"] < cost:
                    send_to(username,{"t":"msg","m":f"Need {cost}g, have {p['gold']}g."}); return
                p["gold"] -= cost
                if key:
                    p[key] = item
                    send_to(username,{"t":"msg","m":f"Bought and equipped {item}!"})
                else:
                    inv_add(p, item)
                    send_to(username,{"t":"msg","m":f"Bought {item}!"})
                save_db(); return
        send_to(username,{"t":"msg","m":f"Unknown item '{item}'."})

    # ── CHAT ──
    elif cmd in ("chat","say","c"):
        if now - p.get("last_chat",0) < CHAT_COOLDOWN:
            send_to(username,{"t":"msg","m":"Chat cooldown! 1 second."}); return
        p["last_chat"] = now
        text = " ".join(args)[:200].strip()
        if not text:
            send_to(username,{"t":"msg","m":"Usage: chat <message>"}); return
        broadcast({"t":"chat","from":username,"m":text})

    # ── ONLINE ──
    elif cmd == "online":
        lines = ["=== ONLINE ==="]
        for name in list(online):
            pp  = players_db.get(name, {})
            tag = " [OP]" if pp.get("op") else ""
            lines.append(f"  {name:<16} Lv{pp.get('level',1)} ({pp.get('x',0)},{pp.get('y',0)}){tag}")
        lines.append(f"  Total: {len(online)}/{MAX_PLAYERS}")
        send_to(username,{"t":"msg","m":"\n".join(lines)})

    # ── HELP ──
    elif cmd == "help":
        lines = [
            "=== COMMANDS ===",
            "  w/a/s/d         — move (walk into enemy to attack)",
            "  mine w/a/s/d    — mine adjacent block",
            "  place d wood    — place block (wood/stone)",
            "  craft [item]    — craft (no args = list recipes)",
            "  stats           — your stats",
            "  inv             — inventory",
            "  use <item>      — use consumable",
            "  shop            — item shop",
            "  buy <item>      — purchase item",
            "  chat <message>  — send chat",
            "  online          — who is online",
            "  help            — this list",
            "  quit            — disconnect",
            "================",
        ]
        if p.get("op"):
            lines[-1:] = [
                "--- OP COMMANDS ---",
                "  op/deop <player>",
                "  kick/ban <player>",
                "  give <p> <item> [qty]",
                "  tp <p> <x> <y>",
                "  setblock <x> <y> <tile>",
                "  spawn [type]",
                "  say <message>",
                "  save / stop",
                "==================",
            ]
        send_to(username,{"t":"msg","m":"\n".join(lines)})

    # ── RESPAWN ──
    elif cmd == "respawn":
        if p["hp"] > 0:
            return
        sx, sy      = find_safe_tile(world["grid"], SPAWN_X, SPAWN_Y)
        p["hp"]     = p["max_hp"]
        p["x"], p["y"] = sx, sy
        p["water_time"] = 0
        send_to(username,{"t":"teleport","x":sx,"y":sy})
        send_to(username,{"t":"msg","m":"Respawned!"})
        send_world_view(username)
        broadcast_state()

    # ── QUIT ──
    elif cmd in ("quit","exit","disconnect"):
        c = online.get(username)
        if c:
            try: c.conn.close()
            except: pass

    # ── OP COMMANDS ──
    elif cmd == "op":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        t2 = args[0] if args else ""
        if t2 in players_db:
            players_db[t2]["op"] = True
            save_db()
            send_to(username,{"t":"msg","m":f"{t2} is now OP."})
            send_to(t2,{"t":"msg","m":"You are now OP!"})

    elif cmd == "deop":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        t2 = args[0] if args else ""
        if t2 in players_db:
            players_db[t2]["op"] = False
            save_db()
            send_to(username,{"t":"msg","m":f"{t2} is no longer OP."})

    elif cmd == "kick":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        t2 = args[0] if args else ""
        if t2 in online:
            send_to(t2,{"t":"msg","m":"Kicked by server."})
            time.sleep(0.1)
            try: online[t2].conn.close()
            except: pass

    elif cmd == "ban":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        t2 = args[0] if args else ""
        if t2 in players_db:
            players_db[t2]["banned"] = True
            save_db()
            if t2 in online:
                send_to(t2,{"t":"msg","m":"You have been banned."})
                time.sleep(0.1)
                try: online[t2].conn.close()
                except: pass

    elif cmd == "give":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        if len(args) < 2:
            send_to(username,{"t":"msg","m":"Usage: give <player> <item> [qty]"}); return
        t2  = args[0]
        qty = int(args[-1]) if len(args) > 2 and args[-1].isdigit() else 1
        item = "_".join(args[1:-1] if qty > 1 else args[1:])
        if t2 not in players_db:
            send_to(username,{"t":"msg","m":f"{t2} not found."}); return
        inv_add(players_db[t2], item, qty)
        save_db()
        send_to(username,{"t":"msg","m":f"Gave {qty}x {item} to {t2}."})
        send_to(t2,{"t":"msg","m":f"Received {qty}x {item}."})

    elif cmd == "tp":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        try:
            t2, x, y = args[0], int(args[1]), int(args[2])
            if t2 in players_db:
                players_db[t2]["x"] = max(0,min(WORLD_W-1,x))
                players_db[t2]["y"] = max(0,min(WORLD_H-1,y))
                send_to(t2,{"t":"teleport","x":x,"y":y})
                broadcast_state()
        except:
            send_to(username,{"t":"msg","m":"Usage: tp <player> <x> <y>"})

    elif cmd == "setblock":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        try:
            x, y, tile = int(args[0]), int(args[1]), args[2]
            if tile not in TILES:
                send_to(username,{"t":"msg","m":"Unknown tile."}); return
            set_tile(x, y, tile)
            broadcast({"t":"tile","x":x,"y":y,"tile":tile})
        except:
            send_to(username,{"t":"msg","m":"Usage: setblock <x> <y> <tile>"})

    elif cmd == "spawn":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        etype = args[0] if args else None
        if etype and etype not in ENEMIES:
            send_to(username,{"t":"msg","m":f"Unknown enemy. Valid: {', '.join(ENEMIES)}"}); return
        eid = spawn_enemy(etype)
        if eid:
            send_to(username,{"t":"msg","m":f"Spawned {etype or 'random'} (id={eid})."})

    elif cmd == "say":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        broadcast({"t":"chat","from":"[SERVER]","m":" ".join(args)})

    elif cmd == "save":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        save_db(); save_world()
        send_to(username,{"t":"msg","m":"Save queued."})

    elif cmd == "stop":
        if not p.get("op"):
            send_to(username,{"t":"msg","m":"No permission."}); return
        broadcast({"t":"msg","m":"*** Server shutting down! ***"})
        time.sleep(1)
        save_db(); save_world()
        time.sleep(1)
        os._exit(0)

    else:
        send_to(username,{"t":"msg","m":f"Unknown command '{cmd}'. Type 'help'."})

def _attack_enemy(username: str, eid: int):
    now = time.time()
    p   = players_db.get(username)
    if not p:
        return
    if now - p.get("last_attack",0) < ATTACK_COOLDOWN:
        return
    p["last_attack"] = now
    with enemy_lock:
        e = enemies.get(eid)
        if not e:
            return
        dmg  = max(1, calc_atk(p) - e["def"] + random.randint(-2, 3))
        e["hp"] -= dmg
        alive = e["hp"] > 0
        xp    = e["xp"]
        gold  = e["gold"]
        etype = e["type"]
        mhp   = e["max_hp"]
        hp    = max(0, e["hp"])
        if not alive:
            del enemies[eid]
    send_to(username,{"t":"msg","m":f"Hit {etype} for {dmg}! (HP:{hp}/{mhp})"})
    if not alive:
        p["xp"]    += xp
        p["gold"]  += gold
        p["kills"] += 1
        send_to(username,{"t":"msg","m":f"Killed {etype}! +{xp}XP +{gold}g"})
        for m in check_levelup(p):
            send_to(username,{"t":"msg","m":m})
        broadcast_enemies()
        save_db()
    broadcast_state()

# ============================================================
#  DROWNING
# ============================================================

def _drown_loop():
    while server_running:
        time.sleep(2)
        now = time.time()
        for uname in list(online):
            p  = players_db.get(uname)
            if not p:
                continue
            wt = p.get("water_time", 0)
            if not wt:
                continue
            secs = now - wt
            if secs > 5:
                dmg = max(1, int((secs-5)/2))
                p["hp"] = max(0, p["hp"] - dmg)
                p["water_time"] = now - 4
                send_to(uname,{"t":"msg","m":f"Drowning! -{dmg} HP! ({p['hp']}/{p['max_hp']})"})
                broadcast_state()
                if p["hp"] <= 0:
                    kill_player(uname)

# ============================================================
#  AUTO SAVE
# ============================================================

def _autosave_loop():
    while server_running:
        time.sleep(SAVE_INTERVAL)
        save_db()
        save_world()

# ============================================================
#  CLIENT HANDLER
# ============================================================

class Client:
    def __init__(self, conn, addr):
        self.conn     = conn
        self.addr     = addr
        self.username = None
        self._buf     = ""
        self.alive    = True
        self._lock    = threading.Lock()

    def send(self, msg: dict):
        if not self.alive:
            return
        try:
            data = net_encode(msg)
            with self._lock:
                self.conn.sendall(data)
        except Exception:
            self.alive = False

    def readline(self):
        while "\n" not in self._buf:
            try:
                chunk = self.conn.recv(4096).decode("utf-8","replace")
                if not chunk:
                    return None
                if len(self._buf) + len(chunk) > MAX_MSG_LEN * 2:
                    return None  # flood guard
                self._buf += chunk
            except Exception:
                return None
        line, self._buf = self._buf.split("\n", 1)
        return line.strip()

def handle_client(conn, addr):
    log(f"Connection from {addr[0]}:{addr[1]}")
    client   = Client(conn, addr)
    username = None

    try:
        conn.settimeout(30)
        client.send({"t":"auth_req","v":VERSION,"require_password":REQUIRE_PASSWORD})

        # auth loop — up to 5 attempts
        for _ in range(5):
            line = client.readline()
            if line is None:
                return
            try:
                msg = net_decode(line)
            except Exception:
                continue
            if msg.get("t") != "auth":
                continue

            uname = str(msg.get("username","")).strip()[:16]
            pw    = str(msg.get("password",""))[:64]

            if len(uname) < 2 or not uname.replace("_","").isalnum():
                client.send({"t":"auth_fail","reason":"Username: 2-16 alphanumeric chars."})
                continue

            with db_lock:
                if uname in players_db and players_db[uname].get("banned"):
                    client.send({"t":"auth_fail","reason":"You are banned."}); return

                if USE_WHITELIST:
                    wl = []
                    try:
                        with open(WHITELIST_FILE) as f:
                            wl = json.load(f)
                    except Exception:
                        pass
                    if uname not in wl:
                        client.send({"t":"auth_fail","reason":"Not on whitelist."}); return

                if uname in online:
                    client.send({"t":"auth_fail","reason":"Username already online."})
                    continue

                if REQUIRE_PASSWORD:
                    if uname not in players_db:
                        if not pw or len(pw) < 3:
                            client.send({"t":"auth_fail","reason":"New account — choose a password (3+ chars)."})
                            continue
                        np = new_player(uname)
                        np["password"] = hash_pw(pw)
                        players_db[uname] = np
                        save_db()
                        log(f"Registered: {uname}")
                    else:
                        if players_db[uname]["password"] != hash_pw(pw):
                            client.send({"t":"auth_fail","reason":"Wrong password."})
                            continue
                else:
                    if uname not in players_db:
                        np = new_player(uname)
                        players_db[uname] = np
                        save_db()
                username = uname
                break

        if not username:
            return

        client.username = username
        online[username] = client
        conn.settimeout(None)

        p = players_db[username]
        client.send({"t":"auth_ok","username":username,"op":p.get("op",False)})
        client.send({"t":"player","data":{
            "x":p["x"],"y":p["y"],
            "hp":p["hp"],"mhp":p["max_hp"],
            "lvl":p["level"],"xp":p["xp"],
            "gold":p["gold"],"atk":p["atk"],"def":p["def"],
            "weapon":p["weapon"],"armor":p["armor"],
            "inv":p.get("inventory",{}),
            "kills":p["kills"],"deaths":p["deaths"],
            "char":p.get("char","@"),"col":p.get("color","white"),
        }})
        send_world_view(username)
        broadcast_state()
        broadcast_enemies()
        broadcast({"t":"msg","m":f"*** {username} joined ***"}, exclude=(username,))
        log(f"Joined: {username} ({len(online)} online)")

        # main receive loop
        while client.alive:
            line = client.readline()
            if line is None:
                break
            if not line:
                continue
            try:
                msg = net_decode(line)
            except Exception:
                continue
            if msg.get("t") == "cmd":
                handle_cmd(username, str(msg.get("c",""))[:256])

    except Exception as e:
        log(f"Client error {addr[0]}: {e}")
    finally:
        if username and username in online:
            del online[username]
            broadcast({"t":"msg","m":f"*** {username} left ***"})
            broadcast_state()
            save_db()
            log(f"Disconnected: {username} ({len(online)} online)")
        try:
            conn.close()
        except Exception:
            pass

# ============================================================
#  SERVER CONSOLE  (run in main thread or background)
# ============================================================

def console_loop():
    log("Server console ready. Type 'help' for commands.")
    while server_running:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if not line.strip():
            continue
        parts = line.strip().split()
        cmd   = parts[0].lower()
        args  = parts[1:]

        if cmd == "help":
            print("  list              — online players")
            print("  players           — all accounts")
            print("  op/deop <player>  — OP control")
            print("  kick/ban <player> — moderation")
            print("  give <p> <i> [q]  — give item")
            print("  tp <p> <x> <y>    — teleport")
            print("  say <message>     — broadcast")
            print("  spawn [type]      — spawn enemy")
            print("  save              — force save")
            print("  stop              — shutdown")

        elif cmd == "list":
            if online:
                print("Online: " + ", ".join(
                    f"{u}(Lv{players_db[u]['level']})" for u in online))
            else:
                print("No players online.")

        elif cmd == "players":
            print(f"Accounts: {len(players_db)}")
            for name, pp in players_db.items():
                tags = [t for t,v in [("OP",pp.get("op")),("BANNED",pp.get("banned")),
                                       ("ONLINE",name in online)] if v]
                print(f"  {name:<16} Lv{pp['level']} {' '.join(tags)}")

        elif cmd == "op" and args:
            t2 = args[0]
            if t2 in players_db:
                players_db[t2]["op"] = True
                save_db()
                send_to(t2,{"t":"msg","m":"You are now OP!"})
                log(f"{t2} is now OP.")
            else:
                print(f"'{t2}' not found.")

        elif cmd == "deop" and args:
            t2 = args[0]
            if t2 in players_db:
                players_db[t2]["op"] = False
                save_db()
                log(f"{t2} is no longer OP.")

        elif cmd == "kick" and args:
            t2 = args[0]
            if t2 in online:
                send_to(t2,{"t":"msg","m":"Kicked by server."})
                time.sleep(0.1)
                try: online[t2].conn.close()
                except: pass
                log(f"Kicked {t2}.")
            else:
                print(f"{t2} not online.")

        elif cmd == "ban" and args:
            t2 = args[0]
            if t2 in players_db:
                players_db[t2]["banned"] = True
                save_db()
                if t2 in online:
                    send_to(t2,{"t":"msg","m":"You are banned."})
                    time.sleep(0.1)
                    try: online[t2].conn.close()
                    except: pass
                log(f"Banned {t2}.")

        elif cmd == "give" and len(args) >= 2:
            t2   = args[0]
            qty  = int(args[-1]) if len(args) > 2 and args[-1].isdigit() else 1
            item = "_".join(args[1:-1] if qty > 1 else args[1:])
            if t2 in players_db:
                inv_add(players_db[t2], item, qty)
                save_db()
                send_to(t2,{"t":"msg","m":f"Received {qty}x {item} from server."})
                log(f"Gave {qty}x {item} to {t2}.")
            else:
                print(f"'{t2}' not found.")

        elif cmd == "tp" and len(args) == 3:
            try:
                t2, x, y = args[0], int(args[1]), int(args[2])
                if t2 in players_db:
                    players_db[t2]["x"] = x
                    players_db[t2]["y"] = y
                    send_to(t2,{"t":"teleport","x":x,"y":y})
                    broadcast_state()
                    log(f"Teleported {t2} to ({x},{y}).")
            except Exception:
                print("Usage: tp <player> <x> <y>")

        elif cmd == "say":
            text = " ".join(args)
            broadcast({"t":"chat","from":"[SERVER]","m":text})
            log(f"[Broadcast] {text}")

        elif cmd == "spawn":
            etype = args[0] if args else None
            if etype and etype not in ENEMIES:
                print(f"Valid types: {', '.join(ENEMIES)}")
            else:
                eid = spawn_enemy(etype)
                log(f"Spawned {etype or 'random'} (id={eid}).")

        elif cmd == "save":
            save_db(); save_world()
            log("Save queued.")

        elif cmd == "stop":
            log("Stopping…")
            broadcast({"t":"msg","m":"*** Server shutting down ***"})
            time.sleep(1)
            save_db(); save_world()
            time.sleep(1)
            os._exit(0)

        else:
            print(f"Unknown: '{cmd}'. Type 'help'.")

# ============================================================
#  MAIN
# ============================================================

def main():
    global world, server_running

    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Usage: python server.py [port]")
            sys.exit(1)

    log(f"TermQuest RPG Server v{VERSION}")
    log(f"Port: {port}  |  Max players: {MAX_PLAYERS}")
    log(f"Password required: {REQUIRE_PASSWORD}")

    # load or generate world
    if not load_world_file():
        world = generate_world()
        save_world()
    load_db()

    # seed starting enemies
    if SPAWN_ENEMIES:
        for _ in range(5):
            spawn_enemy()

    # background threads
    threading.Thread(target=_save_worker,  daemon=True).start()
    threading.Thread(target=_autosave_loop,daemon=True).start()
    threading.Thread(target=_drown_loop,   daemon=True).start()
    threading.Thread(target=_enemy_loop,   daemon=True).start()

    # server socket
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((DEFAULT_HOST, port))
    except OSError as e:
        log(f"Bind failed: {e}")
        sys.exit(1)
    srv.listen(MAX_PLAYERS)
    srv.settimeout(1.0)

    log(f"Listening on {DEFAULT_HOST}:{port}")
    log(f"Players connect with:  python client.py <your-ip> {port}")
    log(f"To give OP:  op <playername>  in this console")
    log(f"Type 'help' for console commands.\n")

    # accept loop (main thread) + console in background
    threading.Thread(target=console_loop, daemon=True).start()

    try:
        while server_running:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if len(online) >= MAX_PLAYERS:
                try:
                    conn.sendall(net_encode({"t":"auth_fail","reason":"Server full."}))
                    conn.close()
                except Exception:
                    pass
                continue
            t = threading.Thread(target=handle_client, args=(conn,addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        pass
    finally:
        server_running = False
        log("Saving and shutting down…")
        save_db(); save_world()
        time.sleep(1)
        srv.close()
        log("Goodbye!")

if __name__ == "__main__":
    main()
