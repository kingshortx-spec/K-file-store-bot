import os
import base64
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAEm-4dKhJlKsttcW09xLIS_a6SWCgpZDDk")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))
BOT_OWNER = int(os.environ.get("BOT_OWNER", 910090161))

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# Keyboard Menu
ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Create Batch"), KeyboardButton("✅ Done Batch")],
        [KeyboardButton("🔄 Restart Bot")]
    ],
    resize_keyboard=True
)

# Helper functions for Direct Link encoding/decoding
def encode_batch(start_id, end_id):
    string_data = f"{start_id}_{end_id}"
    b64_encoded = base64.urlsafe_b64encode(string_data.encode("ascii")).decode("ascii")
    return b64_encoded.strip("=")

def decode_batch(b64_string):
    try:
        padding = "=" * (4 - len(b64_string) % 4)
        b64_string += padding
        decoded = base64.urlsafe_b64decode(b64_string.encode("ascii")).decode("ascii")
        start_id, end_id = decoded.split("_")
        return int(start_id), int(end_id)
    except Exception:
        return None, None

@app.on_message(filters.command("start") | filters.regex("^🔄 Restart Bot") & filters.private)
async def start_cmd(client, message):
    text = message.text.split() if message.text else []

    # File Fetching Logic (Direct Link)
    if len(text) > 1 and text[1].startswith("BATCH_"):
        encoded_data = text[1].replace("BATCH_", "")
        start_id, end_id = decode_batch(encoded_data)

        if start_id and end_id:
            await message.reply_text("📥 Sending files...")
            for msg_id in range(start_id, end_id + 1):
                try:
                    await client.copy_message(message.chat.id, DB_CHANNEL_ID, msg_id)
                except Exception as e:
                    await message.reply_text(f"❌ Error: {e}")
        else:
            await message.reply_text("❌ Invalid link structure.")
    else:
        # Welcome message
        if message.from_user.id == BOT_OWNER:
            await message.reply_text("👋 Hello Admin!\n\nUse the buttons below.", reply_markup=ADMIN_KEYBOARD)
        else:
            await message.reply_text("👋 Hello! Welcome to File Store Bot.")

# Admin-Only Batch Commands
@app.on_message((filters.command("batch") | filters.regex("^📦 Create Batch")) & filters.private)
async def batch_cmd(client, message):
    if message.from_user.id != BOT_OWNER:
        await message.reply_text("⛔ Only the Admin can create a batch!")
        return

    user_data[message.from_user.id] = []
    await message.reply_text(
        "📦 **Batch Mode Active!**\n\nForward your files. After done, tap [✅ Done Batch].",
        reply_markup=ADMIN_KEYBOARD
    )

@app.on_message((filters.command("done") | filters.regex("^✅ Done Batch")) & filters.private)
async def done_cmd(client, message):
    if message.from_user.id != BOT_OWNER:
        return

    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]:
        file_ids = user_data[user_id]
        encoded_key = encode_batch(file_ids[0], file_ids[-1])
        batch_link = f"https://t.me/{BOT_USERNAME}?start=BATCH_{encoded_key}"
        
        await message.reply_text(
            f"🎉 **Permanent Batch Link Ready:**\n\n`{batch_link}`\n\n*(This link is permanent and will NEVER expire even if hosting changes)*",
            reply_markup=ADMIN_KEYBOARD
        )
        del user_data[user_id]
    else:
        await message.reply_text("❌ First tap [📦 Create Batch] and forward files.")

# Collect Files
@app.on_message(filters.private & ~filters.command(["start", "batch", "done", "clear"]) & ~filters.regex("^(📦 Create Batch|✅ Done Batch|🔄 Restart Bot)$"))
async def collect_files(client, message):
    if message.from_user.id != BOT_OWNER:
        return

    user_id = message.from_user.id
    if user_id in user_data:
        try:
            msg = await message.copy(DB_CHANNEL_ID)
            user_data[user_id].append(msg.id)
            total = len(user_data[user_id])
            await message.reply_text(f"✅ Saved! Total Files: **{total}**")
        except Exception as e:
            await message.reply_text(f"❌ Error saving file: {e}")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
