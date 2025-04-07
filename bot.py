import os
import asyncio
import pandas as pd
import fcntl
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from solana.keypair import Keypair
from solana.rpc.api import Client

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOTIFY_USER_ID = os.getenv("NOTIFY_USER_ID")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
GAS_BUFFER_LAMPORTS = int(os.getenv("GAS_BUFFER_LAMPORTS", 5000))
FORWARD_WALLET = os.getenv("FORWARD_WALLET")

client = Client(SOLANA_RPC_URL)

MAIN_MENU, ASK_DETAILS, COLLECT_NAME, COLLECT_ADDRESS, COLLECT_REFERRAL, CHOOSE_TYPE = range(6)
order_data = {}

ORDER_USD_PRICES = {
    "Tier 1": 50, "Tier 2": 95, "Tier 3": 135,
    "Tier 4": 175, "Tier 5": 210, "Tier 6": 240
}
SHIPPING_USD = 15

async def get_current_sol_price():
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
    return r.json()["solana"]["usd"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("📝 Reviews", callback_data="reviews"),
        InlineKeyboardButton("🛒 Order Now", callback_data="order")
    ]]
    await update.message.reply_text("Welcome to the Shop!", reply_markup=InlineKeyboardMarkup(keyboard))
    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "reviews":
        await query.edit_message_text("Here are our reviews:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")]]))
    elif query.data == "order":
        keyboard = [
            [InlineKeyboardButton("💳 How to Pay using SOL", callback_data="howtopay")],
            [InlineKeyboardButton("📦 Enter Shipping Info", callback_data="get_info")]
        ]
        await query.edit_message_text("Select an option:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif query.data == "howtopay":
        await query.edit_message_text(
    "After placing your order, we'll give you a Solana (SOL) address and the exact amount to send.\n\n"
    "No crypto knowledge needed — just copy and paste. We'll handle the rest.\n\n"
    "Need help? Here are step-by-step videos:\n"
    "▶️ [How to Buy Solana on Coinbase](https://www.youtube.com/watch?v=O4YzYAKrFME)\n"
    "▶️ [How to Send Solana from Coinbase](https://www.youtube.com/watch?v=3sXN-ZJB-7U)",
    parse_mode='Markdown'
)
    elif query.data == "menu":
        await start(update, context)

async def get_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Please enter your Telegram handle:")
    return ASK_DETAILS

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    order_data[uid] = {"telegram": update.message.text}
    await update.message.reply_text("Enter your full name for shipping:")
    return COLLECT_NAME

async def ask_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    order_data[uid]["name"] = update.message.text
    await update.message.reply_text("Enter your full shipping address:")
    return COLLECT_ADDRESS

async def ask_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    order_data[uid]["address"] = update.message.text
    await update.message.reply_text("Optional: Enter the Telegram handle of the person who referred you (or type 'none'):")
    return COLLECT_REFERRAL

async def choose_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    referral = update.message.text.strip()
    order_data[uid]["referral"] = referral if referral.lower() != "none" else ""

    file_path = "orders.xlsx"
    if os.path.exists(file_path):
        df = pd.read_excel(file_path)
        if referral and referral in df["Telegram"].values:
            order_data[uid]["loyalty_discount"] = True
            await update.message.reply_text("Referral found! 🎉 You've earned a 10% loyalty bonus.")
        else:
            order_data[uid]["loyalty_discount"] = False
    else:
        order_data[uid]["loyalty_discount"] = False

    keyboard = [[InlineKeyboardButton(t, callback_data=t)] for t in ORDER_USD_PRICES.keys()]
    await update.message.reply_text("Choose your order type:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_TYPE

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu)],
            ASK_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            COLLECT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_address)],
            COLLECT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_referral)],
            COLLECT_REFERRAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_type)],
            CHOOSE_TYPE: [CallbackQueryHandler(choose_type)]
        },
        fallbacks=[]
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(get_info, pattern="^get_info$"))
    app.run_polling()

if __name__ == "__main__":
    main()
