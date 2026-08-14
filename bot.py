import os
import sqlite3
import secrets
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAGJqaa65ww-Bak2ls60IlF1SE_vp8juyXQ")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))
BOT_OWNER = int(os.environ.get("BOT_OWNER", 910090161))

# Local Database
conn = sqlite3.connect('batch_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS batches 
                  (unique_key TEXT PRIMARY KEY, start_id INTEGER, end_id INTEGER)''')
conn.commit()

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# Keyboard Menu (Neeche hamesha dikhega)
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Create Batch"), KeyboardButton("✅ Done Batch")],
        [KeyboardButton("🔄 Restart Bot")]
    ],
    resize_keyboard=True
)

@app.on_message(filters.command("start") | filters.regex("^🔄 Restart Bot") & filters.private)
async def start_cmd(client, message):
    text = message.text.split() if message.text else []
    if len(text) > 1 and text[1].startswith("KEY_"):
        unique_key = text[1]
        cursor.execute("SELECT start_id, end_id FROM batches WHERE unique_key=?", (unique_key,))
        row = cursor.fetchone()
        if row:
            start_id, end_id = row
            await message.reply_text("📥 Files send ki ja rahi hain...", reply_markup=MAIN_KEYBOARD)
            for msg_id in range(start_id, end_id + 1):
                try:
                    await client.copy_message(message.chat.id, DB_CHANNEL_ID, msg_id)
                except Exception as e:
                    await message.reply_text(f"❌ Error on msg {msg_id}: {e}")
        else:
            await message.reply_text("❌ Link galat hai ya expire ho gaya hai.", reply_markup=MAIN_KEYBOARD)
    else:
        await message.reply_text(
            "👋 **Welcome to File Store Bot!**\n\nNeeche diye gaye buttons se operate karein 👇",
            reply_markup=MAIN_KEYBOARD
        )

@app.on_message(filters.command("batch") | filters.regex("^📦 Create Batch") & filters.private)
async def batch_cmd(client, message):
    user_data[message.from_user.id] = []
    await message.reply_text(
        "📦 **Batch Mode Active!**\n\nAb jitni chahe files bhejte rahein. Sab bhej lene ke baad **[✅ Done Batch]** button dabayein.",
        reply_markup=MAIN_KEYBOARD
    )

@app.on_message(filters.command("done") | filters.regex("^✅ Done Batch") & filters.private)
async def done_cmd(client, message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]:
        file_ids = user_data[user_id]
        unique_key = "KEY_" + secrets.token_hex(4) 
        cursor.execute("INSERT INTO batches VALUES (?, ?, ?)", (unique_key, file_ids[0], file_ids[-1]))
        conn.commit()
        batch_link = f"https://t.me/{BOT_USERNAME}?start={unique_key}"
        await message.reply_text(
            f"🎉 **Aapka Batch Link Ready Hai:**\n\n`{batch_link}`\n\nIse copy karke share kar sakte hain!",
            reply_markup=MAIN_KEYBOARD
        )
        del user_data[user_id]
    else:
        await message.reply_text("❌ Pehle **[📦 Create Batch]** dabakar files bhejein.", reply_markup=MAIN_KEYBOARD)

# Collect Files (Jab batch on ho)
@app.on_message(filters.private & ~filters.command(["start", "batch", "done", "clear"]) & ~filters.regex("^(📦 Create Batch|✅ Done Batch|🔄 Restart Bot)$"))
async def collect_files(client, message):
    user_id = message.from_user.id
    if user_id in user_data:
        try:
            msg = await message.copy(DB_CHANNEL_ID)
            user_data[user_id].append(msg.id)
            await message.reply_text(f"✅ Saved! Total Files: **{len(user_data[user_id])}**")
        except Exception as e:
            await message.reply_text(f"❌ Error saving file: {e}")

if __name__ == "__main__":
    print("Bot is starting...")
    app.run()
  
