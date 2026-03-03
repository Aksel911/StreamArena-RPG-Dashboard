"""
StreamArena RPG — Flask Dashboard
Disk-based udata cache (bypasses 4KB cookie limit)
"""
import os, json, hashlib, time, requests, threading, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify)

app = Flask(__name__)
app.secret_key = 'streamarena_secret_2026'

API_URL       = 'https://streamarenarpg.com/portal/portal_api.php'
GUILD_API_URL = 'https://streamarenarpg.com/guild/guild_api.php'
API_VERSION   = '0.32.04'
HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Origin': 'https://streamarenarpg.com',
    'Referer': 'https://streamarenarpg.com/portal/app/portal.html',
}

# ── Shared requests session (reuses TCP connections, ~30% faster) ─────────────
_http = requests.Session()
_http.headers.update(HEADERS)

# ── Disk cache (udata ~14KB — way over Flask's 4KB cookie limit) ──────────────
CACHE_DIR = '/tmp/streamarena_cache'
CACHE_TTL = 120  # 2 minutes
os.makedirs(CACHE_DIR, exist_ok=True)

def _cache_path(token):
    return os.path.join(CACHE_DIR, hashlib.sha256(token.encode()).hexdigest() + '.json')

def cache_save(token, data):
    with open(_cache_path(token), 'w') as f:
        json.dump(data, f)

def cache_load(token):
    p = _cache_path(token)
    if os.path.exists(p):
        if time.time() - os.path.getmtime(p) < CACHE_TTL:
            with open(p) as f:
                return json.load(f)
        os.remove(p)  # Expired
    return None

def cache_clear(token):
    p = _cache_path(token)
    if os.path.exists(p):
        os.remove(p)

# ── Constants ─────────────────────────────────────────────────────────────────
SLOT_ICONS = {
    'weapon':'⚔️','off_hand':'🛡️','head':'⛑️','body':'👘',
    'hands':'🧤','feet':'👟','ring':'💍','neck':'📿','any':'🎒'
}
CLASS_ICONS = {
    'barbarian':'🪓','tank':'🛡️','rogue':'🗡️',
    'mage':'🔮','summoner':'👁️','healer':'✨','ranger':'🏹',
}

# ── Inventory Slot Price Calculator ─────────────────────────────────────────
def inv_slots_price_calc(inventory_slots: int) -> int:
    """Returns platinum cost for next +10 inventory slots."""
    multi = (inventory_slots - 100) / 10.0
    price = 1
    for _ in range(int(multi)):
        price *= 2
    return int(price)

# ── Auto Worker (server-side background automation) ───────────────────────────
AUTO_DIR = os.path.join(CACHE_DIR, 'auto')
os.makedirs(AUTO_DIR, exist_ok=True)

def _auto_path(token: str) -> str:
    return os.path.join(AUTO_DIR, hashlib.sha256(token.encode()).hexdigest() + '_auto.json')

def auto_load(token: str) -> dict:
    try:
        with open(_auto_path(token)) as f:
            return json.load(f)
    except Exception:
        return {}

def auto_save(token: str, data: dict):
    with open(_auto_path(token), 'w') as f:
        json.dump(data, f)

