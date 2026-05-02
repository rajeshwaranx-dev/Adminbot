# handlers/admin.py – Admin panel and commands

import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import config
import database as db
from utils import HTML, remaining_text, gen_order_id, main_kb

logger = logging.getLogger(__name__)

ADMIN_ADD_PLAN      = 10
ADMIN_BROADCAST     = 11
ADMIN_REJECT_REASON = 12
ADMIN_ADDUSER       = 13


def admin_panel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats",          callback_data="adm_stats"),
         InlineKeyboardButton("⏳ Pending",        callback_data="adm_pending")],
        [InlineKeyboardButton("🧾 All Orders",     callback_data="adm_orders"),
         InlineKeyboardButton("👥 Users",          callback_data="adm_users")],
        [InlineKeyboardButton("📦 DB Plans",       callback_data="adm_plans"),
         InlineKeyboardButton("📢 Broadcast",      callback_data="adm_broadcast")],
        [InlineKeyboardButton("🔔 Active Subs",    callback_data="adm_subs")],
    ])


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        await update.message.reply_text("⛔ Admins only!")
        return
    await update.message.reply_text(
        "⚙️ <b>Admin Panel</b>\n\nChoose an option:",
        parse_mode=HTML, reply_markup=admin_panel_kb()
    )


# ── Stats ─────────────────────────────────────────────────────

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
        f"💰 Revenue:       <code>₹{stats['revenue']:.0f}</code>\n"
    )
    await query.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
    )


# ── Pending orders ────────────────────────────────────────────

async def show_pending(query, ctx):
    orders = db.get_pending_orders()
    if not orders:
        await query.message.reply_text(
            "✅ <b>No pending orders!</b>", parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
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
            await ctx.bot.send_photo(query.from_user.id, o["screenshot_file"],
                                     caption=text, parse_mode=HTML,
                                     reply_markup=InlineKeyboardMarkup(kb))
        else:
            await query.message.reply_text(text, parse_mode=HTML,
                                           reply_markup=InlineKeyboardMarkup(kb))


# ── All orders ────────────────────────────────────────────────

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
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
    )


# ── Users ─────────────────────────────────────────────────────

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
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
    )


# ── Active subs ───────────────────────────────────────────────

async def show_subs(query):
    subs = db.get_all_subscriptions(active_only=True)
    if not subs:
        await query.message.reply_text("📋 No active subscriptions.")
        return
    text = f"🔔 <b>Active Subscriptions: {len(subs)}</b>\n\n"
    for s in subs[:15]:
        bot_name = s.get("bot_name") or "—"
        text += (
            f"• <b>{s['plan_name']}</b> – {s['full_name']}\n"
            f"   🤖 Bot: {bot_name}\n"
            f"   ⏰ {s['expires_at'][:16]} | ⌛ {remaining_text(s['expires_at'])}\n\n"
        )
    if len(subs) > 15:
        text += f"<i>...and {len(subs) - 15} more</i>"
    await query.message.reply_text(
        text, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm_back")]])
    )


# ── DB Plans ──────────────────────────────────────────────────

async def show_db_plans(query):
    plans = db.get_plans(active_only=False)
    text = "📦 <b>DB Plans:</b>\n\n"
    if not plans:
        text += "No plans in DB yet.\n"
    for p in plans:
        status = "🟢" if p["is_active"] else "🔴"
        text += f"{status} <b>{p['name']}</b> – ₹{p['price']:.0f} / {p['duration']}d\n"
    kb = []
    for p in plans:
        kb.append([
            InlineKeyboardButton(
                f"{'🔴 Disable' if p['is_active'] else '🟢 Enable'} {p['name']}",
                callback_data=f"adm_toggle_{p['id']}"
            ),
            InlineKeyboardButton("🗑", callback_data=f"adm_delplan_{p['id']}"),
        ])
    kb.append([InlineKeyboardButton("➕ Add Plan",   callback_data="adm_addplan")])
    kb.append([InlineKeyboardButton("🔙 Back",        callback_data="adm_back")])
    await query.message.reply_text(text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))


