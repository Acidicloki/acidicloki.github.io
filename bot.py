#!/usr/bin/env python3
"""
Torn City & Discord Suite - 24/7 Companion Bot
Features:
 - Interactive /bingo card generator (renders 5x5 PNG image attachments)
 - /bingo call, check, history, reset game state manager
 - /race schedule & automated background race reminders via Torn API
 - /torn item & faction lookups
 - Compatible with GitHub Pages Web GUI config.json
"""

import os
import io
import json
import random
import hashlib
import logging
from datetime import datetime, timezone
import aiohttp
from PIL import Image, ImageDraw, ImageFont
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
TORN_API_KEY = os.getenv("TORN_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
BINGO_CHANNEL_ID = int(os.getenv("BINGO_CHANNEL_ID", "0"))
RACE_CHANNEL_ID = int(os.getenv("RACE_CHANNEL_ID", "0"))
PING_ROLE_ID = os.getenv("PING_ROLE_ID", "")

# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TornSuiteBot")

# Default Torn Word Pool
DEFAULT_TORN_ITEMS = [
    "Xanax", "Vicodin", "Ecstasy", "Speed", "Opium",
    "Blood Bag : A+", "Blood Bag : O-", "Blood Bag : AB+", "Empty Blood Bag",
    "Armored Vest", "Liquid Body Armor", "Combat Helmet",
    "Diamond Bladed Knife", "Dual Bushmasters", "Armalite M-15A4", "RPG Launcher",
    "Box of Medical Supplies", "First Aid Kit", "Morphine",
    "Can of Red Cow", "Can of Rockstar", "Can of Munster",
    "Donator Pack", "Point", "Lottery Voucher", "Lawyer Business Card",
    "Feathery Hotel Coupon", "Six-Pack of Alcohol", "Bottle of Beer", "Box of Grenades"
]

CONFIG_FILE = "config.json"
STATE_FILE = "bingo_state.json"

class BingoManager:
    def __init__(self):
        self.word_pool = list(DEFAULT_TORN_ITEMS)
        self.drawn_words = []
        self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.drawn_words = data.get("drawn_words", [])
                    if "word_pool" in data and len(data["word_pool"]) >= 24:
                        self.word_pool = data["word_pool"]
            except Exception as e:
                logger.error(f"Error loading state: {e}")

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({
                    "drawn_words": self.drawn_words,
                    "word_pool": self.word_pool
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def reset_game(self):
        self.drawn_words = []
        self.save_state()

    def draw_next(self):
        remaining = [w for w in self.word_pool if w not in self.drawn_words]
        if not remaining:
            return None
        drawn = random.choice(remaining)
        self.drawn_words.append(drawn)
        self.save_state()
        return drawn

    def get_card_cells(self, seed_str: str, free_space: str = "FREE SPACE"):
        # Deterministic shuffle using hash
        h = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(h)
        shuffled = list(self.word_pool)
        rng.shuffle(shuffled)
        selected = shuffled[:24]

        cells = []
        idx = 0
        for i in range(25):
            if i == 12:
                cells.append({"text": free_space, "is_free": True, "index": i})
            else:
                cells.append({"text": selected[idx], "is_free": False, "index": i})
                idx += 1
        return cells

    def check_win(self, seed_str: str):
        cells = self.get_card_cells(seed_str)
        marked_indices = set()
        marked_indices.add(12) # Free space
        for i, c in enumerate(cells):
            if c["text"] in self.drawn_words:
                marked_indices.add(i)

        winning_lines = [
            # Rows
            [0,1,2,3,4], [5,6,7,8,9], [10,11,12,13,14], [15,16,17,18,19], [20,21,22,23,24],
            # Columns
            [0,5,10,15,20], [1,6,11,16,21], [2,7,12,17,22], [3,8,13,18,23], [4,9,14,19,24],
            # Diagonals
            [0,6,12,18,24], [4,8,12,16,20]
        ]
        completed_lines = [line for line in winning_lines if all(pos in marked_indices for pos in line)]
        return len(completed_lines) > 0, len(completed_lines), len(marked_indices)


def render_bingo_card_image(title: str, player_name: str, seed: str, cells: list) -> io.BytesIO:
    """Renders a high-res 800x900 Bingo Card PNG."""
    width, height = 800, 900
    img = Image.new("RGB", (width, height), color="#12141a")
    draw = ImageDraw.Draw(img)

    # Header Card Background
    draw.rectangle([40, 40, 760, 140], fill="#1a1d26", outline="#2a2f3d", width=2)

    # Simple cross-platform fonts
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        meta_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        letter_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        cell_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        cell_font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()
        letter_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()
        cell_font_bold = ImageFont.load_default()

    # Draw Title & Player Meta
    draw.text((400, 65), title, fill="#ffffff", font=title_font, anchor="mm")
    draw.text((400, 105), f"Player: {player_name}  |  Seed: {seed}", fill="#94a3b8", font=meta_font, anchor="mm")

    # B-I-N-G-O Letters
    letters = ["B", "I", "N", "G", "O"]
    cell_w, cell_h = 138, 132
    start_x, start_y = 55, 160

    for col in range(5):
        x = start_x + col * cell_w
        draw.rectangle([x, start_y, x + cell_w - 6, start_y + 40], fill="#3b82f6")
        draw.text((x + (cell_w - 6) / 2, start_y + 20), letters[col], fill="#ffffff", font=letter_font, anchor="mm")

    # Grid Cells
    grid_y = start_y + 50
    for idx, cell in enumerate(cells):
        row = idx // 5
        col = idx % 5
        x = start_x + col * cell_w
        y = grid_y + row * cell_h
        w, h = cell_w - 6, cell_h - 6

        bg_color = "#2d2416" if cell["is_free"] else "#1e222d"
        border_color = "#f59e0b" if cell["is_free"] else "#2a2f3d"
        text_color = "#f59e0b" if cell["is_free"] else "#e2e8f0"

        draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=border_color, width=2 if cell["is_free"] else 1)

        # Word wrap text into cell
        words = cell["text"].split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= 15:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        line_h = 16
        total_text_h = len(lines) * line_h
        text_start_y = y + (h - total_text_h) / 2 + 8

        f = cell_font_bold if cell["is_free"] else cell_font
        for i_line, line in enumerate(lines):
            draw.text((x + w / 2, text_start_y + i_line * line_h), line, fill=text_color, font=f, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


class TornSuiteClient(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.bingo = BingoManager()
        self.notified_races = set()

    async def setup_hook(self):
        # Sync slash commands
        await self.tree.sync()
        self.race_reminder_task.start()
        logger.info("Slash commands synchronized and race reminder background task started.")

    async def close(self):
        self.race_reminder_task.cancel()
        await super().close()

    @tasks.loop(minutes=5.0)
    async def race_reminder_task(self):
        """Background poller checking Torn Races and dispatching alerts."""
        if not TORN_API_KEY:
            return

        try:
            url = f"https://api.torn.com/torn/?selections=races&key={TORN_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        races = data.get("races", {})
                        now_ts = datetime.now(timezone.utc).timestamp()

                        for race_id, race in races.items():
                            start_ts = race.get("time_start", 0)
                            diff_min = (start_ts - now_ts) / 60

                            # Trigger reminder if race is starting within 15 minutes and hasn't been notified yet
                            if 0 < diff_min <= 15 and race_id not in self.notified_races:
                                self.notified_races.add(race_id)
                                await self.broadcast_race_alert(race, int(diff_min))
        except Exception as e:
            logger.error(f"Race reminder loop error: {e}")

    @race_reminder_task.before_loop
    async def before_race_reminder_task(self):
        await self.wait_until_ready()

    async def broadcast_race_alert(self, race: dict, minutes_left: int):
        channel = self.get_channel(RACE_CHANNEL_ID) if RACE_CHANNEL_ID else None
        role_mention = f"<@&{PING_ROLE_ID}> " if PING_ROLE_ID else ""

        embed = discord.Embed(
            title=f"🏁 Upcoming Race: {race.get('title', 'Torn City Race')}",
            description=f"{role_mention}Race starts in approximately **{minutes_left} minutes**! Ensure your car is ready.",
            color=0xe53e3e,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="🛣️ Track", value=race.get("track_name", "Standard"), inline=True)
        embed.add_field(name="🏎️ Car Class", value=race.get("car_class", "All"), inline=True)
        embed.add_field(name="🔄 Laps", value=f"{race.get('laps', 100)} Laps", inline=True)
        embed.add_field(name="👥 Enrolled", value=f"{race.get('enrolled', 0)} / {race.get('max_drivers', 100)}", inline=True)
        embed.set_footer(text="Torn Racing Alerts")

        if channel:
            await channel.send(content=role_mention if role_mention else None, embed=embed)
        elif DISCORD_WEBHOOK_URL:
            # Fallback to Webhook
            async with aiohttp.ClientSession() as session:
                await session.post(DISCORD_WEBHOOK_URL, json={
                    "content": role_mention if role_mention else None,
                    "embeds": [embed.to_dict()]
                })


bot = TornSuiteClient()


# ================= SLASH COMMANDS =================

@bot.tree.command(name="bingo-card", description="Generate your personal 5x5 Torn Bingo Card image")
@app_commands.describe(
    player_name="Your Torn player name or handle",
    seed="Custom seed to generate or reproduce a specific card"
)
async def cmd_bingo_card(interaction: discord.Interaction, player_name: str = None, seed: str = None):
    await interaction.response.defer()
    p_name = player_name or interaction.user.display_name
    card_seed = seed or f"{p_name}-{datetime.now().strftime('%Y%m%d')}"

    cells = bot.bingo.get_card_cells(card_seed)
    image_buf = render_bingo_card_image("TORN FACTION BINGO", p_name, card_seed, cells)

    file = discord.File(image_buf, filename=f"bingo_{card_seed}.png")
    embed = discord.Embed(
        title=f"🎯 Bingo Card for {p_name}",
        description=f"**Card Seed:** `{card_seed}`\nKeep this seed to verify your winning lines or load in the GitHub Pages GUI!",
        color=0x3b82f6
    )
    embed.set_image(url=f"attachment://bingo_{card_seed}.png")
    embed.set_footer(text="Torn & Discord Bingo Suite")
    await interaction.followup.send(embed=embed, file=file)


@bot.tree.command(name="bingo-call", description="Draw the next Bingo word/item and announce it")
@app_commands.describe(announce="Post the drawn word to the channel")
async def cmd_bingo_call(interaction: discord.Interaction, announce: bool = True):
    drawn = bot.bingo.draw_next()
    if not drawn:
        await interaction.response.send_message("❌ All words in the pool have already been drawn!", ephemeral=True)
        return

    call_num = len(bot.bingo.drawn_words)
    total_pool = len(bot.bingo.word_pool)

    embed = discord.Embed(
        title=f"📢 BINGO DRAW #{call_num}: **{drawn}**",
        description=f"Check your 5x5 cards for **{drawn}**!",
        color=0xf59e0b,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📊 Progress", value=f"{call_num} / {total_pool} items called", inline=True)
    embed.add_field(name="📜 Recent Calls", value=" • ".join(bot.bingo.drawn_words[-5:]) or drawn, inline=False)
    embed.set_footer(text="Torn Bingo Live Announcer")

    role_mention = f"<@&{PING_ROLE_ID}> " if PING_ROLE_ID else ""
    await interaction.response.send_message(content=role_mention if announce else None, embed=embed)


@bot.tree.command(name="bingo-check", description="Verify if a card seed has won Bingo")
@app_commands.describe(seed="The card seed identifier to verify")
async def cmd_bingo_check(interaction: discord.Interaction, seed: str):
    has_win, line_count, marked_count = bot.bingo.check_win(seed)
    status_text = "🎉 **BINGO! WINNER CONFIRMED!**" if has_win else "⏳ No completed lines yet."

    embed = discord.Embed(
        title=f"🔍 Bingo Card Verification: `{seed}`",
        description=status_text,
        color=0x10b981 if has_win else 0x64748b
    )
    embed.add_field(name="Completed Lines", value=str(line_count), inline=True)
    embed.add_field(name="Marked Squares", value=f"{marked_count} / 25", inline=True)
    embed.add_field(name="Total Calls in Game", value=str(len(bot.bingo.drawn_words)), inline=True)
    embed.set_footer(text="Official Verification Engine")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="bingo-history", description="List all words drawn in the current game")
async def cmd_bingo_history(interaction: discord.Interaction):
    if not bot.bingo.drawn_words:
        await interaction.response.send_message("No words have been drawn yet in this game.", ephemeral=True)
        return

    history_str = "\n".join([f"**#{i+1}:** {w}" for i, w in enumerate(bot.bingo.drawn_words)])
    if len(history_str) > 3800:
        history_str = history_str[:3800] + "\n... (truncated)"

    embed = discord.Embed(
        title=f"📜 Bingo Drawn Words History ({len(bot.bingo.drawn_words)} Calls)",
        description=history_str,
        color=0x3b82f6
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="bingo-reset", description="Reset the active Bingo game and clear drawn words (Admin)")
async def cmd_bingo_reset(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You must be a server administrator to reset the Bingo game.", ephemeral=True)
        return
    bot.bingo.reset_game()
    await interaction.response.send_message("✅ Bingo game state has been reset. All drawn words cleared!", ephemeral=False)


@bot.tree.command(name="race-schedule", description="View active and upcoming Torn City races")
async def cmd_race_schedule(interaction: discord.Interaction):
    await interaction.response.defer()
    if not TORN_API_KEY:
        await interaction.followup.send("❌ Torn API key is not configured on the bot.", ephemeral=True)
        return

    url = f"https://api.torn.com/torn/?selections=races&key={TORN_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await interaction.followup.send("❌ Failed to reach Torn API.", ephemeral=True)
                return
            data = await resp.json()

    if data.get("error"):
        await interaction.followup.send(f"❌ Torn API Error: {data['error'].get('error')}", ephemeral=True)
        return

    races = data.get("races", {})
    if not races:
        await interaction.followup.send("🏁 No active public races found on Torn City right now.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏁 Torn City Racing Schedule",
        description="Upcoming races pulled directly from Torn API:",
        color=0xe53e3e,
        timestamp=datetime.now(timezone.utc)
    )

    for r_id, race in list(races.items())[:6]:
        start_ts = race.get("time_start", 0)
        dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
        embed.add_field(
            name=f"🏎️ {race.get('title', 'Race')} ({race.get('car_class', 'Open')})",
            value=f"**Track:** {race.get('track_name', 'Standard')} | **Laps:** {race.get('laps', 100)}\n**Starts:** <t:{start_ts}:R> (<t:{start_ts}:t>)\n**Drivers:** {race.get('enrolled', 0)}/{race.get('max_drivers', 100)}",
            inline=False
        )

    embed.set_footer(text="Torn City Race Radar")
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="torn-item", description="Lookup an item's details on Torn City")
@app_commands.describe(item_name="Name or keyword of the item")
async def cmd_torn_item(interaction: discord.Interaction, item_name: str):
    await interaction.response.defer()
    if not TORN_API_KEY:
        await interaction.followup.send("❌ Torn API key is not configured on the bot.", ephemeral=True)
        return

    url = f"https://api.torn.com/torn/?selections=items&key={TORN_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()

    items = data.get("items", {})
    matched = None
    for it_id, it in items.items():
        if item_name.lower() in it.get("name", "").lower():
            matched = it
            break

    if not matched:
        await interaction.followup.send(f"❌ Could not find any item matching `{item_name}`.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📦 {matched.get('name')}",
        description=matched.get("description", "No description available."),
        color=0x3b82f6
    )
    embed.add_field(name="Type", value=matched.get("type", "General"), inline=True)
    embed.add_field(name="Market Value", value=f"${matched.get('market_value', 0):,}", inline=True)
    embed.add_field(name="Circulation", value=f"{matched.get('circulation', 0):,}", inline=True)
    if matched.get("image"):
        embed.set_thumbnail(url=matched.get("image"))
    embed.set_footer(text="Torn City Item Database")

    await interaction.followup.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        logger.warning("DISCORD_TOKEN environment variable not set. Please set it in .env to run the bot gateway.")
    else:
        bot.run(TOKEN)
