import telebot
import pyotp
import json
import os
from telebot import types
from faker import Faker
from flask import Flask
from threading import Thread

# --- FLASK SERVER FOR 24/7 HOSTING ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is Running Online!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CONFIGURATION ---
API_TOKEN = '8427393618:AAHcKU6WjDRE7DGnh_LlH3b8qs2lvLLDI9k'
ADMIN_ID = 8220394592
fake = Faker()
bot = telebot.TeleBot(API_TOKEN)
DB_FILE = "bot_database.json"

# --- DATABASE FUNCTIONS ---
def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {}, "emails": [], "tasks": [],
            "pending": {}, "progress": {}, "task_pass": "Admin@123",
            "wd_methods": [], "min_wd": 0.5, "wd_requests": {}
        }
    with open(DB_FILE, "r") as f:
        try: return json.load(f)
        except: return {"users": {}, "emails": [], "tasks": [], "pending": {}, "progress": {}, "task_pass": "Admin@123", "wd_methods": [], "min_wd": 0.5, "wd_requests": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

# --- KEYBOARDS ---
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(" Balance", " Tasks", " Withdraw", " Profile")
    return markup

def task_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(" Submit Task", " Cancel Task")
    return markup

def wd_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(" Add Method", " Remove Method", " Set Min WD", " Back to Menu")
    return markup

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start(message):
    db = load_db()
    uid = str(message.from_user.id)
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0.0, "total_task": 0, "active_task": None}
        save_db(db)
    bot.send_message(message.chat.id, " Welcome to the Earning Bot!", reply_markup=main_menu())
    if message.from_user.id == ADMIN_ID:
        show_admin_panel(message.chat.id)

def show_admin_panel(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton(" Add Emails", callback_data="adm_email"),
        types.InlineKeyboardButton(" Add Task", callback_data="adm_task"),
        types.InlineKeyboardButton(" Remove Task", callback_data="rem_task"),
        types.InlineKeyboardButton(" Pending", callback_data="adm_pending"),
        types.InlineKeyboardButton(" Progress List", callback_data="adm_prog_list"),
        types.InlineKeyboardButton(" Bal Edit", callback_data="adm_bal_edit"),
        types.InlineKeyboardButton(" WD Settings", callback_data="adm_wd_set")
    )
    bot.send_message(chat_id, " Admin Control Panel:", reply_markup=markup)

# --- MAIN TEXT HANDLER ---
@bot.message_handler(func=lambda m: True)
def handle_text(message):
    uid = str(message.from_user.id)
    db = load_db()

    # --- User Navigation ---
    if message.text == " Balance":
        bal = db["users"].get(uid, {}).get("balance", 0.0)
        bot.send_message(message.chat.id, f" Your Current Balance: **${bal:.2f}**", parse_mode="Markdown")

    elif message.text == " Tasks":
        if not db["tasks"]: return bot.send_message(message.chat.id, "No tasks available at the moment.")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for t in db["tasks"]: markup.add(t['name'])
        markup.add(" Back to Menu")
        bot.send_message(message.chat.id, "Choose a Task to Start:", reply_markup=markup)

    elif message.text == " Withdraw":
        bal = db["users"].get(uid, {}).get("balance", 0.0)
        min_amt = db.get("min_wd", 0.5)
        if bal < min_amt:
            return bot.send_message(message.chat.id, f" Min Withdraw is ${min_amt}. Keep earning!")
        if not db["wd_methods"]: return bot.send_message(message.chat.id, "No withdraw methods available.")
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for m in db["wd_methods"]: markup.add(m)
        markup.add(" Back to Menu")
        bot.send_message(message.chat.id, "Select Payment Method:", reply_markup=markup)

    elif message.text == " Back to Menu":
        bot.send_message(message.chat.id, "Main Menu:", reply_markup=main_menu())

    elif message.text == " Profile":
        u = db["users"].get(uid, {})
        bot.send_message(message.chat.id, f" User: {message.from_user.first_name}\n ID: `{uid}`\n Balance: ${u.get('balance',0)}")

    # --- Admin Large Buttons ---
    elif message.text == " Add Method" and message.from_user.id == ADMIN_ID:
        msg = bot.send_message(message.chat.id, "Enter Method Name (e.g., Bkash):")
        bot.register_next_step_handler(msg, add_method_logic)

    elif message.text == " Remove Method" and message.from_user.id == ADMIN_ID:
        if not db["wd_methods"]: return bot.send_message(message.chat.id, "Methods List Empty.")
        m = types.InlineKeyboardMarkup()
        for meth in db["wd_methods"]: m.add(types.InlineKeyboardButton(f"Delete {meth}", callback_data=f"delmet_{meth}"))
        bot.send_message(message.chat.id, "Select method to delete:", reply_markup=m)

    elif message.text == " Set Min WD" and message.from_user.id == ADMIN_ID:
        msg = bot.send_message(message.chat.id, "Enter Minimum Withdraw Amount:")
        bot.register_next_step_handler(msg, set_min_logic)

    # --- Task Submission ---
    elif message.text == " Submit Task":
        active = db["users"].get(uid, {}).get("active_task")
        if active:
            sid = f"S{fake.random_int(1000, 9999)}"
            db["pending"][sid] = {"uid": uid, **active}
            db["users"][uid]["active_task"] = None
            save_db(db)
            bot.send_message(message.chat.id, " Task submitted!", reply_markup=main_menu())
            bot.send_message(ADMIN_ID, f" New Task from {uid}: {sid}")

    elif message.text == " Cancel Task":
        db["users"][uid]["active_task"] = None
        save_db(db)
        bot.send_message(message.chat.id, "Task Cancelled.", reply_markup=main_menu())

    elif message.text in db["wd_methods"]:
        msg = bot.send_message(message.chat.id, f"Enter your {message.text} details:")
        bot.register_next_step_handler(msg, lambda m: final_wd_logic(m, message.text))

    else:
        for t in db["tasks"]:
            if message.text == t['name']: start_task_ui(message, t)

