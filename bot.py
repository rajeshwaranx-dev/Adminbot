"""
bot.py – Telegram Subscription Bot + Inline Admin Dashboard
Run: python bot.py
"""
import logging
import random
import string
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler
)
from telegram.constants import ParseMode

import config
import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Conversation states ──────────────────────────────────────
(
    SELECTING_PLAN,
    SELECTING_PAYMENT,
    WAITING_SCREENSHOT,
    WAITING_TXN_ID,
    ADMIN_ADD_PLAN,
    ADMIN_BROADCAST,
    ADMIN_REJECT_REASON,
) = range(7)

HTML = ParseMode.HTML


# ── Helpers ──────────────────────────────────────────────────

def gen_order_id():
    return "LCU_" + "".join(random.choices(string.digits, k=10))


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


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def main_kb(user_id: int):
    rows = [
        [KeyboardButton("🛍 Buy Subscription"), KeyboardButton("📋 My Subscriptions")],
        [KeyboardButton("🔗 Get Invites"),       KeyboardButton("🔍 Payment Status")],
    ]
    if is_admin(user_id):
        rows.append([KeyboardButton("⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats",          callback_data="adm_stats"),
         InlineKeyboardButton("⏳ Pending Orders", callback_data="adm_pending")],
        [InlineKeyboardButton("🧾 All Orders",     callback_data="adm_orders"),
         InlineKeyboardButton("👥 Users",          callback_data="adm_users")],
        [InlineKeyboardButton("📦 Plans",          callback_data="adm_plans"),
         InlineKeyboardButton("📢 Broadcast",      callback_data="adm_broadcast")],
        [InlineKeyboardButton("🔔 Active Subs",    callback_data="adm_subs")],
    ])


# ════════════════════════════════════════════════════════════
#  USER COMMANDS
# ════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username or "", u.full_name)
    text = (
        f"🎉 <b>Welcome to {config.BOT_NAME}!</b>\n\n"
        f"👤 User ID: <code>{u.id}</code>\n\n"
        f"💳 <b>Payment Method:</b> UPI QR Code and Manual UPI\n"
        f"🆔 <b>Our UPI ID:</b> <code>{config.UPI_ID}</code>\n\n"
        f"🔗 <b>Available Commands:</b>\n"
        f"🛍 /buy - Purchase subscription\n"
        f"📋 /plans - View available plans\n"
        f"📱 /myplan - Check your subscriptions\n"
        f"🔗 /invites - Get group and channel invite links\n"
        f"🔍 /status - Check payment status\n\n"
        f"🔧 <b>How it works:</b>\n"
        f"1️⃣ Choose a plan (/buy)\n"
        f"2️⃣ Get QR code or manual UPI details\n"
        f"3️⃣ Make payment with order ID in note\n"
        f"4️⃣ Send payment screenshot\n"
        f"5️⃣ Get instant activation on approval\n"
        f"6️⃣ Use /invites to access groups and channels\n\n"
        f"📞 Admin Support: {config.SUPPORT_USERNAME}"
    )
    await update.message.reply_text(text, parse_mode=HTML, reply_markup=main_kb(u.id))


async def cmd_plans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    plans = db.get_plans()
    if not plans:
        await update.message.reply_text("❌ No plans available right now.")
        return
    text = "📋 <b>Available Plans:</b>\n\n"
    for p in plans:
        text += (
            f"⭐ <b>{p['name']}</b>\n"
            f"   📦 Category: {p['category']}\n"
            f"   ⏱ Duration: {p['duration']} days\n"
            f"   💰 Price: ₹{p['price']:.0f}\n"
            f"   🔧 Services: {p['services']}\n\n"
        )
    kb = [[InlineKeyboardButton(f"🛍 Buy {p['name']} - ₹{p['price']:.0f}", callback_data=f"buy_{p['id']}")]
          for p in plans]
    await update.message.reply_text(text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))


