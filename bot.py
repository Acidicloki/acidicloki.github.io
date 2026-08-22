#!/usr/bin/env python3
"""
Weekend at Loki's - Torn City Event Discord Bot (v5.9 Auto-Repo Sync Edition)
Hosted by Loki [2356475]
Features:
 - Automatic GitHub Repository commit/sync on /bingo-card registration
 - Locked session cards registry (Strictly 1 card per player)
 - Sequential Raffle Ticket numbering on each Bingo card in order of sign-up
 - /raffle-roll: Draws winners directly from the roster of claimed cards
 - /bingo-new-game: Starts a fresh match, resetting cards and raffle numbers back to #1
 - Secret Jumbles: Answers hidden from Discord
 - Scheduled 3-Day Races logging
 - #announcements reaction RSVP listener (🎉)
"""

import os
import io
import json
import random
import hashlib
import logging
import base64
import urllib.request
import urllib.error
import asyncio
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except ImportError as err:
    print("\n[ERROR] Missing required library 'discord.py'. Install with: pip install discord.py")
    raise SystemExit(1)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as err:
    print("\n[ERROR] Missing required library 'Pillow'. Install with: pip install Pillow")
    raise SystemExit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WeekendAtLokis")

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
TORN_API_KEY = os.getenv("TORN_API_KEY", "").strip()

# GitHub Repo Auto-Sync (Optional - enables automatic commit to GitHub Pages repo)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip() # Format: "username/repository-name"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()

DISCORD_ANNOUNCEMENTS_WEBHOOK_URL = os.getenv("DISCORD_ANNOUNCEMENTS_WEBHOOK_URL", "").strip()
DISCORD_BINGO_WEBHOOK_URL = os.getenv("DISCORD_BINGO_WEBHOOK_URL", "").strip()
DISCORD_RACE_WEBHOOK_URL = os.getenv("DISCORD_RACE_WEBHOOK_URL", "").strip()
DISCORD_RAFFLE_WEBHOOK_URL = os.getenv("DISCORD_RAFFLE_WEBHOOK_URL", "").strip()

STATE_FILE = "bingo_state.json"
SESSION_CARDS_FILE = "session_cards.json"
ROSTER_FILE = "reaction_roster.json"
DRAWS_LOG_FILE = "draws_log.json"
WINNERS_LOG_FILE = "winners_log.json"
SCHEDULED_RACES_FILE = "scheduled_races_log.json"

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

def safe_load_json(file_path: str, default_val):
    if not os.path.exists(file_path):
        return default_val
    try:
        if os.path.getsize(file_path) == 0:
            return default_val
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Notice: Auto-recovered from '{file_path}' format ({e}).")
        return default_val

