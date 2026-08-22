# 🔥 Weekend at Loki's — Torn City Event Hub (v5.9)
*Hosted by Loki [2356475] for the text-based RPG Torn City*

An all-in-one companion suite custom-tailored for the **Weekend at Loki's** community and faction events:
- 🤖 **Auto-Repo Sync on `/bingo-card` (v5.9)**: When players run `/bingo-card` in Discord, they immediately receive their high-res card image, their board is locked for the session, and their card data is saved and automatically committed to the repository if GitHub token is set!
- 🗂️ **Claimed Cards Ledger & Sequential Raffle Numbers**: Automatic live ledger logging all players who claim cards with sequential Raffle Tickets (`#1`, `#2`, `#3`...).
- 🏎️ **Scheduled 3-Day Races Log**: Persistent logging of all scheduled 3-day tournaments with direct Torn creation links and reminder re-pushes.
- 🔀 **Secret Jumbles**: Jumble answers are strictly hidden from Discord and visible only in the host's private dashboard.
- 🔄 **Cache Refresh & Direct Repo Fetch**: One-click header button that busts browser cache to ensure all players always load the newest version.
- 📱 **Big Bubble Icon Command Center**: Mobile-optimized home screen featuring large touch-friendly action cards.
- 🎟️ **Claimed-Roster Raffle Roller**: Roll raffle winners directly from active Bingo card holders.
- 🚀 **Start New Game Session**: Fresh match reset clearing cards and starting raffle numbers back at #1 while preserving settings and word banks.

---

## 🚀 How `/bingo-card` Works

1. A player in Discord runs `/bingo-card`.
2. The bot generates their deterministic 5x5 board with center "LOKI'S FREE SPACE" and assigns them the next sequential **Raffle Ticket Number** (`#1`, `#2`, `#3`...).
3. The bot sends the player their card image and locks the card to their Discord ID in `session_cards.json` (preventing re-rolls or duplicate cards).
4. If `GITHUB_TOKEN` and `GITHUB_REPO` are configured in `.env`, the bot automatically commits `session_cards.json` to your GitHub Pages repository.
5. In the web dashboard, the player automatically appears in the **Claimed Cards** tab and is entered into the **Raffles** pool!