async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    plans = db.get_plans()
    if not plans:
        await update.message.reply_text("❌ No plans available right now.")
        return ConversationHandler.END
    kb = [[InlineKeyboardButton(
        f"📦 {p['name']} - ₹{p['price']:.0f} / {p['duration']}d",
        callback_data=f"buy_{p['id']}"
    )] for p in plans]
    await update.message.reply_text(
        "🛍 <b>Choose a subscription plan:</b>",
        parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return SELECTING_PLAN


async def cb_buy_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[1])
    plan = db.get_plan(plan_id)
    if not plan:
        await query.message.reply_text("❌ Plan not found.")
        return ConversationHandler.END

    order_id = gen_order_id()
    db.create_order(order_id, query.from_user.id, plan_id, plan["price"])
    ctx.user_data["order_id"] = order_id
    ctx.user_data["plan"] = plan

    text = (
        f"🛍 <b>Your Order Details:</b>\n\n"
        f"📦 Category: {plan['category']}\n"
        f"📋 Plan: {plan['name']}\n"
        f"⏱ Duration: {plan['duration']} days\n"
        f"💰 Amount: ₹{plan['price']:.1f}\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"💳 <b>Choose Your Payment Method:</b>\n\n"
        f"📱 <b>QR Code</b> - Scan with any UPI app\n"
        f"🚀 <b>UPI Apps</b> - Quick payment with native apps\n\n"
        f"📸 Or send payment screenshot if already paid"
    )
    kb = [
        [InlineKeyboardButton("📱 Pay with QR Code",        callback_data="pay_qr")],
        [InlineKeyboardButton("🚀 Pay with UPI Apps",       callback_data="pay_upi")],
        [InlineKeyboardButton("📸 Send Payment Screenshot", callback_data="pay_ss")],
    ]
    await query.message.reply_text(text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_PAYMENT


async def cb_pay_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = ctx.user_data.get("order_id", "N/A")
    plan = ctx.user_data.get("plan", {})
    upi_url = (
        f"upi://pay?pa={config.UPI_ID}&pn={config.UPI_NAME}"
        f"&am={plan.get('price', 0)}&tn={order_id}&cu=INR"
    )
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={upi_url}"
    caption = (
        f"📱 <b>Scan QR Code to Pay</b>\n\n"
        f"💰 Amount: ₹{plan.get('price', 0):.0f}\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"⚠️ Add order ID <code>{order_id}</code> in payment note!\n\n"
        f"After payment, send screenshot below 👇"
    )
    kb = [[InlineKeyboardButton("📸 Send Payment Screenshot", callback_data="pay_ss")]]
    await query.message.reply_photo(qr_img, caption=caption, parse_mode=HTML,
                                    reply_markup=InlineKeyboardMarkup(kb))
    db.update_order_payment(order_id, "qr")
    return WAITING_SCREENSHOT


async def cb_pay_upi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = ctx.user_data.get("order_id", "N/A")
    plan = ctx.user_data.get("plan", {})
    text = (
        f"🚀 <b>Manual UPI Payment</b>\n\n"
        f"🆔 UPI ID: <code>{config.UPI_ID}</code>\n"
        f"👤 Name: {config.UPI_NAME}\n"
        f"💰 Amount: ₹{plan.get('price', 0):.0f}\n\n"
        f"📝 <b>Add this in payment note/remark:</b>\n"
        f"<code>{order_id}</code>\n\n"
        f"After payment, enter transaction ID or send screenshot 👇"
    )
    kb = [
        [InlineKeyboardButton("🔢 Enter Transaction ID", callback_data="pay_txnid")],
        [InlineKeyboardButton("📸 Send Screenshot",      callback_data="pay_ss")],
    ]
    await query.message.reply_text(text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
    db.update_order_payment(order_id, "upi")
    return SELECTING_PAYMENT


async def cb_pay_ss(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 <b>Send your payment screenshot now:</b>\n\n"
        "Our team will verify and activate your subscription shortly.",
        parse_mode=HTML
    )
    return WAITING_SCREENSHOT


async def cb_pay_txnid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🔢 <b>Enter your UPI Transaction ID:</b>\n\nExample: <code>317812345678</code>",
        parse_mode=HTML
    )
    return WAITING_TXN_ID


async def receive_txn_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txn_id = update.message.text.strip()
    order_id = ctx.user_data.get("order_id")
    plan = ctx.user_data.get("plan", {})
    u = update.effective_user
    db.update_order_payment(order_id, "upi", txn_id=txn_id)
    await update.message.reply_text(
        f"✅ <b>Transaction ID received!</b>\n\n"
        f"🔢 TXN ID: <code>{txn_id}</code>\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"⏳ Verification in progress. You will be notified once approved.",
        parse_mode=HTML
    )
    for admin_id in config.ADMIN_IDS:
        try:
            kb = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{order_id}"),
                InlineKeyboardButton("❌ Reject",  callback_data=f"adm_reject_{order_id}"),
            ]]
            await ctx.bot.send_message(
                admin_id,
                f"🔔 <b>New Payment - TXN ID</b>\n\n"
                f"👤 User: <a href='tg://user?id={u.id}'>{u.full_name}</a> (<code>{u.id}</code>)\n"
                f"📋 Plan: {plan.get('name')}\n"
                f"💰 Amount: ₹{plan.get('price', 0):.0f}\n"
                f"🆔 Order: <code>{order_id}</code>\n"
                f"🔢 TXN ID: <code>{txn_id}</code>",
                parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup(kb)
            )
        except Exception as e:
            logger.warning(f"Admin notify failed: {e}")
    return ConversationHandler.END


