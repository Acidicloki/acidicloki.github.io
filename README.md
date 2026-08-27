# 🔥 Weekend at Loki's — Torn City Event Hub (v7.1)
*Hosted by Loki [2356475] for the text-based RPG Torn City*

An all-in-one companion suite custom-tailored for the **Weekend at Loki's (W@L)** community and faction events:
- 📁 **Directory-Anchored Storage (v7.1)**: Bot storage paths are explicitly anchored to the bot's root directory (`os.path.dirname(__file__)`).
- 🔄 **In-Memory Cache Purge (`/bingo-reload-disk` / `/bingo-new-game`)**: Resetting a match or running `/bingo-reload-disk` wipes in-memory Python dictionaries and synchronizes with disk.
- 🧹 **WALL-E Auto-Reset on New Session**: When "Start New Game" is clicked on the website, the webhook push alert automatically triggers WALL-E the bot to wipe `session_cards.json = {}` locally and commit the clean reset directly to your GitHub repository.
- 🌐 **GitHub Repo Sync & Diagnostics (`/bingo-push-repo`)**: Automatic and manual commit of `session_cards.json` directly to your GitHub repository with live status and diagnostic reports in Discord.
- 🗂️ **Claimed Cards Sync (`/bingo-sync-export` / `/bingo-card-export`)**: Instant JSON export command and web dashboard file loader/paste tool.
- 🤖 **WALL-E Themed Bot & App Banner**: High-resolution custom graphic banner featuring Disney's WALL-E with the bold **`W@L`** logo (`assets/wall_e_banner.png`).
- 🎟️ **Claimed Cards Ledger & Sequential Raffle Numbers**: Automatic live ledger logging all players who claim cards with sequential Raffle Tickets (`#1`, `#2`, `#3`...).
- 🏎️ **Scheduled 3-Day Races Log**: Persistent logging of all scheduled 3-day tournaments with direct Torn creation links and reminder re-pushes.
- 🔀 **Secret Jumbles**: Jumble answers are strictly hidden from Discord and visible only in the host's private dashboard.
- 🔄 **Cache Refresh & Direct Repo Fetch**: One-click header button that busts browser cache to ensure all players always load the newest version.
- 📱 **Big Bubble Icon Command Center**: Mobile-optimized home screen featuring large touch-friendly action cards.
