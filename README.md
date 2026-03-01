<div align="center">

<img src="https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/static/favicon/android-chrome-512x512.png" alt="StreamArena RPG Dashboard" width="80%">

<br><br>

# ⚔️ StreamArena RPG — Portal Dashboard

**Unofficial web dashboard for full account management of StreamArena RPG**

[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)
[![Made with Claude](https://img.shields.io/badge/Made%20with-Claude%20Sonnet%204.6-8B5CF6)](https://anthropic.com)

*Inventory · Equipment · Market · Guild · Bosses · Leaderboard · Chat — all in one place*

</div>

---

## 📸 Screenshots

| Dashboard | Inventory | Market |
|:---:|:---:|:---:|
| ![Dashboard](https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/git/Dashboard.png) | ![Inventory](https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/git/Inventory.png) | ![Market](https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/git/Market.png) |

---

## 🚀 Quick Start

### Requirements
- Python **3.13+**
- A [StreamArena RPG](https://streamarenarpg.com) account

### Install & Run

```bash
git clone https://github.com/Aksel911/StreamArena-RPG-Dashboard.git
cd StreamArena-RPG-Dashboard

# Optional but recommended: virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows

pip install flask requests
python app.py
```

Open **http://127.0.0.1:5000** in your browser, paste your token, done.

---

## 🔑 Getting Your Token

1. Go to [StreamArena Auth Portal](https://streamarenarpg.com/auth.html)
2. Login with Twitch
3. Copy your `token` 
4. Paste it on the dashboard login page

> ⚠️ **Your token grants full account access. Never share it.**

---

## ✨ Full Feature List

### 🏠 Dashboard
Your account command center — everything at a glance.

- 💰 **Currency bar** — Gold, Platinum, Gems with thousands formatting
- 🎒 **Inventory meter** — visual progress bar, turns orange at 75%, red at 90%
- 🧝 **Character card** — class, level, XP progress bar, game time, location, skin
- 🏰 **Guild widget** — shows **Guild Name** + ID with a quick link
- 📜 **Skills** — active skills displayed as badges
- 🧪 **Consumables** — all potions, orbs and summons with quantities
- 📬 **Mail preview** — latest 4 messages, unread highlighted
- 🎡 **Daily spin timer** — live countdown to next available spin
- 📦 **Chests** — your owned chests with gem costs
- 🎫 **Voucher redeemer** — instant code redemption field

---

### 🎒 Inventory
Full paginated inventory with powerful client-side filtering — no page reloads.

| Control | Description |
|---|---|
| **Slot tabs** | All · Weapon · Off-hand · Head · Body · Hands · Feet · Ring · Neck |
| **Sort** | ✨ Power ↓↑ · 📛 Name A-Z / Z-A |
| **Class dropdown** | Dynamically built from your actual inventory |
| **🔍 Search** | Instant filter by item name |
| **🟢 Show Equipped** | Hidden by default — equipped items show green border + 🟢 tag |
| **💰 Show Listed** | Hidden by default — market-listed items show 💰 tag, no delete button |
| **Lock / Unlock** | Prevent accidental deletion (locked items are excluded from mass delete) |
| **Destroy** | Single item with confirmation |
| **Market listing** | Modal with live fee calculator (10% gold fee + plat × 100,000 gold) |
| **Mass delete** | Checkbox multi-select + Select All (visible, unlocked, unlisted only) |

---

### ⚔️ Equipment
Visual equipment management with full inventory panel.

- **8-slot grid** — Weapon, Off-hand, Head, Body, Hands, Feet, Ring, Neck
- **Power bars** — per slot with correct labels: Damage / Armor / HP / Attack Speed / Move Speed / Bonus
- **Color-coded power** — teal → gold → orange → red by percentage
- **Total power** — combined % across all 8 slots + average per slot
- **Unequip** — one click from the slot card
- **Inventory panel** — sort by ✨ Power ↓↑ / 📛 Name A-Z/Z-A + 🔍 search
- **Equip modal** — slot selector pre-filled based on item type

---

### ⚖️ Market
Full marketplace integration.

- **Browse listings** — filter by slot and class
- **Live sort** — Power ↑↓, Gold price low→high, Platinum price, Best value (power/gold)
- **Balance bar** — live Gold / Platinum / Gems fetched fresh from `get_inv`
- **Buy modal** — shows affordability before confirming purchase
- **My Listings** — your active market listings panel
- **Game Chests** — available chests with costs

---

### 🏰 Guild
Complete guild management.

- **Guild info** — name, tag, leader, level, XP, member/elder count, your role, visibility
- **Description** — displayed if set
- **Roster** — all members sorted by level, class icons, role badges (👑 leader / 🌟 elder / ⚔️ member), location
- **Your entry** highlighted in gold
- **Guild Chat** — **live auto-refresh every 15 seconds** with Pause/Resume toggle
- **Send messages** — no page reload, your message appears immediately
- **Manual Guild ID** — if auto-detection fails, enter it manually via form

---

### 💀 Bosses & Dungeons
Live world event tracker.

- **World Bosses** — mob name, level, HP bar with %, time remaining, reward badges, participant count
- **HP color** — red for alive, grey for defeated
- **Active Dungeons** — chest count, streamer coin cost
- **World Battles** — live boss battles with channel info and participant count

---

### 🏆 Leaderboard
Player rankings across all classes.

- **Top 25** — rank medal (🥇🥈🥉), player, class, level, game time, skin, location
- **Class filter** — all / barbarian / tank / rogue / mage / summoner / healer / ranger
- **Extended rankings** — players #26+ in compact card grid
- **Your entry** highlighted in gold

---

### 💬 Global Chat
Community chat with live updates.

- Sender role styling: Dev 🔧 · Streamer 🎥 · Player ⚔️
- **Live polling every 15s** — appends only new messages, no full reload
- **Pause / Resume** toggle
- Send messages — your own appears immediately after send
- Max 200 characters enforced

---

### ✨ Cosmetics
Visual customization with tabbed layout.

| Tab | Contents |
|---|---|
| 🎒 **Backpacks** | Owned cosmetics with EQUIPPED badge; backpack shop with prices |
| 🎨 **Skins Shop** | All available character shaders (name_string + costs) |
| 🧪 **Consumables** | Full equip/unequip system for 3 consumable slots |

#### Consumables Equip System
- **3 equipment slots** shown at the top — see what's equipped at a glance
- **Equip →** button on each consumable card opens a slot picker modal
- **Occupied slots** shown with ⚠️ warning — selecting replaces the existing consumable
- **Unequip** directly from the slot card or from the consumable card
- Supports all consumable types: potions, resurrection orbs, summons

---

### 📬 Mail
Full in-game inbox.

- Sender, message, received date, expiry date
- **NEW** badge for unread messages
- System messages marked with ⚙️

---

## 🏗️ Technical Architecture

### Why disk-based cache?

Flask sessions use signed cookies — **4 KB limit**. The `get_udata` API response is **~14 KB**. Storing it in a cookie silently truncates the data, causing all pages to show empty data with no error message.

**Solution:** Full user data is saved to `/tmp/streamarena_cache/[sha256_of_token].json` with a 5-minute TTL. Only the token (~100 bytes) lives in the cookie. Cache is cleared automatically after equip/unequip/buy actions.

### Parallel API calls (ThreadPoolExecutor)

Pages that require multiple API calls run them concurrently:

| Page | Calls | Sequential | Parallel |
|---|---|---|---|
| Dashboard | 6 | ~4,000ms | ~700ms |
| Market | 4 | ~2,800ms | ~700ms |
| Guild | 3 | ~2,100ms | ~700ms |
| Bosses | 3 | ~2,100ms | ~700ms |

> Flask's `session` is a thread-local proxy — it cannot be accessed inside worker threads. The token is extracted **before** spawning threads and passed as an explicit argument. This is the correct, safe pattern.

### Shared `requests.Session()`

A single `requests.Session` object reuses TCP connections across all API calls, reducing per-request overhead by ~30%.

### Live polling (Chat & Guild Chat)

Both chat pages fetch `/api/chat_messages` or `/api/guild_messages` every 15 seconds, track seen message IDs in a `Set`, and append only new DOM elements. Zero full-page reloads.

---

## 📁 Project Structure

```
StreamArena-RPG-Dashboard/
├── app.py                   ← All routes, API client, cache, parallel calls
├── README.md
└── templates/
    ├── base.html            ← Sidebar, global CSS, JS helpers (toast, apiAction)
    ├── index.html           ← Login page (standalone)
    ├── dashboard.html       ← Account overview
    ├── inventory.html       ← Paginated inventory with full filter suite
    ├── equipment.html       ← Equipment slots + sortable inventory panel
    ├── market.html          ← Marketplace
    ├── guild.html           ← Guild info + roster + live chat
    ├── cosmetics.html       ← Backpacks / Skins / Consumables (tabbed)
    ├── bosses.html          ← World bosses + dungeons + battles
    ├── leaderboard.html     ← Player rankings
    ├── chat.html            ← Global chat with live polling
    └── mail.html            ← In-game inbox
```

---

## ⚙️ Configuration

Everything is at the top of `app.py`:

```python
CACHE_TTL      = 300                      # Seconds before udata cache expires (5 min)
CACHE_DIR      = '/tmp/streamarena_cache' # Cache directory — change for production
app.secret_key = 'streamarena_secret_2026' # Change to a random string in production!
```

### Updating the API Version

If some features stop working after a game update:
1. Open **DevTools → Network → any request to `portal_api.php`**
2. Find the `version` field in the request payload
3. Update `API_VERSION` in `app.py`

### Production Deployment

```bash
pip install gunicorn           # or: pip install waitress  (Windows)
gunicorn -w 4 app:app          # Linux/macOS
waitress-serve --port=5000 app:app  # Windows
```

Checklist:
- [ ] Set `debug=False` in `app.py`
- [ ] Change `app.secret_key` to a long random string
- [ ] Move `CACHE_DIR` outside `/tmp` (lost on reboot)
- [ ] Use HTTPS if exposing to the internet

---

## 🤝 Contributing

Contributions are welcome! The codebase is intentionally simple — one `app.py` + Jinja2 templates, zero JS frameworks, zero build steps.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes
4. Open a pull request

Areas that could use improvement:
- Cancel market listings (API likely has a `cancel_listing` route)
- Friends page (`get_friend_list` API exists)
- Consumable usage in battle context
- Mobile layout refinements

---

## ⚠️ Disclaimer

This is an **unofficial** third-party tool, not affiliated with or endorsed by StreamArena RPG or its developers.

The dashboard communicates with the official game API using your personal token. Use at your own risk and **never share your token**.

---

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.

---

<div align="center">

**Made with ⚔️ by [Aksel911](https://github.com/Aksel911) & Claude Sonnet 4.6**

[🐛 Report a Bug](https://github.com/Aksel911/StreamArena-RPG-Dashboard/issues) · [✨ Request a Feature](https://github.com/Aksel911/StreamArena-RPG-Dashboard/issues) · [⭐ Star the Repo](https://github.com/Aksel911/StreamArena-RPG-Dashboard)

</div>
