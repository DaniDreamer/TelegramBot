import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import sqlite3
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

NAME, STUDENT_ID, SECTION, PAYMENT_METHOD, PAYMENT_PROOF = range(5)

BOT_TOKEN = "8210383932:AAH6do8oGCrwxWCGOvOCpBqGkzGTaBP02uA"
ADMIN_CHAT_ID = "6736339513"
CHANNEL_LINK = "http://t.me/JimmaFresh_bot"

def validate_config():
    if not re.match(r'^\d+:[A-Za-z0-9_-]+$', BOT_TOKEN):
        return False
    if not ADMIN_CHAT_ID.isdigit():
        return False
    return True

def init_db():
    conn = sqlite3.connect('registrations.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            student_id TEXT,
            section INTEGER,
            payment_method TEXT,
            payment_proof TEXT,
            registration_date TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"""
Welcome {user.first_name}

Registration Steps
1. Enter full name
2. Enter student ID
3. Select section
4. Choose payment method
5. Upload payment proof
"""
    keyboard = [[InlineKeyboardButton("Start Registration", callback_data="start_registration")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Enter your full name")
    return NAME

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2:
        await update.message.reply_text("Enter a valid name")
        return NAME
    context.user_data['full_name'] = name
    await update.message.reply_text("Enter your Student ID")
    return STUDENT_ID

async def handle_student_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = update.message.text.strip().upper()
    if len(sid) < 3:
        await update.message.reply_text("Enter valid student ID")
        return STUDENT_ID
    context.user_data['student_id'] = sid
    await update.message.reply_text("Select your section", reply_markup=generate_section_keyboard())
    return SECTION

def generate_section_keyboard():
    keyboard = []
    row = []
    for i in range(1, 34):
        row.append(InlineKeyboardButton(f"Sec {i}", callback_data=f"section_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

async def handle_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    section = int(query.data.split('_')[1])
    context.user_data['section'] = section
    await show_payment_methods(query)
    return PAYMENT_METHOD

async def show_payment_methods(query):
    text = "Choose payment method"
    keyboard = [
        [InlineKeyboardButton("Telebirr", callback_data="payment_telebirr"),
         InlineKeyboardButton("CBE", callback_data="payment_cbe")],
        [InlineKeyboardButton("Awash Bank", callback_data="payment_awash")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_payment_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    method = query.data.split('_')[1]
    context.user_data['payment_method'] = method

    if method == 'telebirr':
        text = "Send 100 ETB via Telebirr to 0929158872"
    elif method == 'cbe':
        text = "Send 100 ETB to CBE account 1000478987459"
    else:
        text = "Send 100 ETB to Awash account 013201440271700"

    keyboard = [[InlineKeyboardButton("Submit Payment Proof", callback_data="submit_proof")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return PAYMENT_PROOF

async def request_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Upload payment screenshot")
    return PAYMENT_PROOF

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Send image proof")
        return PAYMENT_PROOF

    data = context.user_data

    conn = sqlite3.connect('registrations.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, full_name, student_id, section, payment_method, payment_proof, registration_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        update.effective_user.id,
        update.effective_user.username,
        data['full_name'],
        data['student_id'],
        data['section'],
        data['payment_method'],
        file_id,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text("Registration submitted")

    await notify_admin(update, context, data, file_id)

    context.user_data.clear()
    return ConversationHandler.END

async def notify_admin(update, context, data, file_id):
    text = f"""
New Registration

Name: {data['full_name']}
Student ID: {data['student_id']}
Section: {data['section']}
Payment: {data['payment_method']}
"""
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
    await context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=file_id)

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith('approve_'):
        user_id = int(query.data.split('_')[1])

        conn = sqlite3.connect('registrations.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status='approved' WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()

        await context.bot.send_message(user_id, f"Approved. Join channel:\n{CHANNEL_LINK}")
        await query.edit_message_text("Approved")

    elif query.data.startswith('reject_'):
        user_id = int(query.data.split('_')[1])

        conn = sqlite3.connect('registrations.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status='rejected' WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()

        await context.bot.send_message(user_id, "Registration rejected")
        await query.edit_message_text("Rejected")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Registration cancelled")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start to begin registration")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(context.error)

def main():
    if not validate_config():
        return

    init_db()

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_registration, pattern="start_registration")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name)],
            STUDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_student_id)],
            SECTION: [CallbackQueryHandler(handle_section, pattern="section_")],
            PAYMENT_METHOD: [CallbackQueryHandler(show_payment_details, pattern="payment_")],
            PAYMENT_PROOF: [
                CallbackQueryHandler(request_payment_proof, pattern="submit_proof"),
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_payment_proof)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_admin_actions, pattern="^(approve_|reject_)"))

    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == "__main__":
    main()