async def receive_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo
    doc   = update.message.document
    if not photo and not doc:
        await update.message.reply_text("❌ Please send an image/screenshot.")
        return WAITING_SCREENSHOT
    order_id = ctx.user_data.get("order_id")
    plan = ctx.user_data.get("plan", {})
    u = update.effective_user
    file_id = photo[-1].file_id if photo else doc.file_id
    db.update_order_payment(order_id, "screenshot", screenshot=file_id)
    await update.message.reply_text(
        f"📸 <b>Screenshot received!</b>\n\n"
        f"🆔 Order ID: <code>{order_id}</code>\n"
        f"⏳ Admin will verify and activate shortly.\n\n"
        f"📞 Support: {config.SUPPORT_USERNAME}",
        parse_mode=HTML
    )
    for admin_id in config.ADMIN_IDS:
        try:
            cap = (
                f"🔔 <b>New Payment Screenshot</b>\n\n"
                f"👤 User: <a href='tg://user?id={u.id}'>{u.full_name}</a> (<code>{u.id}</code>)\n"
                f"📋 Plan: {plan.get('name')}\n"
                f"💰 Amount: ₹{plan.get('price', 0):.0f}\n"
                f"🆔 Order: <code>{order_id}</code>"
            )
            kb = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{order_id}"),
                InlineKeyboardButton("❌ Reject",  callback_data=f"adm_reject_{order_id}"),
            ]]
            if photo:
                await ctx.bot.send_photo(admin_id, file_id, caption=cap,
                                         parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await ctx.bot.send_document(admin_id, file_id, caption=cap,
                                            parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            logger.warning(f"Admin notify failed: {e}")
    return ConversationHandler.END


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
        text += (
            f"🔗 <b>{s['plan_name']}</b> - 🟢 Active\n"
            f"   📝 Category: {s['category']}\n"
            f"   🔧 Service: {s['services']}\n"
            f"   📅 Current Purchase: {s['duration']} days\n"
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


# ════════════════════════════════════════════════════════════
#  ADMIN PANEL
# ════════════════════════════════════════════════════════════

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admins only!")
        return
    await update.message.reply_text(
        "⚙️ <b>Admin Panel</b>\n\nChoose an option:",
        parse_mode=HTML,
        reply_markup=admin_panel_kb()
    )


async def show_stats(query):
    stats = db.get_stats()
    text = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"👥 Total Users:   <code>{stats['total_users']}</code>\n"
        f"🧾 Total Orders:  <code>{stats['total_orders']}</code>\n"
        f"⏳ Pending:       <code>{stats['pending']}</code>\n"
        f"✅ Approved:      <code>{stats['approved']}</code>\n"
        f"❌ Rejected:      <code>{stats['rejected']}</code>\n"
        f"📋 Active Subs:   <code>{stats['active_subs']}</code>\n"
        f"💰 Total Revenue: <code>₹{stats['revenue']:.0f}</code>\n"
    )
    await query.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Panel", callback_data="adm_back")
        ]])
    )


