#!/usr/bin/env python3
"""
Weekend at Loki's - Torn City Event Discord Bot (v7.0 Directory-Anchored Storage Edition)
Hosted by Loki [2356475]
Features:
 - Absolute Directory Anchoring (BASE_DIR): All JSON files are strictly stored in the same directory as bot.py
 - In-Memory State Purge: /bingo-new-game and webhooks wipe internal Python dictionaries and files
 - /bingo-reload-disk: Forces bot to reload in-memory cache directly from disk (or clear if file was deleted)
 - /bingo-card: Generates 5x5 card, locks 1 card per player, assigns sequential Raffle Ticket #, and auto-syncs to GitHub
 - /bingo-push-repo: Explicitly tests and pushes session_cards.json to GitHub with live diagnostics
 - /bingo-sync-export / /bingo-card-export: Exports session cards JSON attachment for 1-click site paste
 - /raffle-roll: Draws winners directly from the roster of claimed cards
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

# GitHub Repo Auto-Sync Settings
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "").strip() # Format: "username/repository-name"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()

# Discord Channel IDs (Direct Native Bot Routing - No Webhooks Required)
def parse_channel_id(env_var_name: str) -> int:
    val = os.getenv(env_var_name, "").strip()
    return int(val) if val.isdigit() else 0

ANNOUNCEMENTS_CHANNEL_ID = parse_channel_id("ANNOUNCEMENTS_CHANNEL_ID")
BINGO_CHANNEL_ID = parse_channel_id("BINGO_CHANNEL_ID")
RACE_CHANNEL_ID = parse_channel_id("RACE_CHANNEL_ID")
RAFFLE_CHANNEL_ID = parse_channel_id("RAFFLE_CHANNEL_ID")


DISCORD_ANNOUNCEMENTS_WEBHOOK_URL = os.getenv("DISCORD_ANNOUNCEMENTS_WEBHOOK_URL", "").strip()
DISCORD_BINGO_WEBHOOK_URL = os.getenv("DISCORD_BINGO_WEBHOOK_URL", "").strip()
DISCORD_RACE_WEBHOOK_URL = os.getenv("DISCORD_RACE_WEBHOOK_URL", "").strip()
DISCORD_RAFFLE_WEBHOOK_URL = os.getenv("DISCORD_RAFFLE_WEBHOOK_URL", "").strip()

# ABSOLUTE BASE DIRECTORY ANCHORING (Stored in exact folder where bot.py lives)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "bingo_state.json")
SESSION_CARDS_FILE = os.path.join(BASE_DIR, "session_cards.json")
ROSTER_FILE = os.path.join(BASE_DIR, "reaction_roster.json")
DRAWS_LOG_FILE = os.path.join(BASE_DIR, "draws_log.json")
WINNERS_LOG_FILE = os.path.join(BASE_DIR, "winners_log.json")
SCHEDULED_RACES_FILE = os.path.join(BASE_DIR, "scheduled_races_log.json")
BUG_REPORTS_FILE = os.path.join(BASE_DIR, "bug_reports.json")
PRIZES_CONFIG_FILE = os.path.join(BASE_DIR, "prizes_config.json")
RACE_PASSWORD = os.getenv("RACE_PASSWORD", "LOKI2026").strip()

logger.info(f"Storage path anchored to: {BASE_DIR}")


DEFAULT_PRIZES = {
    "raffle_day1": "50x Xanax",
    "raffle_day2": "5x Box of Medical Supplies",
    "raffle_day3": "1x Donator Pack + 50x Xanax",
    "race_bronze_1st": "10x Xanax",
    "race_bronze_2nd": "5x Xanax",
    "race_bronze_3rd": "2x Xanax",
    "race_bronze_last": "1x Xanax (Consolation)",
    "race_silver_1st": "25x Xanax",
    "race_silver_2nd": "15x Xanax",
    "race_silver_3rd": "5x Xanax",
    "race_silver_last": "2x Xanax (Consolation)",
    "race_gold_1st": "50x Xanax + Box of Meds",
    "race_gold_2nd": "25x Xanax",
    "race_gold_3rd": "10x Xanax",
    "race_gold_last": "5x Xanax (Consolation)",
    "bingo_prize": "25x Xanax",
    "bingo_prize": "25x Xanax",
    "bingo_blackout": "100x Xanax + 2x Donator Pack",
    "jumble_fast": "5x Xanax per Drop"
}

def get_configured_prizes() -> dict:
    loaded = safe_load_json(PRIZES_CONFIG_FILE, {})
    if isinstance(loaded, dict) and loaded:
        prizes = dict(DEFAULT_PRIZES)
        prizes.update(loaded)
        return prizes
    return dict(DEFAULT_PRIZES)

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


def fetch_file_from_github_repo(relative_path: str):
    """Fetches latest file content from GitHub repo via REST API."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None
    repo_clean = GITHUB_REPO.replace("https://github.com/", "").strip("/")
    try:
        url = f"https://api.github.com/repos/{repo_clean}/contents/{relative_path}?ref={GITHUB_BRANCH}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "WeekendAtLokisBot"
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                info = json.loads(resp.read().decode("utf-8"))
                import base64
                content_bytes = base64.b64decode(info.get("content", ""))
                return json.loads(content_bytes.decode("utf-8"))
    except Exception as e:
        logger.debug(f"GitHub fetch {relative_path} notice: {e}")
    return None


