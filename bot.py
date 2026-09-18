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

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 26386777))
API_HASH = os.environ.get("API_HASH", "ee7bbb1078fa4aaf4c1b6e9cfeec3ca1")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8836438619:AAEm-4dKhJlKsttcW09xLIS_a6SWCgpZDDk")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Filestore_kingx_bot")
DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL", -1003486068610))
BOT_OWNER = int(os.environ.get("BOT_OWNER", 910090161))

FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", -1003379165829))
FORCE_SUB_USERNAME = os.environ.get("FORCE_SUB_USERNAME", "kingx_update")

app = Client("BatchBotPhone", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

user_data = {}

ADMIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📦 Create Batch"), KeyboardButton("✅ Done Batch")],
        [KeyboardButton("🔄 Restart Bot")]
    ],
    resize_keyboard=True
)

def natural_sort_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

def get_message_title(msg: Message) -> str:
    if msg.audio:
        return msg.audio.title or msg.audio.file_name or msg.caption or ""
    elif msg.document:
        return msg.document.file_name or msg.caption or ""
    elif msg.video:
        return msg.video.file_name or msg.caption or ""
    return msg.caption or str(msg.id)

def encode_batch(start_id: int, end_id: int) -> str:
    raw = f"{start_id}_{end_id}"
    b64 = base64.urlsafe_b64encode(raw.encode("ascii")).decode("ascii")
    return b64.rstrip("=")

def decode_batch(b64_str: str):
    try:
        padding = "=" * (-len(b64_str) % 4)
        raw = base64.urlsafe_b64decode((b64_str + padding).encode("ascii")).decode("ascii")
        start_id, end_id = map(int, raw.split("_"))
        return start_id, end_id
    except Exception:
        return None, None

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

async def deliver_files(client: Client, chat_id: int, start_id: int, end_id: int):
    status_msg = await client.send_message(chat_id, "⏳ Fetching files...")
    
    first = min(start_id, end_id)
    last = max(start_id, end_id)
    
    # DB Channel se saare messages fetch karke list banate hain
    fetched_messages = []
    for msg_id in range(first, last + 1):
        try:
            m = await client.get_messages(DB_CHANNEL_ID, msg_id)
            if m and not m.empty:
                fetched_messages.append(m)
        except Exception:
            pass

    if not fetched_messages:
        await status_msg.edit("❌ Files nahi mili ya DB Channel access error.")
        return

    # Title / Caption ke natural sequence (1, 2, 3...) me sort karna
    sorted_messages = sorted(fetched_messages, key=lambda m: natural_sort_key(get_message_title(m)))

    await status_msg.edit(f"📦 Sending {len(sorted_messages)} files in sequence...")

    for m in sorted_messages:
        try:
            await client.copy_message(chat_id=chat_id, from_chat_id=DB_CHANNEL_ID, message_id=m.id)
            await asyncio.sleep(0.5)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await client.copy_message(chat_id=chat_id, from_chat_id=DB_CHANNEL_ID, message_id=m.id)
        except Exception:
            pass

    await status_msg.delete()

@app.on_message((filters.command("start") | filters.regex("^🔄 Restart Bot")) & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.split() if message.text else []
    param = text[1] if len(text) > 1 else ""

    if not await is_subscribed(client, user_id):
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://telegram.me/{FORCE_SUB_USERNAME}")],
            [InlineKeyboardButton("✅ I Have Joined", callback_data=f"subcheck_{param}")]
        ]
        await message.reply_text(
            "⚠️ **Access Denied!**\n\nFiles pane ke liye pehle update channel join karein:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if not param:
        if user_id == BOT_OWNER:
            await message.reply_text("👋 Hello Admin! Buttons use karein:", reply_markup=ADMIN_KEYBOARD)
        else:
            await message.reply_text("👋 Welcome to File Store Bot.")
        return

    if param.startswith("BATCH_"):
        raw_code = param.replace("BATCH_", "")
        start_id, end_id = decode_batch(raw_code)
        if start_id and end_id:
            await deliver_files(client, message.chat.id, start_id, end_id)
        else:
            await message.reply_text("❌ Corrupted link.")
    else:
        await message.reply_text("❌ Invalid link format.")

@app.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data.startswith("subcheck_"):
        param = data.replace("subcheck_", "")
        if not await is_subscribed(client, user_id):
            await query.answer("❌ Aapne abhi tak channel join nahi kiya!", show_alert=True)
            return

        await query.answer("✅ Verification Successful!")
        await query.message.delete()

        if param.startswith("BATCH_"):
            raw_code = param.replace("BATCH_", "")
            start_id, end_id = decode_batch(raw_code)
            if start_id and end_id:
                await deliver_files(client, user_id, start_id, end_id)

@app.on_message((filters.command("batch") | filters.regex("^📦 Create Batch")) & filters.private)
async def batch_cmd(client: Client, message: Message):
    if message.from_user.id != BOT_OWNER:
        return
    user_data[message.from_user.id] = []
    await message.reply_text("📦 **Batch Mode Active!**\n\nFiles forward karein, fir [✅ Done Batch] dabayein.", reply_markup=ADMIN_KEYBOARD)

@app.on_message((filters.command("done") | filters.regex("^✅ Done Batch")) & filters.private)
async def done_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != BOT_OWNER:
        return

    ids = user_data.get(user_id, [])
    if not ids:
        await message.reply_text("❌ Pehle files forward karein.")
        return

    first_id = min(ids)
    last_id = max(ids)
    encoded = encode_batch(first_id, last_id)
    link = f"https://telegram.me/{BOT_USERNAME}?start=BATCH_{encoded}"

    await message.reply_text(
        f"🎉 **Permanent Batch Link Ready:**\n\n`{link}`\n\n"
        f"📁 Total Files Saved: `{len(ids)}`\n"
        f"🔢 Auto-sorted sequentially on delivery!",
        reply_markup=ADMIN_KEYBOARD,
        disable_web_page_preview=True
    )
    del user_data[user_id]

@app.on_message(filters.private & ~filters.command(["start", "batch", "done"]) & ~filters.regex("^(📦 Create Batch|✅ Done Batch|🔄 Restart Bot)$"))
async def collect_files(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != BOT_OWNER or user_id not in user_data:
        return

    try:
        msg = await message.copy(DB_CHANNEL_ID)
        user_data[user_id].append(msg.id)
        await message.reply_text(f"✅ Saved! Total Files: **{len(user_data[user_id])}**")
        await asyncio.sleep(0.3)
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

if __name__ == "__main__":
    app.run()
