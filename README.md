# 🎯 Torn City & Discord Suite — Multi-Channel & Word Drops Edition

A comprehensive suite designed for Torn City factions and Discord communities featuring:
- 🌐 **GitHub Pages Web Dashboard**: Zero-build static web interface with instant `localStorage` saving.
- 💥 **Bingo 5-Word Drops**: Draw and broadcast 5 words simultaneously with custom batch Discord embeds.
- 📡 **3-Channel Webhook Routing**: Dedicated endpoints for **#bingo**, **#racing**, and **#raffles**.
- 🎲 **5x5 Seeded Bingo Studio**: Instant card generator with high-resolution PNG exports.
- 🏎️ **Torn Race Radar**: Automated background race countdown alerts pulled from Torn API.
- 🎟️ **Faction Raffles & Giveaways**: Provably fair random winner selection and announcements.
- 🤖 **24/7 Companion Discord Bot**: Python slash commands (`/bingo drop`, `/bingo card`, `/race schedule`, `/raffle roll`).

---

## 🚀 Quickstart: Deploying to GitHub Pages (2 Minutes)

1. Create a GitHub repository (e.g. `torn-community-hub`).
2. Upload `index.html` into the root directory.
3. In GitHub: **Settings** → **Pages** → Source: **Deploy from a branch** (`main` / `/ root`) → **Save**.
4. Access your live GUI at `https://<your-username>.github.io/<repo-name>/`.

---

## ⚙️ 3-Channel Webhook Setup

In Discord, create three webhooks for your desired channels (**Server Settings** → **Integrations** → **Webhooks**):
1. **Bingo Webhook**: Target `#bingo` (receives single calls, **5-Word Drops**, and player cards).
2. **Racing Webhook**: Target `#racing` (receives Torn official races, faction tournaments, and countdowns).
3. **Raffles Webhook**: Target `#raffles` (receives ticket pool openings and winner announcements).

Paste each URL into the **3-Channel Settings** tab in the Web GUI and click **Save All Settings**.

---

## 📦 Bingo "Word Drops" Feature

- Click **💥 DROP 5 BINGO WORDS AT ONCE** in the GUI (or use `/bingo drop 5` in Discord) to release 5 items simultaneously.
- Formats a multi-item batch embed to `#bingo` showing all 5 drawn words, updated call count, and remaining pool size.

---

## 🤖 Running the 24/7 Python Bot

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure .env with your 3 webhooks and tokens
cp .env.example .env
# Edit .env

# 3. Start the bot
python bot.py
```

### Slash Commands:
- `/bingo-drop [count: 5]` — Drops 5 words at once with a formatted embed.
- `/bingo-call` — Draws a single item.
- `/bingo-card [player_name] [seed]` — Generates a high-res 5x5 card PNG.
- `/race-schedule` — Displays upcoming Torn races.
- `/raffle-roll [prize] [entrants]` — Randomly picks winner(s) and posts to `#raffles`.
