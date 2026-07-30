
import traceback
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and send message to user"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Send message to user
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred. Please try again later.\n"
            f"Contact {CONTACT_USERNAME} for support."
        )
    
    # Print full traceback
    traceback.print_exception(type(context.error), context.error, context.error.__traceback__)
import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==============================
# CONFIGURATION
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN", "8762939199:AAEemk65EKLZRqnq4-MZggifFsMsNCc4YAg")
DATABASE_FILE = "users.db"

# Source and Contact Information
SOURCE = "@Rachit4455"
CONTACT_USERNAME = "@Rachit4455"  # Payment contact
ADMIN_USERNAME = "Rachit4455"     # Admin username (without @)
ADMIN_IDS = [6014074698]           # Add admin user IDs here (replace with actual admin IDs)

# ==============================
# DATABASE SETUP
# ==============================
def init_db():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            free_trial_used INTEGER DEFAULT 0,
            is_premium INTEGER DEFAULT 0,
            lookups_remaining INTEGER DEFAULT 0,
            subscription_expiry TEXT,
            joined_date TEXT,
            payment_status TEXT DEFAULT 'pending'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            payment_id TEXT,
            plan_type TEXT,
            timestamp TEXT,
            status TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def use_free_trial(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET free_trial_used = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_lookups(user_id, count):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET lookups_remaining = lookups_remaining + ?, is_premium = 1, payment_status = 'completed' WHERE user_id = ?",
        (count, user_id)
    )
    conn.commit()
    conn.close()

def deduct_lookup(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET lookups_remaining = lookups_remaining - 1 WHERE user_id = ? AND lookups_remaining > 0",
        (user_id,)
    )
    conn.commit()
    conn.close()