# ── Add plan conversation ─────────────────────────────────────

async def adm_addplan_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ <b>Add New Plan</b>\n\n"
        "Format:\n<code>Name | Category | Duration(days) | Price | Services</code>\n\n"
        "Example:\n<code>ProBot | Bot Hosting | 30 | 499 | fb,autoleech</code>\n\n"
        "Send /cancel to cancel.",
        parse_mode=HTML
    )
    return ADMIN_ADD_PLAN


async def adm_addplan_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
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
            f"✅ <b>Plan '{name}' added!</b>", parse_mode=HTML,
            reply_markup=main_kb(update.effective_user.id, config.ADMIN_IDS)
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
        "📢 <b>Broadcast</b>\n\nSend message to ALL users. /cancel to cancel.",
        parse_mode=HTML
    )
    return ADMIN_BROADCAST


async def adm_broadcast_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
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
        reply_markup=main_kb(update.effective_user.id, config.ADMIN_IDS)
    )
    return ConversationHandler.END


# ── Reject conversation ───────────────────────────────────────

async def adm_reject_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in config.ADMIN_IDS:
        await query.answer("⛔ Admins only!", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    order_id = "_".join(query.data.split("_")[2:])
    ctx.user_data["rejecting_order"] = order_id
    await query.message.reply_text(
        f"❌ Rejecting <code>{order_id}</code>\n\nSend reason, or /skip to skip:",
        parse_mode=HTML
    )
    return ADMIN_REJECT_REASON


async def adm_reject_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return ConversationHandler.END
    order_id = ctx.user_data.get("rejecting_order")
    reason = "" if update.message.text.strip() == "/skip" else update.message.text.strip()
    order = db.get_order(order_id)
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return ConversationHandler.END
    db.reject_order(order_id, update.effective_user.id, reason)
    await update.message.reply_text(
        f"❌ Order <code>{order_id}</code> rejected.", parse_mode=HTML,
        reply_markup=main_kb(update.effective_user.id, config.ADMIN_IDS)
    )
    try:
        reason_text = f"\n📝 Reason: {reason}" if reason else ""
        await ctx.bot.send_message(
            order["user_id"],
            f"❌ <b>Payment Rejected</b>\n\n🆔 Order: <code>{order_id}</code>{reason_text}\n\n"
            f"Contact {config.SUPPORT_USERNAME} for help.",
            parse_mode=HTML
        )
    except Exception as e:
        logger.warning(f"User notify failed: {e}")
    return ConversationHandler.END


# ── Adduser conversation ──────────────────────────────────────

async def cmd_adduser(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        await update.message.reply_text("⛔ Admins only!")
        return ConversationHandler.END
    plans = db.get_plans()
    text = (
        "👤 <b>Add User Subscription</b>\n\n"
        "Format:\n<code>USER_ID | PLAN_NUMBER | DURATION_DAYS | BOT_NAME</code>\n\n"
        "Available Plans:\n"
    )
    for i, p in enumerate(plans, 1):
        text += f"{i}. {p['name']} – ₹{p['price']:.0f} / {p['duration']}d\n"
    text += (
        "\nExample:\n<code>5102717153 | 1 | 30 | Autopost, Filestore</code>\n\n"
        "📝 BOT_NAME can contain commas. Only | for first 3 fields.\n\n"
        "Send /cancel to cancel."
    )
    ctx.user_data["adduser_plans"] = plans
    await update.message.reply_text(text, parse_mode=HTML)
    return ADMIN_ADDUSER


async def cmd_adduser_receive(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in config.ADMIN_IDS:
        return ConversationHandler.END
    parts = [p.strip() for p in update.message.text.split("|", 3)]
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Format: <code>USER_ID | PLAN_NUMBER | DURATION_DAYS | BOT_NAME</code>",
            parse_mode=HTML
        )
        return ADMIN_ADDUSER
    try:
        user_id  = int(parts[0])
        plan_num = int(parts[1])
        duration = int(parts[2])
        bot_name = parts[3].strip() if len(parts) == 4 else "—"
        plans = ctx.user_data.get("adduser_plans") or db.get_plans()
        if plan_num < 1 or plan_num > len(plans):
            await update.message.reply_text(f"❌ Plan number must be 1 to {len(plans)}.")
            return ADMIN_ADDUSER
        plan = plans[plan_num - 1]
        order_id = gen_order_id()
        db.create_order(order_id, user_id, plan["id"], plan["price"])
        db.approve_order(order_id, update.effective_user.id)
        expires = db.activate_subscription(user_id, plan["id"], order_id, duration, bot_name)
        await update.message.reply_text(
            f"✅ <b>Subscription activated!</b>\n\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"🤖 Bot Name: <b>{bot_name}</b>\n"
            f"📋 Plan: <b>{plan['name']}</b>\n"
            f"⏱ Duration: {duration} days\n"
            f"⏰ Expires: {expires.strftime('%d-%m-%Y %H:%M')} IST\n"
            f"🆔 Order: <code>{order_id}</code>",
            parse_mode=HTML,
            reply_markup=main_kb(update.effective_user.id, config.ADMIN_IDS)
        )
        try:
            await ctx.bot.send_message(
                user_id,
                f"✅ <b>Subscription Activated!</b>\n\n"
                f"🤖 Bot Name: <b>{bot_name}</b>\n"
                f"📋 Plan: <b>{plan['name']}</b>\n"
                f"⏰ Expires: {expires.strftime('%d-%m-%Y %H:%M')} IST\n"
                f"⌛ Duration: {duration} days\n\n"
                f"📞 Support: {config.SUPPORT_USERNAME}",
                parse_mode=HTML
            )
        except Exception as e:
            logger.warning(f"Could not notify user {user_id}: {e}")
            await update.message.reply_text(
                f"⚠️ Activated but could not notify <code>{user_id}</code> (not started bot yet).",
                parse_mode=HTML
            )
    except ValueError:
        await update.message.reply_text("❌ USER_ID, PLAN_NUMBER and DURATION must be numbers.")
        return ADMIN_ADDUSER
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
        return ADMIN_ADDUSER
    return ConversationHandler.END


# ── Approve ───────────────────────────────────────────────────

async def adm_approve(query, ctx, order_id):
    if query.from_user.id not in config.ADMIN_IDS:
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

    if data.startswith("adm_") and query.from_user.id not in config.ADMIN_IDS:
        await query.answer("⛔ Admins only!", show_alert=True)
        return

    await query.answer()

    if data == "adm_back":
        await query.message.reply_text(
            "⚙️ <b>Admin Panel</b>", parse_mode=HTML, reply_markup=admin_panel_kb()
        )
    elif data == "adm_stats":   await show_stats(query)
    elif data == "adm_pending": await show_pending(query, ctx)
    elif data == "adm_orders":  await show_orders(query)
    elif data == "adm_users":   await show_users(query)
    elif data == "adm_subs":    await show_subs(query)
    elif data == "adm_plans":   await show_db_plans(query)
    elif data.startswith("adm_toggle_"):
        plan_id = int(data.split("_")[2])
        db.toggle_plan(plan_id)
        plan = db.get_plan(plan_id)
        await query.answer(
            f"Plan '{plan['name']}' {'enabled 🟢' if plan['is_active'] else 'disabled 🔴'}",
            show_alert=True
        )
        await show_db_plans(query)
    elif data.startswith("adm_delplan_"):
        plan_id = int(data.split("_")[2])
        plan = db.get_plan(plan_id)
        db.delete_plan(plan_id)
        await query.answer(f"Plan '{plan['name']}' deleted!", show_alert=True)
        await show_db_plans(query)
    elif data.startswith("adm_approve_"):
        order_id = "_".join(data.split("_")[2:])
        await adm_approve(query, ctx, order_id)

