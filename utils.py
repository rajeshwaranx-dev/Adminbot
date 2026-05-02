# utils.py – Shared helpers

import random
import string
from datetime import datetime

from telegram import ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ParseMode

HTML = ParseMode.HTML


def gen_order_id():
    return "ASK_" + "".join(random.choices(string.digits, k=10))


def remaining_text(expires_at: str) -> str:
    exp = datetime.fromisoformat(expires_at)
    delta = exp - datetime.utcnow()
    if delta.total_seconds() <= 0:
        return "Expired"
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    mins = rem // 60
    parts = []
    if days:  parts.append(f"{days} day{'s' if days > 1 else ''}")
    if hours: parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if mins:  parts.append(f"{mins} minute{'s' if mins > 1 else ''}")
    return ", ".join(parts) + " !"


def is_admin(user_id: int, admin_ids: list) -> bool:
    return user_id in admin_ids


def main_kb(user_id: int, admin_ids: list):
    rows = [
        [KeyboardButton("🛍 Buy Subscription"), KeyboardButton("📋 My Subscriptions")],
        [KeyboardButton("🔗 Get Invites"),       KeyboardButton("🔍 Payment Status")],
    ]
    if user_id in admin_ids:
        rows.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def upi_deep_link(upi_id: str, name: str, amount: float, note: str) -> str:
    return (
        f"upi://pay?pa={upi_id}&pn={name}"
        f"&am={amount}&tn={note}&cu=INR"
    )


def qr_url(upi_id: str, name: str, amount: float, note: str) -> str:
    link = upi_deep_link(upi_id, name, amount, note)
    return f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={link}"