def check_access(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT free_trial_used, is_premium, lookups_remaining, payment_status FROM users WHERE user_id = ?",
        (user_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def save_transaction(user_id, amount, payment_id, plan_type, status='pending'):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO transactions (user_id, amount, payment_id, plan_type, timestamp, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, payment_id, plan_type, datetime.now().isoformat(), status))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY joined_date DESC")
    users = cursor.fetchall()
    conn.close()
    return users

def get_pending_payments():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE status = 'pending' ORDER BY timestamp DESC")
    payments = cursor.fetchall()
    conn.close()
    return payments

# ==============================
# ADMIN FUNCTIONS
# ==============================
def is_admin(user_id, username):
    """Check if user is admin"""
    if user_id in ADMIN_IDS:
        return True
    if username and username.lower() == ADMIN_USERNAME.lower():
        return True
    return False

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel with all admin commands"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ This command is for admins only!")
        return
    
    admin_message = """
🔐 *ADMIN PANEL*

━━━━━━━━━━━━━━━━━━
📋 *Admin Commands:*
━━━━━━━━━━━━━━━━━━

👤 *User Management:*
• /add_lookups <user_id> <count>
  Add lookups to a user
  
• /remove_lookups <user_id> <count>
  Remove lookups from a user

• /set_premium <user_id> <days>
  Set premium for X days (0 to remove)

• /ban_user <user_id>
  Ban a user

• /unban_user <user_id>
  Unban a user

📊 *View Information:*
• /view_user <user_id>
  View user details

• /all_users
  List all users

• /pending_payments
  View pending payments

• /user_count
  Total user count

💬 *Broadcast:*
• /broadcast <message>
  Send message to all users

━━━━━━━━━━━━━━━━━━
👨‍💻 *Admin:* {SOURCE}
"""
    
    await update.message.reply_text(
        admin_message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def admin_add_lookups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add lookups to a user"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /add_lookups <user_id> <count>\n"
            "Example: /add_lookups 123456789 10\n\n"
            "Or reply to a user's message: /add_lookups 10"
        )
        return
    
    try:
        # Check if replying to a message
        if update.message.reply_to_message:
            target_user_id = update.message.reply_to_message.from_user.id
            count = int(context.args[0])
        else:
            target_user_id = int(context.args[0])
            count = int(context.args[1])
        
        # Check if user exists
        user = get_user(target_user_id)
        if not user:
            await update.message.reply_text(f"❌ User {target_user_id} not found!")
            return
        
        add_lookups(target_user_id, count)
        
        # Notify admin
        await update.message.reply_text(
            f"✅ Successfully added *{count}* lookups to user *{target_user_id}*",
            parse_mode='Markdown'
        )
        
        # Notify user
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🎉 *Lookups Added!*\n\n"
                     f"✅ *{count}* lookups have been added to your account.\n"
                     f"👨‍💻 Admin: {SOURCE}\n\n"
                     f"Use /status to check your balance.",
                parse_mode='Markdown'
            )
        except:
            await update.message.reply_text("⚠️ Could not notify user (they may have blocked the bot)")
    
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or count. Please use numbers only.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def admin_view_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View detailed user information"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    # Check if replying to a message
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
            return
    else:
        await update.message.reply_text(
            "❌ Usage: /view_user <user_id>\n"
            "Or reply to a user's message with /view_user"
        )
        return
    
    user = get_user(target_user_id)
    
    if not user:
        await update.message.reply_text(f"❌ User {target_user_id} not found!")
        return
    
    user_id_db, username_db, first_name, free_trial, premium, lookups, expiry, joined, payment = user
    
    message = f"""
👤 *USER DETAILS*

🆔 User ID: `{user_id_db}`
👤 Username: @{username_db or 'N/A'}
📛 Name: {first_name or 'N/A'}
📅 Joined: {joined or 'N/A'}

━━━━━━━━━━━━━━━━━━
📊 *Status:*
━━━━━━━━━━━━━━━━━━
🎁 Free Trial: {'Available' if not free_trial else 'Used'}
💎 Premium: {'Active' if premium else 'Inactive'}
🔍 Lookups: {lookups or 0}
📅 Expiry: {expiry or 'N/A'}
💳 Payment: {payment or 'N/A'}
"""
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def admin_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    users = get_all_users()
    
    if not users:
        await update.message.reply_text("📊 No users found!")
        return
    
    # Limit to last 50 users to avoid message length issues
    users = users[:50]
    
    message = "📊 *ALL USERS*\n\n"
    
    for i, user in enumerate(users, 1):
        user_id_db, username_db, first_name, free_trial, premium, lookups, expiry, joined, payment = user
        
        trial_status = "✅" if not free_trial else "❌"
        premium_status = "💎" if premium else "🆓"
        
        message += f"{i}. `{user_id_db}` - {first_name or 'N/A'} ({premium_status})\n"
        message += f"   @{username_db or 'N/A'} | Lookups: {lookups or 0}\n\n"
    
    message += f"\n━━━━━━━━━━━━━━━━━━\nTotal users: {len(users)}"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def admin_user_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show total user count"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    users = get_all_users()
    total = len(users)
    premium_users = sum(1 for u in users if u[4])  # is_premium
    free_users = total - premium_users
    
    message = f"""
📊 *USER STATISTICS*

👥 Total Users: *{total}*
💎 Premium Users: *{premium_users}*
🆓 Free Users: *{free_users}*

━━━━━━━━━━━━━━━━━━
👨‍💻 *Bot by:* {SOURCE}
"""
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown'
    )

async def admin_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending payments"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    payments = get_pending_payments()
    
    if not payments:
        await update.message.reply_text("✅ No pending payments!")
        return
    
    message = "💳 *PENDING PAYMENTS*\n\n"
    
    for i, payment in enumerate(payments, 1):
        trans_id, pay_user_id, amount, payment_id, plan, timestamp, status = payment
        
        user = get_user(pay_user_id)
        username_db = user[1] if user else "N/A"
        
        message += f"*{i}. Transaction #{trans_id}*\n"
        message += f"👤 User: `{pay_user_id}` (@{username_db})\n"
        message += f"📦 Plan: {plan}\n"
        message += f"💰 Amount: ₹{amount}\n"
        message += f"📅 Date: {timestamp}\n"
        message += f"📊 Status: {status}\n\n"
        
        # Add quick action buttons
        message += f"Use: `/add_lookups {pay_user_id} <count>`\n"
        message += "━━━━━━━━━━━━━━━━━━\n\n"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast message to all users"""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    if not is_admin(user_id, username):
        await update.message.reply_text("❌ Admin only command!")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /broadcast <message>\n"
            "Example: /broadcast New features added! Check /upgrade"
        )
        return
    
    message = " ".join(context.args)
    
    users = get_all_users()
    success = 0
    failed = 0
    
    await update.message.reply_text(f"📤 Broadcasting to {len(users)} users...")
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user[0],
                text=f"📢 *ANNOUNCEMENT*\n\n{message}\n\n━━━━━━━━━━━━━━━━━━\n👨‍💻 *Bot by:* {SOURCE}",
                parse_mode='Markdown'
            )
            success += 1
        except:
            failed += 1
    
    await update.message.reply_text(
        f"✅ Broadcast complete!\n\n"
        f"✓ Sent: {success}\n"
        f"✗ Failed: {failed}"
    )

# ==============================
# REGULAR BOT HANDLERS
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    create_user(user.id, user.username, user.first_name)
    
    welcome_message = f"""
