# buy.py – Buy flow handler

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

import config
import database as db
from plans import BOT_PLANS, LEECH_PLANS, ADDON_PLANS, ALL_PLANS
from utils import HTML, gen_order_id, qr_url

logger = logging.getLogger(__name__)

SELECTING_CATEGORY = 0
SELECTING_PLAN     = 1
SELECTING_PAYMENT  = 2
WAITING_SCREENSHOT = 3


def _category_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Bot Subscription",           callback_data="cat_botsub")],
        [InlineKeyboardButton("📥 Leech Group Subscription",   callback_data="cat_leech")],
        [InlineKeyboardButton("🖥 Bot Hosting Subscription",   callback_data="cat_hosting")],
        [InlineKeyboardButton("📢 Addon Channel Subscription", callback_data="cat_addon")],
    ])


def _make_upi_links(upi_id, upi_name, amount, note):
    """Generate UPI deep links for each app."""
    base = f"pa={upi_id}&pn={upi_name}&am={amount}&tn={note}&cu=INR"
    return {
        "gpay":    f"gpay://upi/pay?{base}",
        "phonepe": f"phonepe://pay?{base}",
        "paytm":   f"paytmmp://pay?{base}",
        "amazon":  f"amazonpay://pay?{base}",
        "bhim":    f"upi://pay?{base}",
        "any":     f"upi://pay?{base}",
    }


async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 <b>Select subscription category:</b>",
        parse_mode=HTML,
        reply_markup=_category_kb()
    )
    return SELECTING_CATEGORY


async def cb_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data

    if cat == "cat_botsub":
        kb = [[InlineKeyboardButton(f"📋 {p['name']} – ₹{p['price']}/30d",
                                    callback_data=f"iplan_{p['id']}")]
              for p in BOT_PLANS]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="buy_back")])
        await query.message.reply_text(
            "🤖 <b>Bot Subscription Plans:</b>",
            parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif cat == "cat_leech":
        kb = [[InlineKeyboardButton(f"📋 {p['name']} – ₹{p['price']}/30d",
                                    callback_data=f"iplan_{p['id']}")]
              for p in LEECH_PLANS]
        kb.append([InlineKeyboardButton("🔙 Back", callback_data="buy_back")])
        await query.message.reply_text(
            "📥 <b>Leech Group Subscription Plans:</b>",
            parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif cat == "cat_hosting":
        kb = [
            [InlineKeyboardButton(
                f"📩 Contact {config.SUPPORT_USERNAME}",
                url=f"https://t.me/{config.SUPPORT_USERNAME.lstrip('@')}"
            )],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_back")],
        ]
        await query.message.reply_text(
            "🖥 <b>Bot Hosting Subscription</b>\n\n"
            "💰 Price varies per bot. Contact admin for details:",
            parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))

    elif cat == "cat_addon":
        kb = [
            [InlineKeyboardButton("📢 Tmv Links – 7d  ₹5",  callback_data="iplan_ap_tmv_7")],
            [InlineKeyboardButton("📢 Tmv Links – 15d ₹10", callback_data="iplan_ap_tmv_15")],
            [InlineKeyboardButton("📢 Tmv Links – 30d ₹15", callback_data="iplan_ap_tmv_30")],
            [InlineKeyboardButton("📢 Tbl Links – 7d  ₹5",  callback_data="iplan_ap_tbl_7")],
            [InlineKeyboardButton("📢 Tbl Links – 15d ₹10", callback_data="iplan_ap_tbl_15")],
            [InlineKeyboardButton("📢 Tbl Links – 30d ₹15", callback_data="iplan_ap_tbl_30")],
            [InlineKeyboardButton("🔙 Back", callback_data="buy_back")],
        ]
        await query.message.reply_text(
            "📢 <b>Addon Channel Subscription:</b>",
            parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))

    return SELECTING_PLAN


async def cb_buy_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🛒 <b>Select subscription category:</b>",
        parse_mode=HTML, reply_markup=_category_kb())
    return SELECTING_CATEGORY