async def show_pending(query, ctx):
    orders = db.get_pending_orders()
    if not orders:
        await query.message.reply_text(
            "✅ <b>No pending orders!</b>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Panel", callback_data="adm_back")
            ]])
        )
        return
    await query.message.reply_text(f"⏳ <b>{len(orders)} Pending Order(s):</b>", parse_mode=HTML)
    for o in orders:
        text = (
            f"⏳ <b>Pending Order</b>\n\n"
            f"👤 User: <a href='tg://user?id={o['user_id']}'>{o['full_name']}</a> (<code>{o['user_id']}</code>)\n"
            f"📋 Plan: {o['plan_name']}\n"
            f"💰 Amount: ₹{o['amount']:.0f}\n"
            f"💳 Method: {o['payment_method'] or 'not set'}\n"
            f"🆔 Order: <code>{o['order_id']}</code>\n"
            f"📅 Date: {o['created_at'][:16]}"
        )
        kb = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{o['order_id']}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"adm_reject_{o['order_id']}"),
        ]]
        if o.get("screenshot_file"):
            await ctx.bot.send_photo(
                query.from_user.id, o["screenshot_file"],
                caption=text, parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await query.message.reply_text(text, parse_mode=HTML,
                                           reply_markup=InlineKeyboardMarkup(kb))


async def show_orders(query):
    orders = db.get_all_orders(limit=15)
    if not orders:
        await query.message.reply_text("🧾 No orders yet.")
        return
    text = "🧾 <b>Recent Orders (last 15):</b>\n\n"
    for o in orders:
        emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(o["status"], "❓")
        text += (
            f"{emoji} <code>{o['order_id']}</code>\n"
            f"   👤 {o['full_name']} | 📋 {o['plan_name']}\n"
            f"   💰 ₹{o['amount']:.0f} | 📅 {o['created_at'][:10]}\n\n"
        )
    await query.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Panel", callback_data="adm_back")
        ]])
    )


async def show_users(query):
    users = db.get_all_users()
    text = f"👥 <b>All Users: {len(users)}</b>\n\n"
    for u in users[:20]:
        uname = f"@{u['username']}" if u["username"] else ""
        text += f"• <code>{u['user_id']}</code> {u['full_name']} {uname}\n"
    if len(users) > 20:
        text += f"\n<i>...and {len(users) - 20} more</i>"
    await query.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Panel", callback_data="adm_back")
        ]])
    )


async def show_subs(query):
    subs = db.get_all_subscriptions(active_only=True)
    if not subs:
        await query.message.reply_text("📋 No active subscriptions.")
        return
    text = f"🔔 <b>Active Subscriptions: {len(subs)}</b>\n\n"
    for s in subs[:15]:
        text += (
            f"• <b>{s['plan_name']}</b> - {s['full_name']}\n"
            f"   ⏰ {s['expires_at'][:16]} | ⌛ {remaining_text(s['expires_at'])}\n\n"
        )
    if len(subs) > 15:
        text += f"<i>...and {len(subs) - 15} more</i>"
    await query.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back to Panel", callback_data="adm_back")
        ]])
    )


async def show_plans(query):
    plans = db.get_plans(active_only=False)
    text = "📦 <b>Plans Management:</b>\n\n"
    for p in plans:
        status = "🟢" if p["is_active"] else "🔴"
        text += f"{status} <b>{p['name']}</b> - ₹{p['price']:.0f} / {p['duration']}d\n"
    kb = []
    for p in plans:
        kb.append([
            InlineKeyboardButton(
                f"{'🔴 Disable' if p['is_active'] else '🟢 Enable'} {p['name']}",
                callback_data=f"adm_toggle_{p['id']}"
            ),
            InlineKeyboardButton("🗑 Delete", callback_data=f"adm_delplan_{p['id']}"),
        ])
    kb.append([InlineKeyboardButton("➕ Add New Plan",   callback_data="adm_addplan")])
    kb.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="adm_back")])
    await query.message.reply_text(text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))


# ── Add plan conversation ─────────────────────────────────────

async def adm_addplan_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ <b>Add New Plan</b>\n\n"
        "Send plan details in this format:\n\n"
        "<code>Name | Category | Duration(days) | Price | Services</code>\n\n"
        "Example:\n"
        "<code>ProBot | Bot Hosting | 30 | 499 | fb,autoleech</code>\n\n"
        "Send /cancel to cancel.",
        parse_mode=HTML
    )
    return ADMIN_ADD_PLAN


async def adm_addplan_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    parts = [p.strip() for p in update.message.text.split("|")]
    if len(parts) != 5:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n<code>Name | Category | Duration | Price | Services</code>",
            parse_mode=HTML
        )
        return ADMIN_ADD_PLAN
    try:
        name, category, duration, price, services = parts
        db.add_plan(name, category, int(duration), float(price), "", services)
        await update.message.reply_text(
            f"✅ <b>Plan '{name}' added!</b>\n\n"
            f"📦 Category: {category}\n"
            f"⏱ Duration: {duration} days\n"
            f"💰 Price: ₹{price}\n"
            f"🔧 Services: {services}",
            parse_mode=HTML,
            reply_markup=main_kb(update.effective_user.id)
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return ADMIN_ADD_PLAN
    return ConversationHandler.END


# ── Broadcast conversation ────────────────────────────────────

async def adm_broadcast_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📢 <b>Broadcast Message</b>\n\n"
        "Send the message to broadcast to ALL users.\n\n"
        "Send /cancel to cancel.",
        parse_mode=HTML
    )
    return ADMIN_BROADCAST


