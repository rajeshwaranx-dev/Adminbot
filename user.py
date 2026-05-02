# handlers/user.py – User commands

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
from utils import HTML, remaining_text, main_kb


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username or "", u.full_name)
    text = (
        f"🎉 <b>Welcome to {config.BOT_NAME}!</b>\n\n"
        f"👤 User ID: <code>{u.id}</code>\n\n"
        f"💳 <b>Payment:</b> UPI QR Code and UPI Apps\n"
        f"🆔 <b>UPI ID:</b> <code>{config.UPI_ID}</code>\n\n"
        f"🔗 <b>Commands:</b>\n"
        f"🛍 /buy – Purchase subscription\n"
        f"📋 /myplan – Check your subscriptions\n"
        f"🔗 /invites – Get invite links\n"
        f"🔍 /status – Check payment status\n\n"
        f"🔧 <b>How it works:</b>\n"
        f"1️⃣ Choose a category and plan (/buy)\n"
        f"2️⃣ Pay via QR or UPI app\n"
        f"3️⃣ Send payment screenshot\n"
        f"4️⃣ Get instant activation on approval\n\n"
        f"📞 Support: {config.SUPPORT_USERNAME}"
    )
    await update.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=main_kb(u.id, config.ADMIN_IDS)
    )


async def cmd_myplan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    subs = db.get_user_subscriptions(update.effective_user.id)
    if not subs:
        await update.message.reply_text(
            "📋 <b>Your Subscriptions:</b>\n\n❌ No active subscriptions.\n\nUse /buy to purchase one!",
            parse_mode=HTML
        )
        return
    text = "📋 <b>Your Subscriptions:</b>\n\n"
    for s in subs:
        exp = datetime.fromisoformat(s["expires_at"])
        bot_name = s.get("bot_name") or "—"
        text += (
            f"🔗 <b>{s['plan_name']}</b> – 🟢 Active\n"
            f"   🤖 Bot Name: <b>{bot_name}</b>\n"
            f"   📝 Category: {s['category']}\n"
            f"   📅 Duration: {s['duration']} days\n"
            f"   ⏰ Expiry: {exp.strftime('%d-%m-%Y %H:%M')} IST\n"
            f"   ⌛ Remaining: {remaining_text(s['expires_at'])}\n\n"
        )
    await update.message.reply_text(text, parse_mode=HTML)


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    orders = db.get_user_orders(update.effective_user.id)
    if not orders:
        await update.message.reply_text(
            "You don't have any orders from the last 7 days.\n\n🛍 Use /buy to create a new order"
        )
        return
    text = "🔍 <b>Recent Orders:</b>\n\n"
    for o in orders:
        emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(o["status"], "❓")
        text += (
            f"{emoji} <b>{o['plan_name']}</b>\n"
            f"   🆔 Order: <code>{o['order_id']}</code>\n"
            f"   💰 Amount: ₹{o['amount']:.0f}\n"
            f"   📅 Date: {o['created_at'][:10]}\n"
            f"   Status: {o['status'].upper()}\n\n"
        )
    await update.message.reply_text(text, parse_mode=HTML)


async def cmd_invites(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    subs = db.get_user_subscriptions(update.effective_user.id)
    if not subs:
        await update.message.reply_text(
            "❌ You need an active subscription to get invite links.\n\nUse /buy to purchase one!"
        )
        return
    text = (
        f"🔗 <b>Your Invite Links:</b>\n\n"
        f"📢 Updates Channel: {config.CHANNEL_USERNAME}\n\n"
        f"📞 Support: {config.SUPPORT_USERNAME}\n\n"
        f"<i>Links valid for your subscription period.</i>"
    )
    await update.message.reply_text(text, parse_mode=HTML)


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Cancelled.",
        reply_markup=main_kb(update.effective_user.id, config.ADMIN_IDS)
    )
    return ConversationHandler.END