async def cb_inline_plan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan_key = query.data.replace("iplan_", "")
    plan = ALL_PLANS.get(plan_key)
    if not plan:
        await query.message.reply_text("❌ Plan not found.")
        return ConversationHandler.END

    db_plans = db.get_plans()
    db_plan = next((p for p in db_plans if p["name"] == plan["name"]), None)
    if not db_plan:
        db.add_plan(plan["name"], "Inline Plan", plan["duration"], plan["price"], "", "")
        db_plans = db.get_plans()
        db_plan = next((p for p in db_plans if p["name"] == plan["name"]), None)

    order_id = gen_order_id()
    db.create_order(order_id, query.from_user.id, db_plan["id"], plan["price"])
    ctx.user_data["order_id"] = order_id
    ctx.user_data["plan"] = {**db_plan, **plan}

    text = (
        f"🛍 <b>Your Order Details:</b>\n\n"
        f"📋 Plan: <b>{plan['name']}</b>\n"
        f"⏱ Duration: {plan['duration']} days\n"
        f"💰 Amount: ₹{plan['price']}\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"💳 <b>Choose Your Payment Method:</b>"
    )
    kb = [
        [InlineKeyboardButton("📱 Pay with QR Code",        callback_data="pay_qr")],
        [InlineKeyboardButton("🚀 Pay with UPI Apps",       callback_data="pay_upi")],
        [InlineKeyboardButton("📸 Send Payment Screenshot", callback_data="pay_ss")],
    ]
    await query.message.reply_text(
        text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
    return SELECTING_PAYMENT


async def cb_pay_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = ctx.user_data.get("order_id", "N/A")
    plan = ctx.user_data.get("plan", {})
    qr = qr_url(config.UPI_ID, config.UPI_NAME, plan.get("price", 0), order_id)
    caption = (
        f"📱 <b>Scan QR Code to Pay</b>\n\n"
        f"💰 Amount: ₹{plan.get('price', 0)}\n"
        f"🆔 Order ID: <code>{order_id}</code>\n\n"
        f"⚠️ Add <code>{order_id}</code> in payment note!\n\n"
        f"✅ After payment send your screenshot 👇"
    )
    kb = [[InlineKeyboardButton("📸 I've Paid – Send Screenshot", callback_data="pay_ss")]]
    await query.message.reply_photo(
        qr, caption=caption, parse_mode=HTML,
        reply_markup=InlineKeyboardMarkup(kb))
    db.update_order_payment(order_id, "qr")
    return WAITING_SCREENSHOT


async def cb_pay_upi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = ctx.user_data.get("order_id", "N/A")
    plan = ctx.user_data.get("plan", {})
    amount = plan.get("price", 0)
    links = _make_upi_links(config.UPI_ID, config.UPI_NAME, amount, order_id)

    # Send UPI app buttons — each opens the app directly
    # Telegram allows url= on InlineKeyboardButton for https links only
    # So we send deep links as message text (tappable on Android/iOS)
    text = (
        f"🚀 <b>Pay with UPI Apps</b>\n\n"
        f"💰 Amount: <b>₹{amount}</b>\n"
        f"🆔 Order: <code>{order_id}</code>\n"
        f"🆔 UPI ID: <code>{config.UPI_ID}</code>\n\n"
        f"Tap an app button below to pay directly 👇\n\n"
        f"⚠️ If app doesn't open, use QR or copy UPI ID manually."
    )

    # Use url= with intent scheme wrapped via redirects that work in Telegram
    # Best working method: send as inline buttons with upi:// url
    # Telegram on Android opens upi:// links from message text — send as text links
    kb = [
        [
            InlineKeyboardButton("G Pay",     url=links["gpay"]),
            InlineKeyboardButton("PhonePe",   url=links["phonepe"]),
        ],
        [
            InlineKeyboardButton("Paytm",     url=links["paytm"]),
            InlineKeyboardButton("Amazon Pay",url=links["amazon"]),
        ],
        [
            InlineKeyboardButton("BHIM",      url=links["bhim"]),
            InlineKeyboardButton("Any UPI App", url=links["any"]),
        ],
        [InlineKeyboardButton("📸 I've Paid – Send Screenshot", callback_data="pay_ss")],
    ]
    await query.message.reply_text(
        text, parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
    db.update_order_payment(order_id, "upi")
    return WAITING_SCREENSHOT


async def cb_pay_ss(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📸 <b>Send your payment screenshot now:</b>\n\n"
        "Our team will verify and activate your subscription shortly.\n\n"
        f"📞 Support: {config.SUPPORT_USERNAME}",
        parse_mode=HTML
    )
    return WAITING_SCREENSHOT


async def cb_copy_upi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(f"UPI ID: {config.UPI_ID}", show_alert=True)


async def receive_screenshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo
    doc   = update.message.document
    if not photo and not doc:
        await update.message.reply_text("❌ Please send a screenshot image.")
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
                f"📋 Plan: {plan.get('name', 'N/A')}\n"
                f"💰 Amount: ₹{plan.get('price', 0)}\n"
                f"🆔 Order: <code>{order_id}</code>"
            )
            kb = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"adm_approve_{order_id}"),
                InlineKeyboardButton("❌ Reject",  callback_data=f"adm_reject_{order_id}"),
            ]]
            if photo:
                await ctx.bot.send_photo(
                    admin_id, file_id, caption=cap,
                    parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
            else:
                await ctx.bot.send_document(
                    admin_id, file_id, caption=cap,
                    parse_mode=HTML, reply_markup=InlineKeyboardMarkup(kb))
        except Exception as e:
            logger.warning(f"Admin notify failed: {e}")

    return ConversationHandler.END
                              