def _run_auto_for_user(token: str, settings: dict):
    """Run all enabled auto features for one user. Called from background thread."""
    features = settings.get('features', {})
    gm_cache = None

    def get_gm():
        nonlocal gm_cache
        if gm_cache is None:
            r = _api_call_threaded({'route': 'get_game_items'}, token)
            gm_cache = {}
            if r.get('status') == 'success':
                for item in r.get('items', []):
                    gm_cache.setdefault(item['slot'], {})[str(item['id'])] = item
        return gm_cache

    def ann(items):
        gm = get_gm()
        for item in items:
            slot = item.get('slot', '')
            bid  = str(item.get('base_item_id', '0'))
            gi   = gm.get(slot, {}).get(bid)
            item['item_name'] = gi['item_name'] if gi else f'{slot} #{bid}'
            item['classes']   = gi.get('classes', ['any']) if gi else ['any']
        return items

    log = logging.getLogger('auto_worker')
    player_class = settings.get('player_class', '')

    # ── Auto-Equip Best Items ─────────────────────────────────────────
    if features.get('auto_equip', {}).get('enabled'):
        try:
            inv_r  = _api_call_threaded({'route': 'get_inv', 'page': 1}, token)
            udata  = _api_call_threaded({'route': 'get_udata'}, token)
            char   = udata.get('characters', [{}])[0] if udata.get('characters') else {}
            items  = ann(inv_r.get('player_items', []))

            equipped_power = {}
            equipped_by_slot = {}
            for k, slot in SLOT_MAP.items():
                iid = str(char.get(k, '-1'))
                for it in items:
                    if str(it.get('id')) == iid:
                        equipped_power[slot]    = float(it.get('power', 0)) * 100
                        equipped_by_slot[slot]  = it
                        break

            best_by_slot = {}
            for it in items:
                slot    = it.get('slot', '')
                iid     = str(it.get('id'))
                power   = float(it.get('power', 0)) * 100
                classes = it.get('classes', ['any'])
                # Skip if equipped
                if iid in {str(v.get('id')) for v in equipped_by_slot.values() if v}:
                    continue
                class_ok = 'any' in classes or not player_class or player_class in classes
                if not class_ok:
                    continue
                if slot not in best_by_slot or power > best_by_slot[slot]['power']:
                    best_by_slot[slot] = {'id': int(iid), 'power': power, 'slot': slot}

            for slot, best in best_by_slot.items():
                current = equipped_power.get(slot, -1)
                if best['power'] > current:
                    res = _api_call_threaded({'route': 'equip', 'item_id': best['id'], 'slot': slot}, token)
                    if res.get('status') == 'success':
                        log.info(f"Auto-equip: equipped {slot} power={best['power']:.1f}%")
        except Exception as e:
            log.error(f"auto_equip error: {e}")

    # ── Auto-Delete ────────────────────────────────────────────────────
    if features.get('auto_delete', {}).get('enabled'):
        try:
            cfg = features['auto_delete']
            power_max = float(cfg.get('power_max', 10))
            slots     = cfg.get('slots', list(SLOT_MAP.values()))

            inv_r  = _api_call_threaded({'route': 'get_inv', 'page': 1}, token)
            locks_r = _api_call_threaded({'route': 'get_player_item_locks'}, token)
            my_l_r  = _api_call_threaded({'route': 'my_listings'}, token)
            udata   = _api_call_threaded({'route': 'get_udata'}, token)

            locked_ids   = {str(x) for x in locks_r.get('locked_items', [])}
            listed_ids   = {str(l['id']) for l in my_l_r.get('listings', [])}
            char         = udata.get('characters', [{}])[0] if udata.get('characters') else {}
            equipped_ids = {str(char.get(k, '-1')) for k in SLOT_MAP} - {'-1', ''}

            to_delete = []
            for it in ann(inv_r.get('player_items', [])):
                iid   = str(it.get('id'))
                power = float(it.get('power', 0)) * 100
                if (it.get('slot') in slots and power < power_max
                        and iid not in locked_ids
                        and iid not in listed_ids
                        and iid not in equipped_ids):
                    to_delete.append(iid)

            for iid in to_delete:
                _api_call_threaded({'route': 'destroy', 'item_id': iid}, token)
            if to_delete:
                log.info(f"Auto-delete: deleted {len(to_delete)} items")
        except Exception as e:
            log.error(f"auto_delete error: {e}")

    # ── Auto-List ──────────────────────────────────────────────────────
    if features.get('auto_list', {}).get('enabled'):
        try:
            cfg         = features['auto_list']
            power_thr   = float(cfg.get('power_threshold', 15))
            power_mode  = cfg.get('power_mode', 'below')   # 'below' or 'above'
            slots       = cfg.get('slots', list(SLOT_MAP.values()))
            gold_cost   = int(cfg.get('gold', 0))
            plat_cost   = int(cfg.get('plat', 0))
            gem_cost    = int(cfg.get('gems', 0))
            if gold_cost == 0 and plat_cost == 0 and gem_cost == 0:
                pass  # no price set, skip
            else:
                inv_r   = _api_call_threaded({'route': 'get_inv', 'page': 1}, token)
                locks_r = _api_call_threaded({'route': 'get_player_item_locks'}, token)
                my_l_r  = _api_call_threaded({'route': 'my_listings'}, token)
                udata   = _api_call_threaded({'route': 'get_udata'}, token)

                locked_ids   = {str(x) for x in locks_r.get('locked_items', [])}
                listed_ids   = {str(l['id']) for l in my_l_r.get('listings', [])}
                char         = udata.get('characters', [{}])[0] if udata.get('characters') else {}
                equipped_ids = {str(char.get(k, '-1')) for k in SLOT_MAP} - {'-1', ''}

                for it in ann(inv_r.get('player_items', [])):
                    iid   = str(it.get('id'))
                    power = float(it.get('power', 0)) * 100
                    match_power = (power < power_thr) if power_mode == 'below' else (power >= power_thr)
                    if (it.get('slot') in slots and match_power
                            and iid not in locked_ids
                            and iid not in listed_ids
                            and iid not in equipped_ids):
                        _api_call_threaded({'route': 'list_item', 'item_id': int(iid),
                            'gold_cost': gold_cost, 'platinum_cost': plat_cost, 'gem_cost': gem_cost}, token)
                log.info("Auto-list: pass done")
        except Exception as e:
            log.error(f"auto_list error: {e}")

    # ── Auto-Equip Consumables ─────────────────────────────────────────
    if features.get('auto_equip_cons', {}).get('enabled'):
        try:
            cons_r = _api_call_threaded({'route': 'get_player_consumables'}, token)
            equipped_cons = cons_r.get('equipped_consumables', [])
            all_cons      = cons_r.get('consumables', [])

            # Check which slots are empty
            filled_slots = {int(ec.get('slot', 0)) for ec in equipped_cons}
            empty_slots  = [s for s in [1, 2, 3] if s not in filled_slots]

            if empty_slots and all_cons:
                # Build set of already equipped consumable_ids
                equipped_cids = {str(ec.get('consumable_id')) for ec in equipped_cons}
                available = [c for c in all_cons if str(c.get('consumable_id', c.get('id'))) not in equipped_cids]
                for i, slot in enumerate(empty_slots):
                    if i >= len(available):
                        break
                    cid = available[i].get('consumable_id', available[i].get('id'))
                    _api_call_threaded({'route': 'equip_consumable', 'consumable_id': cid, 'slot': slot}, token)
                log.info(f"Auto-equip-cons: filled {len(empty_slots)} empty slot(s)")
        except Exception as e:
            log.error(f"auto_equip_cons error: {e}")

    # ── Auto-Open Chests ───────────────────────────────────────────────
    if features.get('auto_open_chests', {}).get('enabled'):
        try:
            chests_r = _api_call_threaded({'route': 'get_player_chests'}, token)
            for chest in chests_r.get('chests', []):
                if int(chest.get('amount', 0)) > 0:
                    _api_call_threaded({'route': 'open_multi_player_chests', 'chest_id': int(chest.get('chest_id', 0))}, token)
            log.info("Auto-open-chests: pass done")
        except Exception as e:
            log.error(f"auto_open_chests error: {e}")


