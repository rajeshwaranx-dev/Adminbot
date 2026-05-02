# plans.py – All subscription categories and plans

CATEGORIES = [
    ("cat_botsub",  "🤖 Bot Subscription"),
    ("cat_leech",   "📥 Leech Group Subscription"),
    ("cat_hosting", "🖥 Bot Hosting Subscription"),
    ("cat_addon",   "📢 Addon Channel Subscription"),
]

BOT_PLANS = [
    {"id": "bp_autopost",    "name": "Auto Post Bot",    "price": 150, "duration": 30},
    {"id": "bp_filestore",   "name": "File Store Bot",   "price": 50,  "duration": 30},
    {"id": "bp_autofilter",  "name": "Auto Filter Bot",  "price": 80,  "duration": 30},
    {"id": "bp_leech",       "name": "Leech Bot",        "price": 150, "duration": 30},
    {"id": "bp_rss",         "name": "Rss Bot",          "price": 50,  "duration": 30},
    {"id": "bp_forward",     "name": "Forward Bot",      "price": 50,  "duration": 30},
    {"id": "bp_autocaption", "name": "Auto Caption Bot", "price": 50,  "duration": 30},
]

LEECH_PLANS = [
    {"id": "lp_basic", "name": "Ask Leech Group Plan",     "price": 50, "duration": 30},
    {"id": "lp_pro",   "name": "Ask Leech Group Pro Plan", "price": 80, "duration": 30},
]

ADDON_PLANS = [
    {"id": "ap_tmv_7",  "name": "Tmv Links Channel",  "price": 5,  "duration": 7},
    {"id": "ap_tmv_15", "name": "Tmv Links Channel",  "price": 10, "duration": 15},
    {"id": "ap_tmv_30", "name": "Tmv Links Channel",  "price": 15, "duration": 30},
    {"id": "ap_tbl_7",  "name": "Tbl Links Channel",  "price": 5,  "duration": 7},
    {"id": "ap_tbl_15", "name": "Tbl Links Channel",  "price": 10, "duration": 15},
    {"id": "ap_tbl_30", "name": "Tbl Links Channel",  "price": 15, "duration": 30},
]

ALL_PLANS = {p["id"]: p for p in BOT_PLANS + LEECH_PLANS + ADDON_PLANS}

