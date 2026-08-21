#!/usr/bin/env python3
"""
Torn City & Discord Suite - 24/7 Companion Bot (v5.0 Mobile, Announcements & 3-Day Racing)
Features:
 - #announcements channel webhook with 🎉 party reaction listener for auto-roster registration
 - 1-Card-Per-User per session enforcement (anti-cheat card locking)
 - 3-Day Race Tournament Generator (25 Laps, Stock Class E, Randomized tracks)
 - /bingo-jumble & /bingo-drop [5 words] with embedded anagram challenges
 - Winner logging & /payout confirmations
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

# 4 Channel Webhook URLs & IDs
DISCORD_ANNOUNCEMENTS_WEBHOOK_URL = os.getenv("DISCORD_ANNOUNCEMENTS_WEBHOOK_URL", "")
DISCORD_BINGO_WEBHOOK_URL = os.getenv("DISCORD_BINGO_WEBHOOK_URL", "")
DISCORD_RACE_WEBHOOK_URL = os.getenv("DISCORD_RACE_WEBHOOK_URL", "")
DISCORD_RAFFLE_WEBHOOK_URL = os.getenv("DISCORD_RAFFLE_WEBHOOK_URL", "")

ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("ANNOUNCEMENT_CHANNEL_ID", "0"))
BINGO_CHANNEL_ID = int(os.getenv("BINGO_CHANNEL_ID", "0"))
RACE_CHANNEL_ID = int(os.getenv("RACE_CHANNEL_ID", "0"))
RAFFLE_CHANNEL_ID = int(os.getenv("RAFFLE_CHANNEL_ID", "0"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TornSuiteBot")

STATE_FILE = "bingo_state.json"
SESSION_CARDS_FILE = "session_cards.json"
ROSTER_FILE = "reaction_roster.json"

TORN_TRACKS = [
    "Mudpit", "Hammerhead", "Two Islands", "Docks", "Industrial",
    "Speedway", "Stone Park", "Parkland", "Meltdown", "Underpass",
    "Uptown", "Vector", "Sewage"
]

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

def scramble_word(word: str) -> str:
    tokens = word.split()
    scrambled_tokens = []
    for token in tokens:
        if len(token) <= 2:
            scrambled_tokens.append(token)
            continue
        chars = list(token)
        for _ in range(5):
            random.shuffle(chars)
            if "".join(chars) != token:
                break
        scrambled_tokens.append("".join(chars))
    return " ".join(scrambled_tokens)


class BingoSessionManager:
    def __init__(self):
        self.word_pool = list(DEFAULT_TORN_ITEMS)
        self.drawn_words = []
        self.user_cards = {} # { user_id: { seed, cells } }
        self.reacted_roster = set()
        self.load_all()

    def load_all(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.drawn_words = data.get("drawn_words", [])
            except Exception as e:
                logger.error(f"State load error: {e}")

        if os.path.exists(SESSION_CARDS_FILE):
            try:
                with open(SESSION_CARDS_FILE, "r") as f:
                    self.user_cards = json.load(f)
            except Exception as e:
                logger.error(f"Cards load error: {e}")

        if os.path.exists(ROSTER_FILE):
            try:
                with open(ROSTER_FILE, "r") as f:
                    self.reacted_roster = set(json.load(f))
            except Exception as e:
                logger.error(f"Roster load error: {e}")

    def save_cards(self):
        try:
            with open(SESSION_CARDS_FILE, "w") as f:
                json.dump(self.user_cards, f, indent=2)
        except Exception as e:
            logger.error(f"Cards save error: {e}")

    def save_roster(self):
        try:
            with open(ROSTER_FILE, "w") as f:
                json.dump(list(self.reacted_roster), f, indent=2)
        except Exception as e:
            logger.error(f"Roster save error: {e}")

    def get_or_create_card(self, user_id: str, user_name: str):
        # 1-Card-Per-User per session enforcement
        if user_id in self.user_cards:
            return self.user_cards[user_id], False # existing, not new

        # Generate deterministic seed
        seed = f"{user_name}-{user_id[:6]}"
        h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(h)
        shuffled = list(self.word_pool)
        rng.shuffle(shuffled)
        selected = shuffled[:24]

        cells = []
        idx = 0
        for i in range(25):
            if i == 12:
                cells.append({"text": "FREE SPACE", "is_free": True, "index": i})
            else:
                cells.append({"text": selected[idx], "is_free": False, "index": i})
                idx += 1

        card_data = {
            "seed": seed,
            "userName": user_name,
            "cells": cells,
            "lockedAt": datetime.now(timezone.utc).isoformat()
        }
        self.user_cards[user_id] = card_data
        self.save_cards()
        return card_data, True

    def draw_words(self, count: int = 1):
        remaining = [w for w in self.word_pool if w not in self.drawn_words]
        if not remaining: return []
        draw_count = min(count, len(remaining))
        drawn = random.sample(remaining, draw_count)
        self.drawn_words.extend(drawn)
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"drawn_words": self.drawn_words, "word_pool": self.word_pool}, f, indent=2)
        except Exception as e:
            logger.error(f"State save error: {e}")
        return drawn


def render_bingo_card_image(title: str, player_name: str, seed: str, cells: list) -> io.BytesIO:
    width, height = 800, 900
    img = Image.new("RGB", (width, height), color="#141414")
    draw = ImageDraw.Draw(img)

    draw.rectangle([40, 40, 760, 140], fill="#202020", outline="#383838", width=2)
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        meta_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
        letter_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        cell_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        cell_font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except Exception:
        title_font = meta_font = letter_font = cell_font = cell_font_bold = ImageFont.load_default()

    draw.text((400, 65), title, fill="#ffffff", font=title_font, anchor="mm")
    draw.text((400, 105), f"Player: {player_name}  |  (Card Locked for Session)", fill="#94a3b8", font=meta_font, anchor="mm")

    letters = ["B", "I", "N", "G", "O"]
    cell_w, cell_h = 138, 132
    start_x, start_y = 55, 160

    for col in range(5):
        x = start_x + col * cell_w
        draw.rectangle([x, start_y, x + cell_w - 6, start_y + 40], fill="#d32f2f")
        draw.text((x + (cell_w - 6) / 2, start_y + 20), letters[col], fill="#ffffff", font=letter_font, anchor="mm")

    grid_y = start_y + 50
    for idx, cell in enumerate(cells):
        row = idx // 5
        col = idx % 5
        x = start_x + col * cell_w
        y = grid_y + row * cell_h
        w, h = cell_w - 6, cell_h - 6

        bg_color = "#2a1f11" if cell["is_free"] else "#1e1e1e"
        border_color = "#eab308" if cell["is_free"] else "#383838"
        text_color = "#eab308" if cell["is_free"] else "#e5e5e5"

        draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=border_color, width=2 if cell["is_free"] else 1)

        words = cell["text"].split()
        lines, current_line = [], ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= 15: current_line = test_line
            else:
                if current_line: lines.append(current_line)
                current_line = word
        if current_line: lines.append(current_line)

        line_h = 15
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
        intents.message_content = True
        intents.reactions = True
        super().__init__(command_prefix="!", intents=intents)
        self.session = BingoSessionManager()

    async def setup_hook(self):
        await self.tree.sync()
        logger.info("Bot v5.0 ready with Reaction Listeners & 3-Day Race Scheduler.")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Auto-registers any user who reacts with 🎉 or 🥳 to the Bingo roster."""
        emoji_name = str(payload.emoji.name)
        if emoji_name in ["🎉", "🥳"]:
            guild = self.get_guild(payload.guild_id)
            user = guild.get_member(payload.user_id) if guild else None
            user_display = user.display_name if user else f"User_{payload.user_id}"
            
            # Register player into roster
            player_tag = f"{user_display} [{payload.user_id}]"
            if player_tag not in self.session.reacted_roster:
                self.session.reacted_roster.add(player_tag)
                self.session.save_roster()
                logger.info(f"Registered {player_tag} to Bingo Roster via 🎉 reaction.")


