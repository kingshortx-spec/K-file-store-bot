import asyncio
import base64
import os
import re
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from pyrogram.errors import UserNotParticipant, FloodWait

# --- CONFIGURATION (Direct Loaded) ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAEm-4dKhJlKsttcW09xLIS_a6SWCgpZDDk")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))
BOT_OWNER = int(os.environ.get("BOT_OWNER", 910090161))

# Force Subscribe Details
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", -1003379165829))
FORCE_SUB_USERNAME = os.environ.get("FORCE_SUB_USERNAME", "kingx_update")

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-memory storage for file collection
user_data = {}

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Create Batch"), KeyboardButton("✅ Done Batch")],
        [KeyboardButton("🔄 Restart Bot")]
    ],
    resize_keyboard=True
)

# --- HELPER FUNCTIONS ---
def natural_sort_key(s: str):
    """Numbers ko natural sequence (1, 2, 10...) me arrange karne ke liye"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def extract_file_title(message: Message) -> str:
    """Audio title, document name ya caption extract karna"""
    if message.audio:
        return message.audio.title or message.audio.file_name or message.caption or ""
    elif message.document:
        return message.document.file_name or message.caption or ""
    elif message.video:
        return message.video.file_name or message.caption or ""
    return message.caption or str(message.id)

def encode_ids(id_list: list) -> str:
    raw = ",".join(map(str, id_list))
    b64 = base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii")
    return f"LIST_{b64.rstrip('=')}"

def decode_ids(encoded_str: str):
    try:
        if encoded_str.startswith("LIST_"):
            b64 = encoded_str.replace("LIST_", "")
            padding = "=" * (-len(b64) % 4)
            raw = base64.urlsafe_b64decode((b64 + padding).encode("ascii")).decode("ascii")
            return [int(x) for x in raw.split(",")]
        elif encoded_str.startswith("BATCH_"):
            b64 = encoded_str.replace("BATCH_", "")
            padding = "=" * (-len(b64) % 4)
            raw = base64.urlsafe_b64decode((b64 + padding).encode("ascii")).decode("ascii")
            first_id, last_id = map(int, raw.split("_" if "_" in raw else ":"))
            step = 1 if first_id <= last_id else -1
            return list(range(first_id, last_id + step, step))
    except Exception:
        return []
    return []

async def is_subscribed(client: Client, user_id: int) -> bool:
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        if member.status in ["kicked", "left"]:
            return False
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return True

async def send_files_sequence(client: Client, chat_id: int, file_ids: list):
    status_msg = await client.send_message(chat_id, "⏳ Files send ki ja rahi hain...")
    try:
        for msg_id in file_ids:
            try:
                await client.copy_message(
                    chat_id=chat_id,
                    from_chat_id=DB_CHANNEL_ID,
                    message_id=msg_id
                )
                await asyncio.sleep(0.5)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.copy_message(
                    chat_id=chat_id,
                    from_chat_id=DB_CHANNEL_ID,
                    message_id=msg_id
                )
            except Exception:
                pass
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")

# --- COMMAND HANDLERS ---
@app.on_message((filters.command("start") | filters.regex("^🔄 Restart Bot")) & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.split() if message.text else []
    param = text[1] if len(text) > 1 else ""

    # Force Subscribe Verification
    if not await is_subscribed(client, user_id):
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://telegram.me/{FORCE_SUB_USERNAME}")],
            [InlineKeyboardButton("✅ I Have Joined", callback_data=f"checksub_{param}")]
        ]
        await message.reply_text(
            "⚠️ **Access Denied!**\n\nFiles pane ke liye pehle update channel join karein, fir **I Have Joined** button dabayein:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # Normal Start
    if not param:
        if user_id == BOT_OWNER:
            await message.reply_text(
                "👋 Hello Admin!\n\nNiche diye gaye buttons se batch banayein.",
                reply_markup=ADMIN_KEYBOARD
            )
        else:
            await message.reply_text("👋 Hello! Welcome to File Store Bot.")
        return

    # Batch Process
    file_ids = decode_ids(param)
    if not file_ids:
        await message.reply_text("❌ Invalid ya corrupted link.")
        return

    await send_files_sequence(client, message.chat.id, file_ids)

# --- CALLBACK QUERY HANDLER ---
@app.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data.startswith("checksub_"):
        param = data.split("_", 1)[1]
        
        if not await is_subscribed(client, user_id):
            await query.answer("❌ Pehle channel join karein!", show_alert=True)
            return

        await query.answer("✅ Verification successful!", show_alert=False)
        await query.message.delete()

        if not param:
            await client.send_message(user_id, "👋 Channel join karne ke liye shukriya!")
            return

        file_ids = decode_ids(param)
        if file_ids:
            await send_files_sequence(client, user_id, file_ids)
        else:
            await client.send_message(user_id, "❌ Invalid ya corrupted link.")

# --- ADMIN BATCH CREATION (REPLY BUTTONS) ---
@app.on_message((filters.command("batch") | filters.regex("^📦 Create Batch")) & filters.private)
async def batch_cmd(client: Client, message: Message):
    if message.from_user.id != BOT_OWNER:
        await message.reply_text("⛔ Only the Admin can create a batch!")
        return

    user_data[message.from_user.id] = []
    await message.reply_text(
        "📦 **Batch Mode Active!**\n\n"
        "✨ **Auto-Sorting Enabled:** Files aage-peeche kisi bhi order me aayengi, bot unhe title/episodes (1, 2, 3...) ke exact sequence me arrange karega.\n\n"
        "Files forward karein, phir **[✅ Done Batch]** dabayein.",
        reply_markup=ADMIN_KEYBOARD
    )

@app.on_message((filters.command("done") | filters.regex("^✅ Done Batch")) & filters.private)
async def done_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != BOT_OWNER:
        return

    if user_id in user_data and user_data[user_id]:
        raw_items = user_data[user_id]
        
        # Files ko Title / Ep ke hisaab se 1, 2, 3... order me sort karna
        sorted_items = sorted(raw_items, key=lambda x: natural_sort_key(x["title"]))
        sorted_ids = [item["id"] for item in sorted_items]

        encoded_key = encode_ids(sorted_ids)
        link = f"https://telegram.me/{BOT_USERNAME}?start={encoded_key}"
        
        await message.reply_text(
            f"🎉 **Permanent Sorted Link Ready:**\n\n`{link}`\n\n"
            f"📁 Total Files: `{len(sorted_ids)}`\n"
            f"🔢 Order: Perfectly sorted (1, 2, 3...)\n\n"
            f"*(This link is permanent and will NEVER expire)*",
            reply_markup=ADMIN_KEYBOARD,
            disable_web_page_preview=True
        )
        del user_data[user_id]
    else:
        await message.reply_text("❌ Pehle [📦 Create Batch] par tap karein aur files forward karein.")

# --- COLLECT FILES ---
@app.on_message(filters.private & ~filters.command(["start", "batch", "done", "clear"]) & ~filters.regex("^(📦 Create Batch|✅ Done Batch|🔄 Restart Bot)$"))
async def collect_files(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != BOT_OWNER:
        return

    if user_id in user_data:
        try:
            title = extract_file_title(message)
            msg = await message.copy(DB_CHANNEL_ID)
            
            user_data[user_id].append({
                "id": msg.id,
                "title": title
            })
            
            total = len(user_data[user_id])
            await message.reply_text(f"✅ Saved! Total Files: **{total}**")
            await asyncio.sleep(0.3)
        except Exception as e:
            await message.reply_text(f"❌ Error saving file: {e}")

if __name__ == "__main__":
    print("Bot is running...")
    app.run()
                
