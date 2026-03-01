"""
StreamArena RPG — Flask Dashboard
Disk-based udata cache (bypasses 4KB cookie limit)
"""
import os, json, hashlib, time, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import (Flask, render_template, request, session,
                   redirect, url_for, jsonify)

app = Flask(__name__)
app.secret_key = 'streamarena_secret_2026'

API_URL       = 'https://streamarenarpg.com/portal/portal_api.php'
GUILD_API_URL = 'https://streamarenarpg.com/guild/guild_api.php'
API_VERSION   = '0.32.03'  # Update when game updates

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
CACHE_TTL = 300  # 5 minutes
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
    'barbarian':'🪓','Barbarian':'🪓','tank':'🛡️','rogue':'🗡️',
    'mage':'🔮','summoner':'👁️','healer':'✨','ranger':'🏹',
}
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

    return render_template('dashboard.html',
        udata=udata, guild_name=guild_name,
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

    return render_template('inventory.html',
        inv=inv, items=items, page=page,
        locked_ids=locked_ids, listed_ids=listed_ids, equipped_ids=equipped_ids,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS,
        my_listings=my_listings)

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
        player_gems=int(user.get('gems',0)))

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
    })
    shaders      = results['shaders']
    backs        = results['backs']
    consumables  = results['consumables']

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
        backs_by_id=backs_by_id)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