async def adm_broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    msg = update.message.text
    users = db.get_all_users()
    sent = failed = 0
    for u in users:
        try:
            await ctx.bot.send_message(u["user_id"], f"📢 <b>Announcement</b>\n\n{msg}", parse_mode=HTML)
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(
        f"📢 <b>Broadcast Complete!</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}\n👥 Total: {len(users)}",
        parse_mode=HTML,
        reply_markup=main_kb(update.effective_user.id)
    )
    return ConversationHandler.END


# ── Reject reason conversation ────────────────────────────────

async def adm_reject_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Admins only!", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    order_id = "_".join(query.data.split("_")[2:])
    ctx.user_data["rejecting_order"] = order_id
    await query.message.reply_text(
        f"❌ Rejecting order <code>{order_id}</code>\n\n"
        f"Send reason, or send /skip to reject without reason:",
        parse_mode=HTML
    )
    return ADMIN_REJECT_REASON


async def adm_reject_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    order_id = ctx.user_data.get("rejecting_order")
    reason = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    order = db.get_order(order_id)
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return ConversationHandler.END
    db.reject_order(order_id, update.effective_user.id, reason)
    await update.message.reply_text(
        f"❌ Order <code>{order_id}</code> rejected.",
        parse_mode=HTML,
        reply_markup=main_kb(update.effective_user.id)
    )
    try:
        reason_text = f"\n📝 Reason: {reason}" if reason else ""
        await ctx.bot.send_message(
            order["user_id"],
            f"❌ <b>Payment Rejected</b>\n\n"
            f"🆔 Order: <code>{order_id}</code>{reason_text}\n\n"
            f"Please contact {config.SUPPORT_USERNAME} for help.",
            parse_mode=HTML
        )
    except Exception as e:
        logger.warning(f"User notify failed: {e}")
    return ConversationHandler.END


# ── Approve ───────────────────────────────────────────────────

async def adm_approve(query, ctx, order_id):
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Admins only!", show_alert=True)
        return
    order = db.get_order(order_id)
    if not order:
        await query.answer("❌ Order not found.", show_alert=True)
        return
    if order["status"] != "pending":
        await query.answer(f"Already {order['status']}.", show_alert=True)
        return
    db.approve_order(order_id, query.from_user.id)
    plan = db.get_plan(order["plan_id"])
    expires = db.activate_subscription(order["user_id"], order["plan_id"], order_id, plan["duration"])
    await query.answer("✅ Approved!", show_alert=True)
    await query.message.reply_text(
        f"✅ Order <code>{order_id}</code> <b>approved!</b>\n"
        f"Active till <code>{expires.strftime('%d-%m-%Y %H:%M')}</code> IST",
        parse_mode=HTML
    )
    try:
        await ctx.bot.send_message(
            order["user_id"],
            f"✅ <b>Subscription Activated!</b>\n\n"
            f"📋 Plan: <b>{plan['name']}</b>\n"
            f"⏰ Expires: {expires.strftime('%d-%m-%Y %H:%M')} IST\n"
            f"⌛ Duration: {plan['duration']} days\n\n"
            f"🔗 Use /invites to get your access links!\n"
            f"📞 Support: {config.SUPPORT_USERNAME}",
            parse_mode=HTML
        )
    except Exception as e:
        logger.warning(f"User notify failed: {e}")


# ── Master callback router ────────────────────────────────────