bot = TornSuiteClient()


# ================= SLASH COMMANDS =================

# 1. EVENT ANNOUNCEMENT WITH REACTION CALLOUT
@bot.tree.command(name="announce", description="Post an official event announcement prompting 🎉 reactions to join")
@app_commands.describe(
    title="Event Title",
    date_time="Scheduled date and time (TCT / Local)",
    prize="Prize pool description",
    details="Event instructions and rules"
)
async def cmd_announce(interaction: discord.Interaction, title: str, date_time: str, prize: str, details: str = None):
    details_str = details or "React with 🎉 to register your spot on the Bingo card roster!"
    embed = discord.Embed(
        title=f"🏆 {title}",
        description=f"{details_str}\n\n👉 **REACT WITH 🎉 TO THIS MESSAGE TO REGISTER FOR YOUR BINGO CARD!**",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📅 Scheduled Time", value=f"**{date_time}**", inline=True)
    embed.add_field(name="🎁 Prize Pool", value=f"**{prize}**", inline=True)
    embed.add_field(name="🔒 Card Rule", value="Strictly 1 card per player per session.", inline=False)
    embed.set_footer(text="React with 🎉 to join the roster!")

    await interaction.response.send_message(content="@everyone 📢 **UPCOMING FACTION EVENT!**", embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("🎉")


# 2. 1-CARD-PER-USER BINGO CARD GENERATOR
@bot.tree.command(name="bingo-card", description="Get your session-locked 5x5 Bingo Card (1 card per player)")
async def cmd_bingo_card(interaction: discord.Interaction):
    await interaction.response.defer()
    u_id = str(interaction.user.id)
    u_name = interaction.user.display_name

    card_data, is_new = bot.session.get_or_create_card(u_id, u_name)
    buf = render_bingo_card_image("TORN CITY FACTION BINGO", u_name, card_data["seed"], card_data["cells"])
    file = discord.File(buf, filename=f"bingo_{u_id}.png")

    desc = f"**Card Seed:** `{card_data['seed']}`\n✅ **Card Locked for this Session.**" if is_new else f"**Card Seed:** `{card_data['seed']}`\n🔒 **You already have a card for this session! Re-sending your original locked card.**"
    embed = discord.Embed(title=f"🎯 Bingo Card: {u_name}", description=desc, color=0xd32f2f)
    embed.set_image(url=f"attachment://bingo_{u_id}.png")
    await interaction.followup.send(embed=embed, file=file)


# 3. 3-DAY RACE SCHEDULER (25 Laps, Stock Class E)
@bot.tree.command(name="race-schedule-3day", description="Generate and post a 3-Day Race Schedule (25 Laps • Stock Class E)")
@app_commands.describe(start_date="Start date (e.g. Tomorrow 18:00 TCT)")
async def cmd_race_3day(interaction: discord.Interaction, start_date: str = "Tomorrow 18:00 TCT"):
    tracks = random.sample(TORN_TRACKS, 3)
    embed = discord.Embed(
        title="🏁 3-Day Stock Class E Racing Tournament (25 Laps)",
        description=f"**Car Requirement:** Stock Class E Only (Honda Civic, Classic Mini, Ford Fiesta, Peugeot 106, Fiat Punto)\n**Format:** 25 Laps Endurance per stage.",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📅 Stage 1 (Day 1)", value=f"**Track:** {tracks[0]}\n**Laps:** 25 Laps | **Class:** Stock E\n**Start:** {start_date}", inline=False)
    embed.add_field(name="📅 Stage 2 (Day 2)", value=f"**Track:** {tracks[1]}\n**Laps:** 25 Laps | **Class:** Stock E", inline=False)
    embed.add_field(name="📅 Stage 3 (Day 3 Finals)", value=f"**Track:** {tracks[2]}\n**Laps:** 25 Laps | **Class:** Stock E", inline=False)
    embed.set_footer(text="Torn Racing Series • 25 Laps Stock Class E")
    await interaction.response.send_message(content="@everyone 🏎️ **3-DAY RACING SCHEDULE RELEASED!**", embed=embed)


# 4. 5-WORD DROP WITH JUMBLE
@bot.tree.command(name="bingo-drop", description="Drop 5 Bingo words at once with an embedded anagram Jumble challenge")
@app_commands.describe(count="Number of words to drop (default 5)")
async def cmd_bingo_drop(interaction: discord.Interaction, count: int = 5):
    drawn = bot.session.draw_words(count)
    if not drawn:
        await interaction.response.send_message("❌ All words drawn!", ephemeral=True)
        return
    scrambled = scramble_word(drawn[0])
    embed = discord.Embed(
        title=f"📦 BINGO 5-WORD DROP: {len(drawn)} Items Released!",
        description="Check your 5x5 cards for all 5 called items:",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="🔀 Word Jumble Mystery Challenge", value=f"**`{scrambled.upper()}`**\n*(Unscramble to find one of the 5 called words!)*", inline=False)
    embed.add_field(name="📋 All 5 Called Items", value="\n".join([f"**#{len(bot.session.drawn_words) - len(drawn) + i + 1}:** {w}" for i, w in enumerate(drawn)]), inline=False)
    embed.set_footer(text=f"Total Called: {len(bot.session.drawn_words)} / {len(bot.session.word_pool)} | Word Drops")
    await interaction.response.send_message(content="💥 **BINGO 5-WORD DROP & JUMBLE!**", embed=embed)


# 5. STANDALONE JUMBLE PUSH
@bot.tree.command(name="bingo-jumble", description="Push a standalone scrambled Word Jumble challenge")
async def cmd_bingo_jumble(interaction: discord.Interaction):
    drawn = bot.session.draw_words(1)
    if not drawn:
        await interaction.response.send_message("❌ All words drawn!", ephemeral=True)
        return
    actual = drawn[0]
    scrambled = scramble_word(actual)
    call_num = len(bot.session.drawn_words)
    embed = discord.Embed(
        title="🧩 MYSTERY BINGO WORD JUMBLE!",
        description=f"Unscramble to mark this item on your card (Call #{call_num}):\n\n## `{scrambled.upper()}`\n\n*(Click spoiler for answer: ||{actual}||)*",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message(content="🔀 **STANDALONE JUMBLE CHALLENGE!**", embed=embed)


# 6. WINNER & PAYOUT COMMANDS
@bot.tree.command(name="race-winner", description="Log and announce an official race or bingo winner")
@app_commands.describe(event_name="Event name", winner="Winner name & ID", prize="Prize (e.g. 10x Xanax)")
async def cmd_winner(interaction: discord.Interaction, event_name: str, winner: str, prize: str):
    embed = discord.Embed(
        title=f"🥇 {event_name} — Winner!",
        description=f"Congratulations **{winner}** on winning **{prize}**!",
        color=0x22c55e,
        timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message(content="🏆 **OFFICIAL WINNER!**", embed=embed)


@bot.tree.command(name="payout", description="Post prize payment confirmation")
@app_commands.describe(winner="Winner name", prize="Prize amount", event_name="Event name")
async def cmd_payout(interaction: discord.Interaction, winner: str, prize: str, event_name: str):
    embed = discord.Embed(
        title="💸 PRIZE PAYOUT CONFIRMED!",
        description=f"Prize payout for **{event_name}** has been sent to **{winner}** ({prize})!",
        color=0xeab308,
        timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: logger.warning("Set DISCORD_TOKEN in .env to run.")