def _auto_worker_loop():
    """Background thread: runs auto features for all users every 30s."""
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger('auto_worker')
    while True:
        try:
            if os.path.isdir(AUTO_DIR):
                for fname in os.listdir(AUTO_DIR):
                    if not fname.endswith('_auto.json'):
                        continue
                    fpath = os.path.join(AUTO_DIR, fname)
                    try:
                        with open(fpath) as f:
                            settings = json.load(f)
                        token = settings.get('token')
                        if not token:
                            continue
                        features = settings.get('features', {})
                        any_enabled = any(v.get('enabled') for v in features.values() if isinstance(v, dict))
                        if any_enabled:
                            _run_auto_for_user(token, settings)
                    except Exception as e:
                        log.error(f"Worker error for {fname}: {e}")
        except Exception as e:
            log.error(f"Worker loop error: {e}")
        time.sleep(30)


# Start background auto-worker thread (daemon so it exits with Flask)
_auto_thread = threading.Thread(target=_auto_worker_loop, daemon=True, name='auto_worker')
_auto_thread.start()

NO_VERSION_ROUTES = {
    'my_listings','get_listings','toggle_item_lock','destroy','equip','unequip',
    'redeem_voucher','get_skills','get_backs','get_shaders','list_item',
    'buy_listing','send_chat_message','send_guild_message'
}
SLOT_MAP = {
    'head_equip':    'head',
    'body_equip':    'body',
    'hands_equip':   'hands',
    'feet_equip':    'feet',
    'weapon_equip':  'weapon',
    'offhand_equip': 'off_hand',
    'ring_equip':    'ring',
    'neck_equip':    'neck',
}

# ── API helpers ───────────────────────────────────────────────────────────────
def _inject_token(payload, token):
    """Inject token + version into payload. Thread-safe (no session access)."""
    payload['token'] = token
    if 'version' not in payload and payload.get('route') not in NO_VERSION_ROUTES:
        payload['version'] = API_VERSION

def api_call(payload, url=API_URL):
    token = session.get('token')
    if not token:
        return {'status':'error','message':'No token'}
    _inject_token(payload, token)
    try:
        r = _http.post(url, json=payload, timeout=15)
        return r.json()
    except Exception as e:
        return {'status':'error','message':str(e)}

def guild_api_call(payload):
    return api_call(payload, url=GUILD_API_URL)

def _api_call_threaded(payload, token, url=API_URL):
    """Thread-safe API call: token passed explicitly, no Flask session access."""
    _inject_token(payload, token)
    try:
        r = _http.post(url, json=payload, timeout=15)
        return r.json()
    except Exception as e:
        return {'status':'error','message':str(e)}

