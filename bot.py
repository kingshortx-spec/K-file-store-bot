import os
import sqlite3
import secrets
from aiohttp import web
from pyrogram import Client, filters

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAGJqaa65ww-Bak2ls60IlF1SE_vp8juyXQ")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))
BOT_OWNER = int(os.environ.get("BOT_OWNER", 910090161))
PORT = int(os.environ.get("PORT", 8000))

# Local Database
conn = sqlite3.connect('batch_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS batches 
                  (unique_key TEXT PRIMARY KEY, start_id INTEGER, end_id INTEGER)''')
conn.commit()

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    text = message.text.split()
    if len(text) > 1 and text[1].startswith("KEY_"):
        unique_key = text[1]
        cursor.execute("SELECT start_id, end_id FROM batches WHERE unique_key=?", (unique_key,))
        row = cursor.fetchone()
        if row:
            start_id, end_id = row
            await message.reply_text("📥 Files send ki ja rahi hain...")
            for msg_id in range(start_id, end_id + 1):
                try:
                    await client.copy_message(message.chat.id, DB_CHANNEL_ID, msg_id)
                except Exception as e:
                    await message.reply_text(f"❌ Error on msg {msg_id}: {e}")
        else:
            await message.reply_text("❌ Link galat hai ya expire ho gaya hai.")
    else:
        await message.reply_text(f"👋 Welcome! /batch type karke naya batch banayein.")

@app.on_message(filters.command("batch") & filters.private)
async def batch_cmd(client, message):
    user_data[message.from_user.id] = []
    await message.reply_text("📦 **Batch Mode Active!**\n\nFiles bhejte rahein (ek-ek karke). Khatam hone par `/done` likhein.")

@app.on_message(filters.private & ~filters.command(["start", "batch", "done", "clear"]))
async def collect_files(client, message):
    user_id = message.from_user.id
    if user_id in user_data:
        try:
            msg = await message.copy(DB_CHANNEL_ID)
            user_data[user_id].append(msg.id)
            await message.reply_text(f"✅ Saved! Total: {len(user_data[user_id])}")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")

@app.on_message(filters.command("done") & filters.private)
async def done_cmd(client, message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]:
        file_ids = user_data[user_id]
        unique_key = "KEY_" + secrets.token_hex(4) 
        cursor.execute("INSERT INTO batches VALUES (?, ?, ?)", (unique_key, file_ids[0], file_ids[-1]))
        conn.commit()
        batch_link = f"https://t.me/{BOT_USERNAME}?start={unique_key}"
        await message.reply_text(f"🎉 **Aapka Batch Link:**\n\n`{batch_link}`")
        del user_data[user_id]
    else:
        await message.reply_text("❌ Pehle `/batch` karke files bhejein.")

# --- DUMMY WEB SERVER FOR KOYEB ---
async def web_handler(request):
    return web.Response(text="Bot is running 24/7!")

async def main():
    server = web.Application()
    server.router.add_get("/", web_handler)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    await app.start()
    print("Bot started successfully!")
    await web.Event().wait()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
  