def sync_file_to_github_repo(relative_path: str, content_data: dict, commit_message: str):
    """Commits and uploads updated JSON file directly to GitHub repo via REST API. Returns (success: bool, status_msg: str)."""
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN is not configured in .env"
    if not GITHUB_REPO:
        return False, "GITHUB_REPO is not configured in .env (Format: username/repo-name)"

    repo_clean = GITHUB_REPO.replace("https://github.com/", "").strip("/")

    try:
        url = f"https://api.github.com/repos/{repo_clean}/contents/{relative_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "WeekendAtLokisBot"
        }

        sha = None
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 200:
                    info = json.loads(resp.read().decode("utf-8"))
                    sha = info.get("sha")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False, "GitHub Authentication Failed (HTTP 401: Invalid Token)"
            elif e.code == 403:
                return False, "GitHub Permission Denied (HTTP 403: Token requires 'Contents: Read and write' permission)"
            elif e.code == 404:
                sha = None
            else:
                return False, f"GitHub Error {e.code}: {e.reason}"

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
                msg = f"Successfully committed '{relative_path}' to '{repo_clean}' on branch '{GITHUB_BRANCH}'!"
                logger.info(msg)
                return True, msg
            return False, f"Unexpected response from GitHub: HTTP {put_resp.status}"

    except urllib.error.HTTPError as he:
        if he.code == 403:
            err = "GitHub Error 403 Forbidden. Your token needs 'Contents: Read and write' permissions."
        elif he.code == 404:
            err = f"GitHub Error 404 Not Found. Please check repository name '{repo_clean}'."
        else:
            err = f"GitHub API Error {he.code}: {he.reason}"
        logger.warning(err)
        return False, err
    except Exception as ex:
        err = f"GitHub sync error: {ex}"
        logger.warning(err)
        return False, err

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