def parallel_api_calls(calls: dict, url=API_URL) -> dict:
    """
    Execute multiple API calls in parallel.
    Token is read from Flask session BEFORE spawning threads.
    calls = {'key': payload_dict, ...}
    Returns {'key': response_dict, ...}
    """
    token = session.get('token')
    if not token:
        return {k: {'status':'error','message':'No token'} for k in calls}
    results = {}
    with ThreadPoolExecutor(max_workers=min(len(calls), 8)) as ex:
        futures = {}
        for k, p in calls.items():
            if p.get('route') == 'guild_info':
                call_url = GUILD_API_URL
            else:
                call_url = url
                
            futures[ex.submit(_api_call_threaded, p, token, call_url)] = k
            
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
    return results

def get_udata(force_refresh=False):
    """Return full udata — disk-cached or fresh from API."""
    token = session.get('token')
    if not token:
        return {}
    if not force_refresh:
        cached = cache_load(token)
        if cached and cached.get('status') == 'success' and cached.get('characters'):
            return cached
    data = api_call({'route':'get_udata'})
    if data.get('status') == 'success' and data.get('characters'):
        cache_save(token, data)
    return data

def get_game_items_dict():
    data = api_call({'route':'get_game_items'})
    lookup = {}
    if data.get('status') == 'success':
        for item in data.get('items', []):
            lookup.setdefault(item['slot'], {})[str(item['id'])] = item
    return lookup

def annotate_items(items, game_items):
    for item in items:
        slot = item.get('slot','')
        bid  = str(item.get('base_item_id','0'))
        gi   = game_items.get(slot,{}).get(bid)
        item['item_name']    = gi['item_name'] if gi else f'{slot.title()} #{bid}'
        item['classes']      = gi.get('classes',['any']) if gi else ['any']
        item['extra_parsed'] = json.loads(item['extra']) if item.get('extra') else {}
    return items

def get_equipped_ids(udata):
    """Return set of item IDs currently equipped by the character."""
    char = udata.get('characters', [{}])[0] if udata.get('characters') else {}
    return {str(char.get(k, '-1')) for k in SLOT_MAP} - {'-1', ''}

def _auth():
    if not session.get('token'):
        return redirect(url_for('index'))
    return None

# ── Index / Login ─────────────────────────────────────────────────────────────
@app.route('/', methods=['GET','POST'])
def index():
    if request.method == 'POST':
        token = request.form.get('token','').strip()
        if token:
            session.clear()
            session['token'] = token
            data = get_udata(force_refresh=True)
            if data.get('status') == 'success' and data.get('characters'):
                session['username'] = data.get('username','')
                session['guild_id'] = data.get('guild_id')
                return redirect(url_for('dashboard'))
            session.clear()
            return render_template('index.html', error='Invalid token or API returned no data.')
    if session.get('token') and cache_load(session.get('token','')):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    if t := session.get('token'):
        cache_clear(t)
    session.clear()
    return redirect(url_for('index'))

@app.route('/refresh_udata')
def refresh_udata():
    if e := _auth(): return e
    data = get_udata(force_refresh=True)
    if data.get('status') == 'success':
        session['guild_id'] = data.get('guild_id')
    return redirect(request.args.get('next', url_for('dashboard')))

# ── Dashboard (parallel API calls) ───────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if e := _auth(): return e
    udata = get_udata()

    # Resolve guild_id from udata
    guild_id = None
    try:
        guild_id = int(udata.get('guild_id') or 0) or None
    except (TypeError, ValueError):
        guild_id = None

    parallel_calls = {
        'mail':        {'route':'get_player_mail'},
        'spin':        {'route':'get_next_daily_spin'},
        'streamer':    {'route':'is_streamer'},
        'consumables': {'route':'get_player_consumables'},
        'skills':      {'route':'get_skills'},
        'chests':      {'route':'get_player_chests'},
    }
    if guild_id:
        parallel_calls['guild_info'] = {'guild_id': guild_id, 'route': 'guild_info'}

    results = parallel_api_calls(parallel_calls)

    #print(results)
    
    # Extract guild name safely
    guild_name = None
    if guild_id and results.get('guild_info'):
        guild_name = results['guild_info'].get('guild', {}).get('name')
        guild_tag = results['guild_info'].get('guild', {}).get('tag')

    return render_template('dashboard.html',
        udata=udata, guild_name=guild_name, guild_tag=guild_tag,
        mail=results['mail'], spin=results['spin'], streamer=results['streamer'],
        consumables=results['consumables'], skills=results['skills'],
        chests=results['chests'],
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS)