🚗 *Welcome to Vehicle Lookup Bot!*

🔍 Lookup any Indian vehicle registration details instantly.

🎁 *Free Trial:* 1 free lookup
💰 *Premium Plans Available*

━━━━━━━━━━━━━━━━━━
📋 *Commands:*
━━━━━━━━━━━━━━━━━━
• /lookup - Lookup a vehicle
• /status - Check your subscription
• /upgrade - View premium plans
• /help - Get help
• /contact - Contact for payment

━━━━━━━━━━━━━━━━━━
💳 *Payment Contact:*
━━━━━━━━━━━━━━━━━━
📩 {CONTACT_USERNAME}

━━━━━━━━━━━━━━━━━━
👨‍💻 *Source & Credits:*
━━━━━━━━━━━━━━━━━━
Developer: {SOURCE}

💡 *Send a vehicle number to start!*
Example: `UP16AU0116`
"""
    
    await update.message.reply_text(
        welcome_message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
📚 *Help Menu*

1️⃣ Send any Indian vehicle number to lookup details
2️⃣ First lookup is *FREE*
3️⃣ After that, upgrade to premium

━━━━━━━━━━━━━━━━━━
💰 *Premium Plans:*
━━━━━━━━━━━━━━━━━━
• 1 Lookup: ₹10
• 10 Lookups: ₹50
• 50 Lookups: ₹200
• 100 Lookups: ₹350
• Monthly Unlimited: ₹500

━━━━━━━━━━━━━━━━━━
💳 *How to Pay:*
━━━━━━━━━━━━━━━━━━
📩 Contact: {CONTACT_USERNAME}
Payment methods:
• UPI
• Paytm
• Google Pay
• PhonePe

After payment, you'll receive lookups within 5 minutes.

━━━━━━━━━━━━━━━━━━
👨‍💻 *Developer:*
━━━━━━━━━━━━━━━━━━
{SOURCE}

Use /upgrade to see plans or /contact for payment help.
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = check_access(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ User not found. Please use /start first.")
        return
    
    free_trial_used, is_premium, lookups, payment_status = user_data
    
    message = "📊 *Your Account Status*\n\n"
    message += f"🆔 User ID: `{user_id}`\n"
    message += f"🎁 Free Trial: {'✅ Available' if not free_trial_used else '❌ Used'}\n"
    message += f"💎 Premium: {'✅ Active' if is_premium else '❌ Inactive'}\n"
    
    if is_premium and lookups is not None and lookups >= 0:
        message += f"🔍 Lookups Remaining: *{lookups}*\n"
    elif is_premium and lookups == -1:
        message += "🌟 Plan: *Unlimited Monthly*\n"
    
    message += f"💳 Payment Status: *{payment_status}*\n\n"
    
    if not is_premium:
        message += f"📩 Contact {CONTACT_USERNAME} to upgrade!"
    
    message += f"\n━━━━━━━━━━━━━━━━━━\n👨‍💻 *Bot by:* {SOURCE}"
    
    await update.message.reply_text(
        message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_message = f"""
📞 *Contact for Payment & Support*

━━━━━━━━━━━━━━━━━━
💳 *Payment Contact:*
━━━━━━━━━━━━━━━━━━
👤 Username: {CONTACT_USERNAME}
📩 Telegram: t.me/{CONTACT_USERNAME.replace('@', '')}

━━━━━━━━━━━━━━━━━━
💰 *Payment Methods:*
━━━━━━━━━━━━━━━━━━
• UPI
• Paytm
• Google Pay
• PhonePe

