import os
import secrets
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAGJqaa65ww-Bak2ls60IlF1SE_vp8juyXQ")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")

# Storage Channel (Jahan files store hoti hain)
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))

# 📢 Force Subscribe Channel Details (Updated)
FSUB_CHANNEL = os.environ.get("FSUB_CHANNEL", "-1003379165829")
FSUB_LINK = os.environ.get("FSUB_LINK", "https://t.me/kingx_update")

BOT_OWNER = int(os.environ.get("BOT_OWNER", 910090161))

# MongoDB Database Connection
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://mehulrathod8514:IpEFuQmV5zFUWd0B@cluster0.91zmh.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["filestore_database"]
batches_col = db["batches"]

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_data = {}

# Keyboard Menu Buttons
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Create Batch"), KeyboardButton("✅ Done Batch")],
        [KeyboardButton("🔄 Restart Bot")]
    ],
    resize_keyboard=True
)

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

    # Check Force Subscribe
    is_subscribed = await check_fsub(client, message)
    if not is_subscribed:
        join_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Updates Channel", url=FSUB_LINK)],
            [InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{BOT_USERNAME}?start={text[1] if len(text) > 1 else ''}")]
        ])
        await message.reply_text(
            "⚠️ **Access Denied!**\n\nFile access karne ke liye pehle hamara **Updates Channel** join karein, fir **'Try Again'** par tap karein.",
            reply_markup=join_button
        )
        return

    # Check for Key in Deep Link
    if len(text) > 1 and text[1].startswith("KEY_"):
        unique_key = text[1]
        data = await batches_col.find_one({"unique_key": unique_key})
        
        if data:
            start_id = data["start_id"]
            end_id = data["end_id"]
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
            "👋 **Welcome to File Store Bot!**\n\nNeeche diye gaye buttons use karein 👇",
            reply_markup=MAIN_KEYBOARD
        )

@app.on_message(filters.command("batch") | filters.regex("^📦 Create Batch") & filters.private)
async def batch_cmd(client, message):
    user_data[message.from_user.id] = []
    await message.reply_text(
        "📦 **Batch Mode Active!**\n\nFiles bhejte rahein. Sab bhej lene ke baad **[✅ Done Batch]** button dabayein.",
        reply_markup=MAIN_KEYBOARD
    )

@app.on_message(filters.command("done") | filters.regex("^✅ Done Batch") & filters.private)
async def done_cmd(client, message):
    user_id = message.from_user.id
    if user_id in user_data and user_data[user_id]:
        file_ids = user_data[user_id]
        unique_key = "KEY_" + secrets.token_hex(4)

        # Permanent MongoDB storage
        await batches_col.insert_one({
            "unique_key": unique_key,
            "start_id": file_ids[0],
            "end_id": file_ids[-1]
        })

        batch_link = f"https://t.me/{BOT_USERNAME}?start={unique_key}"
        await message.reply_text(
            f"🎉 **Permanent Batch Link:**\n\n`{batch_link}`",
            reply_markup=MAIN_KEYBOARD
        )
        del user_data[user_id]
    else:
        await message.reply_text("❌ Pehle **[📦 Create Batch]** dabakar files bhejein.", reply_markup=MAIN_KEYBOARD)

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
    print("Bot is live with F-Sub & MongoDB!")
    app.run()
