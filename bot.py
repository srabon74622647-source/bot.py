import telebot
import pyotp
import json
import os
import sys
import io
import random
import string
from telebot import types
from faker import Faker
from flask import Flask
from threading import Thread

# --- UTF-8 Fix ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- FLASK SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURATION ---
API_TOKEN = '8326762612:AAGwI_b7gTr27oWF0HK4B91HafJFJ7RuZow'
ADMIN_ID = 8220394592
fake = Faker()
bot = telebot.TeleBot(API_TOKEN)
DB_FILE = "bot_database.json"

# --- CUSTOM LOGIN GENERATOR ---
def generate_custom_login(name):
    prefix = name.lower()[:3]
    length = random.randint(10, 20)
    chars = string.ascii_lowercase + string.digits
    remaining_length = length - (len(prefix) + 1)
    random_part = ''.join(random.choice(chars) for _ in range(remaining_length))
    return f"{prefix}_{random_part}"

# --- DATABASE FUNCTIONS ---
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

def wd_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Add Method", "🗑️ Remove Method", "💵 Set Min WD", "🏠 Back to Menu")
    return markup

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start(message):
    db = load_db()
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0.0, "active_task": None}
        save_db(db)
    bot.send_message(message.chat.id, "🏠 Welcome!", reply_markup=main_menu())
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

# --- MAIN TEXT HANDLERS ---
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

    elif message.text == "📥 Withdraw":
        bal = db["users"].get(uid, {}).get("balance", 0.0)
        min_amt = db.get("min_wd", 0.5)
        if bal < min_amt:
            return bot.send_message(message.chat.id, f"❌ Minimum Withdraw is ${min_amt}")
        if not db["wd_methods"]: return bot.send_message(message.chat.id, "No withdraw methods available.")
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for m in db["wd_methods"]: markup.add(m)
        markup.add("🏠 Back to Menu")
        bot.send_message(message.chat.id, "Select Payment Method:", reply_markup=markup)

    elif message.text == "🏠 Back to Menu":
        bot.send_message(message.chat.id, "Main Menu:", reply_markup=main_menu())

    elif message.text == "👤 Profile":
        u = db["users"].get(uid, {})
        bot.send_message(message.chat.id, f"👤 User: {message.from_user.first_name}\n🆔 ID: `{uid}`\n💰 Balance: ${u.get('balance',0)}")

    elif message.text == "❌ Cancel Task":
        db["users"][uid]["active_task"] = None
        save_db(db)
        bot.send_message(message.chat.id, "❌ Task Cancelled.", reply_markup=main_menu())

    elif message.from_user.id == ADMIN_ID:
        if message.text == "➕ Add Method":
            msg = bot.send_message(message.chat.id, "Enter Method Name:")
            bot.register_next_step_handler(msg, add_method_logic)
        elif message.text == "🗑️ Remove Method":
            m = types.InlineKeyboardMarkup()
            for meth in db["wd_methods"]: m.add(types.InlineKeyboardButton(f"Delete {meth}", callback_data=f"delmet_{meth}"))
            bot.send_message(message.chat.id, "Select method to delete:", reply_markup=m)
        elif message.text == "💵 Set Min WD":
            msg = bot.send_message(message.chat.id, "Enter Min Withdraw Amount:")
            bot.register_next_step_handler(msg, set_min_logic)

    if message.text == "✅ Submit Task":
        active = db["users"][uid].get("active_task")
        if active:
            msg = bot.send_message(message.chat.id, "🔐 Enter your **2FA Secret Key**:")
            bot.register_next_step_handler(msg, process_submission)
    
    # Task Selection
    for t in db["tasks"]:
        if message.text == t['name']:
            start_task_ui(message, t)