# --- LOGIC FUNCTIONS ---
def add_method_logic(message):
    db = load_db()
    db["wd_methods"].append(message.text)
    save_db(db)
    bot.send_message(message.chat.id, f" {message.text} added successfully!", reply_markup=wd_admin_keyboard())

def set_min_logic(message):
    try:
        db = load_db()
        db["min_wd"] = float(message.text)
        save_db(db)
        bot.send_message(message.chat.id, f" Min WD set to ${message.text}", reply_markup=wd_admin_keyboard())
    except: bot.send_message(message.chat.id, "Invalid Input.")

def start_task_ui(message, task):
    db = load_db()
    login = f"{fake.first_name().lower()}{fake.random_int(10, 99)}"
    email = db["emails"].pop(0) if db["emails"] else "Contact Admin"
    db["users"][str(message.from_user.id)]["active_task"] = {"name": task['name'], "login": login, "pass": db["task_pass"], "email": email, "reward": task['reward']}
    save_db(db)
    m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(" Maildrop", url="https://maildrop.cc/"), types.InlineKeyboardButton(" Get 2FA", callback_data="get_2fa"))
    bot.send_message(message.chat.id, f" Task: {task['name']}\n Login: `{login}`\n Email: `{email}`\n Reward: ${task['reward']}", reply_markup=m)
    bot.send_message(message.chat.id, "Choose Action:", reply_markup=task_action_menu())

def final_wd_logic(message, method):
    uid = str(message.from_user.id)
    db = load_db()
    amt = db["users"][uid]["balance"]
    wid = f"WD{fake.random_int(100, 999)}"
    db["wd_requests"][wid] = {"uid": uid, "method": method, "num": message.text, "amt": amt}
    db["users"][uid]["balance"] = 0.0
    save_db(db)
    bot.send_message(message.chat.id, " Withdraw request sent!", reply_markup=main_menu())
    m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(" Paid", callback_data=f"wp_{wid}"), types.InlineKeyboardButton(" Reject", callback_data=f"wr_{wid}"))
    bot.send_message(ADMIN_ID, f" WD Request: {method}\nInfo: {message.text}\nAmt: ${amt}", reply_markup=m)

# --- CALLBACK HANDLERS ---
@bot.callback_query_handler(func=lambda c: c.data == "adm_wd_set")
def wd_set_menu(call):
    bot.delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Manage Withdraw Methods:", reply_markup=wd_admin_keyboard())

@bot.callback_query_handler(func=lambda c: c.data.startswith("delmet_"))
def del_met(call):
    meth = call.data.split("_")[1]
    db = load_db()
    if meth in db["wd_methods"]:
        db["wd_methods"].remove(meth)
        save_db(db)
        bot.edit_message_text(f" {meth} Deleted.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_bal_edit")
def bal_edit_start(call):
    msg = bot.send_message(call.message.chat.id, "Enter User ID:")
    bot.register_next_step_handler(msg, bal_edit_amount)

