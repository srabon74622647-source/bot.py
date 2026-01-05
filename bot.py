import telebot
import pyotp
import json
import os
import sys
import io
from telebot import types
from faker import Faker
from flask import Flask
from threading import Thread

# --- UTF-8 Fix ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- FLASK SERVER FOR 24/7 ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Running Online!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURATION ---
API_TOKEN = '8427393618:AAHcKU6WjDRE7DGnh_LlH3b8qs2lvLLDI9k'
ADMIN_ID = 8220394592
fake = Faker()
bot = telebot.TeleBot(API_TOKEN)
DB_FILE = "bot_database.json"

# --- DATABASE ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "emails": [], "tasks": [], "pending": {}, "progress": {}, "wd_methods": [], "min_wd": 0.5, "wd_requests": {}}
    with open(DB_FILE, "r") as f:
        try: return json.load(f)
        except: return {"users": {}, "emails": [], "tasks": [], "pending": {}, "progress": {}, "wd_methods": [], "min_wd": 0.5, "wd_requests": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

# --- KEYBOARDS ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💰 Balance", "📋 Tasks", "📥 Withdraw", "👤 Profile")
    return markup

def task_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("✅ Submit Task", "❌ Cancel Task")
    return markup

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start(message):
    db = load_db()
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0.0, "active_task": None}
        save_db(db)
    bot.send_message(message.chat.id, "🏠 Welcome to the Earning Bot!", reply_markup=main_menu())
    if message.from_user.id == ADMIN_ID:
        show_admin_panel(message.chat.id)

def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📧 Emails", callback_data="adm_email"),
        types.InlineKeyboardButton("📝 Add Task", callback_data="adm_task"),
        types.InlineKeyboardButton("🗑️ Remove Task", callback_data="rem_task"),
        types.InlineKeyboardButton("⏳ Pending", callback_data="adm_pending"),
        types.InlineKeyboardButton("🔄 Progress", callback_data="adm_prog_list"),
        types.InlineKeyboardButton("💵 Bal Edit", callback_data="adm_bal_edit"),
        types.InlineKeyboardButton("💳 WD Set", callback_data="adm_wd_set")
    )
    bot.send_message(chat_id, "👑 Admin Panel:", reply_markup=markup)

# --- BUTTON HANDLERS ---
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    uid = str(message.from_user.id)
    db = load_db()

    if message.text == "💰 Balance":
        bal = db["users"].get(uid, {}).get("balance", 0.0)
        bot.send_message(message.chat.id, f"💳 Your Balance: **${bal:.2f}**", parse_mode="Markdown")

    elif message.text == "📋 Tasks":
        if not db["tasks"]: return bot.send_message(message.chat.id, "No tasks available.")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for t in db["tasks"]: markup.add(t['name'])
        markup.add("🏠 Back to Menu")
        bot.send_message(message.chat.id, "Select a Task:", reply_markup=markup)

    elif message.text == "👤 Profile":
        u = db["users"].get(uid, {})
        bot.send_message(message.chat.id, f"👤 User: {message.from_user.first_name}\n🆔 ID: `{uid}`\n💰 Balance: ${u.get('balance',0)}")

    elif message.text == "🏠 Back to Menu":
        bot.send_message(message.chat.id, "Main Menu:", reply_markup=main_menu())

    elif message.text == "✅ Submit Task":
        active = db["users"].get(uid, {}).get("active_task")
        if active:
            msg = bot.send_message(message.chat.id, "🔐 Please enter your **2FA Secret Key**:")
            bot.register_next_step_handler(msg, process_submission)
        else:
            bot.send_message(message.chat.id, "No active task found!", reply_markup=main_menu())

    elif message.text == "❌ Cancel Task":
        db["users"][uid]["active_task"] = None
        save_db(db)
        bot.send_message(message.chat.id, "Task Cancelled.", reply_markup=main_menu())

    # Task Selection Logic
    else:
        for t in db["tasks"]:
            if message.text == t['name']:
                start_task_ui(message, t)
                return

# --- TASK LOGIC ---
def start_task_ui(message, task):
    db = load_db()
    f_name, l_name = fake.first_name(), fake.last_name()
    login = f"{f_name.lower()}{fake.random_int(10, 99)}"
    email = db["emails"].pop(0) if db["emails"] else "Contact Admin"
    db["users"][str(message.from_user.id)]["active_task"] = {
        "name": task['name'], "f_name": f_name, "l_name": l_name,
        "login": login, "pass": task['password'], "email": email, "reward": task['reward']
    }
    save_db(db)
    
    text = (
        f"🎯 **Task:** {task['name']}\n\n"
        f"👤 **First Name:** `{f_name}`\n"
        f"👤 **Last Name:** `{l_name}`\n"
        f"🔑 **Login:** `{login}`\n"
        f"🔐 **Password:** `{task['password']}`\n"
        f"📧 **Email:** `{email}`\n"
        f"💰 **Reward:** ${task['reward']}\n\n"
        f"⚠️ *Must be on 2FA, otherwise task will be rejected.*"
    )
    m = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("📩 Get Code", url="https://maildrop.cc/"),
        types.InlineKeyboardButton("🔐 Get 2FA", callback_data="get_2fa")
    )
    bot.send_message(message.chat.id, text, reply_markup=m, parse_mode="Markdown")
    bot.send_message(message.chat.id, "Submit or Cancel:", reply_markup=task_action_menu())

