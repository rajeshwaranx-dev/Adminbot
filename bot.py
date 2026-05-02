"""
bot.py – Ask Subscription Bot – Main Entry Point
Run: python3 bot.py
"""
import logging

from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
    ConversationHandler
)

import config
import database as db
from utils import remaining_text, HTML

from handlers.buy import (
    cmd_buy, cb_category, cb_buy_back, cb_inline_plan,
    cb_pay_qr, cb_pay_upi, cb_pay_ss, cb_copy_upi,
    receive_screenshot,
    SELECTING_CATEGORY, SELECTING_PLAN, SELECTING_PAYMENT, WAITING_SCREENSHOT,
)
from handlers.user import (
    cmd_start, cmd_myplan, cmd_status, cmd_invites, cmd_cancel,
)
from handlers.admin import (
    cmd_admin, callback_router,
    adm_addplan_start, adm_addplan_receive,
    adm_broadcast_start, adm_broadcast_send,
    adm_reject_start, adm_reject_do,
    cmd_adduser, cmd_adduser_receive,
    ADMIN_ADD_PLAN, ADMIN_BROADCAST, ADMIN_REJECT_REASON, ADMIN_ADDUSER,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_text(update, ctx):
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


async def check_expiry(ctx: ContextTypes.DEFAULT_TYPE):
    for s in db.get_expiring_soon(48):
        try:
            await ctx.bot.send_message(
                s["user_id"],
                f"⚠️ <b>Subscription Expiring Soon!</b>\n\n"
                f"Your subscription for <b>{s['plan_name']}</b> expires in "
                f"{remaining_text(s['expires_at'])}\n\n"
                f"📅 Expiry: {s['expires_at'][:16]} IST\n\n"
                f"🛒 Use /buy to renew now!",
                parse_mode=HTML
            )
        except Exception as e:
            logger.warning(f"Expiry notify failed: {e}")
    for e in db.expire_subscriptions():
        try:
            await ctx.bot.send_message(
                e["user_id"],
                f"❌ <b>Subscription Expired</b>\n\n"
                f"Your subscription for <b>{e['plan_name']}</b> has expired.\n\n"
                f"🛒 Use /buy to renew.",
                parse_mode=HTML
            )
        except Exception as e2:
            logger.warning(f"Expired notify failed: {e2}")


def main():
    db.init_db()
    app = Application.builder().token(config.BOT_TOKEN).build()

    buy_conv = ConversationHandler(
        entry_points=[
            CommandHandler("buy", cmd_buy),
            MessageHandler(filters.Regex("^🛍 Buy Subscription$"), cmd_buy),
        ],
        states={
            SELECTING_CATEGORY: [
                CallbackQueryHandler(cb_category, pattern="^cat_"),
            ],
            SELECTING_PLAN: [
                CallbackQueryHandler(cb_inline_plan, pattern="^iplan_"),
                CallbackQueryHandler(cb_buy_back,    pattern="^buy_back$"),
                CallbackQueryHandler(cb_category,    pattern="^cat_"),
            ],
            SELECTING_PAYMENT: [
                CallbackQueryHandler(cb_pay_qr,  pattern="^pay_qr$"),
                CallbackQueryHandler(cb_pay_upi, pattern="^pay_upi$"),
                CallbackQueryHandler(cb_pay_ss,  pattern="^pay_ss$"),
            ],
            WAITING_SCREENSHOT: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_screenshot),
                CallbackQueryHandler(cb_pay_ss,   pattern="^pay_ss$"),
                CallbackQueryHandler(cb_copy_upi, pattern="^copy_upi$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_chat=True, per_user=True, per_message=False,
    )

    addplan_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_addplan_start, pattern="^adm_addplan$")],
        states={
            ADMIN_ADD_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_addplan_receive)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_chat=True, per_user=True, per_message=False,
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_broadcast_start, pattern="^adm_broadcast$")],
        states={
            ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_chat=True, per_user=True, per_message=False,
    )

    reject_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(adm_reject_start, pattern=r"^adm_reject_")],
        states={
            ADMIN_REJECT_REASON: [MessageHandler(filters.TEXT, adm_reject_do)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_chat=True, per_user=True, per_message=False,
    )

    adduser_conv = ConversationHandler(
        entry_points=[CommandHandler("adduser", cmd_adduser)],
        states={
            ADMIN_ADDUSER: [MessageHandler(filters.TEXT & ~filters.COMMAND, cmd_adduser_receive)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_chat=True, per_user=True, per_message=False,
    )

    app.add_handler(buy_conv)
    app.add_handler(addplan_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(reject_conv)
    app.add_handler(adduser_conv)

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("myplan",  cmd_myplan))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("invites", cmd_invites))
    app.add_handler(CommandHandler("admin",   cmd_admin))
    app.add_handler(CommandHandler("adduser", cmd_adduser))
    app.add_handler(CommandHandler("cancel",  cmd_cancel))

    app.add_handler(CallbackQueryHandler(cb_copy_upi, pattern="^copy_upi$"))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.job_queue.run_repeating(check_expiry, interval=1800, first=60)

    logger.info("🤖 Ask Subscription Bot started!")
    app.run_polling()


if __name__ == "__main__":
    main()
                                  