async def callback_router(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("adm_") and not is_admin(query.from_user.id):
        await query.answer("⛔ Admins only!", show_alert=True)
        return

    await query.answer()

    if data == "adm_back":
        await query.message.reply_text(
            "⚙️ <b>Admin Panel</b>", parse_mode=HTML,
            reply_markup=admin_panel_kb()
        )
    elif data == "adm_stats":
        await show_stats(query)
    elif data == "adm_pending":
        await show_pending(query, ctx)
    elif data == "adm_orders":
        await show_orders(query)
    elif data == "adm_users":
        await show_users(query)
    elif data == "adm_subs":
        await show_subs(query)
    elif data == "adm_plans":
        await show_plans(query)
    elif data.startswith("adm_toggle_"):
        plan_id = int(data.split("_")[2])
        db.toggle_plan(plan_id)
        plan = db.get_plan(plan_id)
        status = "enabled 🟢" if plan["is_active"] else "disabled 🔴"
        await query.answer(f"Plan '{plan['name']}' {status}", show_alert=True)
        await show_plans(query)
    elif data.startswith("adm_delplan_"):
        plan_id = int(data.split("_")[2])
        plan = db.get_plan(plan_id)
        db.delete_plan(plan_id)
        await query.answer(f"Plan '{plan['name']}' deleted!", show_alert=True)
        await show_plans(query)
    elif data.startswith("adm_approve_"):
        order_id = "_".join(data.split("_")[2:])
        await adm_approve(query, ctx, order_id)
    # adm_reject_ handled by reject_conv ConversationHandler


# ── Text shortcuts ────────────────────────────────────────────

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🛍 Buy Subscription":
        await cmd_buy(update, ctx)
    elif text == "📋 My Subscriptions":
        await cmd_myplan(update, ctx)
    elif text == "🔗 Get Invites":
        await cmd_invites(update, ctx)
    elif text == "🔍 Payment Status":
        await cmd_status(update, ctx)
    elif text == "⚙️ Admin Panel":
        await cmd_admin(update, ctx)


# ── Cancel ────────────────────────────────────────────────────

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Cancelled.", reply_markup=main_kb(update.effective_user.id))
    return ConversationHandler.END


# ── Scheduled expiry checker ──────────────────────────────────

async def check_expiry(ctx: ContextTypes.DEFAULT_TYPE):
    for s in db.get_expiring_soon(48):
        try:
            await ctx.bot.send_message(
                s["user_id"],
                f"⚠️ <b>Subscription Expiring Soon!</b>\n\n"
                f"Your subscription for <b>{s['plan_name']}</b> will expire in "
                f"{remaining_text(s['expires_at'])}\n\n"
                f"📅 Expiry: {s['expires_at'][:16]} IST\n\n"
                f"🛒 Renew now to continue enjoying the service!",
                parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Renew Subscription", callback_data=f"buy_{s['plan_id']}")
                ]])
            )
        except Exception as e:
            logger.warning(f"Expiry notify failed: {e}")

    for e in db.expire_subscriptions():
        try:
            await ctx.bot.send_message(
                e["user_id"],
                f"❌ <b>Subscription Expired</b>\n\n"
                f"Your subscription for <b>{e['plan_name']}</b> has expired.\n\n"
                f"🛒 Renew now to continue using the service!",
                parse_mode=HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🛒 Renew Now", callback_data=f"buy_{e['plan_id']}")
                ]])
            )
        except Exception as e2:
            logger.warning(f"Expired notify failed: {e2}")


# ── Main ──────────────────────────────────────────────────────

def main():
    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    buy_conv = ConversationHandler(
        entry_points=[
            CommandHandler("buy", cmd_buy),
            CallbackQueryHandler(cb_buy_plan, pattern=r"^buy_\d+$"),
        ],
        states={
            SELECTING_PLAN:    [CallbackQueryHandler(cb_buy_plan, pattern=r"^buy_\d+$")],
            SELECTING_PAYMENT: [
                CallbackQueryHandler(cb_pay_qr,    pattern="^pay_qr$"),
                CallbackQueryHandler(cb_pay_upi,   pattern="^pay_upi$"),
                CallbackQueryHandler(cb_pay_ss,    pattern="^pay_ss$"),
                CallbackQueryHandler(cb_pay_txnid, pattern="^pay_txnid$"),
            ],
            WAITING_SCREENSHOT: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_screenshot),
                CallbackQueryHandler(cb_pay_ss, pattern="^pay_ss$"),
            ],
            WAITING_TXN_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_txn_id),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    addplan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_addplan_start, pattern="^adm_addplan$")],
        states={
            ADMIN_ADD_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_addplan_receive)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_broadcast_start, pattern="^adm_broadcast$")],
        states={
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    reject_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_reject_start, pattern=r"^adm_reject_")],
        states={
            ADMIN_REJECT_REASON: [MessageHandler(filters.TEXT, adm_reject_do)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(buy_conv)
    app.add_handler(addplan_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(reject_conv)

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("plans",   cmd_plans))
    app.add_handler(CommandHandler("myplan",  cmd_myplan))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("invites", cmd_invites))
    app.add_handler(CommandHandler("admin",   cmd_admin))
    app.add_handler(CommandHandler("cancel",  cmd_cancel))

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.job_queue.run_repeating(check_expiry, interval=1800, first=60)

    logger.info("🤖 Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
