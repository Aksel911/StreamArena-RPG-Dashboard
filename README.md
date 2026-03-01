
# StreamArena RPG Dashboard

> **⚔️ A powerful web dashboard for managing your StreamArena RPG account**  
> Inventory, equipment, market, guild, bosses, leaderboard, chat — all in one place.

[![Flask](https://img.shields.io/badge/Flask-2.3+-black?logo=flask)](https://flask.palletsprojects.com/)
[![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![AI Generated](https://img.shields.io/badge/Generated%20by-Claude%204.6%20Sonnet-8A2BE2)](https://anthropic.com)

---

## 📸 Screenshots

| Dashboard | Inventory | Market |
|:---:|:---:|:---:|
| ![Dashboard](https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/git/Dashboard.png) | ![Inventory](https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/git/Inventory.png) | ![Market](https://raw.githubusercontent.com/Aksel911/StreamArena-RPG-Dashboard/refs/heads/main/git/Market.png) |

> *More screenshots coming soon —> run the project to see it in action!*

---

## ✨ Features at a Glance

### 🎮 **Core Game Management**
- **Dashboard** – Character stats, gold/plat/gems, inventory usage, mail preview, daily spin timer, chests, and voucher redeemer
- **Equipment** – View equipped items with power bars, unequip, equip from inventory, total power calculation
- **Inventory** – Paginated view, lock/unlock, destroy, list on market, mass delete unlocked items
- **Cosmetics** – Owned backpacks, skin shop, backpack shop

### 💰 **Economy**
- **Marketplace** – Browse all listings, filter by slot/class, live sorting (power, price, value), buy instantly
- **My Listings** – View your active market listings
- **Game Chests** – See available chests and their costs

### 🏰 **Social & World**
- **Guild** – Guild info, roster (sorted by level), guild chat with message sending, manual guild ID override
- **Leaderboard** – Top 25 players by class, extended rankings, class filtering
- **Bosses & Dungeons** – Active world bosses with HP bars, dungeons, world battles
- **Global Chat** – Read and send messages
- **Mail** – Read in-game mail with unread indicators

### 🛠️ **Technical Highlights**
- **Disk‑based cache** – Stores large user data (~14KB) in `/tmp/streamarena_cache` – bypasses Flask's 4KB cookie limit
- **No JavaScript frameworks** – Pure vanilla JS, minimal dependencies
- **Responsive design** – Works on desktop and mobile (collapsible sidebar)
- **Dark fantasy theme** – Custom CSS with gold accents, power bars, and game‑styled components

---

## 🚀 Quick Start

### Prerequisites
- Python 3.13 or higher
- A [StreamArena RPG](https://streamarenarpg.com) account

### Installation

```bash
# Clone the repository
git clone https://github.com/Aksel911/StreamArena-RPG-Dashboard.git
cd StreamArena-RPG-Dashboard

# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install flask requests

# Run the application
python app.py
```

Open your browser and navigate to `http://127.0.0.1:5000`

---

## 🔑 Authentication & API Version

### Getting Your Token
1. Go to [StreamArena Auth Portal](https://streamarenarpg.com/auth.html)
2. Login with Twitch
3. Copy your `token` 
4. Paste it on the dashboard login page

### ⚠️ **Important: API Version**
The dashboard uses a hardcoded `API_VERSION = '0.32.03'` in `app.py`. If some features stop working, the game API version may have changed.

**To find the current API version:**
1. Open Developer Tools (F12) → Network tab
2. Look for any API request (e.g., `get_chat_messages`, `get_udata`)
3. Check the request payload – it contains the `version` parameter:
```json
{"route":"get_chat_messages","token":"your_token","version":"0.31.05"}
```
4. Update the `API_VERSION` variable in `app.py` to match

---

## 📖 Detailed Feature Tour

### 🏠 Dashboard
Your command center:
- **Currency display** – Gold, Platinum, Gems with formatting
- **Inventory usage** – Visual progress bar showing slot usage
- **Character card** – Level, experience bar, game time, location, skin
- **Guild status** – Quick link to guild page
- **Skills** – Your active skills as badges
- **Mail preview** – Latest 4 messages with unread indicators
- **Daily spin** – Countdown timer to next spin
- **Chests** – Your owned chests
- **Voucher redeemer** – Instant code redemption

### 🎒 Inventory
Full inventory management:
- **Pagination** – Navigate through multiple pages
- **Filter by slot** – Weapon, off-hand, head, body, etc.
- **Sort options** – Power (↑/↓), name (A-Z/Z-A), class
- **Item cards** – Show power percentage with color-coded bar, extra stats, class restrictions
- **Lock/Unlock** – Prevent accidental destruction
- **Destroy** – Single item deletion with confirmation
- **Market listing** – Modal with fee calculator (10% gold fee, platinum converted to gold)
- **Mass delete** – Select multiple unlocked items and delete at once

### ⚔️ Equipment
Visual equipment management:
- **Equipped slots grid** – Each slot shows equipped item (if any) with power bar
- **Empty slots** – Click to equip from inventory
- **Inventory panel** – Click any item to equip (if slot matches) or unequip if already equipped
- **Total power** – Combined power percentage across all slots
- **Character stats** – Level, experience, game time, location
- **Skills display** – Your active skills

### ⚖️ Marketplace
Full market integration:
- **Browse listings** – Paginated view of all listings
- **Advanced filtering** – By slot, class
- **Live sorting** – Power (high/low), gold price (low/high), platinum price, best value (power/price)
- **Your balance** – Displayed at top
- **Buy modal** – Shows your balance vs. item cost, affordability check
- **My listings** – Your active market listings
- **Game chests** – Available chests with costs

### 🏰 Guild
Complete guild management:
- **Guild info** – Name, tag, leader, level, experience, member count, your role, visibility
- **Description** – Displayed if available
- **Roster** – All members sorted by level, with class icons, roles, and locations
- **Guild chat** – Read messages, send new messages
- **Manual override** – If guild ID isn't detected, enter it manually

### 💀 Bosses & Dungeons
Live world events:
- **World bosses** – Current HP, time left, participants, rewards
- **HP bars** – Visual health with color coding (red for alive, gray for dead)
- **Dungeons** – Active dungeons with chest counts and coin costs
- **World battles** – Live boss battles with channel info

### 🏆 Leaderboard
Player rankings:
- **Class filtering** – All, barbarian, tank, rogue, mage, summoner, healer, ranger
- **Top 25** – Detailed table with rank, player, class, level, game time, skin, location
- **Medal icons** – 🥇🥈🥉 for top 3
- **Your highlight** – Your entry is highlighted in gold
- **Extended rankings** – Players #26+ in compact cards

### 💬 Global Chat
Community interaction:
- **Message list** – All global messages with timestamps
- **Sender highlighting** – Devs (🔧) and Streamers (🎥) have distinct colors
- **Send messages** – Input with character limit

### 📜 Mail
In-game mail:
- **Inbox view** – All messages with sender, content, dates
- **Unread indicators** – Gold badge for new messages
- **Expiry dates** – Shown for each message

### ✨ Cosmetics
Visual customization:
- **Owned backpacks** – Your collection with equipped indicator
- **Skin shop** – Available character skins with costs
- **Backpack shop** – Available backpacks with costs

---

## 🏗️ Architecture

### Backend (Flask)
- **Routes** – 20+ endpoints for pages and actions
- **API abstraction** – `api_call()` and `guild_api_call()` handle all requests
- **Disk cache** – User data stored in JSON files, keyed by token hash
- **Session management** – Only token stored in session (not large data)
- **Action endpoints** – JSON endpoints for all game actions (equip, destroy, list, buy, etc.)

### Frontend (Vanilla JS)
- **No frameworks** – Pure JavaScript for all interactions
- **Modals** – For buying, listing, equipping
- **Live sorting** – Client-side sorting on market page
- **Toast notifications** – For action feedback
- **Mass delete** – Checkbox selection with "Select All"
- **Timer updates** – Daily spin countdown updates every second

### Caching Strategy
- **Why disk cache?** – User data (`udata`) is ~14KB, exceeding Flask's 4KB cookie limit
- **How it works** – Data saved to `/tmp/streamarena_cache/[token_hash].json`
- **TTL** – 5 minutes (configurable)
- **Refresh** – Manual refresh button clears cache and fetches fresh data

---

## 🛠️ Configuration

### Environment Variables (Optional)
You can modify these in `app.py`:
```python
CACHE_DIR = '/tmp/streamarena_cache'  # Cache location
CACHE_TTL = 300                        # Cache TTL in seconds
API_VERSION = '0.32.03'                # Game API version
```

### For Production Deployment
1. Change `app.secret_key` to a secure random value
2. Use a proper WSGI server (Gunicorn, Waitress)
3. Set `debug=False`
4. Consider using a permanent cache directory

---

## 🤝 Contributing

Contributions are welcome! Since this project was AI‑generated, there's plenty of room for:
- Bug fixes
- UI/UX improvements
- Additional features
- Performance optimizations
- Documentation

### Development Workflow
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## 🙏 Acknowledgments

- **StreamArena RPG** – For creating an amazing game with a public API
- **Anthropic Claude 3.7 Sonnet** – The AI that wrote 99% of this code
- **Flask community** – For the lightweight yet powerful framework

---

## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This is an **unofficial** third‑party dashboard. It is not affiliated with, endorsed by, or connected to StreamArena RPG or its developers. Use at your own risk.

The dashboard communicates with the official game API using your personal token – treat your token like a password and never share it.

---

**Made with ⚔️ by AI and a little human touch**  
[Report Bug](https://github.com/Akseel911/StreamArena-RPG-Dashboard/issues) · [Request Feature](https://github.com/Aksel911/StreamArena-RPG-Dashboard/issues)
