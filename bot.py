import json
import os
import telebot
from telebot import types

BOT_TOKEN = "8765104365:AAFPTCvIRu7YsC2ljqvmRAsXyQeBAa7yP7s"
OWNER_USERNAME = "raouf100K"
DATA_FILE = "bot_config.json"

CHANNELS = [
    {"name": "قناة F_ONDRAY_FF", "username": "F_ONDRAY_FF", "url": "https://t.me/F_ONDRAY_FF"},
    {"name": "قناة setupvedeo", "username": "setupvedeo", "url": "https://t.me/setupvedeo"},
    {"name": "قناة shadowxtn", "username": "shadowxtn", "url": "https://t.me/shadowxtn"},
]

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}


def load_config():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "code": "ON-DRAY-VIP-2026",
            "devs": [OWNER_USERNAME.lower()],
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, ensure_ascii=False, indent=2)
        return default_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


config_data = load_config()