━━━━━━━━━━━━━━━━━━
📋 *Payment Process:*
━━━━━━━━━━━━━━━━━━
1️⃣ Send a message to {CONTACT_USERNAME}
2️⃣ Mention your User ID: `{update.effective_user.id}`
3️⃣ Select your plan
4️⃣ Complete payment
5️⃣ Receive lookups within 5 minutes

━━━━━━━━━━━━━━━━━━
👨‍💻 *Source & Credits:*
━━━━━━━━━━━━━━━━━━
Developer: {SOURCE}
"""
    
    await update.message.reply_text(
        contact_message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 1 Lookup - ₹10", callback_data="plan_1")],
        [InlineKeyboardButton("🔍 10 Lookups - ₹50", callback_data="plan_10")],
        [InlineKeyboardButton("🔍 50 Lookups - ₹200", callback_data="plan_50")],
        [InlineKeyboardButton("🔍 100 Lookups - ₹350", callback_data="plan_100")],
        [InlineKeyboardButton("🌟 Monthly Unlimited - ₹500", callback_data="plan_monthly")],
        [InlineKeyboardButton("📞 Contact for Payment", url=f"https://t.me/{CONTACT_USERNAME.replace('@', '')}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    plans_message = f"""
💎 *Premium Plans*

━━━━━━━━━━━━━━━━━━
📦 *Available Packages:*
━━━━━━━━━━━━━━━━━━
• 1 Lookup: ₹10
• 10 Lookups: ₹50 (₹5/lookup)
• 50 Lookups: ₹200 (₹4/lookup)
• 100 Lookups: ₹350 (₹3.5/lookup)
• Unlimited Monthly: ₹500

━━━━━━━━━━━━━━━━━━
💳 *To Purchase:*
━━━━━━━━━━━━━━━━━━
1️⃣ Select a plan below
2️⃣ Contact {CONTACT_USERNAME} for payment
3️⃣ Share your User ID: `{update.effective_user.id}`
4️⃣ Complete payment
5️⃣ Get lookups activated

━━━━━━━━━━━━━━━━━━
👨‍💻 *Developer:* {SOURCE}
"""
    
    await update.message.reply_text(
        plans_message,
        reply_markup=reply_markup,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    plans = {
        "plan_1": ("1 Lookup", 10, 1),
        "plan_10": ("10 Lookups", 50, 10),
        "plan_50": ("50 Lookups", 200, 50),
        "plan_100": ("100 Lookups", 350, 100),
        "plan_monthly": ("Monthly Unlimited", 500, -1)
    }
    
    if query.data in plans:
        plan_name, price, lookups = plans[query.data]
        
        # Save pending transaction
        save_transaction(user_id, price, "PENDING", plan_name, 'pending')
        
        payment_message = f"""
💳 *Payment Required*

━━━━━━━━━━━━━━━━━━
📦 *Selected Plan:*
━━━━━━━━━━━━━━━━━━
Plan: *{plan_name}*
Amount: *₹{price}*
Your User ID: `{user_id}`

━━━━━━━━━━━━━━━━━━
📩 *Complete Payment:*
━━━━━━━━━━━━━━━━━━
Contact: {CONTACT_USERNAME}
Link: @{CONTACT_USERNAME.replace('@', '')}

━━━━━━━━━━━━━━━━━━
📋 *Steps:*
━━━━━━━━━━━━━━━━━━
1️⃣ Message {CONTACT_USERNAME}
2️⃣ Share your User ID: `{user_id}`
3️⃣ Pay ₹{price} via UPI/Paytm/GPay
4️⃣ Share payment screenshot
5️⃣ Get lookups activated within 5 mins

