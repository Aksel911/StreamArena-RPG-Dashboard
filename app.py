"""
StreamArena RPG — Flask Dashboard
Disk-based udata cache (bypasses 4KB cookie limit)
"""
import os, json, hashlib, requests
from flask import (Flask, render_template, request, session, redirect, url_for, jsonify)
import time

app = Flask(__name__)
app.secret_key = 'streamarena_secret_2026'

API_URL     = 'https://streamarenarpg.com/portal/portal_api.php'
GUILD_API_URL = 'https://streamarenarpg.com/guild/guild_api.php'
API_VERSION = '0.32.03' # Remember to update this as soon as a new version is released.
HEADERS = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Origin': 'https://streamarenarpg.com',
    'Referer': 'https://streamarenarpg.com/portal/app/portal.html',
}

# ── Disk cache (udata is ~14KB — way over Flask's 4KB cookie limit) ───────────
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
        os.remove(p)
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

# ── API helpers ───────────────────────────────────────────────────────────────
def api_call(payload):
    token = session.get('token')
    if not token:
        return {'status':'error','message':'No token'}
    payload['token'] = token
    if 'version' not in payload and payload.get('route') not in NO_VERSION_ROUTES:
        payload['version'] = API_VERSION
    try:
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=15)
        #print(API_URL, payload, HEADERS)
        return r.json()
    except Exception as e:
        return {'status':'error','message':str(e)}
    
    
def guild_api_call(payload):
    token = session.get('token')
    if not token:
        return {'status':'error','message':'No token'}
    payload['token'] = token
    if 'version' not in payload and payload.get('route') not in NO_VERSION_ROUTES:
        payload['version'] = API_VERSION
    try:
        r = requests.post(GUILD_API_URL, json=payload, headers=HEADERS, timeout=15)
        #print(API_URL, payload, HEADERS)
        return r.json()
    except Exception as e:
        return {'status':'error','message':str(e)}

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

def _auth():
    """Redirect to index if not logged in."""
    if not session.get('token'):
        return redirect(url_for('index'))
    return None

# ── Routes ────────────────────────────────────────────────────────────────────
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
                # guild_id is at ROOT of udata response (not inside user{})
                session['guild_id'] = data.get('guild_id')
                return redirect(url_for('dashboard'))
            session.clear()
            return render_template('index.html',
                error='Invalid token or API returned no data.')
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

@app.route('/dashboard')
def dashboard():
    if e := _auth(): return e
    udata       = get_udata()
    mail        = api_call({'route':'get_player_mail'})
    spin        = api_call({'route':'get_next_daily_spin'})
    streamer    = api_call({'route':'is_streamer'})
    consumables = api_call({'route':'get_player_consumables'})
    skills      = api_call({'route':'get_skills'})
    chests      = api_call({'route':'get_player_chests'})
    return render_template('dashboard.html',
        udata=udata, mail=mail, spin=spin, streamer=streamer,
        consumables=consumables, skills=skills, chests=chests,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS)

@app.route('/inventory')
def inventory():
    if e := _auth(): return e
    page  = int(request.args.get('page', 1))
    inv   = api_call({'route':'get_inv','page':page})
    locks = api_call({'route':'get_player_item_locks'})
    gm    = get_game_items_dict()
    locked_ids = {str(x) for x in locks.get('locked_items',[])}
    items = annotate_items(inv.get('player_items',[]), gm)
    my_listings = api_call({'route':'my_listings'})
    for item in items:
        item['is_locked'] = str(item['id']) in locked_ids
    return render_template('inventory.html',
        inv=inv, items=items, page=page,
        locked_ids=locked_ids, slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS, my_listings=my_listings)

@app.route('/equipment')
def equipment():
    if e := _auth(): return e
    udata  = get_udata()
    skills = api_call({'route':'get_skills'})
    gm     = get_game_items_dict()

    char         = udata.get('characters',[{}])[0] if udata.get('characters') else {}
    player_items = {str(i['id']): i for i in udata.get('player_items',[])}
    all_inv      = annotate_items(list(udata.get('player_items',[])), gm)

    slot_map = {
        'head_equip':'head','body_equip':'body','hands_equip':'hands',
        'feet_equip':'feet','weapon_equip':'weapon','offhand_equip':'off_hand',
        'ring_equip':'ring','neck_equip':'neck',
    }
    equipped = {}
    for key, slot in slot_map.items():
        iid = str(char.get(key,'-1'))
        if iid not in ('-1','') and iid in player_items:
            item = dict(player_items[iid])
            gi   = gm.get(slot,{}).get(str(item.get('base_item_id','0')))
            item['item_name']    = gi['item_name'] if gi else f'{slot.title()} #{item.get("base_item_id","?")}'
            item['extra_parsed'] = json.loads(item['extra']) if item.get('extra') else {}
            equipped[slot] = item
        else:
            equipped[slot] = None

    equipped_ids = {str(char.get(k,'-1')) for k in slot_map} - {'-1',''}

    return render_template('equipment.html',
        character=char, equipped=equipped, all_inv=all_inv,
        equipped_ids=equipped_ids, skills=skills,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS)

