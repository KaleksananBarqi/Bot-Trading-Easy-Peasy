
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

load_dotenv("src/.env")

async def check_bot(token_name, chat_id_name, thread_id_name=None):
    token = os.getenv(token_name)
    chat_id = os.getenv(chat_id_name)
    thread_id = os.getenv(thread_id_name) if thread_id_name else None

    print(f"\n--- Checking {token_name} ---")
    print(f"Token: {token[:5]}...*****")
    print(f"Chat ID: {chat_id}")
    if thread_id:
        print(f"Thread ID: {thread_id}")

    if not token:
        print("❌ Token not found in .env")
        return

    bot = Bot(token=token)
    
    # 1. Check Bot Identity
    try:
        me = await bot.get_me()
        print(f"✅ Token Valid. Bot Name: {me.first_name} (@{me.username})")
    except TelegramError as e:
        print(f"❌ Token Invalid or Network Error: {e}")
        return

    # 2. Check Chat Access
    try:
        chat = await bot.get_chat(chat_id=chat_id)
        print(f"✅ Chat Found: {chat.title} (Type: {chat.type})")
        
        # Check permissions if possible (rough check)
        # Note: get_chat typically works if bot is in chat or chat is public
    except TelegramError as e:
        print(f"❌ Chat Access Failed: {e}")
        print("   -> Kemungkinan Bot belum diinvite ke Group/Channel ini atau belum jadi Admin.")

    # 3. Try Sending a Test Message
    try:
        msg_kwargs = {"chat_id": chat_id, "text": "🔔 Test Message from Debugger"}
        if thread_id:
            msg_kwargs["message_thread_id"] = int(thread_id)
        
        await bot.send_message(**msg_kwargs)
        print("✅ Test Message Sent Successfully!")
    except TelegramError as e:
        print(f"❌ Send Message Failed: {e}")

async def main():
    print("Mulai Diagnosa Telegram...")
    # Check Default Bot
    # await check_bot("TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID", "TELEGRAM_MESSAGE_THREAD_ID")
    
    # Check Sentiment Bot (The one failing)
    await check_bot("TELEGRAM_TOKEN_SENTIMENT", "TELEGRAM_CHAT_ID_SENTIMENT", "TELEGRAM_MESSAGE_THREAD_ID_SENTIMENT")

if __name__ == "__main__":
    asyncio.run(main())