━━━━━━━━━━━━━━━━━━
👨‍💻 *Bot by:* {SOURCE}
"""
        
        # Create keyboard with contact button
        keyboard = [[
            InlineKeyboardButton(
                "📞 Contact Now",
                url=f"https://t.me/{CONTACT_USERNAME.replace('@', '')}"
            )
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            payment_message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = check_access(user_id)
    
    if not user_data:
        await update.message.reply_text("❌ Please use /start first!")
        return
    
    free_trial_used, is_premium, lookups_remaining, payment_status = user_data
    
    # Check access
    has_access = False
    access_type = ""
    
    if not free_trial_used:
        # Free trial available
        has_access = True
        access_type = "🎁 Free Trial"
        use_free_trial(user_id)
    elif is_premium and (lookups_remaining > 0 or lookups_remaining == -1):
        # Premium with lookups or unlimited
        has_access = True
        access_type = "💎 Premium"
        if lookups_remaining > 0:
            deduct_lookup(user_id)
    
    if not has_access:
        keyboard = [
            [InlineKeyboardButton("💎 View Plans", callback_data="plan_1")],
            [InlineKeyboardButton("📞 Contact for Payment", url=f"https://t.me/{CONTACT_USERNAME.replace('@', '')}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ *No lookups remaining!*\n\n"
            f"You've used your free trial.\n\n"
            f"💳 Contact {CONTACT_USERNAME} to purchase lookups.\n"
            f"🆔 Your User ID: `{user_id}`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    # Process the lookup
    rc = update.message.text.strip().upper()
    
    # Validate vehicle number format (basic check)
    if len(rc) < 8 or len(rc) > 12:
        await update.message.reply_text("❌ Invalid vehicle number format. Example: UP16AU0116")
        return
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    url = f"https://darknagi-osint-vehicle-api.vercel.app/api/vehicle?rc={rc}"
    
    try:
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            await update.message.reply_text(f"❌ API Error ({response.status_code})\nPlease try again later.")
            return
        
        data = response.json()
        
        if data.get("error"):
            await update.message.reply_text("❌ Vehicle not found. Please check the number and try again.")
            return
        
        vehicle = data.get("result", {}).get("Nexus2", {})
        
        message = f"""
🚗 *VEHICLE DETAILS*

🔢 *Number:* `{data.get('rc', 'N/A')}`

━━━━━━━━━━━━━━━━━━
👤 *Owner Info:*
━━━━━━━━━━━━━━━━━━
Name: {vehicle.get('Owner Name') or 'N/A'}
Father: {vehicle.get("Father's Name") or 'N/A'}

━━━━━━━━━━━━━━━━━━
🚘 *Vehicle Info:*
━━━━━━━━━━━━━━━━━━
Model: {vehicle.get('Model Name') or 'N/A'}
Class: {vehicle.get('Vehicle Class') or 'N/A'}
Fuel: {vehicle.get('Fuel Type') or 'N/A'}

━━━━━━━━━━━━━━━━━━
📋 *Registration:*
━━━━━━━━━━━━━━━━━━
Date: {vehicle.get('Registration Date') or 'N/A'}
Insurance: {vehicle.get('Insurance Expiry') or 'N/A'}
RTO: {vehicle.get('Registered RTO') or 'N/A'}

━━━━━━━━━━━━━━━━━━
📍 *Location:*
━━━━━━━━━━━━━━━━━━
Address: {vehicle.get('Address') or 'N/A'}
City: {vehicle.get('City Name') or 'N/A'}

━━━━━━━━━━━━━━━━━━
🤖 *Source:* {data.get('source_by', 'Unknown')}
👨‍💻 *Bot by:* {SOURCE}
"""
        
        # Add access type and remaining lookups
        message += f"\n📊 *Access:* {access_type}"
        if is_premium and lookups_remaining > 0:
            message += f"\n💎 *Remaining lookups:* {lookups_remaining}"
        elif is_premium and lookups_remaining == -1:
            message += f"\n🌟 *Plan:* Unlimited Monthly"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except requests.exceptions.Timeout:
        await update.message.reply_text(
            "⌛ Request timed out. Please try again.\n"
            f"If problem persists, contact {CONTACT_USERNAME}"
        )
    except requests.exceptions.ConnectionError:
        await update.message.reply_text(
            "🌐 Unable to connect to API. Please try again later.\n"
            f"Contact {CONTACT_USERNAME} if issue continues."
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ An error occurred. Please try again.\n"
            f"Contact {CONTACT_USERNAME} for support."
        )

async def lookup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a vehicle number.\n"
            "Example: `/lookup UP16AU0116`",
            parse_mode='Markdown'
        )
        return
    
    # Create a mock message for the lookup function
    update.message.text = context.args[0]
    await lookup(update, context)

# ==============================
# MAIN FUNCTION
# ==============================
import os

# Application ko global banao (webhook ke liye)
application = None

def main():
    # ... saare handlers same rahenge ...
    
    # SIMPLE POLLING (no webhook tension)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()