def safe_save_json(file_path: str, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving to {file_path}: {e}")

def sync_file_to_github_repo(relative_path: str, content_data: dict, commit_message: str):
    """Commits and uploads updated JSON file directly to GitHub repo via REST API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{relative_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "WeekendAtLokisBot"
        }
        # Check if file exists to get sha
        sha = None
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    info = json.loads(resp.read().decode("utf-8"))
                    sha = info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                logger.warning(f"GitHub SHA check error: {e}")

        content_bytes = json.dumps(content_data, indent=2).encode("utf-8")
        b64_content = base64.b64encode(content_bytes).decode("utf-8")
        payload = {
            "message": commit_message,
            "content": b64_content,
            "branch": GITHUB_BRANCH
        }
        if sha:
            payload["sha"] = sha

        put_data = json.dumps(payload).encode("utf-8")
        put_req = urllib.request.Request(url, data=put_data, headers=headers, method="PUT")
        with urllib.request.urlopen(put_req) as put_resp:
            if put_resp.status in (200, 201):
                logger.info(f"Successfully committed and uploaded '{relative_path}' to GitHub repo '{GITHUB_REPO}' on branch '{GITHUB_BRANCH}'.")
    except Exception as ex:
        logger.warning(f"GitHub Auto-Sync notice: {ex}")

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


class LogManager:
    @staticmethod
    def append_draw_log(words: list, drop_type: str = "Call", scramble: str = None, answer: str = None):
        records = safe_load_json(DRAWS_LOG_FILE, [])
        if not isinstance(records, list):
            records = []
        for i, w in enumerate(words):
            records.append({
                "word": w,
                "type": drop_type,
                "jumbleScramble": scramble if i == 0 else None,
                "jumbleAnswer": answer if i == 0 else w,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        safe_save_json(DRAWS_LOG_FILE, records)

    @staticmethod
    def append_winner_log(event_name: str, winner: str, rank: str, prize: str, category: str = "racing", notes: str = "", is_paid: bool = False):
        records = safe_load_json(WINNERS_LOG_FILE, [])
        if not isinstance(records, list):
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
        safe_save_json(WINNERS_LOG_FILE, records)
        return record

    @staticmethod
    def append_race_schedule(title: str, t1: str, time1: str, t2: str, time2: str, t3: str, time3: str):
        records = safe_load_json(SCHEDULED_RACES_FILE, [])
        if not isinstance(records, list):
            records = []
        record = {
            "id": f"RACE-{int(datetime.now().timestamp())}",
            "title": title,
            "stage1": {"track": t1, "laps": 25, "class": "Stock E", "time": time1},
            "stage2": {"track": t2, "laps": 25, "class": "Stock E", "time": time2},
            "stage3": {"track": t3, "laps": 25, "class": "Stock E", "time": time3},
            "scheduledAt": datetime.now(timezone.utc).isoformat()
        }
        records.append(record)
        safe_save_json(SCHEDULED_RACES_FILE, records)
        return record


class BingoSessionManager:
    def __init__(self):
        self.word_pool = list(DEFAULT_TORN_ITEMS)
        self.drawn_words = []
        self.user_cards = {}
        self.reacted_roster = set()
        self.load_all()

    def load_all(self):
        state_data = safe_load_json(STATE_FILE, {})
        if isinstance(state_data, dict):
            self.drawn_words = state_data.get("drawn_words", [])
            if "word_pool" in state_data and isinstance(state_data["word_pool"], list) and len(state_data["word_pool"]) >= 24:
                self.word_pool = state_data["word_pool"]

        cards_data = safe_load_json(SESSION_CARDS_FILE, {})
        if isinstance(cards_data, dict):
            self.user_cards = cards_data

        roster_data = safe_load_json(ROSTER_FILE, [])
        if isinstance(roster_data, list):
            self.reacted_roster = set(roster_data)

    def save_cards(self):
        safe_save_json(SESSION_CARDS_FILE, self.user_cards)
        # Background sync to GitHub Repo if configured
        if GITHUB_TOKEN and GITHUB_REPO:
            asyncio.create_task(asyncio.to_thread(
                sync_file_to_github_repo,
                "session_cards.json",
                self.user_cards,
                f"Update session_cards.json ({len(self.user_cards)} locked cards) via Bot"
            ))

    def save_roster(self):
        safe_save_json(ROSTER_FILE, list(self.reacted_roster))

    def save_state(self):
        safe_save_json(STATE_FILE, {"drawn_words": self.drawn_words, "word_pool": self.word_pool})

    def start_new_game(self):
        """Starts a fresh session: clears cards & raffle tickets back to #1, preserves settings."""
        self.drawn_words = []
        self.user_cards = {}
        self.save_state()
        self.save_cards()
        logger.info("Fresh session started! Session cards reset to #1 and synced.")

    def get_or_create_card(self, user_id: str, user_name: str):
        # 1-Card-Per-Player Session Lock
        if str(user_id) in self.user_cards:
            return self.user_cards[str(user_id)], False

        # Sequential Raffle Ticket assignment in order of sign-up
        raffle_num = len(self.user_cards) + 1
        seed = f"{user_name}-{str(user_id)[:6]}"
        h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(h)
        shuffled = list(self.word_pool)
        rng.shuffle(shuffled)
        selected = shuffled[:24]

        cells = []
        idx = 0
        for i in range(25):
            if i == 12:
                cells.append({"text": "LOKI'S FREE SPACE", "is_free": True, "index": i})
            else:
                cells.append({"text": selected[idx], "is_free": False, "index": i})
                idx += 1

        card_data = {
            "seed": seed,
            "userName": user_name,
            "userId": str(user_id),
            "raffleNumber": raffle_num,
            "cells": cells,
            "lockedAt": datetime.now(timezone.utc).isoformat()
        }
        self.user_cards[str(user_id)] = card_data
        self.save_cards()
        logger.info(f"Locked Bingo Card for {user_name} [{user_id}] -> 🎟️ Raffle Ticket #{raffle_num}")
        return card_data, True

    def draw_words(self, count: int = 1, drop_type: str = "Call", scramble: str = None, answer: str = None):
        remaining = [w for w in self.word_pool if w not in self.drawn_words]
        if not remaining:
            return []
        draw_count = min(count, len(remaining))
        drawn = random.sample(remaining, draw_count)
        self.drawn_words.extend(drawn)
        self.save_state()
        LogManager.append_draw_log(drawn, drop_type, scramble, answer or (drawn[0] if scramble else None))
        return drawn


def get_cross_platform_font(font_size: int, is_bold: bool = False):
    candidates = [
        "impact.ttf", "Impact.ttf", "arialbd.ttf", "Arial-Bold.ttf", "DejaVuSans-Bold.ttf",
        "arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, font_size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=font_size)
    except Exception:
        return ImageFont.load_default()


def render_bingo_card_image(title: str, player_name: str, seed: str, raffle_number: int, cells: list) -> io.BytesIO:
    width, height = 800, 900
    img = Image.new("RGB", (width, height), color="#141414")
    draw = ImageDraw.Draw(img)

    draw.rectangle([40, 40, 760, 140], fill="#202020", outline="#383838", width=2)
    title_font = get_cross_platform_font(28, is_bold=True)
    meta_font = get_cross_platform_font(13, is_bold=True)
    letter_font = get_cross_platform_font(22, is_bold=True)
    cell_font = get_cross_platform_font(12, is_bold=False)
    cell_font_bold = get_cross_platform_font(12, is_bold=True)

    draw.text((400, 65), title, fill="#ffffff", font=title_font, anchor="mm")
    draw.text((400, 105), f"Player: {player_name}  |  🎟️ Raffle Ticket #{raffle_number} (Card Locked)", fill="#eab308", font=meta_font, anchor="mm")

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
            if len(test_line) <= 14: current_line = test_line
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
        try:
            intents.message_content = True
            intents.reactions = True
        except Exception:
            pass
        super().__init__(command_prefix="!", intents=intents)
        self.session = BingoSessionManager()

    async def setup_hook(self):
        try:
            await self.tree.sync()
            logger.info("Weekend at Loki's slash commands synced (v5.9 Auto-Repo Sync Active).")
        except Exception as e:
            logger.warning(f"Sync note: {e}")

    async def on_ready(self):
        activity = discord.Activity(type=discord.ActivityType.watching, name="Weekend at Loki's | /bingo-card")
        await self.change_presence(activity=activity)
        logger.info(f"Connected to Discord as {self.user}. Ready!")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        try:
            emoji_name = str(payload.emoji.name)
            if emoji_name in ["🎉", "🥳"]:
                guild = self.get_guild(payload.guild_id)
                user = guild.get_member(payload.user_id) if guild else None
                user_display = user.display_name if user else f"User_{payload.user_id}"
                player_tag = f"{user_display} [{payload.user_id}]"

                if player_tag not in self.session.reacted_roster:
                    self.session.reacted_roster.add(player_tag)
                    self.session.save_roster()
                    logger.info(f"Registered {player_tag} to Weekend at Loki's roster via 🎉 reaction.")
        except Exception as e:
            logger.warning(f"Reaction handler note: {e}")


bot = TornSuiteClient()


# ================= SLASH COMMANDS =================

# 1. BINGO CARD GENERATOR (LOCKS 1 CARD PER PLAYER & SYNCS TO REPO)
@bot.tree.command(name="bingo-card", description="Get your locked 5x5 Bingo Card with sequential Raffle Ticket")
async def cmd_bingo_card(interaction: discord.Interaction):
    await interaction.response.defer()
    u_id = str(interaction.user.id)
    u_name = interaction.user.display_name

    card_data, is_new = bot.session.get_or_create_card(u_id, u_name)
    raffle_num = card_data.get("raffleNumber", 1)
    buf = render_bingo_card_image("WEEKEND AT LOKI'S BINGO", u_name, card_data["seed"], raffle_num, card_data["cells"])
    file = discord.File(buf, filename=f"bingo_{u_id}.png")

    desc = f"🎟️ **Assigned Raffle Ticket:** `#{raffle_num}` *(Sign-Up Order #{raffle_num})*\n**Card Seed:** `{card_data['seed']}`\n✅ **Card Locked for this Session & Logged to Roster.**" if is_new else f"🎟️ **Assigned Raffle Ticket:** `#{raffle_num}`\n**Card Seed:** `{card_data['seed']}`\n🔒 **You already have a card for this session! Re-sending your locked card.**"
    embed = discord.Embed(title=f"🎯 Weekend at Loki's Card: {u_name}", description=desc, color=0xd32f2f)
    embed.set_image(url=f"attachment://bingo_{u_id}.png")
    embed.set_footer(text=f"Total Registered: {len(bot.session.user_cards)} Players | 1 Card Per Session")
    await interaction.followup.send(embed=embed, file=file)


# 2. BINGO SYNC EXPORT (Bridges Discord to Web Dashboard)
@bot.tree.command(name="bingo-sync-export", description="Export all claimed Discord Bingo cards to JSON for 1-click site sync")
async def cmd_bingo_sync_export(interaction: discord.Interaction):
    cards = bot.session.user_cards
    count = len(cards)
    json_str = json.dumps({"sessionCards": cards}, indent=2)
    buf = io.BytesIO(json_str.encode("utf-8"))
    file = discord.File(buf, filename="session_cards.json")

    embed = discord.Embed(
        title="🗂️ Weekend at Loki's — Session Cards Sync Export",
        description=f"Exported **{count} claimed Bingo cards** with sequential Raffle Tickets!\n\n**To Sync to Web Dashboard:**\n1. In the Web GUI, go to **Claimed Cards** tab.\n2. Click **Load Discord `session_cards.json`** and select this file (or click **Paste Sync**).",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Sync Bridge")
    await interaction.response.send_message(embed=embed, file=file, ephemeral=False)


# 3. START NEW GAME (RESET TICKETS)
@bot.tree.command(name="bingo-new-game", description="Start a fresh match (resets cards and raffle numbers back to #1)")
async def cmd_bingo_new_game(interaction: discord.Interaction):
    bot.session.start_new_game()
    embed = discord.Embed(
        title="🚀 FRESH WEEKEND AT LOKI'S BINGO SESSION STARTED!",
        description="All previous cards and drawn words have been reset!\n\n👉 Type `/bingo-card` to generate your **1 fresh Bingo card & sequential Raffle Ticket** (starting at Ticket #1)!",
        color=0x22c55e,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="🎟️ Sequential Tickets", value="Assigned in order of sign-up (Ticket #1, #2, #3...).", inline=False)
    embed.set_footer(text="Weekend at Loki's • Hosted by Loki")
    await interaction.response.send_message(content="@everyone 🎉 **NEW BINGO SESSION IS LIVE!**", embed=embed)


# 4. RAFFLE ROLLER (DRAWS FROM CLAIMED CARDS ROSTER)
@bot.tree.command(name="raffle-roll", description="Draw a random winner from players who have claimed Bingo cards")
@app_commands.describe(prize="Prize description (e.g. 50x Xanax + $25,000,000)")
async def cmd_raffle_roll(interaction: discord.Interaction, prize: str = "50x Xanax"):
    cards = bot.session.user_cards
    if not cards:
        await interaction.response.send_message("❌ No players have claimed Bingo cards yet in this session!", ephemeral=True)
        return

    winner_id = random.choice(list(cards.keys()))
    winner_card = cards[winner_id]
    ticket_num = winner_card.get("raffleNumber", 1)
    winner_name = winner_card.get("userName", f"User_{winner_id}")

    LogManager.append_winner_log("Weekend at Loki's Raffle", f"Ticket #{ticket_num} - {winner_name}", "Raffle Winner", prize, category="raffle")

    embed = discord.Embed(
        title="🎟️ WEEKEND AT LOKI'S RAFFLE WINNER DRAWN!",
        description=f"Congratulations to our winning ticket from the claimed Bingo cards roster!\n\n👑 **Winning Ticket:** `#{ticket_num} - ${winner_name}`\n🎁 **Prize:** **{prize}**",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Faction Vault")
    await interaction.response.send_message(content="@everyone 🏆 **RAFFLE WINNER DRAWN!**", embed=embed)


# 5. WEEKEND AT LOKI'S ANNOUNCEMENT
@bot.tree.command(name="announce", description="Post an official Weekend at Loki's announcement")
@app_commands.describe(
    date_time="Scheduled date & time (e.g. Saturday at 18:00 TCT)",
    title="Event Title (Default: Weekend at Loki's)"
)
async def cmd_announce(interaction: discord.Interaction, date_time: str = "Saturday at 18:00 TCT", title: str = "🎉 Weekend at Loki's"):
    embed = discord.Embed(
        title=f"🏆 {title}",
        description=f"Join us for the next session on **{date_time}**!\n\n👉 **REACT WITH 🎉 TO THIS MESSAGE TO JOIN & CLAIM YOUR SEQUENTIAL RAFFLE TICKET!**",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📅 Scheduled Session", value=f"**{date_time}**", inline=False)
    embed.set_footer(text="Weekend at Loki's • Hosted by Loki [2356475] • React with 🎉 to join!")

    await interaction.response.send_message(content="@everyone 📢 **WEEKEND AT LOKI'S ANNOUNCEMENT!**", embed=embed)
    try:
        msg = await interaction.original_response()
        await msg.add_reaction("🎉")
    except Exception:
        pass


# 6. 3-DAY RACE SCHEDULER & LOGGER
@bot.tree.command(name="race-schedule-3day", description="Generate and log Loki's 3-Day Race Schedule (25 Laps • Stock Class E)")
@app_commands.describe(start_date="Start date (e.g. Tomorrow 18:00 TCT)")
async def cmd_race_3day(interaction: discord.Interaction, start_date: str = "Tomorrow 18:00 TCT"):
    tracks = random.sample(TORN_TRACKS, 3)
    LogManager.append_race_schedule("Weekend at Loki's 3-Day Series", tracks[0], start_date, tracks[1], "Day 2 18:00 TCT", tracks[2], "Day 3 18:00 TCT")

    embed = discord.Embed(
        title="🏁 Weekend at Loki's — 3-Day Stock Class E Series (25 Laps)",
        description=f"**Car Requirement:** Stock Class E Only (Honda Civic, Classic Mini, Ford Fiesta, Peugeot 106, Fiat Punto)\n**Format:** 25 Laps Endurance per stage.\n[Create Custom Race in Torn](https://www.torn.com/loader.php?sid=racing#/tab=customrace)",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📅 Stage 1 (Day 1)", value=f"**Track:** {tracks[0]}\n**Laps:** 25 Laps | **Class:** Stock E\n**Start:** {start_date}", inline=False)
    embed.add_field(name="📅 Stage 2 (Day 2)", value=f"**Track:** {tracks[1]}\n**Laps:** 25 Laps | **Class:** Stock E", inline=False)
    embed.add_field(name="📅 Stage 3 (Day 3 Finals)", value=f"**Track:** {tracks[2]}\n**Laps:** 25 Laps | **Class:** Stock E", inline=False)
    embed.set_footer(text="Weekend at Loki's Racing Series • Logged to Tournament Ledger")
    await interaction.response.send_message(content="@everyone 🏎️ **LOKI'S 3-DAY RACING SCHEDULE!**", embed=embed)


# 7. 5-WORD DROP WITH SECRET JUMBLE
@bot.tree.command(name="bingo-drop", description="Release Loki's 5-Word Drop with an anagram Jumble challenge")
@app_commands.describe(count="Number of words to drop (default 5)")
async def cmd_bingo_drop(interaction: discord.Interaction, count: int = 5):
    remaining = [w for w in bot.session.word_pool if w not in bot.session.drawn_words]
    if not remaining:
        await interaction.response.send_message("❌ All words drawn! Use `/bingo-new-game` to start a fresh match.", ephemeral=True)
        return

    scramble_target = remaining[0]
    scrambled = scramble_word(scramble_target)
    drawn = bot.session.draw_words(count, "5-Word Drop", scrambled, scramble_target)

    embed = discord.Embed(
        title=f"📦 Weekend at Loki's — 5-Word Drop Released!",
        description="Check your 5x5 cards for all 5 called items:",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="🔀 Loki's Mystery Jumble Challenge", value=f"**`{scrambled.upper()}`**\n*(Unscramble to find one of the 5 called items!)*", inline=False)
    embed.add_field(name="📋 All 5 Released Items", value="\n".join([f"**#{len(bot.session.drawn_words) - len(drawn) + i + 1}:** {w}" for i, w in enumerate(drawn)]), inline=False)
    embed.set_footer(text=f"Total Called: {len(bot.session.drawn_words)} / {len(bot.session.word_pool)} | Weekend at Loki's")
    await interaction.response.send_message(content="💥 **LOKI'S 5-WORD BINGO DROP & JUMBLE!**", embed=embed)


# 8. STANDALONE SECRET JUMBLE PUSH
@bot.tree.command(name="bingo-jumble", description="Push a standalone scrambled Word Jumble challenge (secret answer)")
async def cmd_bingo_jumble(interaction: discord.Interaction):
    remaining = [w for w in bot.session.word_pool if w not in bot.session.drawn_words]
    if not remaining:
        await interaction.response.send_message("❌ All words drawn! Use `/bingo-new-game` to start a fresh match.", ephemeral=True)
        return

    actual_target = remaining[0]
    scrambled = scramble_word(actual_target)
    drawn = bot.session.draw_words(1, "Standalone Jumble", scrambled, actual_target)
    call_num = len(bot.session.drawn_words)

    embed = discord.Embed(
        title="🧩 WEEKEND AT LOKI'S — MYSTERY WORD JUMBLE!",
        description=f"Unscramble to mark this item on your card (Call #{call_num}):\n\n## `{scrambled.upper()}`",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Call #{call_num} | Hosted by Loki")
    await interaction.response.send_message(content="🔀 **LOKI'S STANDALONE JUMBLE!**", embed=embed)


# 9. WINNERS & VAULT PAYOUTS
@bot.tree.command(name="race-winner", description="Log and announce a Weekend at Loki's winner")
@app_commands.describe(event_name="Event name", winner="Winner name & ID", prize="Prize")
async def cmd_winner(interaction: discord.Interaction, event_name: str, winner: str, prize: str):
    LogManager.append_winner_log(event_name, winner, "Winner", prize)
    embed = discord.Embed(
        title=f"🥇 Weekend at Loki's — Winner Announcement!",
        description=f"Congratulations **{winner}** on winning **{prize}** in **{event_name}**!",
        color=0x22c55e,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Hosted by Loki")
    await interaction.response.send_message(content="🏆 **OFFICIAL WINNER!**", embed=embed)


@bot.tree.command(name="payout", description="Post prize payment confirmation from Loki's Vault")
@app_commands.describe(winner="Winner name", prize="Prize amount", event_name="Event name")
async def cmd_payout(interaction: discord.Interaction, winner: str, prize: str, event_name: str):
    embed = discord.Embed(
        title="💸 Loki's Vault Payout Confirmed!",
        description=f"Sent **{prize}** to **{winner}** for **{event_name}**!",
        color=0xeab308,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Faction Vault")
    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        print("\n[SETUP REQUIRED] Set DISCORD_TOKEN in .env\n")
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            print("\n[DISCORD INTENTS REQUIRED] Enable Message Content & Server Members Intent in Discord Developer Portal.\n")
        except Exception as ex:
            logger.error(f"Bot startup error: {ex}")
