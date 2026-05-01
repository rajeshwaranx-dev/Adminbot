# 🤖 Ask Subscription Bot

Telegram subscription manager with UPI payments + full admin panel inside Telegram.
No web server. No Flask. Everything runs from one bot.

---

## 📁 Files

```
subscription_bot/
├── bot.py          ← Everything: bot + admin panel
├── database.py     ← SQLite database
├── config.py       ← Your settings (edit first!)
└── requirements.txt
```

---

## ⚙️ Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Edit config.py
| Setting | What to put |
|---------|-------------|
| `BOT_TOKEN` | From @BotFather |
| `ADMIN_IDS` | Your Telegram user ID (get from @userinfobot) |
| `UPI_ID` | Your UPI ID e.g. yourname@paytm |
| `UPI_NAME` | Your name |
| `SUPPORT_USERNAME` | Your Telegram @username |
| `CHANNEL_USERNAME` | Your channel @username |

### 3. Run
```bash
python bot.py
```

---

## 🤖 User Commands

| Command | Action |
|---------|--------|
| /start | Welcome + menu |
| /buy | Buy a subscription |
| /plans | View all plans |
| /myplan | My active subscriptions |
| /status | Recent order status |
| /invites | Get channel invite links |

---

## ⚙️ Admin Panel (Telegram only)

Admins see an extra **⚙️ Admin Panel** button in the keyboard.
Or type /admin.

| Button | Action |
|--------|--------|
| 📊 Stats | Users, orders, revenue |
| ⏳ Pending Orders | Review + approve/reject payments |
| 🧾 All Orders | Last 15 orders |
| 👥 Users | All registered users |
| 📦 Plans | Enable/disable/delete/add plans |
| 📢 Broadcast | Send message to all users |
| 🔔 Active Subs | All active subscriptions |

---

## 💳 Payment Flow

1. User selects plan → gets Order ID
2. Pays via QR code / UPI / screenshot
3. Admin gets notified instantly with ✅ Approve / ❌ Reject buttons
4. On approval → subscription auto-activated, user notified

---

## 🔔 Auto Notifications

- ⚠️ Warning sent 48h before expiry
- ❌ Expiry message sent when subscription ends
- Checks run every 30 minutes automatically
- 
