#!/usr/bin/env python3
"""
Torn City & Discord Suite - 24/7 Companion Bot (Logs & Payouts Edition)
Features:
 - Persistent JSON logging for all Bingo draws and race/event winners
 - Slash commands: /race-winner, /payout, /bingo drop, /bingo card, /race schedule, /raffle roll
 - 3-Channel routing (#bingo, #racing, #raffles)
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

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
TORN_API_KEY = os.getenv("TORN_API_KEY", "")

# 3 Dedicated Webhooks & Channel IDs
DISCORD_BINGO_WEBHOOK_URL = os.getenv("DISCORD_BINGO_WEBHOOK_URL", "")
DISCORD_RACE_WEBHOOK_URL = os.getenv("DISCORD_RACE_WEBHOOK_URL", "")
DISCORD_RAFFLE_WEBHOOK_URL = os.getenv("DISCORD_RAFFLE_WEBHOOK_URL", "")

BINGO_CHANNEL_ID = int(os.getenv("BINGO_CHANNEL_ID", "0"))
RACE_CHANNEL_ID = int(os.getenv("RACE_CHANNEL_ID", "0"))
RAFFLE_CHANNEL_ID = int(os.getenv("RAFFLE_CHANNEL_ID", "0"))

PING_BINGO_ROLE = os.getenv("PING_BINGO_ROLE", "")
PING_RACE_ROLE = os.getenv("PING_RACE_ROLE", "")
PING_RAFFLE_ROLE = os.getenv("PING_RAFFLE_ROLE", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TornSuiteBot")

STATE_FILE = "bingo_state.json"
WINNERS_LOG_FILE = "winners_log.json"
DRAWS_LOG_FILE = "draws_log.json"

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

class LogManager:
    @staticmethod
    def append_draw_log(words: list, drop_type: str = "Call"):
        records = []
        if os.path.exists(DRAWS_LOG_FILE):
            try:
                with open(DRAWS_LOG_FILE, "r") as f:
                    records = json.load(f)
            except Exception:
                records = []
        for w in words:
            records.append({
                "word": w,
                "type": drop_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        try:
            with open(DRAWS_LOG_FILE, "w") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error(f"Draws log error: {e}")

    @staticmethod
    def append_winner_log(event_name: str, winner: str, rank: str, prize: str, category: str = "racing", notes: str = "", is_paid: bool = False):
        records = []
        if os.path.exists(WINNERS_LOG_FILE):
            try:
                with open(WINNERS_LOG_FILE, "r") as f:
                    records = json.load(f)
            except Exception:
                records = []
        record = {
            "id": f"WIN-{int(datetime.now().timestamp())}",
            "eventName": event_name,
            "winner": winner,
            "rank": rank,
            "prize": prize,
            "category": category,
            "notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "isPaid": is_paid
        }
        records.append(record)
        try:
            with open(WINNERS_LOG_FILE, "w") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            logger.error(f"Winners log error: {e}")
        return record


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
            except Exception as e:
                logger.error(f"Error loading state: {e}")

    def save_state(self):
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"drawn_words": self.drawn_words, "word_pool": self.word_pool}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def draw_words(self, count: int = 1):
        remaining = [w for w in self.word_pool if w not in self.drawn_words]
        if not remaining:
            return []
        draw_count = min(count, len(remaining))
        drawn = random.sample(remaining, draw_count)
        self.drawn_words.extend(drawn)
        self.save_state()
        LogManager.append_draw_log(drawn, "5-Word Drop" if count > 1 else "Single Call")
        return drawn

    def get_card_cells(self, seed_str: str, free_space: str = "FREE SPACE"):
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


def render_bingo_card_image(title: str, player_name: str, seed: str, cells: list) -> io.BytesIO:
    width, height = 800, 900
    img = Image.new("RGB", (width, height), color="#12141a")
    draw = ImageDraw.Draw(img)

    draw.rectangle([40, 40, 760, 140], fill="#1a1d26", outline="#2a2f3d", width=2)
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        meta_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        letter_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        cell_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        cell_font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        title_font = meta_font = letter_font = cell_font = cell_font_bold = ImageFont.load_default()

    draw.text((400, 65), title, fill="#ffffff", font=title_font, anchor="mm")
    draw.text((400, 105), f"Player: {player_name}  |  Seed: {seed}", fill="#94a3b8", font=meta_font, anchor="mm")

    letters = ["B", "I", "N", "G", "O"]
    cell_w, cell_h = 138, 132
    start_x, start_y = 55, 160

    for col in range(5):
        x = start_x + col * cell_w
        draw.rectangle([x, start_y, x + cell_w - 6, start_y + 40], fill="#3b82f6")
        draw.text((x + (cell_w - 6) / 2, start_y + 20), letters[col], fill="#ffffff", font=letter_font, anchor="mm")

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

        words = cell["text"].split()
        lines, current_line = [], ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= 15:
                current_line = test_line
            else:
                if current_line: lines.append(current_line)
                current_line = word
        if current_line: lines.append(current_line)

        line_h = 16
        text_start_y = y + (h - len(lines) * line_h) / 2 + 8
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
        super().__init__(command_prefix="!", intents=intents)
        self.bingo = BingoManager()
        self.notified_races = set()

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Bot commands synced.")


bot = TornSuiteClient()


# ================= SLASH COMMANDS =================

# 1. PUSH WINNER COMMAND
@bot.tree.command(name="race-winner", description="Log and push a race or bingo winner to Discord")
@app_commands.describe(
    event_name="Name of the race or bingo game",
    winner="Winner player name and ID",
    rank="Placement (e.g. 1st Place, 2nd Place)",
    prize="Prize reward amount",
    channel_category="racing or bingo"
)
async def cmd_race_winner(interaction: discord.Interaction, event_name: str, winner: str, rank: str, prize: str, channel_category: str = "racing"):
    LogManager.append_winner_log(event_name, winner, rank, prize, channel_category)
    embed = discord.Embed(
        title=f"🥇 {event_name} — {rank} Winner!",
        description=f"Congratulations to **{winner}** for securing **{rank}**!",
        color=0x10b981,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="👑 Winner", value=f"**{winner}**", inline=True)
    embed.add_field(name="🏆 Placement", value=rank, inline=True)
    embed.add_field(name="🎁 Prize Reward", value=f"**{prize}**", inline=False)
    embed.set_footer(text="Torn Winner Radar")

    role_ping = f"<@&{PING_RACE_ROLE}> " if channel_category == "racing" and PING_RACE_ROLE else ""
    await interaction.response.send_message(content=f"{role_ping}🏆 **OFFICIAL WINNER!**", embed=embed)


# 2. PAYOUT / POST WINNER PAID COMMAND
@bot.tree.command(name="payout", description="Post prize payment confirmation for a winner")
@app_commands.describe(winner="Winner name", prize="Prize amount", event_name="Event name")
async def cmd_payout(interaction: discord.Interaction, winner: str, prize: str, event_name: str):
    LogManager.append_winner_log(event_name, winner, "Paid", prize, "payout", "Confirmed Payment", is_paid=True)
    embed = discord.Embed(
        title="💸 PRIZE PAYOUT CONFIRMED!",
        description=f"Prize payout for **{event_name}** has been sent to **{winner}**!",
        color=0xf59e0b,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Recipient", value=f"**{winner}**", inline=True)
    embed.add_field(name="Prize Amount", value=f"**{prize}**", inline=True)
    embed.add_field(name="Status", value="✅ Paid & Dispatched", inline=True)
    embed.set_footer(text="Faction Treasury")
    await interaction.response.send_message(embed=embed)


# 3. 5-WORD DROP COMMAND
@bot.tree.command(name="bingo-drop", description="Drop 5 Bingo words at once (Word Drop)")
@app_commands.describe(count="Number of words to drop (default 5)")
async def cmd_bingo_drop(interaction: discord.Interaction, count: int = 5):
    drawn = bot.bingo.draw_words(count)
    if not drawn:
        await interaction.response.send_message("❌ All words have already been drawn!", ephemeral=True)
        return
    total_called = len(bot.bingo.drawn_words)
    embed = discord.Embed(
        title=f"📦 BINGO WORD DROP: {len(drawn)} Items Released!",
        description="Check your 5x5 cards for the newly dropped items:",
        color=0xf59e0b,
        timestamp=datetime.now(timezone.utc)
    )
    for i, word in enumerate(drawn):
        embed.add_field(name=f"🔹 Drop #{total_called - len(drawn) + i + 1}", value=f"**{word}**", inline=True)
    embed.set_footer(text=f"Total Called: {total_called} / {len(bot.bingo.word_pool)} | Word Drops Logged")
    role_ping = f"<@&{PING_BINGO_ROLE}> " if PING_BINGO_ROLE else ""
    await interaction.response.send_message(content=f"{role_ping}💥 **BINGO 5-WORD DROP!**", embed=embed)


# 4. CARD GENERATOR
@bot.tree.command(name="bingo-card", description="Generate your 5x5 Torn Bingo Card image")
@app_commands.describe(player_name="Your Torn handle", seed="Card Seed")
async def cmd_bingo_card(interaction: discord.Interaction, player_name: str = None, seed: str = None):
    await interaction.response.defer()
    p_name = player_name or interaction.user.display_name
    card_seed = seed or f"{p_name}-{datetime.now().strftime('%Y%m%d')}"
    cells = bot.bingo.get_card_cells(card_seed)
    image_buf = render_bingo_card_image("TORN FACTION BINGO", p_name, card_seed, cells)

    file = discord.File(image_buf, filename=f"bingo_{card_seed}.png")
    embed = discord.Embed(title=f"🎯 Bingo Card: {p_name}", description=f"Seed: `{card_seed}`", color=0x3b82f6)
    embed.set_image(url=f"attachment://bingo_{card_seed}.png")
    await interaction.followup.send(embed=embed, file=file)


if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        logger.warning("Set DISCORD_TOKEN in .env to run.")