def bal_edit_amount(message):
    uid = message.text
    msg = bot.send_message(message.chat.id, "Amount to add:")
    bot.register_next_step_handler(msg, lambda m: bal_edit_final(m, uid))

def bal_edit_final(message, uid):
    db = load_db()
    if uid in db["users"]:
        db["users"][uid]["balance"] += float(message.text)
        save_db(db)
        bot.send_message(message.chat.id, " User Balance Updated!")
    else: bot.send_message(message.chat.id, "User Not Found.")

@bot.callback_query_handler(func=lambda c: c.data.startswith(("ap_", "pg_", "rj_", "wp_", "wr_")))
def handle_reviews(call):
    act, sid = call.data.split("_")
    db = load_db()
    if act in ["ap", "pg", "rj"]:
        sub = db["pending"].pop(sid, None) or db["progress"].pop(sid, None)
        if sub:
            if act == "ap":
                db["users"][str(sub['uid'])]["balance"] += sub['reward']
                bot.send_message(sub['uid'], " Task Approved!")
            elif act == "pg": db["progress"][sid] = sub
            save_db(db)
            bot.edit_message_text(f"Review {act} Complete.", call.message.chat.id, call.message.message_id)
    elif act in ["wp", "wr"]:
        req = db["wd_requests"].pop(sid, None)
        if req:
            if act == "wp": bot.send_message(req['uid'], " Your Withdraw Paid!")
            else:
                db["users"][str(req['uid'])]["balance"] += req['amt']
                bot.send_message(req['uid'], " WD Rejected. Money Refunded.")
            save_db(db)
            bot.edit_message_text(f"WD {act} Complete.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda c: c.data == "adm_pending")
def view_pending(call):
    db = load_db()
    if not db["pending"]: return bot.answer_callback_query(call.id, "No pending tasks.")
    for sid, d in db["pending"].items():
        m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"), types.InlineKeyboardButton("Progress", callback_data=f"pg_{sid}"))
        bot.send_message(ADMIN_ID, f" Pending: {sid}\nLogin: {d['login']}", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data == "adm_prog_list")
def view_progress(call):
    db = load_db()
    if not db["progress"]: return bot.answer_callback_query(call.id, "Progress list empty.")
    for sid, d in db["progress"].items():
        m = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("Approve", callback_data=f"ap_{sid}"))
        bot.send_message(ADMIN_ID, f" In Progress: {sid}\nLogin: {d['login']}", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data == "get_2fa")
def g2fa_logic(call):
    msg = bot.send_message(call.message.chat.id, "Enter Secret Key:")
    bot.register_next_step_handler(msg, lambda m: bot.send_message(m.chat.id, f"OTP Code: `{pyotp.TOTP(m.text.replace(' ','')).now()}`"))

@bot.callback_query_handler(func=lambda c: c.data == "adm_email")
def add_emails(call):
    msg = bot.send_message(call.message.chat.id, "Enter Emails (one per line):")
    bot.register_next_step_handler(msg, lambda m: [db := load_db(), db["emails"].extend(m.text.split("\n")), save_db(db), bot.send_message(m.chat.id, "Emails Added!")])

@bot.callback_query_handler(func=lambda c: c.data == "adm_task")
def add_task_adm(call):
    msg = bot.send_message(call.message.chat.id, "Task Name:")
    bot.register_next_step_handler(msg, lambda m: bot.register_next_step_handler(bot.send_message(m.chat.id, "Reward Amount ($):"), lambda r: [db := load_db(), db["tasks"].append({"name":m.text, "reward":float(r.text)}), save_db(db), bot.send_message(r.chat.id, "Task Created!")]))

@bot.callback_query_handler(func=lambda c: c.data == "rem_task")
def rem_task_adm(call):
    db = load_db()
    m = types.InlineKeyboardMarkup()
    for i, t in enumerate(db["tasks"]): m.add(types.InlineKeyboardButton(t['name'], callback_data=f"rmt_{i}"))
    bot.send_message(call.message.chat.id, "Select task to delete:", reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data.startswith("rmt_"))
def rmt_done(call):
    idx = int(call.data.split("_")[1])
    db = load_db()
    db["tasks"].pop(idx)
    save_db(db)
    bot.edit_message_text("Task Deleted!", call.message.chat.id, call.message.message_id)

# --- START BOT ---
if __name__ == "__main__":
    keep_alive() # Keeps the web server running for Render/Koyeb
    print("Bot is starting...")
    bot.infinity_polling()