# --- TASK UI (আপনার পছন্দের সেই ফরম্যাট) ---
def start_task_ui(message, task):
    db = load_db()
    f, l = fake.first_name(), fake.last_name()
    full_name = f"{f} {l}"
    login = generate_custom_login(f)
    email = db["emails"].pop(0) if db["emails"] else "Contact Admin"
    
    db["users"][str(message.from_user.id)]["active_task"] = {
        "name": task['name'], "f_name": f, "l_name": l, 
        "login": login, "pass": task['password'], "email": email, "reward": task['reward']
    }
    save_db(db)
    
    # শুরুর সেই সুন্দর ফরম্যাট
    text = (
        f"🎯 Task: {task['name']}\n\n"
        f"👤 Name: `{full_name}`\n"
        f"🔑 Login: `{login}`\n"
        f"🔐 Pass: `{task['password']}`\n"
        f"📧 Email: `{email}`\n"
        f"💰 Reward: ${task['reward']}\n\n"
        f"⚠️ Must be on 2FA, otherwise task will be rejected."
    )
    
    m = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("📩 Get Code", url="https://maildrop.cc/"),
        types.InlineKeyboardButton("🔐 Get 2FA", callback_data="get_2fa")
    )
    bot.send_message(message.chat.id, text, reply_markup=m, parse_mode="Markdown")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Submit Task", "❌ Cancel Task")
    bot.send_message(message.chat.id, "Submit or Cancel?", reply_markup=markup)

# --- ADMIN CALLBACKS & REMOVE TASK FIX ---
@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call):
    db = load_db()
    
    if call.data == "rem_task":
        if not db["tasks"]: return bot.answer_callback_query(call.id, "No tasks to remove.")
        markup = types.InlineKeyboardMarkup()
        for t in db["tasks"]:
            markup.add(types.InlineKeyboardButton(f"❌ {t['name']}", callback_data=f"del_tk_{t['name']}"))
        bot.send_message(ADMIN_ID, "Select task to remove:", reply_markup=markup)

    elif call.data.startswith("del_tk_"):
        tname = call.data.replace("del_tk_", "")
        db["tasks"] = [t for t in db["tasks"] if t['name'] != tname]
        save_db(db)
        bot.edit_message_text(f"✅ Task '{tname}' removed!", call.message.chat.id, call.message.message_id)

    elif call.data == "adm_wd_set":
        bot.send_message(call.message.chat.id, "Withdraw Settings:", reply_markup=wd_admin_keyboard())
    
    elif call.data == "adm_bal_edit":
        msg = bot.send_message(call.message.chat.id, "Enter User ID:")
        bot.register_next_step_handler(msg, bal_edit_step_1)

    elif call.data.startswith("delmet_"):
        meth = call.data.split("_")[1]
        if meth in db["wd_methods"]:
            db["wd_methods"].remove(meth)
            save_db(db)
            bot.edit_message_text(f"✅ {meth} Deleted.", call.message.chat.id, call.message.message_id)

    elif call.data.startswith(("ap_", "pg_", "rj_", "wp_", "wr_")):
        act, sid = call.data.split("_")
        if act in ["ap", "pg", "rj"]:
            sub = db["pending"].pop(sid, None) or db["progress"].pop(sid, None)
            if sub:
                if act == "ap":
                    db["users"][str(sub['uid'])]["balance"] += sub['reward']
                    bot.send_message(sub['uid'], "✅ Approved!")
                elif act == "pg": db["progress"][sid] = sub
                elif act == "rj": bot.send_message(sub['uid'], "❌ Rejected.")
                save_db(db)
                bot.edit_message_text(f"Action Done: {act}", call.message.chat.id, call.message.message_id)
        elif act in ["wp", "wr"]:
            req = db["wd_requests"].pop(sid, None)
            if req:
                if act == "wp": bot.send_message(req['uid'], "✅ Paid!")
                else: 
                    db["users"][str(req['uid'])]["balance"] += req['amt']
                    bot.send_message(req['uid'], "❌ Rejected. Refunded.")
                save_db(db)
                bot.edit_message_text(f"WD {act} Done.", call.message.chat.id, call.message.message_id)

    elif call.data == "adm_pending":
        if not db["pending"]: return bot.answer_callback_query(call.id, "No pending tasks.")
        for sid, d in db["pending"].items():
            text = f"⏳ **ID:** {sid}\n👤 **User:** `{d['uid']}`\n🔑 **Login:** `{d['login']}`\n🔐 **Pass:** `{d['pass']}`\n📧 **Email:** `{d['email']}`\n🔑 **2FA:** `{d['2fa']}`"
            m = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"), 
                types.InlineKeyboardButton("Progress", callback_data=f"pg_{sid}"),
                types.InlineKeyboardButton("Reject", callback_data=f"rj_{sid}")
            )
            bot.send_message(ADMIN_ID, text, reply_markup=m, parse_mode="Markdown")

    elif call.data == "adm_prog_list":
        if not db["progress"]: return bot.answer_callback_query(call.id, "No progress tasks.")
        for sid, d in db["progress"].items():
            text = f"🔄 **ID:** {sid}\n🔑 **Login:** `{d['login']}`\n📧 **Email:** `{d['email']}`\n🔑 **2FA:** `{d['2fa']}`"
            m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"), types.InlineKeyboardButton("Reject", callback_data=f"rj_{sid}"))
            bot.send_message(ADMIN_ID, text, reply_markup=m, parse_mode="Markdown")

    elif call.data == "adm_task":
        msg = bot.send_message(call.message.chat.id, "Task Name:")
        bot.register_next_step_handler(msg, lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, f"Password for {m.text}:"), lambda p, n=m.text: bot.register_next_step_handler(bot.send_message(p.chat.id, "Reward ($):"), lambda r, n=n, p=p.text: [db := load_db(), db["tasks"].append({"name":n, "password":p, "reward":float(r.text)}), save_db(db), bot.send_message(r.chat.id, "Task Created!")])))

    elif call.data == "adm_email":
        msg = bot.send_message(call.message.chat.id, "Enter Emails (one per line):")
        bot.register_next_step_handler(msg, lambda m: [db := load_db(), db["emails"].extend(m.text.split("\n")), save_db(db), bot.send_message(m.chat.id, "Emails Added!")])

    elif call.data == "get_2fa":
        msg = bot.send_message(call.message.chat.id, "Enter Secret Key:")
        bot.register_next_step_handler(msg, lambda m: bot.send_message(m.chat.id, f"OTP Code: `{pyotp.TOTP(m.text.replace(' ','')).now()}`"))