@app.route('/market')
def market():
    if e := _auth(): return e
    slot_filter  = request.args.get('slot','any')
    class_filter = request.args.get('class_flag','any')
    page         = int(request.args.get('page',1))

    listings    = api_call({'route':'get_listings','slot':slot_filter,'class':class_filter,'page':page})
    my_listings = api_call({'route':'my_listings'})
    game_chests = api_call({'route':'get_chests'})
    gm          = get_game_items_dict()
    annotate_items(listings.get('listings',[]), gm)
    annotate_items(my_listings.get('listings',[]), gm)

    # get_inv always returns fresh user with gold/platinum/gems
    inv_data = api_call({'route':'get_inv','page':1})
    user     = inv_data.get('user',{})
    return render_template('market.html',
        listings=listings, my_listings=my_listings, game_chests=game_chests,
        slot_filter=slot_filter, class_filter=class_filter, page=page,
        slot_icons=SLOT_ICONS, class_icons=CLASS_ICONS,
        player_gold=int(user.get('gold',0)),
        player_plat=int(user.get('platinum',0)),
        player_gems=int(user.get('gems',0)))

@app.route('/guild')
def guild():
    if e := _auth(): return e
    udata    = get_udata()
    # guild_id is at ROOT level of get_udata response
    guild_id = udata.get('guild_id')
    try:
        guild_id = int(guild_id) if guild_id else None
    except (TypeError, ValueError):
        guild_id = None
    # Fallback: manually set via form
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

    guild_info = guild_api_call({'guild_id':guild_id,'route':'guild_info'})
    roster     = guild_api_call({'guild_id':guild_id,'route':'guild_roster'})
    messages   = guild_api_call({'route':'get_guild_messages'})
    
    return render_template('guild.html',
        guild_info=guild_info, roster=roster, messages=messages,
        guild_id=guild_id, class_icons=CLASS_ICONS, error=None)

@app.route('/guild/set_id', methods=['POST'])
def guild_set_id():
    if e := _auth(): return e
    try:
        session['guild_id'] = int(request.form.get('guild_id',0))
    except (ValueError, TypeError):
        pass
    return redirect(url_for('guild'))

@app.route('/cosmetics')
def cosmetics():
    if e := _auth(): return e
    shaders = api_call({'route':'get_shaders'})
    backs   = api_call({'route':'get_backs'})

    # Build lookups
    shaders_by_id = {str(s['id']): s for s in shaders.get('shaders',[])}
    backs_by_id   = {str(b['id']): b for b in backs.get('back_items',[])}

    # Owned cosmetics from udata.user.cosmetics
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
            # Not in shop but user owns it
            owned_backs.append({'id':bid,'display_name':f'Back Item #{bid}',
                                 'platinum_cost':'0','gold_cost':'0','gem_cost':'0'})

    equipped_back_id = str(char.get('back_equip','-1'))
    return render_template('cosmetics.html',
        shaders=shaders, backs=backs,
        owned_backs=owned_backs,
        equipped_back_id=equipped_back_id,
        shaders_by_id=shaders_by_id,
        backs_by_id=backs_by_id)

@app.route('/bosses')
def bosses():
    if e := _auth(): return e
    return render_template('bosses.html',
        bosses_data = api_call({'route':'get_active_world_bosses'}),
        battles     = api_call({'route':'get_current_world_battles'}),
        dungeons    = api_call({'route':'get_active_dungeons'}))

@app.route('/leaderboard')
def leaderboard():
    if e := _auth(): return e
    class_flag = request.args.get('class_flag','all')
    top = api_call({'class_flag':class_flag,'route':'get_top_players'})
    return render_template('leaderboard.html',
        top=top, class_flag=class_flag, class_icons=CLASS_ICONS)

@app.route('/chat')
def chat():
    if e := _auth(): return e
    return render_template('chat.html',
        messages=api_call({'route':'get_chat_messages'}))

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
    # Проверка авторизации (используйте вашу существующую функцию _auth)
    if e := _auth():
        return e

    data = request.get_json()
    item_ids = data.get('item_ids', [])
    if not item_ids:
        return jsonify({'status': 'error', 'message': 'No item IDs provided'})

    success_count = 0
    errors = []

    for item_id in item_ids:
        # Вызов API для удаления одного предмета (аналогично /action/destroy)
        res = api_call({'item_id': item_id, 'route': 'destroy'})
        if res.get('status') == 'success':
            success_count += 1
        else:
            errors.append({'id': item_id, 'error': res.get('message', 'Unknown error')})

    if success_count == len(item_ids):
        return jsonify({'status': 'success', 'deleted_count': success_count})
    elif success_count > 0:
        return jsonify({'status': 'partial', 'deleted_count': success_count, 'errors': errors})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to delete any items', 'errors': errors})



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
    return jsonify(api_call({'route':'send_guild_message','message':d.get('message','')}))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
