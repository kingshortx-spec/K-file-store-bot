import os
import sqlite3
import secrets
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
# Naya Token yahan update kar diya hai
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAEm-4dKhJlKsttcW09xLIS_a6SWCgpZDDk")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")

# Storage Channel
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))

# Force Subscribe Channel Details
FSUB_CHANNEL = os.environ.get("FSUB_CHANNEL", "-1003379165829")
FSUB_LINK = os.environ.get("FSUB_LINK", "https://t.me/kingx_update")

# Bot Owner / Admin ID
ADMIN_ID = int(os.environ.get("BOT_OWNER", 910090161))

# Local Database (SQLite)
conn = sqlite3.connect('batch_data.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS batches 
                  (unique_key TEXT PRIMARY KEY, start_id INTEGER, end_id INTEGER)''')
conn.commit()

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# Admin-only Keyboard
ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Create Batch"), KeyboardButton("✅ Done Batch")],
        [KeyboardButton("🔄 Restart Bot")]
    ],
    resize_keyboard=True
)

# Force Subscribe Check
async def check_fsub(client, message):
    if not FSUB_CHANNEL:
        return True
    try:
        chat_id = int(FSUB_CHANNEL)
        user = await client.get_chat_member(chat_id, message.from_user.id)
        if user.status in ["kicked", "left"]:
            return False
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

@app.on_message(filters.command("start") | filters.regex("^🔄 Restart Bot") & filters.private)
async def start_cmd(client, message):
    text = message.text.split() if message.text else []

    # 1. Check Force Subscribe
    is_subscribed = await check_fsub(client, message)
    if not is_subscribed:
        join_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Updates Channel", url=FSUB_LINK)],
            [InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{BOT_USERNAME}?start={text[1] if len(text) > 1 else ''}")]
        ])
        await message.reply_text(
            "⚠️ **Access Denied!**\n\nPlease join our **Updates Channel** first to access the files, then tap **'Try Again'**.",
            reply_markup=join_button
        )
        return

    # 2. File Delivery
    if len(text) > 1 and text[1].startswith("KEY_"):
        unique_key = text[1]
        cursor.execute("SELECT start_id, end_id FROM batches WHERE unique_key=?", (unique_key,))
        row = cursor.fetchone()
        if row:
            start_id, end_id = row
            await message.reply_text("📥 **Sending your files...**")
            for msg_id in range(start_id, end_id + 1):
                try:
                    await client.copy_message(message.chat.id, DB_CHANNEL_ID, msg_id)
                except Exception as e:
                    await message.reply_text(f"❌ Error on message {msg_id}: {e}")
        return

    # 3. Start Message
    if message.from_user.id == ADMIN_ID:
        await message.reply_text(
            "👋 **Welcome Admin!**\n\nUse the buttons below to create batch links 👇",
            reply_markup=ADMIN_KEYBOARD
        )
    else:
        await message.reply_text("👋 **Welcome to File Store Bot!**\n\nClick on any shared batch link to get your files.")

# Admin-Only: Create Batch
@app.on_message((filters.command("batch") | filters.regex("^📦 Create Batch")) & filters.private)
async def batch_cmd(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("⛔ **Access Denied!** Only the admin can use this command.")
        return

    user_data[message.from_user.id] = []
    await message.reply_text(
        "📦 **Batch Mode Activated!**\n\nSend all the files you want to include. Once done, tap **[✅ Done Batch]**.",
        reply_markup=ADMIN_KEYBOARD
    )

# Admin-Only: Done Batch
@app.on_message((filters.command("done") | filters.regex("^✅ Done Batch")) & filters.private)
async def done_cmd(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply_text("⛔ **Access Denied!** Only the admin can use this command.")
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]:
        file_ids = user_data[user_id]
        unique_key = "KEY_" + secrets.token_hex(4)

        cursor.execute("INSERT INTO batches VALUES (?, ?, ?)", (unique_key, file_ids[0], file_ids[-1]))
        conn.commit()

        batch_link = f"https://t.me/{BOT_USERNAME}?start={unique_key}"
        await message.reply_text(
            f"🎉 **Your Batch Link is Ready:**\n\n`{batch_link}`",
            reply_markup=ADMIN_KEYBOARD
        )
        del user_data[user_id]
    else:
        await message.reply_text("❌ Please tap **[📦 Create Batch]** and forward files first.", reply_markup=ADMIN_KEYBOARD)

# Admin-Only: Collect Files
@app.on_message(filters.private & ~filters.command(["start", "batch", "done", "clear"]) & ~filters.regex("^(📦 Create Batch|✅ Done Batch|🔄 Restart Bot)$"))
async def collect_files(client, message):
    if message.from_user.id != ADMIN_ID:
        return

    user_id = message.from_user.id
    if user_id in user_data:
        try:
            msg = await message.copy(DB_CHANNEL_ID)
            user_data[user_id].append(msg.id)
            await message.reply_text(f"✅ Saved! Total Files: **{len(user_data[user_id])}**")
        except Exception as e:
            await message.reply_text(f"❌ Error saving file: {e}")

if __name__ == "__main__":
    print("Bot is live with new token!")
    app.run()