# ── Inventory ─────────────────────────────────────────────────────────────────
@app.route('/inventory')
def inventory():
    if e := _auth(): return e
    page = int(request.args.get('page', 1))

    # Parallel: inventory page + locks + my_listings
    results = parallel_api_calls({
        'inv':         {'route':'get_inv','page':page},
        'locks':       {'route':'get_player_item_locks'},
        'my_listings': {'route':'my_listings'},
    })
    inv         = results['inv']
    locks       = results['locks']
    my_listings = results['my_listings']

    gm         = get_game_items_dict()
    locked_ids = {str(x) for x in locks.get('locked_items', [])}
    listed_ids = {str(l['id']) for l in my_listings.get('listings', [])}

    # equipped_ids from cached udata (no extra API call)
    udata        = get_udata()
    equipped_ids = get_equipped_ids(udata)

    items = annotate_items(inv.get('player_items', []), gm)
    for item in items:
        item['is_locked']   = str(item['id']) in locked_ids
        item['is_listed']   = str(item['id']) in listed_ids
        item['is_equipped'] = str(item['id']) in equipped_ids

    user        = udata.get('user', {})
    inv_total   = int(user.get('inventory_slots', 0))
    items_used  = len(udata.get('player_items', []))
    next_price  = inv_slots_price_calc(inv_total)

    return render_template('inventory.html',
        inv=inv, items=items, page=page,
        locked_ids=locked_ids, listed_ids=listed_ids, equipped_ids=equipped_ids,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS,
        my_listings=my_listings,
        inv_total=inv_total, items_used=items_used, next_price=next_price, user=user)

# ── Equipment ─────────────────────────────────────────────────────────────────
@app.route('/equipment')
def equipment():
    if e := _auth(): return e
    udata  = get_udata()
    skills = api_call({'route':'get_skills'})
    gm     = get_game_items_dict()

    char         = udata.get('characters',[{}])[0] if udata.get('characters') else {}
    player_items = {str(i['id']): i for i in udata.get('player_items',[])}
    all_inv      = annotate_items(list(udata.get('player_items',[])), gm)

    equipped = {}
    for key, slot in SLOT_MAP.items():
        iid = str(char.get(key,'-1'))
        if iid not in ('-1','') and iid in player_items:
            item = dict(player_items[iid])
            gi   = gm.get(slot,{}).get(str(item.get('base_item_id','0')))
            item['item_name']    = gi['item_name'] if gi else f'{slot.title()} #{item.get("base_item_id","?")}'
            item['extra_parsed'] = json.loads(item['extra']) if item.get('extra') else {}
            equipped[slot] = item
        else:
            equipped[slot] = None

    equipped_ids = get_equipped_ids(udata)

    return render_template('equipment.html',
        character=char, equipped=equipped, all_inv=all_inv,
        equipped_ids=equipped_ids, skills=skills,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS)

# ── Market ────────────────────────────────────────────────────────────────────
@app.route('/market')
def market():
    if e := _auth(): return e
    slot_filter  = request.args.get('slot','any')
    class_filter = request.args.get('class_flag','any')
    page         = int(request.args.get('page',1))

    results = parallel_api_calls({
        'listings':    {'route':'get_listings','slot':slot_filter,'class':class_filter,'page':page},
        'my_listings': {'route':'my_listings'},
        'game_chests': {'route':'get_chests'},
        'inv_data':    {'route':'get_inv','page':1},
    })
    listings    = results['listings']
    my_listings = results['my_listings']
    game_chests = results['game_chests']
    user        = results['inv_data'].get('user', {})

    gm = get_game_items_dict()
    annotate_items(listings.get('listings',[]), gm)
    annotate_items(my_listings.get('listings',[]), gm)

    return render_template('market.html',
        listings=listings, my_listings=my_listings, game_chests=game_chests,
        slot_filter=slot_filter, class_filter=class_filter, page=page,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS,
        player_gold=int(user.get('gold',0)),
        player_plat=int(user.get('platinum',0)),
        player_gems=int(user.get('gems',0)),
        my_username=session.get('username',''))

# ── Guild ─────────────────────────────────────────────────────────────────────
@app.route('/guild')
def guild():
    if e := _auth(): return e
    udata    = get_udata()
    guild_id = udata.get('guild_id')
    try:
        guild_id = int(guild_id) if guild_id else None
    except (TypeError, ValueError):
        guild_id = None
    if not guild_id:
        try:
            guild_id = int(session.get('guild_id') or 0) or None
        except (TypeError, ValueError):
            guild_id = None

    if not guild_id:
        return render_template('guild.html',
            guild_info={}, roster={}, messages={}, guild_id=None,
            class_icons=CLASS_ICONS,
            error='Guild not found. Click 🔄 Refresh or enter Guild ID manually.')

    results = parallel_api_calls({
        'guild_info': {'guild_id':guild_id,'route':'guild_info'},
        'roster':     {'guild_id':guild_id,'route':'guild_roster'},
    }, url=GUILD_API_URL)
    messages = guild_api_call({'route':'get_guild_messages'})

    return render_template('guild.html',
        guild_info=results['guild_info'], roster=results['roster'],
        messages=messages, guild_id=guild_id,
        class_icons=CLASS_ICONS, error=None)