# --- BALANCE & SUBMISSION ---
def bal_edit_step_1(message):
    uid = message.text
    msg = bot.send_message(message.chat.id, f"Amount to add for `{uid}`:")
    bot.register_next_step_handler(msg, lambda m, u=uid: bal_edit_step_2(m, u))

def bal_edit_step_2(message, uid):
    try:
        db = load_db()
        if uid in db["users"]:
            db["users"][uid]["balance"] += float(message.text)
            save_db(db)
            bot.send_message(message.chat.id, "✅ Done!")
        else: bot.send_message(message.chat.id, "User not found.")
    except: bot.send_message(message.chat.id, "Error.")

def add_method_logic(message):
    db = load_db()
    db["wd_methods"].append(message.text)
    save_db(db)
    bot.send_message(message.chat.id, "✅ Method Added!", reply_markup=wd_admin_keyboard())

def set_min_logic(message):
    try:
        db = load_db()
        db["min_wd"] = float(message.text)
        save_db(db)
        bot.send_message(message.chat.id, f"✅ Min WD set to ${message.text}", reply_markup=wd_admin_keyboard())
    except: bot.send_message(message.chat.id, "Invalid number.")

def final_wd_logic(message, method):
    uid = str(message.from_user.id)
    db = load_db()
    amt = db["users"][uid]["balance"]
    wid = f"WD{fake.random_int(100, 999)}"
    db["wd_requests"][wid] = {"uid": uid, "method": method, "num": message.text, "amt": amt}
    db["users"][uid]["balance"] = 0.0
    save_db(db)
    bot.send_message(message.chat.id, "✅ Withdraw request sent!", reply_markup=main_menu())
    m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("✅ Paid", callback_data=f"wp_{wid}"), types.InlineKeyboardButton("❌ Reject", callback_data=f"wr_{wid}"))
    bot.send_message(ADMIN_ID, f"💰 **WD Request!**\nMethod: {method}\nInfo: {message.text}\nAmt: ${amt}\nUID: `{uid}`", reply_markup=m)

def process_submission(message):
    uid = str(message.from_user.id)
    db = load_db()
    active = db["users"][uid].get("active_task")
    if active:
        sid = f"S{fake.random_int(1000, 9999)}"
        db["pending"][sid] = {**active, "uid": uid, "2fa": message.text}
        db["users"][uid]["active_task"] = None
        save_db(db)
        bot.send_message(message.chat.id, "✅ Submitted!", reply_markup=main_menu())
        
        admin_info = f"🔔 **New Submission!**\nID: {sid}\nLogin: `{active['login']}`\nPass: `{active['pass']}`\nEmail: `{active['email']}`\n2FA: `{message.text}`"
        m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"), types.InlineKeyboardButton("Progress", callback_data=f"pg_{sid}"), types.InlineKeyboardButton("Reject", callback_data=f"rj_{sid}"))
        bot.send_message(ADMIN_ID, admin_info, reply_markup=m, parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()

