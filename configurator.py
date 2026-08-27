#!/usr/bin/env python3
"""
================================================================================
WEEKEND AT LOKI'S - WINDOWS DESKTOP COMPANION CONFIGURATOR (v7.0)
================================================================================
A desktop configuration and management GUI for Windows to configure:
 - Discord Bot Token, Presence & Channel Settings
 - 4 Dedicated Webhook URLs (Announcements, Bingo, Racing, Raffles) & Avatars
 - Torn City API Key & Connection Testing
 - GitHub Sync Token & Repo Target
 - Word Bank & Item Pool Editor (bingo_state.json)
 - Event Prize Configuration Matrix
 - Live Bot Process Manager (Start / Stop Bot / View Live Logs)
 - Session Reset & Bug Report Viewer

Requirements: Python 3.10+ (Standard Library: tkinter, json, urllib, subprocess)
================================================================================
"""

import os
import sys
import json
import time
import queue
import threading
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, scrolledtext
except ImportError:
    print("[ERROR] Tkinter is required for the Windows GUI. On Windows, Python includes Tkinter by default.")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")
ENV_EXAMPLE = os.path.join(BASE_DIR, ".env.example")
STATE_FILE = os.path.join(BASE_DIR, "bingo_state.json")
SESSION_CARDS_FILE = os.path.join(BASE_DIR, "session_cards.json")
BUG_REPORTS_FILE = os.path.join(BASE_DIR, "bug_reports.json")
WINNERS_LOG_FILE = os.path.join(BASE_DIR, "winners_log.json")
PRIZES_CONFIG_FILE = os.path.join(BASE_DIR, "prizes_config.json")

DEFAULT_ITEMS = [
    "Xanax", "Vicodin", "Ecstasy", "Speed", "Opium", "Blood Bag : A+", "Blood Bag : O-",
    "Armored Vest", "Liquid Body Armor", "Combat Helmet", "Diamond Bladed Knife",
    "Dual Bushmasters", "Armalite M-15A4", "RPG Launcher", "First Aid Kit", "Morphine",
    "Can of Red Cow", "Can of Rockstar", "Donator Pack", "Point", "Lottery Voucher",
    "Lawyer Business Card", "Feathery Hotel Coupon", "Six-Pack of Alcohol",
    "Box of Medical Supplies", "Box of Grenades", "Drug Pack", "Goodie Bag",
    "Erotic DVD", "Can of Munster", "Can of Tourine Elite", "Can of Santa Shooters",
    "Can of X-MASS", "Bottle of Beer", "Bottle of Tequila", "Bottle of Kandy Kane"
]

# Color Palette: Torn Charcoal & Gold Theme
BG_DARK = "#141414"
PANEL_DARK = "#202020"
WELL_DARK = "#181818"
BORDER_DARK = "#383838"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#9ca3af"
ACCENT_RED = "#d32f2f"
ACCENT_GOLD = "#eab308"
ACCENT_GREEN = "#22c55e"
ACCENT_BLUE = "#3b82f6"
ACCENT_PURPLE = "#a855f7"

def safe_load_json(file_path, default_val):
    if not os.path.exists(file_path):
        return default_val
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else default_val
    except Exception:
        return default_val

def safe_save_json(file_path, data):
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        return False

def load_env_dict():
    env_data = {}
    target = ENV_FILE if os.path.exists(ENV_FILE) else ENV_EXAMPLE
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_data[k.strip()] = v.strip().strip('"').strip("'")
    return env_data

def save_env_dict(env_data):
    lines = [
        "# ==============================================================================",
        "# WEEKEND AT LOKI'S - ENVIRONMENT CONFIGURATION (v7.0)",
        "# Generated via Windows Companion Configurator",
        "# ==============================================================================",
        "",
        "# Discord Bot Token (From Discord Developer Portal)",
        f"DISCORD_TOKEN={env_data.get('DISCORD_TOKEN', '')}",
        "",
        "# Torn City API Key (Minimal / Public Access)",
        f"TORN_API_KEY={env_data.get('TORN_API_KEY', '')}",
        "",
        "# GitHub Auto-Sync Integration (Contents: Read and write)",
        f"GITHUB_TOKEN={env_data.get('GITHUB_TOKEN', '')}",
        f"GITHUB_REPO={env_data.get('GITHUB_REPO', '')}",
        f"GITHUB_BRANCH={env_data.get('GITHUB_BRANCH', 'main')}",
        "",
        "# Official Race Password (Printed on Bingo Cards)",
        f"RACE_PASSWORD={env_data.get('RACE_PASSWORD', 'LOKI2026')}",
        "",
        "# Discord Channel IDs (Direct Bot Routing & Auto Deployment)",
        f"ANNOUNCEMENTS_CHANNEL_ID={env_data.get('ANNOUNCEMENTS_CHANNEL_ID', '')}",
        f"BINGO_CHANNEL_ID={env_data.get('BINGO_CHANNEL_ID', '')}",
        f"RACE_CHANNEL_ID={env_data.get('RACE_CHANNEL_ID', '')}",
        f"RAFFLE_CHANNEL_ID={env_data.get('RAFFLE_CHANNEL_ID', '')}",
        "",
        "# Optional Fallback Webhook URLs",
        f"DISCORD_ANNOUNCEMENTS_WEBHOOK_URL={env_data.get('DISCORD_ANNOUNCEMENTS_WEBHOOK_URL', '')}",
        f"DISCORD_BINGO_WEBHOOK_URL={env_data.get('DISCORD_BINGO_WEBHOOK_URL', '')}",
        f"DISCORD_RACE_WEBHOOK_URL={env_data.get('DISCORD_RACE_WEBHOOK_URL', '')}",
        f"DISCORD_RAFFLE_WEBHOOK_URL={env_data.get('DISCORD_RAFFLE_WEBHOOK_URL', '')}",
        ""
    ]
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return True


class LokisCompanionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Weekend at Loki's — Windows Companion Configurator v7.0")
        self.root.geometry("1020x740")
        self.root.minsize(900, 650)
        self.root.configure(bg=BG_DARK)

        self.bot_process = None
        self.log_queue = queue.Queue()
        self.is_monitoring = False

        self.env_data = load_env_dict()
        self.prizes_data = safe_load_json(PRIZES_CONFIG_FILE, {})

        self.setup_styles()
        self.build_ui()
        self.load_all_data()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TNotebook", background=BG_DARK, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_DARK, foreground=TEXT_MUTED, padding=[14, 8], font=("Impact", 11))
        style.map("TNotebook.Tab", background=[("selected", ACCENT_RED)], foreground=[("selected", TEXT_WHITE)])

        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=PANEL_DARK, relief="flat")

        style.configure("Header.TLabel", background=BG_DARK, foreground=TEXT_WHITE, font=("Impact", 16))
        style.configure("Subheader.TLabel", background=BG_DARK, foreground=TEXT_MUTED, font=("Segoe UI", 9))
        style.configure("CardTitle.TLabel", background=PANEL_DARK, foreground=ACCENT_GOLD, font=("Impact", 12))
        style.configure("FieldLabel.TLabel", background=PANEL_DARK, foreground=TEXT_WHITE, font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background=WELL_DARK, foreground=TEXT_MUTED, font=("Segoe UI", 9))

        style.configure("Primary.TButton", background=ACCENT_RED, foreground=TEXT_WHITE, font=("Impact", 10), borderwidth=0, padding=[12, 6])
        style.map("Primary.TButton", background=[("active", "#b71c1c"), ("disabled", "#4b5563")])

        style.configure("Gold.TButton", background=ACCENT_GOLD, foreground="#000000", font=("Impact", 10), borderwidth=0, padding=[12, 6])
        style.map("Gold.TButton", background=[("active", "#ca8a04")])

        style.configure("Green.TButton", background=ACCENT_GREEN, foreground=TEXT_WHITE, font=("Impact", 10), borderwidth=0, padding=[12, 6])
        style.map("Green.TButton", background=[("active", "#15803d")])

        style.configure("Dark.TButton", background="#374151", foreground=TEXT_WHITE, font=("Segoe UI", 9, "bold"), borderwidth=0, padding=[10, 5])
        style.map("Dark.TButton", background=[("active", "#4b5563")])

    def build_ui(self):
        # 1. Top Header Banner
        header_frame = tk.Frame(self.root, bg=PANEL_DARK, height=64, padx=16, pady=10, highlightthickness=1, highlightbackground=BORDER_DARK)
        header_frame.pack(fill="x", side="top")

        title_label = tk.Label(header_frame, text="WEEKEND AT LOKI'S", font=("Impact", 18), fg=TEXT_WHITE, bg=PANEL_DARK)
        title_label.pack(side="left")

        version_badge = tk.Label(header_frame, text="v7.0 Windows Companion", font=("Segoe UI", 9, "bold"), fg=ACCENT_GOLD, bg="#27272a", padx=8, pady=2)
        version_badge.pack(side="left", padx=10)

        # Process status in header
        self.header_status = tk.Label(header_frame, text="● Bot Offline", font=("Segoe UI", 9, "bold"), fg="#ef4444", bg=PANEL_DARK)
        self.header_status.pack(side="right", padx=10)

        self.btn_header_start = tk.Button(header_frame, text="▶ START BOT", font=("Impact", 10), bg=ACCENT_GREEN, fg=TEXT_WHITE, relief="flat", padx=12, pady=4, cursor="hand2", command=self.toggle_bot_process)
        self.btn_header_start.pack(side="right", padx=4)

        # 2. Main Notebook Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=10)

        self.tab_credentials = ttk.Frame(self.notebook)
        self.tab_webhooks = ttk.Frame(self.notebook)
        self.tab_wordbank = ttk.Frame(self.notebook)
        self.tab_prizes = ttk.Frame(self.notebook)
        self.tab_console = ttk.Frame(self.notebook)
        self.tab_tools = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_credentials, text="🔑 BOT & TOKENS")
        self.notebook.add(self.tab_webhooks, text="📡 CHANNEL IDS")
        self.notebook.add(self.tab_wordbank, text="🎯 WORD BANK")
        self.notebook.add(self.tab_prizes, text="🏆 PRIZE CONFIG")
        self.notebook.add(self.tab_console, text="💻 BOT CONSOLE & LOGS")
        self.notebook.add(self.tab_tools, text="⚙️ SESSIONS & BUGS")

        self.build_tab_credentials()
        self.build_tab_webhooks()
        self.build_tab_wordbank()
        self.build_tab_prizes()
        self.build_tab_console()
        self.build_tab_tools()

        # 3. Bottom Status Bar
        bottom_bar = tk.Frame(self.root, bg=WELL_DARK, height=28, padx=12, pady=4, highlightthickness=1, highlightbackground=BORDER_DARK)
        bottom_bar.pack(fill="x", side="bottom")

        self.status_bar_text = tk.Label(bottom_bar, text="Ready. Config loaded from local directory.", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=WELL_DARK)
        self.status_bar_text.pack(side="left")

        save_btn = tk.Button(bottom_bar, text="💾 SAVE ALL SETTINGS (.env & JSON)", font=("Impact", 10), bg=ACCENT_RED, fg=TEXT_WHITE, relief="flat", padx=12, pady=2, cursor="hand2", command=self.save_all_settings)
        save_btn.pack(side="right")

    # --------------------------------------------------------------------------
    # TAB 1: CREDENTIALS, TORN & GITHUB
    # --------------------------------------------------------------------------
    def build_tab_credentials(self):
        frame = tk.Frame(self.tab_credentials, bg=BG_DARK, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        # Discord Bot Token Box
        box_bot = tk.LabelFrame(frame, text=" DISCORD BOT TOKEN ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_bot.pack(fill="x", pady=6)

        tk.Label(box_bot, text="Bot Token (From Discord Developer Portal):", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=0, column=0, sticky="w", pady=2)
        self.ent_discord_token = tk.Entry(box_bot, font=("Consolas", 10), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=70, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_discord_token.grid(row=1, column=0, sticky="we", pady=4, padx=(0, 10))

        # Torn City API Box
        box_torn = tk.LabelFrame(frame, text=" TORN CITY API ACCESS ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_torn.pack(fill="x", pady=6)

        tk.Label(box_bot, text="🏎️ Current Race Password (Printed on every Bingo Card):", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=2, column=0, sticky="w", pady=(6, 2))
        self.ent_race_password = tk.Entry(box_bot, font=("Consolas", 10, "bold"), bg=WELL_DARK, fg=ACCENT_GOLD, insertbackground="white", width=30, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_race_password.grid(row=3, column=0, sticky="w", pady=2)

        tk.Label(box_torn, text="Torn API Key (16 Characters - Minimal / Public Access):", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=0, column=0, sticky="w", pady=2)
        self.ent_torn_key = tk.Entry(box_torn, font=("Consolas", 10), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=50, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_torn_key.grid(row=1, column=0, sticky="w", pady=4)

        btn_test_torn = tk.Button(box_torn, text="⚡ TEST TORN KEY", font=("Segoe UI", 9, "bold"), bg="#2563eb", fg=TEXT_WHITE, relief="flat", padx=10, pady=3, cursor="hand2", command=self.test_torn_api)
        btn_test_torn.grid(row=1, column=1, padx=10)

        self.lbl_torn_status = tk.Label(box_torn, text="Status: Not Verified", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_DARK)
        self.lbl_torn_status.grid(row=2, column=0, sticky="w", pady=2)

        # GitHub Repo Sync Box
        box_gh = tk.LabelFrame(frame, text=" GITHUB REPOSITORY SYNC ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_gh.pack(fill="x", pady=6)

        tk.Label(box_gh, text="Personal Access Token (Contents: Read and write):", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=0, column=0, sticky="w", pady=2)
        self.ent_gh_token = tk.Entry(box_gh, font=("Consolas", 10), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=70, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_gh_token.grid(row=1, column=0, columnspan=2, sticky="we", pady=4)

        tk.Label(box_gh, text="Repository (Format: username/repository-name):", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=2, column=0, sticky="w", pady=2)
        self.ent_gh_repo = tk.Entry(box_gh, font=("Consolas", 10), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=40, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_gh_repo.grid(row=3, column=0, sticky="w", pady=4)

        btn_test_gh = tk.Button(box_gh, text="🔍 TEST GITHUB ACCESS", font=("Segoe UI", 9, "bold"), bg="#059669", fg=TEXT_WHITE, relief="flat", padx=10, pady=3, cursor="hand2", command=self.test_github_repo)
        btn_test_gh.grid(row=3, column=1, sticky="w", padx=10)

        tk.Label(box_gh, text="Branch (Default: main):", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=4, column=0, sticky="w", pady=2)
        self.ent_gh_branch = tk.Entry(box_gh, font=("Consolas", 10), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=20, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_gh_branch.grid(row=5, column=0, sticky="w", pady=4)

        self.lbl_gh_status = tk.Label(box_gh, text="Status: Not Tested", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_DARK)
        self.lbl_gh_status.grid(row=6, column=0, sticky="w", pady=2)

    # --------------------------------------------------------------------------
    # TAB 2: DISCORD CHANNEL IDS (AUTO-DEPLOY ROUTING - NO WEBHOOKS)
    # --------------------------------------------------------------------------
    def build_tab_channels(self):
        canvas = tk.Canvas(self.tab_channels, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_channels, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_DARK, padx=16, pady=12)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.channel_entries = {}

        box_ch = tk.LabelFrame(scroll_frame, text=" 📡 DISCORD CHANNEL IDS (DIRECT AUTO DEPLOYMENT) ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_ch.pack(fill="x", pady=6)

        tk.Label(box_ch, text="Set your Discord Channel IDs here. The bot directly auto-deploys race schedules, raffle rolls, and bingo cards to the right place without needing webhooks.", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_DARK, wraplength=700, justify="left").pack(anchor="w", pady=(0, 8))

        channels = [
            ("ANNOUNCEMENTS_CHANNEL_ID", "📣 Announcements Channel ID:", "For event notices, date setters & 🎉 reaction roster"),
            ("BINGO_CHANNEL_ID", "🎯 Bingo Channel ID:", "For Bingo calls, 5-Word Drops, Jumbles & Card claims"),
            ("RACE_CHANNEL_ID", "🏎️ Racing Channel ID:", "For 3-Day Tournament schedules & live race alerts"),
            ("RAFFLE_CHANNEL_ID", "🎟️ Raffles Channel ID:", "For giveaway ticket rolls & winner announcements")
        ]

        for idx, (key, label_txt, sub_txt) in enumerate(channels):
            row_frame = tk.Frame(box_ch, bg=PANEL_DARK)
            row_frame.pack(fill="x", pady=4)

            tk.Label(row_frame, text=label_txt, font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK, width=28, anchor="w").pack(side="left")
            ent = tk.Entry(row_frame, font=("Consolas", 10, "bold"), bg=WELL_DARK, fg=ACCENT_GOLD, insertbackground="white", width=30, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent.pack(side="left", padx=4)
            self.channel_entries[key] = ent

            tk.Label(row_frame, text=f"({sub_txt})", font=("Segoe UI", 8, "italic"), fg=TEXT_MUTED, bg=PANEL_DARK).pack(side="left", padx=6)

        # Helper info box on how to get Discord Channel IDs
        box_help = tk.LabelFrame(scroll_frame, text=" 💡 HOW TO FIND CHANNEL IDS IN DISCORD ", font=("Impact", 10), fg=ACCENT_BLUE, bg=WELL_DARK, padx=12, pady=8, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_help.pack(fill="x", pady=8)

        help_text = (
            "1. In Discord, go to User Settings (⚙️) -> Advanced -> Enable 'Developer Mode'.\n"
            "2. Right-click any channel (#announcements, #bingo, #racing, #raffles) and click 'Copy Channel ID'.\n"
            "3. Paste the numeric ID above and click 'SAVE ALL SETTINGS'."
        )
        tk.Label(box_help, text=help_text, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=WELL_DARK, justify="left").pack(anchor="w")

    def build_tab_races_cfg(self):
        canvas = tk.Canvas(self.tab_races_cfg, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_races_cfg, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_DARK, padx=16, pady=12)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        box_race_main = tk.LabelFrame(scroll_frame, text=" 🏎️ 3-DAY RACE TOURNAMENT SCHEDULE (scheduled_races_log.json) ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_race_main.pack(fill="x", pady=6)

        tk.Label(box_race_main, text="Configure the 3-day racing tournament schedule here. Players can view this anytime in Discord using the /race-schedule command.", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_DARK).pack(anchor="w", pady=(0, 8))

        # Title
        f_title = tk.Frame(box_race_main, bg=PANEL_DARK)
        f_title.pack(fill="x", pady=4)
        tk.Label(f_title, text="Tournament Title:", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK, width=20, anchor="w").pack(side="left")
        self.ent_race_title = tk.Entry(f_title, font=("Segoe UI", 9, "bold"), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=45, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_race_title.pack(side="left", padx=4)
        self.ent_race_title.insert(0, "Loki's 3-Day Stock Class E Endurance Series")

        btn_random_tracks = tk.Button(f_title, text="🎲 ROLL RANDOM TRACKS", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg=TEXT_WHITE, relief="flat", padx=10, pady=2, cursor="hand2", command=self.roll_random_race_tracks)
        btn_random_tracks.pack(side="left", padx=10)

        # Stages 1, 2, 3
        self.race_stage_entries = {}
        stage_defaults = [
            (1, "Stage 1 (Day 1)", "Mudpit", "25", "Stock Class E", "Friday 18:00 TCT"),
            (2, "Stage 2 (Day 2)", "Hammerhead", "25", "Stock Class E", "Saturday 18:00 TCT"),
            (3, "Stage 3 (Day 3 Finals)", "Two Islands", "25", "Stock Class E", "Sunday 18:00 TCT")
        ]

        for s_num, s_label, def_track, def_laps, def_class, def_time in stage_defaults:
            s_box = tk.LabelFrame(box_race_main, text=f" 📅 {s_label} ", font=("Impact", 10), fg=ACCENT_RED, bg=WELL_DARK, padx=10, pady=8, highlightthickness=1, highlightbackground=BORDER_DARK)
            s_box.pack(fill="x", pady=5)

            grid_f = tk.Frame(s_box, bg=WELL_DARK)
            grid_f.pack(fill="x")

            # Track
            tk.Label(grid_f, text="Track:", font=("Segoe UI", 8, "bold"), fg=TEXT_WHITE, bg=WELL_DARK).grid(row=0, column=0, sticky="w", padx=4, pady=2)
            ent_track = tk.Entry(grid_f, font=("Segoe UI", 9), bg=PANEL_DARK, fg=TEXT_WHITE, insertbackground="white", width=18, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent_track.grid(row=0, column=1, padx=4, pady=2)
            ent_track.insert(0, def_track)

            # Laps
            tk.Label(grid_f, text="Laps:", font=("Segoe UI", 8, "bold"), fg=TEXT_WHITE, bg=WELL_DARK).grid(row=0, column=2, sticky="w", padx=4, pady=2)
            ent_laps = tk.Entry(grid_f, font=("Segoe UI", 9), bg=PANEL_DARK, fg=TEXT_WHITE, insertbackground="white", width=6, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent_laps.grid(row=0, column=3, padx=4, pady=2)
            ent_laps.insert(0, def_laps)

            # Car Class
            tk.Label(grid_f, text="Class:", font=("Segoe UI", 8, "bold"), fg=TEXT_WHITE, bg=WELL_DARK).grid(row=0, column=4, sticky="w", padx=4, pady=2)
            ent_class = tk.Entry(grid_f, font=("Segoe UI", 9), bg=PANEL_DARK, fg=TEXT_WHITE, insertbackground="white", width=16, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent_class.grid(row=0, column=5, padx=4, pady=2)
            ent_class.insert(0, def_class)

            # Start Time
            tk.Label(grid_f, text="Start Time:", font=("Segoe UI", 8, "bold"), fg=TEXT_WHITE, bg=WELL_DARK).grid(row=0, column=6, sticky="w", padx=4, pady=2)
            ent_time = tk.Entry(grid_f, font=("Segoe UI", 9), bg=PANEL_DARK, fg=ACCENT_GOLD, insertbackground="white", width=20, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent_time.grid(row=0, column=7, padx=4, pady=2)
            ent_time.insert(0, def_time)

            self.race_stage_entries[f"s{s_num}_track"] = ent_track
            self.race_stage_entries[f"s{s_num}_laps"] = ent_laps
            self.race_stage_entries[f"s{s_num}_class"] = ent_class
            self.race_stage_entries[f"s{s_num}_time"] = ent_time

        # Tournament Notes
        f_notes = tk.Frame(box_race_main, bg=PANEL_DARK)
        f_notes.pack(fill="x", pady=6)
        tk.Label(f_notes, text="Tournament Notes:", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK, width=20, anchor="w").pack(side="left")
        self.ent_race_notes = tk.Entry(f_notes, font=("Segoe UI", 9), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=65, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.ent_race_notes.pack(side="left", padx=4)
        self.ent_race_notes.insert(0, "Password required. Stock Class E only (Honda Civic, Classic Mini, Ford Fiesta, Peugeot 106, Fiat Punto).")

        btn_save_races = tk.Button(box_race_main, text="💾 SAVE 3-DAY RACE SCHEDULE TO JSON", font=("Impact", 10), bg=ACCENT_GREEN, fg=TEXT_WHITE, relief="flat", padx=14, pady=5, cursor="hand2", command=self.save_race_schedule_to_json)
        btn_save_races.pack(anchor="w", pady=8)

    def roll_random_race_tracks(self):
        import random
        tracks = ["Mudpit", "Hammerhead", "Two Islands", "Docks", "Industrial", "Speedway", "Stone Park", "Parkland", "Meltdown", "Underpass", "Uptown", "Vector", "Sewage"]
        selected = random.sample(tracks, 3)
        self.race_stage_entries["s1_track"].delete(0, "end")
        self.race_stage_entries["s1_track"].insert(0, selected[0])
        self.race_stage_entries["s2_track"].delete(0, "end")
        self.race_stage_entries["s2_track"].insert(0, selected[1])
        self.race_stage_entries["s3_track"].delete(0, "end")
        self.race_stage_entries["s3_track"].insert(0, selected[2])
        messagebox.showinfo("Random Tracks", f"✓ Rolled tracks:\nStage 1: {selected[0]}\nStage 2: {selected[1]}\nStage 3: {selected[2]}")

    def save_race_schedule_to_json(self):
        records = safe_load_json(SCHEDULED_RACES_FILE, [])
        if not isinstance(records, list):
            records = []

        title = self.ent_race_title.get().strip() or "Loki's 3-Day Stock Class E Endurance Series"
        s1 = {
            "track": self.race_stage_entries["s1_track"].get().strip() or "Mudpit",
            "laps": int(self.race_stage_entries["s1_laps"].get().strip() or 25),
            "car_class": self.race_stage_entries["s1_class"].get().strip() or "Stock Class E",
            "time": self.race_stage_entries["s1_time"].get().strip() or "Friday 18:00 TCT"
        }
        s2 = {
            "track": self.race_stage_entries["s2_track"].get().strip() or "Hammerhead",
            "laps": int(self.race_stage_entries["s2_laps"].get().strip() or 25),
            "car_class": self.race_stage_entries["s2_class"].get().strip() or "Stock Class E",
            "time": self.race_stage_entries["s2_time"].get().strip() or "Saturday 18:00 TCT"
        }
        s3 = {
            "track": self.race_stage_entries["s3_track"].get().strip() or "Two Islands",
            "laps": int(self.race_stage_entries["s3_laps"].get().strip() or 25),
            "car_class": self.race_stage_entries["s3_class"].get().strip() or "Stock Class E",
            "time": self.race_stage_entries["s3_time"].get().strip() or "Sunday 18:00 TCT"
        }
        notes = self.ent_race_notes.get().strip()

        record = {
            "id": f"RACE-{int(datetime.now().timestamp())}",
            "title": title,
            "stage1": s1,
            "stage2": s2,
            "stage3": s3,
            "notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        records.append(record)
        safe_save_json(SCHEDULED_RACES_FILE, records)
        messagebox.showinfo("Saved", "✓ 3-Day Race Schedule saved to scheduled_races_log.json! Discord users can now view it using /race-schedule.")

    def build_tab_wordbank(self):
        frame = tk.Frame(self.tab_wordbank, bg=BG_DARK, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        top_bar = tk.Frame(frame, bg=BG_DARK)
        top_bar.pack(fill="x", pady=(0, 10))

        tk.Label(top_bar, text="🎯 ACTIVE BINGO WORD BANK (bingo_state.json)", font=("Impact", 13), fg=TEXT_WHITE, bg=BG_DARK).pack(side="left")

        btn_sync_gh = tk.Button(top_bar, text="🌐 SYNC TO GITHUB REPO", font=("Segoe UI", 9, "bold"), bg="#059669", fg=TEXT_WHITE, relief="flat", padx=10, pady=3, cursor="hand2", command=self.sync_wordbank_to_github)
        btn_sync_gh.pack(side="right", padx=4)

        btn_fetch_torn = tk.Button(top_bar, text="⚡ FETCH TORN ITEMS (API)", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg=TEXT_WHITE, relief="flat", padx=10, pady=3, cursor="hand2", command=self.fetch_torn_items_to_pool)
        btn_fetch_torn.pack(side="right", padx=4)

        btn_default = tk.Button(top_bar, text="↺ RESET TO DEFAULTS", font=("Segoe UI", 9, "bold"), bg="#4b5563", fg=TEXT_WHITE, relief="flat", padx=10, pady=3, cursor="hand2", command=self.reset_wordbank_defaults)
        btn_default.pack(side="right", padx=4)

        # Text area with items (1 per line)
        self.txt_wordbank = scrolledtext.ScrolledText(frame, font=("Consolas", 10), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK, wrap="word")
        self.txt_wordbank.pack(fill="both", expand=True, pady=6)
        self.txt_wordbank.bind("<KeyRelease>", self.update_wordbank_stats)

        # Stats bar
        self.lbl_wordbank_stats = tk.Label(frame, text="Total Items: 0 | Minimum Required for 5x5: 24", font=("Segoe UI", 9, "bold"), fg=ACCENT_GOLD, bg=BG_DARK)
        self.lbl_wordbank_stats.pack(anchor="w", pady=4)

    # --------------------------------------------------------------------------
    # TAB 4: EVENT PRIZES CONFIGURATION
    # --------------------------------------------------------------------------
    def build_tab_prizes(self):
        canvas = tk.Canvas(self.tab_prizes, bg=BG_DARK, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.tab_prizes, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_DARK, padx=16, pady=12)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.prize_entries = {}

        # 1. 3-Day Raffle Prizes
        box_raffle = tk.LabelFrame(scroll_frame, text=" 🎟️ 3-DAY RAFFLE PRIZES ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=10, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_raffle.pack(fill="x", pady=6)

        raffle_fields = [("raffle_day1", "Day 1 Raffle Prize:", "50x Xanax"), ("raffle_day2", "Day 2 Raffle Prize:", "5x Box of Medical Supplies"), ("raffle_day3", "Day 3 Grand Raffle Prize:", "1x Donator Pack + 50x Xanax")]
        for r_idx, (key, label_txt, default_v) in enumerate(raffle_fields):
            tk.Label(box_raffle, text=label_txt, font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=r_idx, column=0, sticky="w", pady=3)
            ent = tk.Entry(box_raffle, font=("Segoe UI", 9), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=45, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent.grid(row=r_idx, column=1, sticky="w", pady=3, padx=10)
            self.prize_entries[key] = ent

        # 2. Race Series (Bronze, Silver, Gold)
        box_races = tk.LabelFrame(scroll_frame, text=" 🏎️ 3-DAY RACE PRIZES (BRONZE, SILVER & GOLD) ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=10, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_races.pack(fill="x", pady=6)

        race_tiers = [
            ("Bronze Series", "race_bronze", [("1st", "10x Xanax"), ("2nd", "5x Xanax"), ("3rd", "2x Xanax"), ("Last", "1x Xanax (Consolation)")]),
            ("Silver Series", "race_silver", [("1st", "25x Xanax"), ("2nd", "15x Xanax"), ("3rd", "5x Xanax"), ("Last", "2x Xanax (Consolation)")]),
            ("Gold Series", "race_gold", [("1st", "50x Xanax + Box of Meds"), ("2nd", "25x Xanax"), ("3rd", "10x Xanax"), ("Last", "5x Xanax (Consolation)")])
        ]

        for t_idx, (tier_title, tier_prefix, placements) in enumerate(race_tiers):
            tk.Label(box_races, text=f"• {tier_title}:", font=("Impact", 10), fg=ACCENT_GOLD, bg=PANEL_DARK).grid(row=t_idx*5, column=0, sticky="w", pady=(6, 2))
            for p_idx, (pos_name, default_v) in enumerate(placements):
                p_key = f"{tier_prefix}_{pos_name.lower().replace(' ', '_')}"
                tk.Label(box_races, text=f"{pos_name} Place:", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=PANEL_DARK).grid(row=t_idx*5 + p_idx + 1, column=0, sticky="w", padx=10, pady=2)
                ent = tk.Entry(box_races, font=("Segoe UI", 9), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=40, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
                ent.grid(row=t_idx*5 + p_idx + 1, column=1, sticky="w", pady=2, padx=10)
                self.prize_entries[p_key] = ent

        # 3. Bingo & Jumble Prizes
        box_bingo_p = tk.LabelFrame(scroll_frame, text=" 🎯 BINGO & WORD JUMBLE PRIZES ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=10, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_bingo_p.pack(fill="x", pady=6)

        bingo_fields = [("bingo_prize", "Bingo Prize:", "25x Xanax"), ("bingo_blackout", "Full Card (Blackout) Prize:", "100x Xanax + 2x Donator Pack"), ("jumble_fast", "Fastest Jumble Solver Prize:", "5x Xanax per Drop")]
        for b_idx, (key, label_txt, default_v) in enumerate(bingo_fields):
            tk.Label(box_bingo_p, text=label_txt, font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK).grid(row=b_idx, column=0, sticky="w", pady=3)
            ent = tk.Entry(box_bingo_p, font=("Segoe UI", 9), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", width=45, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
            ent.grid(row=b_idx, column=1, sticky="w", pady=3, padx=10)
            self.prize_entries[key] = ent

    # --------------------------------------------------------------------------
    # TAB 5: BOT CONSOLE & PROCESS MANAGER
    # --------------------------------------------------------------------------
    def build_tab_console(self):
        frame = tk.Frame(self.tab_console, bg=BG_DARK, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        ctrl_bar = tk.Frame(frame, bg=BG_DARK)
        ctrl_bar.pack(fill="x", pady=(0, 10))

        self.btn_bot_toggle = tk.Button(ctrl_bar, text="▶ START DISCORD BOT (bot.py)", font=("Impact", 11), bg=ACCENT_GREEN, fg=TEXT_WHITE, relief="flat", padx=16, pady=6, cursor="hand2", command=self.toggle_bot_process)
        self.btn_bot_toggle.pack(side="left", padx=4)

        btn_restart = tk.Button(ctrl_bar, text="🔄 RESTART BOT", font=("Impact", 11), bg="#2563eb", fg=TEXT_WHITE, relief="flat", padx=14, pady=6, cursor="hand2", command=self.restart_bot_process)
        btn_restart.pack(side="left", padx=4)

        btn_clear_log = tk.Button(ctrl_bar, text="🧹 CLEAR CONSOLE", font=("Segoe UI", 9, "bold"), bg="#4b5563", fg=TEXT_WHITE, relief="flat", padx=12, pady=6, cursor="hand2", command=self.clear_console_log)
        btn_clear_log.pack(side="right", padx=4)

        # Scrolled Text for Process Output
        self.txt_console = scrolledtext.ScrolledText(frame, font=("Consolas", 9), bg="#090a0f", fg="#38bdf8", insertbackground="white", relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.txt_console.pack(fill="both", expand=True, pady=4)

        self.log_console("[SYSTEM] Windows Companion Configurator ready. Click 'START DISCORD BOT' to launch bot.py in the background.\n")

    # --------------------------------------------------------------------------
    # TAB 6: SESSIONS & BUG TRACKER
    # --------------------------------------------------------------------------
    def build_tab_tools(self):
        frame = tk.Frame(self.tab_tools, bg=BG_DARK, padx=16, pady=16)
        frame.pack(fill="both", expand=True)

        # Session Reset Tool
        box_session = tk.LabelFrame(frame, text=" 🚀 SESSION MANAGEMENT (START NEW GAME) ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_session.pack(fill="x", pady=6)

        tk.Label(box_session, text="Clears all player cards from memory and session_cards.json, resets drawn words, and allows fresh 1-card signups.", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=PANEL_DARK).pack(anchor="w", pady=2)
        btn_reset_session = tk.Button(box_session, text="🚀 START NEW GAME (CLEAR CARDS & RESET DRAW POOL)", font=("Impact", 11), bg=ACCENT_RED, fg=TEXT_WHITE, relief="flat", padx=16, pady=6, cursor="hand2", command=self.action_reset_session)
        btn_reset_session.pack(anchor="w", pady=6)

        # Bug Reports Viewer
        box_bugs = tk.LabelFrame(frame, text=" 🐞 BUG REPORTS LOG (bug_reports.json) ", font=("Impact", 11), fg=ACCENT_GOLD, bg=PANEL_DARK, padx=14, pady=12, highlightthickness=1, highlightbackground=BORDER_DARK)
        box_bugs.pack(fill="both", expand=True, pady=6)

        top_bug_bar = tk.Frame(box_bugs, bg=PANEL_DARK)
        top_bug_bar.pack(fill="x", pady=(0, 6))

        self.lbl_bug_count = tk.Label(top_bug_bar, text="Logged Bugs: 0", font=("Segoe UI", 9, "bold"), fg=TEXT_WHITE, bg=PANEL_DARK)
        self.lbl_bug_count.pack(side="left")

        btn_refresh_bugs = tk.Button(top_bug_bar, text="🔄 REFRESH BUGS", font=("Segoe UI", 8, "bold"), bg="#4b5563", fg=TEXT_WHITE, relief="flat", padx=8, pady=2, cursor="hand2", command=self.load_bug_reports)
        btn_refresh_bugs.pack(side="right")

        self.txt_bugs = scrolledtext.ScrolledText(box_bugs, font=("Consolas", 9), bg=WELL_DARK, fg=TEXT_WHITE, insertbackground="white", height=8, relief="flat", highlightthickness=1, highlightbackground=BORDER_DARK)
        self.txt_bugs.pack(fill="both", expand=True, pady=4)

    # --------------------------------------------------------------------------
    # DATA LOADING & SAVING LOGIC
    # --------------------------------------------------------------------------
    def load_all_data(self):
        # 1. Credentials
        self.ent_discord_token.insert(0, self.env_data.get("DISCORD_TOKEN", ""))
        self.ent_race_password.insert(0, self.env_data.get("RACE_PASSWORD", "LOKI2026"))
        self.ent_torn_key.insert(0, self.env_data.get("TORN_API_KEY", ""))
        self.ent_gh_token.insert(0, self.env_data.get("GITHUB_TOKEN", ""))
        self.ent_gh_repo.insert(0, self.env_data.get("GITHUB_REPO", ""))
        self.ent_gh_branch.insert(0, self.env_data.get("GITHUB_BRANCH", "main"))

        # 2. Channel IDs & Role Pings
        for key, entry in self.channel_entries.items():
            entry.insert(0, self.env_data.get(key, ""))

        # 3. Word Bank
        state = safe_load_json(STATE_FILE, {})
        words = state.get("word_pool", DEFAULT_ITEMS)
        self.txt_wordbank.delete("1.0", "end")
        self.txt_wordbank.insert("1.0", "\n".join(words))
        self.update_wordbank_stats()

        # 4. Prizes
        prizes = safe_load_json(PRIZES_CONFIG_FILE, {})
        for k, ent in self.prize_entries.items():
            if k in prizes:
                ent.delete(0, "end")
                ent.insert(0, str(prizes[k]))

        # 5. Bugs
        self.load_bug_reports()

    def update_wordbank_stats(self, event=None):
        items = [w.strip() for w in self.txt_wordbank.get("1.0", "end").splitlines() if w.strip()]
        self.lbl_wordbank_stats.config(text=f"Total Items: {len(items)} | Minimum Required for 5x5 Card: 24 | Status: {'✓ Valid' if len(items) >= 24 else '⚠️ Add more items'}")

    def sync_wordbank_to_github(self):
        token = self.ent_gh_token.get().strip()
        repo = self.ent_gh_repo.get().strip().replace("https://github.com/", "").strip("/")
        if not token or not repo:
            messagebox.showerror("Error", "Please configure GitHub Token and Repository first in 'Bot & Tokens' tab.")
            return

        items = [w.strip() for w in self.txt_wordbank.get("1.0", "end").splitlines() if w.strip()]
        if len(items) < 24:
            messagebox.showerror("Error", f"Word bank only has {len(items)} items. Minimum 24 required.")
            return

        state = safe_load_json(STATE_FILE, {"drawn_words": []})
        state["word_pool"] = items
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        safe_save_json(STATE_FILE, state)

        try:
            url = f"https://api.github.com/repos/{repo}/contents/bingo_state.json"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "WeekendAtLokisConfigurator"
            }
            sha = None
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        info = json.loads(resp.read().decode("utf-8"))
                        sha = info.get("sha")
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise e

            import base64
            content_bytes = json.dumps(state, indent=2).encode("utf-8")
            payload = {
                "message": f"Sync word bank ({len(items)} items) via Windows Configurator",
                "content": base64.b64encode(content_bytes).decode("utf-8"),
                "branch": self.ent_gh_branch.get().strip() or "main"
            }
            if sha:
                payload["sha"] = sha

            put_req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
            with urllib.request.urlopen(put_req, timeout=10) as resp:
                if resp.status in (200, 201):
                    messagebox.showinfo("GitHub Sync", f"✓ Word bank ({len(items)} items) synced directly to GitHub repository!")
                    self.status_bar_text.config(text=f"✓ Word bank synced to GitHub ({repo}) at {time.strftime('%H:%M:%S')}")
                else:
                    messagebox.showerror("Sync Failed", f"HTTP Response: {resp.status}")
        except Exception as e:
            messagebox.showerror("Sync Error", f"Failed to sync to GitHub: {e}")

    def save_all_settings(self):
        # 1. Update env_data
        self.env_data["DISCORD_TOKEN"] = self.ent_discord_token.get().strip()
        self.env_data["RACE_PASSWORD"] = self.ent_race_password.get().strip() or "LOKI2026"
        self.env_data["TORN_API_KEY"] = self.ent_torn_key.get().strip()
        self.env_data["GITHUB_TOKEN"] = self.ent_gh_token.get().strip()
        self.env_data["GITHUB_REPO"] = self.ent_gh_repo.get().strip()
        self.env_data["GITHUB_BRANCH"] = self.ent_gh_branch.get().strip() or "main"

        for key, entry in self.channel_entries.items():
            self.env_data[key] = entry.get().strip()

        save_env_dict(self.env_data)

        # 2. Save Word Bank to bingo_state.json
        items = [w.strip() for w in self.txt_wordbank.get("1.0", "end").splitlines() if w.strip()]
        if len(items) < 24:
            messagebox.showwarning("Word Bank Notice", f"Word bank has {len(items)} items. At least 24 items are required for 5x5 Bingo cards.")

        state = safe_load_json(STATE_FILE, {"word_pool": items, "drawn_words": []})
        state["word_pool"] = items
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        safe_save_json(STATE_FILE, state)

        # 3. Save Prizes to prizes_config.json
        prizes = {}
        for k, ent in self.prize_entries.items():
            prizes[k] = ent.get().strip()
        safe_save_json(PRIZES_CONFIG_FILE, prizes)

        self.status_bar_text.config(text=f"✓ All settings saved successfully to .env and JSON files at {time.strftime('%H:%M:%S')}")
        messagebox.showinfo("Saved", "✓ All settings, tokens, webhooks, word banks and prize matrices have been saved!")

    def reset_wordbank_defaults(self):
        if messagebox.askyesno("Reset Word Bank", "Reset word bank to the default 36 Torn item catalog?"):
            self.txt_wordbank.delete("1.0", "end")
            self.txt_wordbank.insert("1.0", "\n".join(DEFAULT_ITEMS))
            self.update_wordbank_stats()

    def fetch_torn_items_to_pool(self):
        key = self.ent_torn_key.get().strip()
        if not key:
            messagebox.showerror("Error", "Please enter a Torn API key first.")
            return
        try:
            url = f"https://api.torn.com/torn/?selections=items&key={key}"
            req = urllib.request.Request(url, headers={"User-Agent": "WeekendAtLokisConfigurator"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "items" in data:
                    items = [i["name"] for i in data["items"].values() if i.get("name") and i.get("type") != "Unused"][:80]
                    self.txt_wordbank.delete("1.0", "end")
                    self.txt_wordbank.insert("1.0", "\n".join(items))
                    self.update_wordbank_stats()
                    messagebox.showinfo("Torn API", f"✓ Successfully fetched and loaded {len(items)} Torn items!")
                else:
                    messagebox.showerror("Torn API Error", data.get("error", {}).get("error", "Unknown API error"))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect to Torn API: {e}")

    # --------------------------------------------------------------------------
    # API & CONNECTION TESTERS
    # --------------------------------------------------------------------------
    def test_torn_api(self):
        key = self.ent_torn_key.get().strip()
        if not key:
            messagebox.showerror("Error", "Enter Torn API Key first.")
            return
        try:
            url = f"https://api.torn.com/user/?selections=basic&key={key}"
            req = urllib.request.Request(url, headers={"User-Agent": "WeekendAtLokisConfigurator"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if "name" in data:
                    p_name = data["name"]
                    p_id = data["player_id"]
                    self.lbl_torn_status.config(text=f"✓ Verified: {p_name} [{p_id}]", fg=ACCENT_GREEN)
                    messagebox.showinfo("Torn Verified", f"✓ Connected to Torn API as: {p_name} [{p_id}]")
                else:
                    err_msg = data.get("error", {}).get("error", "Invalid API response")
                    self.lbl_torn_status.config(text=f"❌ Error: {err_msg}", fg="#ef4444")
                    messagebox.showerror("Torn API Error", err_msg)
        except Exception as e:
            self.lbl_torn_status.config(text=f"❌ Connection Error", fg="#ef4444")
            messagebox.showerror("Error", f"Failed to connect: {e}")

    def test_github_repo(self):
        token = self.ent_gh_token.get().strip()
        repo = self.ent_gh_repo.get().strip().replace("https://github.com/", "").strip("/")
        if not token or not repo:
            messagebox.showerror("Error", "Please provide both GitHub Token and Repository (username/repo).")
            return
        try:
            url = f"https://api.github.com/repos/{repo}"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "WeekendAtLokisConfigurator"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    info = json.loads(resp.read().decode("utf-8"))
                    self.lbl_gh_status.config(text=f"✓ Verified Repo: {info.get('full_name')} (Stars: {info.get('stargazers_count', 0)})", fg=ACCENT_GREEN)
                    messagebox.showinfo("GitHub Verified", f"✓ Successfully connected to repository: {info.get('full_name')}")
                else:
                    self.lbl_gh_status.config(text="❌ HTTP " + str(resp.status), fg="#ef4444")
        except urllib.error.HTTPError as e:
            msg = f"HTTP {e.code}: {e.reason}"
            if e.code == 401: msg += " (Invalid GitHub Token)"
            if e.code == 404: msg += " (Repository Not Found or Token lacks access)"
            self.lbl_gh_status.config(text=f"❌ {msg}", fg="#ef4444")
            messagebox.showerror("GitHub Error", msg)
        except Exception as e:
            self.lbl_gh_status.config(text=f"❌ {e}", fg="#ef4444")
            messagebox.showerror("Error", f"Connection failed: {e}")

    def test_webhook_url(self, hook_key, name_key):
        url = self.webhook_entries[hook_key].get().strip()
        name = self.webhook_entries[name_key].get().strip() or "Weekend at Loki's"
        if not url or not url.startswith("http"):
            messagebox.showerror("Error", "Please enter a valid Discord Webhook URL.")
            return
        try:
            payload = json.dumps({
                "username": name,
                "embeds": [{
                    "title": "🎯 Weekend at Loki's — Webhook Test!",
                    "description": f"Test message from **Windows Companion Configurator** for `{hook_key}`.",
                    "color": 0x22c55e,
                    "footer": {"text": "Windows Companion Configurator v7.0"}
                }]
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "WeekendAtLokisConfigurator"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    messagebox.showinfo("Webhook Test", "✓ Test message sent successfully to Discord!")
                else:
                    messagebox.showerror("Webhook Test", f"HTTP Response: {resp.status}")
        except Exception as e:
            messagebox.showerror("Webhook Error", f"Failed to send webhook: {e}")

    # --------------------------------------------------------------------------
    # PROCESS CONTROLLER (RUN bot.py)
    # --------------------------------------------------------------------------
    def toggle_bot_process(self):
        if self.bot_process is None or self.bot_process.poll() is not None:
            self.start_bot_process()
        else:
            self.stop_bot_process()

    def start_bot_process(self):
        bot_script = os.path.join(BASE_DIR, "bot.py")
        if not os.path.exists(bot_script):
            messagebox.showerror("File Missing", f"Could not find bot.py in: {BASE_DIR}")
            return

        # Auto-save settings first
        self.save_all_settings()

        try:
            self.log_console(f"\n[LAUNCHER] Starting bot.py with Python interpreter: {sys.executable}...\n")
            self.bot_process = subprocess.Popen(
                [sys.executable, "-u", bot_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=BASE_DIR
            )
            self.is_monitoring = True
            threading.Thread(target=self.stream_bot_output, daemon=True).start()

            self.header_status.config(text="● Bot Running", fg=ACCENT_GREEN)
            self.btn_header_start.config(text="⏹ STOP BOT", bg="#ef4444")
            self.btn_bot_toggle.config(text="⏹ STOP DISCORD BOT", bg="#ef4444")
            self.status_bar_text.config(text="Bot is running (PID: " + str(self.bot_process.pid) + ")")
        except Exception as e:
            self.log_console(f"[ERROR] Failed to start bot process: {e}\n")
            messagebox.showerror("Launch Error", f"Failed to start bot: {e}")

    def stream_bot_output(self):
        while self.is_monitoring and self.bot_process:
            line = self.bot_process.stdout.readline()
            if not line:
                if self.bot_process.poll() is not None:
                    break
                time.sleep(0.1)
                continue
            self.log_queue.put(line)

        rc = self.bot_process.poll() if self.bot_process else None
        self.log_queue.put(f"\n[LAUNCHER] Bot process ended with exit code: {rc}\n")
        self.root.after(100, self.update_bot_stopped_ui)

    def update_bot_stopped_ui(self):
        self.header_status.config(text="● Bot Offline", fg="#ef4444")
        self.btn_header_start.config(text="▶ START BOT", bg=ACCENT_GREEN)
        self.btn_bot_toggle.config(text="▶ START DISCORD BOT (bot.py)", bg=ACCENT_GREEN)
        self.status_bar_text.config(text="Bot process stopped.")

    def stop_bot_process(self):
        if self.bot_process and self.bot_process.poll() is None:
            self.log_console("\n[LAUNCHER] Terminating bot process...\n")
            self.bot_process.terminate()
            try:
                self.bot_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.bot_process.kill()
        self.update_bot_stopped_ui()

    def restart_bot_process(self):
        self.stop_bot_process()
        self.root.after(1000, self.start_bot_process)

    def log_console(self, text):
        self.txt_console.insert("end", text)
        self.txt_console.see("end")

    def clear_console_log(self):
        self.txt_console.delete("1.0", "end")

    # --------------------------------------------------------------------------
    # SESSIONS & BUGS
    # --------------------------------------------------------------------------
    def action_reset_session(self):
        if messagebox.askyesno("Start New Game", "Start a new session? This will clear all player cards in session_cards.json and reset the drawn word pool while preserving all tokens and webhooks."):
            safe_save_json(SESSION_CARDS_FILE, {})
            state = safe_load_json(STATE_FILE, {})
            state["drawn_words"] = []
            safe_save_json(STATE_FILE, state)
            messagebox.showinfo("Session Reset", "✓ New game session started! Player cards cleared and word pool refreshed.")

    def load_bug_reports(self):
        bugs = safe_load_json(BUG_REPORTS_FILE, [])
        self.lbl_bug_count.config(text=f"Logged Bugs: {len(bugs)} ({len([b for b in bugs if b.get('status') == 'OPEN'])} Open)")
        self.txt_bugs.delete("1.0", "end")
        if not bugs:
            self.txt_bugs.insert("1.0", "No bugs logged in bug_reports.json.")
            return

        for b in reversed(bugs):
            self.txt_bugs.insert("end", f"[{b.get('id', 'BUG')}] [{b.get('status', 'OPEN')}] {b.get('feature', 'Gen')} ({b.get('severity', 'Med')}) by {b.get('reporterName', 'User')}\n  Description: {b.get('description', '')}\n\n")

    def poll_log_queue(self):
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self.log_console(line)
            except queue.Empty:
                break
        self.root.after(100, self.poll_log_queue)

    def on_close(self):
        if self.bot_process and self.bot_process.poll() is None:
            if messagebox.askyesno("Exit Configurator", "The Discord bot is currently running. Stop the bot and exit?"):
                self.stop_bot_process()
                self.root.destroy()
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = LokisCompanionApp(root)
    app.poll_log_queue()
    root.mainloop()

if __name__ == "__main__":
    main()