async def send_to_channel_or_fallback(channel_id: int, content: str = None, embed: discord.Embed = None, file: discord.File = None):
    """Natively sends messages directly to configured Discord channel ID."""
    if channel_id and channel_id > 0:
        try:
            channel = bot.get_channel(channel_id)
            if not channel:
                channel = await bot.fetch_channel(channel_id)
            if channel:
                return await channel.send(content=content, embed=embed, file=file)
        except Exception as e:
            logger.error(f"Failed to send to channel {channel_id}: {e}")
    return None

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
    def append_bug_report(reporter_name: str, reporter_id: str, description: str, severity: str = "Medium", feature: str = "General"):
        records = safe_load_json(BUG_REPORTS_FILE, [])
        if not isinstance(records, list):
            records = []
        bug_id = f"BUG-{len(records) + 1001}"
        record = {
            "id": bug_id,
            "reporterName": reporter_name,
            "reporterId": str(reporter_id),
            "description": description,
            "severity": severity,
            "feature": feature,
            "status": "OPEN",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        records.append(record)
        safe_save_json(BUG_REPORTS_FILE, records)
        logger.info(f"[BUG REPORT] Logged {bug_id} ({feature} - {severity}) from {reporter_name}: {description[:60]}")
        # Automatically sync to GitHub repo if token is configured
        sync_file_to_github_repo("bug_reports.json", records, f"Log bug report {bug_id} from {reporter_name}")
        return record

    @staticmethod
    def update_bug_status(bug_id: str, new_status: str = "RESOLVED"):
        records = safe_load_json(BUG_REPORTS_FILE, [])
        if not isinstance(records, list):
            return False, "No bug reports found"
        found = False
        for r in records:
            if r.get("id", "").upper() == bug_id.upper():
                r["status"] = new_status
                r["resolvedAt"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if found:
            safe_save_json(BUG_REPORTS_FILE, records)
            sync_file_to_github_repo("bug_reports.json", records, f"Update bug report {bug_id} status to {new_status}")
            return True, f"Bug {bug_id} marked as {new_status}"
        return False, f"Bug ID {bug_id} not found"

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
        else:
            self.user_cards = {}

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
        state_data = {
            "drawn_words": self.drawn_words,
            "word_pool": self.word_pool,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        safe_save_json(STATE_FILE, state_data)
        if GITHUB_TOKEN and GITHUB_REPO:
            try:
                import asyncio
                asyncio.create_task(asyncio.to_thread(
                    sync_file_to_github_repo,
                    "bingo_state.json",
                    state_data,
                    f"Sync bingo_state.json ({len(self.word_pool)} words, {len(self.drawn_words)} called) via Bot"
                ))
            except Exception:
                pass

    def start_new_game(self):
        """Starts a fresh session: clears cards & raffle tickets back to #1, purges memory & disk, and syncs."""
        self.drawn_words = []
        self.user_cards = {}
        self.save_state()
        self.save_cards()
        logger.info("🤖 WALL-E Cleaned Session: Cards reset to {} and synced.")

    def get_or_create_card(self, user_id: str, user_name: str):
        if str(user_id) in self.user_cards:
            return self.user_cards[str(user_id)], False

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



async def get_or_fetch_target_channel(channel_id: int):
    if not channel_id:
        return None
    ch = bot.get_channel(channel_id)
    if not ch:
        try:
            ch = await bot.fetch_channel(channel_id)
        except Exception:
            ch = None
    return ch

def get_current_race_password() -> str:
    prizes = safe_load_json(PRIZES_CONFIG_FILE, {})
    if isinstance(prizes, dict) and prizes.get("race_password"):
        return str(prizes["race_password"]).strip()
    return os.getenv("RACE_PASSWORD", "LOKI2026").strip()


def render_bingo_card_image(title: str, player_name: str, seed: str, raffle_number: int, cells: list, race_password: str = None) -> io.BytesIO:
    width, height = 860, 1020
    img = Image.new("RGB", (width, height), color="#141414")
    draw = ImageDraw.Draw(img)

    if not race_password:
        race_password = get_current_race_password()

    # Top Header Box (Enlarged +50% Font Styling)
    draw.rectangle([35, 30, 825, 175], fill="#1e1e1e", outline="#383838", width=2)
    
    # 50% Increased Font Sizes
    title_font = get_cross_platform_font(42, is_bold=True)     # 28 -> 42 (+50%)
    meta_font = get_cross_platform_font(20, is_bold=True)      # 13 -> 20 (+50%)
    pass_font = get_cross_platform_font(18, is_bold=True)      # +50% Password font
    letter_font = get_cross_platform_font(33, is_bold=True)    # 22 -> 33 (+50%)
    cell_font = get_cross_platform_font(18, is_bold=False)     # 12 -> 18 (+50%)
    cell_font_bold = get_cross_platform_font(18, is_bold=True)# 12 -> 18 (+50%)

    # Header Text
    draw.text((430, 62), title, fill="#ffffff", font=title_font, anchor="mm")
    draw.text((430, 110), f"Player: {player_name}  |  🎟️ Raffle Ticket #{raffle_number}", fill="#eab308", font=meta_font, anchor="mm")
    draw.text((430, 148), f"🔑 Official Race Password: {race_password}", fill="#22c55e", font=pass_font, anchor="mm")

    letters = ["B", "I", "N", "G", "O"]
    cell_w, cell_h = 150, 150
    start_x, start_y = 45, 195

    # Column B-I-N-G-O Headers
    for col in range(5):
        x = start_x + col * cell_w
        draw.rectangle([x, start_y, x + cell_w - 6, start_y + 48], fill="#d32f2f")
        draw.text((x + (cell_w - 6) / 2, start_y + 24), letters[col], fill="#ffffff", font=letter_font, anchor="mm")

    # 5x5 Cells
    grid_y = start_y + 56
    for idx, cell in enumerate(cells):
        row = idx // 5
        col = idx % 5
        x = start_x + col * cell_w
        y = grid_y + row * cell_h
        w, h = cell_w - 6, cell_h - 6

        bg_color = "#2a1f11" if cell["is_free"] else "#1e1e1e"
        border_color = "#eab308" if cell["is_free"] else "#383838"
        text_color = "#eab308" if cell["is_free"] else "#ffffff"

        draw.rectangle([x, y, x + w, y + h], fill=bg_color, outline=border_color, width=2 if cell["is_free"] else 1)

        # Multi-line word wrapping with 18px font (+50%)
        words = cell["text"].split()
        lines, current_line = [], ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= 11:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        line_h = 22
        text_start_y = y + (h - len(lines) * line_h) / 2 + 10
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

    async def send_to_channel(self, channel_id: int, content: str = None, embed: discord.Embed = None, file: discord.File = None) -> bool:
        """Auto-deploys messages natively to the configured channel ID without webhooks."""
        if not channel_id:
            return False
        try:
            channel = self.get_channel(channel_id)
            if not channel:
                channel = await self.fetch_channel(channel_id)
            if channel:
                await channel.send(content=content, embed=embed, file=file)
                return True
        except Exception as e:
            logger.warning(f"[AUTO-DEPLOY] Could not send to channel {channel_id}: {e}")
        return False

    async def setup_hook(self):
        try:
            await self.tree.sync()
            logger.info("Weekend at Loki's slash commands synced (v7.0 Storage Anchored).")
        except Exception as e:
            logger.warning(f"Sync note: {e}")

    async def on_ready(self):
        activity = discord.Activity(type=discord.ActivityType.watching, name="Weekend at Loki's | /bingo-card")
        await self.change_presence(activity=activity)
        logger.info(f"🤖 WALL-E connected as {self.user} for Weekend at Loki's!")

    async def on_message(self, message: discord.Message):
        """Listens for 'Start New Game' push notification webhooks from the website to auto-clear session_cards.json."""
        if message.author.id == self.user.id:
            return

        is_new_session_alert = False
        content_lower = (message.content or "").lower()
        if "a new weekend at loki's bingo session has started" in content_lower or "fresh bingo session started" in content_lower:
            is_new_session_alert = True

        for embed in message.embeds:
            title_lower = (embed.title or "").lower()
            desc_lower = (embed.description or "").lower()
            if "fresh bingo session started" in title_lower or "new weekend at loki's bingo" in title_lower or "all previous cards have been cleared" in desc_lower:
                is_new_session_alert = True
                break

        if is_new_session_alert:
            logger.info("🤖 WALL-E intercepted New Session webhook from website! Wiping session_cards.json & auto-syncing to GitHub...")
            self.session.start_new_game()
            try:
                await message.add_reaction("🤖")
                await message.add_reaction("🧹")
            except Exception:
                pass

        await self.process_commands(message)

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


# 2. FORCE RELOAD STATE FROM DISK (v7.0)
@bot.tree.command(name="bingo-reload-disk", description="Forces bot to reload or clear in-memory state directly from disk")
async def cmd_bingo_reload_disk(interaction: discord.Interaction):
    bot.session.load_all()
    count = len(bot.session.user_cards)
    embed = discord.Embed(
        title="🔄 Bot Storage Reloaded from Disk",
        description=f"**File Location:** `{SESSION_CARDS_FILE}`\n**Active In-Memory Cards:** `{count}`\n**Drawn Words Count:** `{len(bot.session.drawn_words)}`\n\n*(If you deleted `session_cards.json`, memory is now 0 cards)*",
        color=0x3b82f6,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Storage Manager")
    await interaction.response.send_message(embed=embed)


# 3. BINGO SYNC EXPORT & ALIAS /bingo-card-export
async def handle_sync_export(interaction: discord.Interaction):
    cards = bot.session.user_cards
    count = len(cards)
    json_str = json.dumps({"sessionCards": cards}, indent=2)
    buf = io.BytesIO(json_str.encode("utf-8"))
    file = discord.File(buf, filename="session_cards.json")

    gh_status = "Not configured in .env (Use file upload on website)"
    if GITHUB_TOKEN and GITHUB_REPO:
        gh_status = f"Configured for `{GITHUB_REPO}` on branch `{GITHUB_BRANCH}`"

    embed = discord.Embed(
        title="🗂️ Weekend at Loki's — Session Cards Export",
        description=f"Exported **{count} claimed Bingo cards** with sequential Raffle Tickets from memory & `session_cards.json`.\n\n**File on Disk:** `{SESSION_CARDS_FILE}`\n\n**To Sync to Web Dashboard:**\n1. In the Web GUI, go to **Claimed Cards** tab.\n2. Click **Load Discord `session_cards.json`** and select this file, or click **Paste Sync**.\n\n**GitHub Auto-Sync Status:**\n`{gh_status}`",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Session Cards Bridge")
    await interaction.response.send_message(embed=embed, file=file, ephemeral=False)

@bot.tree.command(name="bingo-sync-export", description="Export all claimed Discord Bingo cards to JSON for 1-click site sync")
async def cmd_bingo_sync_export(interaction: discord.Interaction):
    await handle_sync_export(interaction)

@bot.tree.command(name="bingo-card-export", description="Export all claimed Discord Bingo cards to JSON (alias)")
async def cmd_bingo_card_export(interaction: discord.Interaction):
    await handle_sync_export(interaction)


# 4. PUSH CARDS TO GITHUB REPO WITH LIVE DIAGNOSTICS
@bot.tree.command(name="bingo-push-repo", description="Push session_cards.json directly to GitHub repository with status report")
async def cmd_bingo_push_repo(interaction: discord.Interaction):
    await interaction.response.defer()
    cards = bot.session.user_cards
    count = len(cards)

    success, message = await asyncio.to_thread(
        sync_file_to_github_repo,
        "session_cards.json",
        cards,
        f"Manual sync session_cards.json ({count} cards) via /bingo-push-repo"
    )

    embed = discord.Embed(
        title="🌐 GitHub Repository Auto-Sync Report",
        description=f"**Status:** {'✅ **SUCCESS**' if success else '❌ **FAILED**'}\n\n**Details:**\n`{message}`\n\n**Target Repository:** `{GITHUB_REPO or 'None'}`\n**Branch:** `{GITHUB_BRANCH}`\n**Total Locked Cards:** `{count}`",
        color=0x22c55e if success else 0xef4444,
        timestamp=datetime.now(timezone.utc)
    )
    if not success:
        embed.add_field(
            name="💡 Troubleshooting",
            value="1. Verify `GITHUB_TOKEN` and `GITHUB_REPO=username/repo-name` in `.env`.\n2. Ensure your token has **Contents: Read and write** permissions.\n3. Alternatively, use `/bingo-sync-export` to download and import manually.",
            inline=False
        )
    await interaction.followup.send(embed=embed)


# 5. START NEW GAME (RESET TICKETS & PURGE MEMORY)
@bot.tree.command(name="bingo-new-game", description="Start a fresh match (resets cards and raffle numbers back to #1)")
async def cmd_bingo_new_game(interaction: discord.Interaction):
    bot.session.start_new_game()
    embed = discord.Embed(
        title="🚀 FRESH WEEKEND AT LOKI'S BINGO SESSION STARTED!",
        description="All previous cards and drawn words have been purged from bot memory and disk!\n\n👉 Type `/bingo-card` to generate your **1 fresh Bingo card & sequential Raffle Ticket** (starting at Ticket #1)!",
        color=0x22c55e,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="🎟️ Sequential Tickets", value="Assigned in order of sign-up (Ticket #1, #2, #3...).", inline=False)
    embed.set_footer(text="Weekend at Loki's • Hosted by Loki")
    await interaction.response.send_message(content="@everyone 🎉 **NEW BINGO SESSION IS LIVE!**", embed=embed)


# 6. RAFFLE ROLLER (DRAWS FROM CLAIMED CARDS ROSTER)
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
        description=f"Congratulations to our winning ticket from the claimed Bingo cards roster!\n\n👑 **Winning Ticket:** `#{ticket_num} - {winner_name}`\n🎁 **Prize:** **${prize}**",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="Weekend at Loki's • Faction Vault")
    await interaction.response.send_message(content="@everyone 🏆 **RAFFLE WINNER DRAWN!**", embed=embed)


# 7. WEEKEND AT LOKI'S ANNOUNCEMENT


@bot.tree.command(name="bingo-jumble", description="Push a standalone scrambled Word Jumble challenge (secret answer)")
async def cmd_bingo_jumble(interaction: discord.Interaction):
    remaining = [w for w in bot.session.word_pool if w not in bot.session.drawn_words]
    if not remaining:
        await interaction.response.send_message("❌ All words drawn! Use `/bingo-new-game` to start a fresh match.", ephemeral=True)
        return

    actual_target = random.choice(remaining)
    scrambled = scramble_word(actual_target)
    drawn = bot.session.draw_words(1, "Standalone Jumble", scrambled, actual_target)
    call_num = len(bot.session.drawn_words)
    logger.info(f"[STANDALONE JUMBLE] Scrambled: '{scrambled}' -> Secret Answer: '{actual_target}' (Consumed #{call_num})")

    embed = discord.Embed(
        title="🧩 WEEKEND AT LOKI'S — STANDALONE MYSTERY WORD JUMBLE!",
        description=f"Unscramble to identify this drawn item (Call #{call_num}):\n\n## `{scrambled.upper()}`\n\n*(This item is officially consumed and will not be re-drawn.)*",
        color=0xa855f7,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=f"Call #{call_num} / {len(bot.session.word_pool)} | Weekend at Loki's")
    await interaction.response.send_message(content="🔀 **LOKI'S STANDALONE WORD JUMBLE!**", embed=embed)


# 11. WINNERS & VAULT PAYOUTS

@bot.tree.command(name="bug-report", description="Report a bug or issue with Weekend at Loki's (logged to bug_reports.json)")
@app_commands.describe(
    description="Detailed description of what went wrong or the unexpected behavior",
    severity="Severity level of the bug",
    feature="Which feature or tab had the issue"
)
@app_commands.choices(severity=[
    app_commands.Choice(name="🟢 Low (Visual / Minor typo)", value="Low"),
    app_commands.Choice(name="🟡 Medium (Feature glitch / Workaround available)", value="Medium"),
    app_commands.Choice(name="🔴 High (Feature broken / Impaired)", value="High"),
    app_commands.Choice(name="🔥 Critical (Bot crash / Session blocker)", value="Critical"),
])
@app_commands.choices(feature=[
    app_commands.Choice(name="🎯 Bingo Cards & Generator", value="Bingo Cards"),
    app_commands.Choice(name="💥 Word Drops & Jumbles", value="Word Drops & Jumbles"),
    app_commands.Choice(name="🏎️ 3-Day Race Scheduler", value="Race Scheduler"),
    app_commands.Choice(name="🎟️ Raffles & Tickets", value="Raffles"),
    app_commands.Choice(name="🏆 Winner Payouts & Vault", value="Winner Payouts"),
    app_commands.Choice(name="📣 Announcements & RSVP", value="Announcements"),
    app_commands.Choice(name="🌐 Web GUI & Sync", value="Web GUI & Sync"),
    app_commands.Choice(name="⚙️ Other / General", value="General"),
])
async def cmd_bug_report(
    interaction: discord.Interaction,
    description: str,
    severity: app_commands.Choice[str] = None,
    feature: app_commands.Choice[str] = None
):
    sev_val = severity.value if severity else "Medium"
    feat_val = feature.value if feature else "General"
    reporter_name = interaction.user.display_name
    reporter_id = str(interaction.user.id)

    record = LogManager.append_bug_report(
        reporter_name=reporter_name,
        reporter_id=reporter_id,
        description=description,
        severity=sev_val,
        feature=feat_val
    )

    sev_colors = {
        "Low": 0x22c55e,
        "Medium": 0xeab308,
        "High": 0xf97316,
        "Critical": 0xd32f2f
    }
    color = sev_colors.get(sev_val, 0xeab308)

    embed = discord.Embed(
        title=f"🐞 Bug Report Logged: `{record['id']}`",
        description="Thank you for reporting! The issue has been recorded to **`bug_reports.json`**.",
        color=color,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="📋 Description", value=description[:1000], inline=False)
    embed.add_field(name="🏷️ Feature", value=f"`{feat_val}`", inline=True)
    embed.add_field(name="⚡ Severity", value=f"`{sev_val}`", inline=True)
    embed.add_field(name="👤 Reporter", value=f"{reporter_name} (`{reporter_id}`)", inline=True)
    embed.add_field(name="📌 Status", value="`OPEN`", inline=True)
    embed.set_footer(text="Weekend at Loki's • Bug Tracking System")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="bug-list", description="View logged bug reports from bug_reports.json")
@app_commands.describe(status="Filter by status (All, Open, Resolved)")
@app_commands.choices(status=[
    app_commands.Choice(name="All Statuses", value="ALL"),
    app_commands.Choice(name="Open Only", value="OPEN"),
    app_commands.Choice(name="Resolved Only", value="RESOLVED"),
])
async def cmd_bug_list(interaction: discord.Interaction, status: app_commands.Choice[str] = None):
    filter_status = status.value if status else "OPEN"
    records = safe_load_json(BUG_REPORTS_FILE, [])
    if not isinstance(records, list) or not records:
        await interaction.response.send_message("✅ No bug reports logged in `bug_reports.json`.", ephemeral=True)
        return

    filtered = [r for r in records if filter_status == "ALL" or r.get("status") == filter_status]
    if not filtered:
        await interaction.response.send_message(f"✅ No bugs matching status `{filter_status}`.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🐞 Bug Reports Log ({len(filtered)} items - Filter: {filter_status})",
        description="Recent entries from **`bug_reports.json`**:",
        color=0xd32f2f,
        timestamp=datetime.now(timezone.utc)
    )
    for b in filtered[-6:]:
        status_icon = "🟢" if b.get("status") == "RESOLVED" else "🔴"
        b_id = b.get('id', 'BUG')
        b_feat = b.get('feature', 'General')
        b_sev = b.get('severity', 'Med')
        b_rep = b.get('reporterName', 'User')
        b_stat = b.get('status', 'OPEN')
        b_desc = b.get('description', '')[:120]
        embed.add_field(
            name=f"{status_icon} [{b_id}] {b_feat} ({b_sev})",
            value=f"**Reporter:** {b_rep} | **Status:** `{b_stat}`\n**Issue:** {b_desc}",
            inline=False
        )
    embed.set_footer(text="Weekend at Loki's • bug_reports.json")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="bug-resolve", description="Mark a logged bug report as RESOLVED")
@app_commands.describe(bug_id="The ID of the bug to resolve (e.g. BUG-1001)")
async def cmd_bug_resolve(interaction: discord.Interaction, bug_id: str):
    success, msg = LogManager.update_bug_status(bug_id, "RESOLVED")
    if success:
        embed = discord.Embed(
            title=f"✅ Bug Resolved: `{bug_id.upper()}`",
            description=f"The bug status has been updated to **RESOLVED** in `bug_reports.json`.",
            color=0x22c55e,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Resolved by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"❌ {msg}", ephemeral=True)


@bot.tree.command(name="bug-export", description="Export all logged bug reports as a downloadable JSON file")
async def cmd_bug_export(interaction: discord.Interaction):
    records = safe_load_json(BUG_REPORTS_FILE, [])
    if not isinstance(records, list):
        records = []
    buf = io.BytesIO(json.dumps(records, indent=2).encode("utf-8"))
    file = discord.File(buf, filename="bug_reports.json")
    await interaction.response.send_message(
        content=f"🐞 Attached **`bug_reports.json`** containing **{len(records)}** logged bug reports.",
        file=file,
        ephemeral=True
    )



# 13. PRIZE AWARDING & EPHEMERAL QUERIES (v7.0)


@bot.tree.command(name="prize-pool", description="View the current prize pool for Raffles, Races, Bingo & Jumbles (Visible only to you)")
async def cmd_prize_pool(interaction: discord.Interaction):
    prizes = get_configured_prizes()

    embed = discord.Embed(
        title="🎁 Weekend at Loki's — Current Prize Pool Matrix",
        description="Here is the full breakdown of prizes configured for this weekend's events:",
        color=0xeab308,
        timestamp=datetime.now(timezone.utc)
    )

    # 1. 3-Day Raffles
    p_raf1 = prizes.get('raffle_day1', '50x Xanax')
    p_raf2 = prizes.get('raffle_day2', '5x Box of Medical Supplies')
    p_raf3 = prizes.get('raffle_day3', '1x Donator Pack + 50x Xanax')
    raffle_text = (
        f"• **Day 1 Raffle:** {p_raf1}\n"
        f"• **Day 2 Raffle:** {p_raf2}\n"
        f"• **Day 3 Grand Raffle:** {p_raf3}"
    )
    embed.add_field(name="🎟️ 3-Day Faction Raffles", value=raffle_text, inline=False)

    # 2. Race Series
    b1, b2, b3, bl = prizes.get('race_bronze_1st', '10x Xanax'), prizes.get('race_bronze_2nd', '5x'), prizes.get('race_bronze_3rd', '2x'), prizes.get('race_bronze_last', '1x')
    s1, s2, s3, sl = prizes.get('race_silver_1st', '25x Xanax'), prizes.get('race_silver_2nd', '15x'), prizes.get('race_silver_3rd', '5x'), prizes.get('race_silver_last', '2x')
    g1, g2, g3, gl = prizes.get('race_gold_1st', '50x Xanax'), prizes.get('race_gold_2nd', '25x'), prizes.get('race_gold_3rd', '10x'), prizes.get('race_gold_last', '5x')

    race_text = (
        f"🥉 **Bronze Series:** 1st: `{b1}` | 2nd: `{b2}` | 3rd: `{b3}` | Last: `{bl}`\n"
        f"🥈 **Silver Series:** 1st: `{s1}` | 2nd: `{s2}` | 3rd: `{s3}` | Last: `{sl}`\n"
        f"🥇 **Gold Series:** 1st: `{g1}` | 2nd: `{g2}` | 3rd: `{g3}` | Last: `{gl}`"
    )
    embed.add_field(name="🏎️ 3-Day Race Series (Tiered)", value=race_text, inline=False)

    # 3. Bingo & Jumbles
    p_bline = prizes.get('bingo_prize', prizes.get('bingo_line', '25x Xanax'))
    p_bblack = prizes.get('bingo_blackout', '100x Xanax + 2x Donator Pack')
    p_jfast = prizes.get('jumble_fast', '5x Xanax per Drop')
    bingo_text = (
        f"• **Bingo Prize:** {p_bline}\n"
        f"• **Full Card Blackout:** {p_bblack}\n"
        f"• **Fastest Jumble Solver:** {p_jfast}"
    )
    embed.add_field(name="🎯 Bingo & Mystery Jumbles", value=bingo_text, inline=False)

    embed.set_footer(text="Private View • Weekend at Loki's Prize Vault")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="called-words", description="View all called Bingo items so far with Jumbles remaining scrambled (Visible only to you)")
async def cmd_called_words(interaction: discord.Interaction):
    # Dynamic reload: reflect any words called from the website or disk immediately
    bot.session.load_all()
    # Dynamic reload to catch any words called from the website
    bot.session.load_state()
    draw_logs = safe_load_json(DRAWS_LOG_FILE, [])
    drawn_list = bot.session.drawn_words
    total_pool = len(bot.session.word_pool)

    if not drawn_list and not draw_logs:
        await interaction.response.send_message(
            "ℹ️ No Bingo words have been called yet in this session! Use `/bingo-card` to claim your card.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎯 Weekend at Loki's — Official Called Words Tracker",
        description=f"**Total Consumed:** {len(drawn_list)} / {total_pool} items in pool.\n*(All Jumble challenges remain strictly scrambled to keep the game fair!)*",
        color=0x3b82f6,
        timestamp=datetime.now(timezone.utc)
    )

    # Map each word to its scrambled version if it was drawn as a jumble
    scramble_map = {}
    if isinstance(draw_logs, list):
        for log in draw_logs:
            w = log.get("word") or log.get("jumbleAnswer")
            scramble = log.get("jumbleScramble") or log.get("scramble")
            if w and scramble:
                scramble_map[w] = scramble.upper()

    # Build display lines
    lines = []
    for idx, word in enumerate(drawn_list):
        call_num = idx + 1
        if word in scramble_map:
            lines.append(f"**#{call_num}:** 🧩 *Jumble Challenge:* **`{scramble_map[word]}`**")
        else:
            lines.append(f"**#{call_num}:** {word}")

    # Chunk lines if long (Discord embed field value max is 1024 chars)
    chunk_size = 18
    chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]

    for c_idx, chunk in enumerate(chunks):
        field_name = f"📋 Called Items ({c_idx * chunk_size + 1} - {min(len(lines), (c_idx + 1) * chunk_size)})"
        embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

    embed.set_footer(text="Private View • Jumble Answers Remain Secret • Weekend at Loki's")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# RACE SCHEDULE COMMAND (Reads scheduled_races_log.json set by Companion / Site)