@app.route('/guild/set_id', methods=['POST'])
def guild_set_id():
    if e := _auth(): return e
    try:
        session['guild_id'] = int(request.form.get('guild_id',0))
    except (ValueError, TypeError):
        pass
    return redirect(url_for('guild'))

# ── Cosmetics ─────────────────────────────────────────────────────────────────
@app.route('/cosmetics')
def cosmetics():
    if e := _auth(): return e
    results = parallel_api_calls({
        'shaders':      {'route':'get_shaders'},
        'backs':        {'route':'get_backs'},
        'consumables':  {'route':'get_player_consumables'},
        'player_chests':{'route':'get_player_chests'},
        'game_chests':  {'route':'get_chests'},
        'inv_data':     {'route':'get_inv','page':1},
    })
    shaders        = results['shaders']
    backs          = results['backs']
    consumables    = results['consumables']
    player_chests  = results['player_chests']
    game_chests    = results['game_chests']
    balance_user   = results['inv_data'].get('user', {})

    shaders_by_id = {str(s['id']): s for s in shaders.get('shaders',[])}
    backs_by_id   = {str(b['id']): b for b in backs.get('back_items',[])}

    udata = get_udata()
    user  = udata.get('user',{})
    char  = udata.get('characters',[{}])[0] if udata.get('characters') else {}
    raw   = user.get('cosmetics','{}') or '{}'
    try:
        owned = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        owned = {}

    owned_back_ids = [str(x) for x in owned.get('back_items',[])]
    owned_backs = []
    for bid in owned_back_ids:
        if bid in backs_by_id:
            owned_backs.append(backs_by_id[bid])
        else:
            owned_backs.append({'id':bid,'display_name':f'Back Item #{bid}',
                                 'platinum_cost':'0','gold_cost':'0','gem_cost':'0'})

    return render_template('cosmetics.html',
        shaders=shaders, backs=backs, consumables=consumables,
        owned_backs=owned_backs,
        equipped_back_id=str(char.get('back_equip','-1')),
        shaders_by_id=shaders_by_id,
        backs_by_id=backs_by_id,
        player_chests=player_chests,
        game_chests=game_chests,
        player_gold=int(balance_user.get('gold',0)),
        player_plat=int(balance_user.get('platinum',0)),
        player_gems=int(balance_user.get('gems',0)),
        slot_icons=SLOT_ICONS)

# ── Bosses ────────────────────────────────────────────────────────────────────
@app.route('/bosses')
def bosses():
    if e := _auth(): return e
    results = parallel_api_calls({
        'bosses_data': {'route':'get_active_world_bosses'},
        'battles':     {'route':'get_current_world_battles'},
        'dungeons':    {'route':'get_active_dungeons'},
    })
    return render_template('bosses.html', **results)

# ── Leaderboard ───────────────────────────────────────────────────────────────
@app.route('/leaderboard')
def leaderboard():
    if e := _auth(): return e
    class_flag = request.args.get('class_flag','all')
    top = api_call({'class_flag':class_flag,'route':'get_top_players'})
    return render_template('leaderboard.html',
        top=top, class_flag=class_flag, class_icons=CLASS_ICONS)

# ── Chat ──────────────────────────────────────────────────────────────────────
@app.route('/chat')
def chat():
    if e := _auth(): return e
    return render_template('chat.html',
        messages=api_call({'route':'get_chat_messages'}))

# JSON endpoint for live chat polling
@app.route('/api/chat_messages')
def api_chat_messages():
    if e := _auth(): return e
    return jsonify(api_call({'route':'get_chat_messages'}))

@app.route('/api/guild_messages')
def api_guild_messages():
    if e := _auth(): return e
    return jsonify(guild_api_call({'route':'get_guild_messages'}))

# ── Friends ──────────────────────────────────────────────────────────────────
@app.route('/friends')
def friends():
    if e := _auth(): return e
    data = api_call({'route': 'get_friend_list', 'version': API_VERSION})
    return render_template('friends.html', friend_data=data, class_icons=CLASS_ICONS)

# ── Mail ──────────────────────────────────────────────────────────────────────
@app.route('/mail')
def mail():
    if e := _auth(): return e
    return render_template('mail.html',
        mail_data=api_call({'route':'get_player_mail'}))

