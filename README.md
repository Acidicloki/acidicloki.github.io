# 🎯 Torn City & Discord Suite — v5.0 Mobile & 3-Day Racing Edition

An all-in-one suite designed for Torn City factions featuring:
- 📱 **Mobile-Optimized Torn.com Charcoal Theme**: High-contrast grey/dark palette with **Impact** header typography.
- 📢 **#announcements Webhook & 🎉 Reaction Roster**: Date & time setter, event builder, and automatic player registration from Discord emoji reactions.
- 🔒 **1-Card-Per-Player Session Enforcement**: Anti-cheat card locker preventing duplicate card creation per session.
- 🏎️ **3-Day Race Scheduler**: 25 Laps, Stock Class E cars, randomized tracks, and instant Discord push.
- 💥 **5-Word Drops & Standalone Jumbles**: Releases 5 words with an embedded anagram challenge or standalone puzzle.
- 🏆 **Winner & Payout Hub**: Categorized prize selector (Boosters, Supply Packs, Xanax, Cash) with quantities and payment transfer links.
- 💾 **Full JSON Settings Sync**: Exports and imports all 4 Webhook URLs, keys, word banks, and registered session rosters.

---

## 🚀 Quickstart

1. Upload `index.html` into your GitHub repository root.
2. Enable GitHub Pages (**Settings** → **Pages** → **Deploy from branch** `main`).
3. Set your 4 Webhooks in the **Settings** tab:
   - `#announcements` Webhook (for event notices & 🎉 reactions)
   - `#bingo` Webhook (for single calls, 5-Word Drops, and Jumbles)
   - `#racing` Webhook (for 3-Day tournaments and live race radar)
   - `#raffles` Webhook (for giveaways and ticket rolls)

---

## 🤖 Discord Bot Commands

```bash
pip install -r requirements.txt
python bot.py
```

### Slash Commands:
- `/announce [title] [date_time] [prize] [details]` — Posts an event announcement with a 🎉 reaction prompt.
- `/bingo-card` — Generates (or retrieves) the user's locked session Bingo Card.
- `/race-schedule-3day [start_date]` — Generates a 3-Day Stock Class E, 25-Lap tournament schedule with random tracks.
- `/bingo-drop [count: 5]` — Drops 5 words with an anagram challenge.
- `/bingo-jumble` — Standalone mystery word jumble challenge.
- `/race-winner [event] [winner] [prize]` — Logs and broadcasts event victory.
- `/payout [winner] [prize] [event]` — Posts payment confirmation.