@bot.tree.command(name="race-schedule", description="View the current 3-Day Race Series Schedule (Visible only to you)")
async def cmd_race_schedule(interaction: discord.Interaction):
    schedules = safe_load_json(SCHEDULED_RACES_FILE, [])
    
    embed = discord.Embed(
        title="🏎️ Weekend at Loki's — 3-Day Race Series Schedule",
        description="**Tournament Requirement:** 25 Laps Endurance • Stock Class E Only",
        color=0x10b981,
        timestamp=datetime.now(timezone.utc)
    )

    if isinstance(schedules, list) and schedules:
        latest = schedules[-1]
        title = latest.get("title", "Loki's 3-Day Stock Class E Series")
        s1 = latest.get("stage1", {})
        s2 = latest.get("stage2", {})
        s3 = latest.get("stage3", {})
        notes = latest.get("notes", "")

        embed.add_field(name="🏆 Tournament Title", value=f"**{title}**", inline=False)
        embed.add_field(
            name="📅 Stage 1 (Day 1)",
            value=f"**Track:** {s1.get('track', 'Mudpit')} | **Laps:** {s1.get('laps', 25)} | **Class:** {s1.get('car_class', 'Stock E')}\n**Start:** `{s1.get('time', s1.get('date', 'Friday 18:00 TCT'))}`",
            inline=False
        )
        embed.add_field(
            name="📅 Stage 2 (Day 2)",
            value=f"**Track:** {s2.get('track', 'Hammerhead')} | **Laps:** {s2.get('laps', 25)} | **Class:** {s2.get('car_class', 'Stock E')}\n**Start:** `{s2.get('time', s2.get('date', 'Saturday 18:00 TCT'))}`",
            inline=False
        )
        embed.add_field(
            name="📅 Stage 3 (Day 3 Finals)",
            value=f"**Track:** {s3.get('track', 'Two Islands')} | **Laps:** {s3.get('laps', 25)} | **Class:** {s3.get('car_class', 'Stock E')}\n**Start:** `{s3.get('time', s3.get('date', 'Sunday 18:00 TCT'))}`",
            inline=False
        )
        if notes:
            embed.add_field(name="📝 Tournament Notes", value=notes, inline=False)
    else:
        embed.add_field(
            name="📅 Default Tournament Format",
            value="Stage 1: **Mudpit** (25 Laps • Stock Class E)\nStage 2: **Hammerhead** (25 Laps • Stock Class E)\nStage 3: **Two Islands** (25 Laps • Stock Class E)",
            inline=False
        )
        embed.add_field(name="ℹ️ Notice", value="No custom schedule configured yet. Configure one in the **Windows Companion Program** or Web GUI.", inline=False)

    embed.set_footer(text="Private View • Weekend at Loki's Racing")
    await interaction.response.send_message(embed=embed, ephemeral=True)


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
