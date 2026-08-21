# 🎯 Torn City & Discord Suite — Bingo & Race Hub

A comprehensive, all-in-one Discord & Torn City companion suite featuring:
- 🌐 **GitHub Pages Web GUI**: Zero-build static dashboard with dark mode and real-time settings.
- 🎲 **Interactive 5x5 Bingo Card Studio**: Randomized seedable card generator, live card viewer, and PNG image exporter.
- 📢 **Live Bingo Caller & Announcer**: Manual or timed auto-draws broadcasting rich Discord embeds.
- 🏎️ **Torn City Race Radar**: Live race tracking via Torn API + automated Discord race countdown reminders.
- 🤖 **24/7 Companion Discord Bot**: Python (`discord.py`) slash commands (`/bingo card`, `/bingo call`, `/race schedule`, etc.).

---

## 🚀 Quickstart: Deploying the Web GUI to GitHub Pages (2 Minutes)

Because the Web GUI is completely static (HTML5, Tailwind CSS CDN, Lucide Icons, and Vanilla JS), it requires **zero build tools** or servers.

1. **Create a GitHub Repository**:
   - Go to [GitHub](https://github.com) and create a new public repository (e.g. `torn-bingo-hub`).
2. **Upload `index.html`**:
   - Upload the `index.html` file into the root of the repository.
3. **Enable GitHub Pages**:
   - In your repository, go to **Settings** → **Pages**.
   - Under **Build and deployment** > **Source**, choose **Deploy from a branch**.
   - Select Branch: `main` (or `master`) and Folder: `/ (root)`.
   - Click **Save**.
4. **Access your Live Dashboard**:
   - Your Web GUI will be live at `https://<your-username>.github.io/<repo-name>/`.

---

## ⚙️ Configuration & Settings

Open the **Settings & Keys** tab on the Web GUI:
1. **Discord Webhook URL**:
   - In your Discord Server: `Channel Settings` → `Integrations` → `Webhooks` → `New Webhook` → `Copy Webhook URL`.
   - Paste the URL into the **Discord Webhook URL** field.
   - Click **Test Webhook** to verify.
2. **Torn API Key**:
   - In Torn City: `Preferences` → `API Keys` → `Create New Key` (Public or Minimal access is sufficient).
   - Paste into the **Torn API Key** field and click **Verify & Pull Info**.
3. **Storage Security**:
   - All API keys and webhooks are stored strictly in your browser's private `localStorage`.

---

## 🎲 Bingo System Features

- **Word / Item Pool**: Pre-loaded with 30+ classic Torn items (Xanax, Blood Bags, Armored Vests, etc.), or one-click pull live items from the Torn API.
- **5x5 Seeded Cards**: Every card can be generated with a seed (e.g. Player ID or Name) so any card can be reproduced or verified later.
- **Free Space**: Center tile default `FREE SPACE` (or custom faction text).
- **PNG Card Download**: Export high-resolution 800x900 graphic bingo cards for distribution.
- **Discord Post**: Post individual cards directly into Discord channels.
- **Live Caller & Announcer**: Draw words with live history tracking and automatic rich embed broadcasts to Discord.
- **Winning Line Check**: Instant detection of winning lines (rows, columns, diagonals, blackout).

---

## 🏎️ Torn Race Reminders

- **Live Torn Races**: Fetches public & custom races from Torn API endpoint `https://api.torn.com/torn/?selections=races`.
- **One-Click Alerts**: Dispatches rich embeds detailing track name, laps, car class, start time, and ping roles.
- **Custom Race Builder**: Create custom alerts for faction tournaments with passwords, prizes, and specific rules.

---

## 🤖 Running the 24/7 Companion Discord Bot (Optional)

If you wish to have slash commands directly in Discord and background race polling without keeping a browser open:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment variables in .env
DISCORD_TOKEN=your_bot_token_here
TORN_API_KEY=your_torn_api_key_here
DISCORD_WEBHOOK_URL=your_webhook_url_here
RACE_CHANNEL_ID=your_race_channel_id
PING_ROLE_ID=your_ping_role_id

# 3. Run the bot
python bot.py
```

### Slash Commands:
- `/bingo-card [player_name] [seed]` — Generates and uploads a 5x5 card PNG.
- `/bingo-call [announce]` — Draws the next item and posts the embed.
- `/bingo-check [seed]` — Verifies whether a card seed has won.
- `/bingo-history` — Shows all words drawn in the current match.
- `/race-schedule` — Displays upcoming races with countdown timers.
- `/torn-item [item_name]` — Looks up item value and circulation from Torn.