def process_submission(message):
    uid = str(message.from_user.id)
    db = load_db()
    active = db["users"][uid].get("active_task")
    if not active: return
    
    sid = f"S{fake.random_int(1000, 9999)}"
    db["pending"][sid] = {**active, "uid": uid, "2fa": message.text}
    db["users"][uid]["active_task"] = None
    save_db(db)
    
    bot.send_message(message.chat.id, "✅ Task submitted for review!", reply_markup=main_menu())
    
    admin_text = (
        f"🔔 **New Submission!**\n\n"
        f"🆔 **ID:** {sid} | 👤 **UID:** `{uid}`\n"
        f"👤 **Name:** {active['f_name']} {active['l_name']}\n"
        f"🔑 **Login:** `{active['login']}`\n"
        f"🔐 **Pass:** `{active['pass']}`\n"
        f"📧 **Email:** `{active['email']}`\n"
        f"🔑 **2FA Key:** `{message.text}`\n"
        f"💰 **Reward:** ${active['reward']}"
    )
    m = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"),
        types.InlineKeyboardButton("Progress", callback_data=f"pg_{sid}"),
        types.InlineKeyboardButton("Reject", callback_data=f"rj_{sid}")
    )
    bot.send_message(ADMIN_ID, admin_text, reply_markup=m, parse_mode="Markdown")

# --- ADMIN CALLBACKS ---
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    db = load_db()
    
    if call.data.startswith(("ap_", "pg_", "rj_")):
        act, sid = call.data.split("_")
        sub = db["pending"].pop(sid, None) or db["progress"].pop(sid, None)
        if sub:
            if act == "ap":
                db["users"][str(sub['uid'])]["balance"] += sub['reward']
                bot.send_message(sub['uid'], f"✅ Task Approved! ${sub['reward']} added.")
            elif act == "pg": db["progress"][sid] = sub
            elif act == "rj": bot.send_message(sub['uid'], "❌ Task Rejected.")
            save_db(db)
            bot.edit_message_text(f"Task {sid} {act} done.", call.message.chat.id, call.message.message_id)

    elif call.data == "adm_pending":
        if not db["pending"]: return bot.answer_callback_query(call.id, "No pending tasks.")
        for sid, d in db["pending"].items():
            text = f"⏳ **ID:** {sid}\n👤 **User:** `{d['uid']}`\n🔑 **Login:** `{d['login']}`\n🔐 **Pass:** `{d['pass']}`\n🔑 **2FA:** `{d['2fa']}`"
            m = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"),
                types.InlineKeyboardButton("Progress", callback_data=f"pg_{sid}"),
                types.InlineKeyboardButton("Reject", callback_data=f"rj_{sid}")
            )
            bot.send_message(ADMIN_ID, text, reply_markup=m, parse_mode="Markdown")

    elif call.data == "adm_prog_list":
        if not db["progress"]: return bot.answer_callback_query(call.id, "No progress tasks.")
        for sid, d in db["progress"].items():
            text = f"🔄 **ID:** {sid}\n🔑 **Login:** `{d['login']}`\n🔑 **2FA:** `{d['2fa']}`"
            m = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"),
                types.InlineKeyboardButton("Reject", callback_data=f"rj_{sid}")
            )
            bot.send_message(ADMIN_ID, text, reply_markup=m, parse_mode="Markdown")

    elif call.data == "adm_task":
        msg = bot.send_message(call.message.chat.id, "Enter Task Name:")
        bot.register_next_step_handler(msg, lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, f"Password for {m.text}:"), lambda p, n=m.text: bot.register_next_step_handler(bot.send_message(p.chat.id, "Reward Amount ($):"), lambda r, n=n, p=p.text: [db := load_db(), db["tasks"].append({"name":n, "password":p, "reward":float(r.text)}), save_db(db), bot.send_message(r.chat.id, "Task Created!")])))

    elif call.data == "adm_email":
        msg = bot.send_message(call.message.chat.id, "Enter Emails (one per line):")
        bot.register_next_step_handler(msg, lambda m: [db := load_db(), db["emails"].extend(m.text.split("\n")), save_db(db), bot.send_message(m.chat.id, "Emails Added!")])

    elif call.data == "get_2fa":
        msg = bot.send_message(call.message.chat.id, "Enter Secret Key:")
        bot.register_next_step_handler(msg, lambda m: bot.send_message(m.chat.id, f"OTP Code: `{pyotp.TOTP(m.text.replace(' ','')).now()}`"))

# --- START BOT ---
if __name__ == "__main__":
    keep_alive()
    print("Bot is starting...")
    bot.infinity_polling()