# ── Action endpoints ──────────────────────────────────────────────────────────
def _req():
    if not session.get('token'):
        return jsonify({'error':'unauthorized'}), 401
    return None

@app.route('/action/lock', methods=['POST'])
def action_lock():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'item_ids':d.get('item_ids',[]),'route':'toggle_item_lock','toggle':d.get('toggle','lock')}))

@app.route('/action/destroy', methods=['POST'])
def action_destroy():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'item_id':d.get('item_id'),'route':'destroy'}))

@app.route('/action/destroy_items', methods=['POST'])
def action_destroy_items():
    if r := _req(): return r
    data     = request.get_json()
    item_ids = data.get('item_ids', [])
    if not item_ids:
        return jsonify({'status':'error','message':'No item IDs provided'})

    success_count = 0
    errors = []

    # Sequential (API doesn't support batch destroy)
    for item_id in item_ids:
        res = api_call({'item_id': item_id, 'route': 'destroy'})
        if res.get('status') == 'success':
            success_count += 1
        else:
            errors.append({'id': item_id, 'error': res.get('message','Unknown error')})

    if success_count == len(item_ids):
        return jsonify({'status':'success','deleted_count':success_count})
    elif success_count > 0:
        return jsonify({'status':'partial','deleted_count':success_count,'errors':errors})
    else:
        return jsonify({'status':'error','message':'Failed to delete any items','errors':errors})

@app.route('/action/equip', methods=['POST'])
def action_equip():
    if r := _req(): return r
    d = request.get_json()
    res = api_call({'item_id':d.get('item_id'),'slot':d.get('slot','any'),'route':'equip'})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/unequip', methods=['POST'])
def action_unequip():
    if r := _req(): return r
    d = request.get_json()
    res = api_call({'slot':d.get('slot'),'route':'unequip'})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/list_item', methods=['POST'])
def action_list_item():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'list_item','item_id':d.get('item_id'),
        'gold_cost':int(d.get('gold_cost',0)),'platinum_cost':int(d.get('platinum_cost',0)),
        'gem_cost':int(d.get('gem_cost',0))}))

@app.route('/action/buy_listing', methods=['POST'])
def action_buy_listing():
    if r := _req(): return r
    d = request.get_json()
    res = api_call({'route':'buy_listing','item_id':d.get('item_id'),'currency':d.get('currency','standard')})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/redeem', methods=['POST'])
def action_redeem():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'redeem_voucher','voucher_string':d.get('voucher_string','')}))

@app.route('/action/send_chat', methods=['POST'])
def action_send_chat():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'send_chat_message','message':d.get('message','')}))

@app.route('/action/send_guild_chat', methods=['POST'])
def action_send_guild_chat():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(guild_api_call({'route':'send_guild_message','message':d.get('message','')}))


@app.route('/action/equip_consumable', methods=['POST'])
def action_equip_consumable():
    if r := _req(): return r
    d = request.get_json()
    consumable_id = d.get('consumable_id', -1)  # -1 = unequip
    slot = int(d.get('slot', 1))
    return jsonify(api_call({
        'route': 'equip_consumable',
        'consumable_id': consumable_id,
        'slot': slot,
    }))


@app.route('/action/open_chest', methods=['POST'])
def action_open_chest():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'open_player_chest','chest_id':int(d.get('chest_id',0))}))

@app.route('/action/open_multi_chest', methods=['POST'])
def action_open_multi_chest():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'open_multi_player_chests','chest_id':int(d.get('chest_id',0))}))

@app.route('/action/buy_chest', methods=['POST'])
def action_buy_chest():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'buy_chest','chest_id':int(d.get('chest_id',0)),'currency':d.get('currency','standard')}))

@app.route('/action/cancel_listing', methods=['POST'])
def action_cancel_listing():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route':'cancel_listing','item_id':int(d.get('item_id',0))}))


@app.route('/action/daily_spin', methods=['POST'])
def action_daily_spin():
    if r := _req(): return r
    return jsonify(api_call({'route': 'daily_spin'}))

@app.route('/auto/save', methods=['POST'])
def auto_save_settings():
    if r := _req(): return r
    d = request.get_json()
    token = session.get('token')
    udata = get_udata()
    char  = udata.get('characters', [{}])[0] if udata.get('characters') else {}
    settings = auto_load(token)
    settings['token']        = token
    settings['player_class'] = char.get('class', '')
    settings['features']     = d.get('features', settings.get('features', {}))
    auto_save(token, settings)
    return jsonify({'status': 'success'})

@app.route('/auto/status')
def auto_get_status():
    if not session.get('token'):
        return jsonify({'error': 'unauthorized'}), 401
    s = auto_load(session['token'])
    return jsonify({
        'features': s.get('features', {}),
        'player_class': s.get('player_class', ''),
    })

