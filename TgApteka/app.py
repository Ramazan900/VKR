from dotenv import load_dotenv
import os
import asyncio
import pyodbc
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.helpers import escape_markdown

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=calculator\\mssqlserver02;"
    "DATABASE=MedicineDatabase;"
    "Trusted_Connection=yes;"
)

async def get_db_connection():
    try:
        return await asyncio.to_thread(pyodbc.connect, conn_str)
    except pyodbc.Error:
        return None

async def search_medicine_by_name(name_part: str):
    conn = await get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        query = "SELECT Name FROM Medicines WHERE Name LIKE ?"
        cursor.execute(query, (f"%{name_part}%",))
        rows = cursor.fetchall()
        return [row.Name for row in rows]
    finally:
        conn.close()

async def get_medicine_details(name: str):
    conn = await get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor()
        query = "SELECT Name, ATCCode, ApplicationInChildren, PregnancyAndLactation, Composition FROM Medicines WHERE Name = ?"
        cursor.execute(query, (name,))
        return cursor.fetchone()
    finally:
        conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = (
        "Добро пожаловать! Этот бот помогает найти информацию о лекарствах. "
        "Вы можете узнать название, код АТХ, состав, применение у детей и при беременности. "
        "Просто введите название лекарства для поиска."
    )
    await update.message.reply_text(description + "\n\nВведите название лекарства:")
    context.user_data['searching_medicine'] = True

async def receive_medicine_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('searching_medicine'):
        context.user_data['searching_medicine'] = True
        await update.message.reply_text("Введите название лекарства:")
        return
    
    name_part = update.message.text
    results = await search_medicine_by_name(name_part)
    
    if not results:
        await update.message.reply_text("Лекарство не найдено. Введите название другого лекарства:")
        context.user_data['searching_medicine'] = True
        return
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"select_{name}")] for name in results]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите лекарство:", reply_markup=reply_markup)

async def select_medicine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    name = query.data.replace("select_", "")
    details = await get_medicine_details(name)
    
    if not details:
        await query.edit_message_text("Ошибка получения данных. Введите название другого лекарства:")
        context.user_data['searching_medicine'] = True
        return
    
    text = f"*Название:* {escape_markdown(details.Name, version=2)}\n"
    text += f"*Код АТХ:* {escape_markdown(details.ATCCode or 'Не указано', version=2)}\n"
    text += f"*Применение у детей:* {escape_markdown(details.ApplicationInChildren or 'Не указано', version=2)}\n"
    text += f"*Применение при беременности и лактации:* {escape_markdown(details.PregnancyAndLactation or 'Не указано', version=2)}\n"
    text += f"*Состав:* {escape_markdown(details.Composition or 'Не указано', version=2)}\n\n"
    text += "Введите название другого лекарства для поиска:"
    
    await query.edit_message_text(text, parse_mode='MarkdownV2')
    context.user_data['searching_medicine'] = True

if __name__ == '__main__':
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_medicine_name))
    application.add_handler(CallbackQueryHandler(select_medicine, pattern="^select_"))
    application.run_polling()