@app.route('/api/auto_data')
def api_auto_data():
    """Single endpoint for all auto-features — called from global base.html runner."""
    if not session.get('token'):
        return jsonify({'error': 'unauthorized'}), 401
    udata = get_udata()
    char  = udata.get('characters', [{}])[0] if udata.get('characters') else {}

    results = parallel_api_calls({
        'spin':        {'route': 'get_next_daily_spin'},
        'consumables': {'route': 'get_consumables'},
        'chests':      {'route': 'get_player_chests'},
        'locks':       {'route': 'get_player_item_locks'},
        'my_listings': {'route': 'my_listings'},
    })

    gm           = get_game_items_dict()
    items        = annotate_items(list(udata.get('player_items', [])), gm)
    locked_ids   = {str(x) for x in results['locks'].get('locked_items', [])}
    listed_ids   = {str(l['id']) for l in results['my_listings'].get('listings', [])}
    equipped_ids = get_equipped_ids(udata)

    slim_items = []
    for it in items:
        slim_items.append({
            'id':          it.get('id'),
            'slot':        it.get('slot', ''),
            'power':       round(float(it.get('power', 0)) * 100, 2),
            'classes':     it.get('classes', ['any']),
            'item_name':   it.get('item_name', ''),
            'is_equipped': str(it['id']) in equipped_ids,
            'is_locked':   str(it['id']) in locked_ids,
            'is_listed':   str(it['id']) in listed_ids,
        })

    return jsonify({
        'spin':         results['spin'],
        'consumables':  results['consumables'],
        'chests':       results['chests'],
        'player_class': char.get('class', ''),
        'items':        slim_items,
    })


@app.route('/action/cancel_all_listings', methods=['POST'])
def action_cancel_all_listings():
    if r := _req(): return r
    my = api_call({'route': 'my_listings'})
    listings = my.get('listings', [])
    ok, fail = 0, 0
    for item in listings:
        res = api_call({'route': 'cancel_listing', 'item_id': int(item['id'])})
        if res.get('status') == 'success': ok += 1
        else: fail += 1
    return jsonify({'status': 'success', 'cancelled': ok, 'failed': fail})


@app.route('/action/set_back', methods=['POST'])
def action_set_back():
    if r := _req(): return r
    d   = request.get_json()
    bid = d.get('back_item_id')
    # bid=None or -1 means unequip (send -1)
    res = api_call({'route': 'set_back', 'back_item_id': bid if bid is not None else -1})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/buy_back', methods=['POST'])
def action_buy_back():
    if r := _req(): return r
    d   = request.get_json()
    res = api_call({'route': 'buy_back', 'back_item_id': d.get('back_item_id'),
                    'currency': d.get('currency', 'standard')})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/buy_shader', methods=['POST'])
def action_buy_shader():
    if r := _req(): return r
    d   = request.get_json()
    res = api_call({'route': 'buy_shader', 'shader': d.get('shader'),
                    'currency': d.get('currency', 'standard')})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/set_skin', methods=['POST'])
def action_set_skin():
    if r := _req(): return r
    d   = request.get_json()
    res = api_call({'route': 'set_skin', 'name_string': d.get('name_string', '')})
    cache_clear(session['token'])
    return jsonify(res)

@app.route('/action/buy_inv_slots', methods=['POST'])
def action_buy_inv_slots():
    if r := _req(): return r
    res = api_call({'route': 'buy_inv_slots'})
    cache_clear(session['token'])
    return jsonify(res)

# ── Friends actions ───────────────────────────────────────────────────────────
@app.route('/action/send_friend_request', methods=['POST'])
def action_send_friend_request():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route': 'send_friend_request', 'target': d.get('target'),
                              'version': API_VERSION}))

@app.route('/action/cancel_friend_request', methods=['POST'])
def action_cancel_friend_request():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route': 'cancel_friend_request', 'target': d.get('target'),
                              'version': API_VERSION}))

@app.route('/action/remove_friend', methods=['POST'])
def action_remove_friend():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route': 'remove_friend', 'target': d.get('target'),
                              'version': API_VERSION}))

@app.route('/action/block_user', methods=['POST'])
def action_block_user():
    if r := _req(): return r
    d = request.get_json()
    return jsonify(api_call({'route': 'block_user', 'target': d.get('target'),
                              'version': API_VERSION}))

@app.route('/api/get_friend', methods=['GET'])
def api_get_friend():
    if not session.get('token'):
        return jsonify({'error': 'unauthorized'}), 401
    target = request.args.get('target', '')
    return jsonify(api_call({'route': 'get_friend', 'target': target,
                              'version': API_VERSION}))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
