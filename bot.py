import asyncio
import base64
import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant, FloodWait

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-100XXXXXXXXXX"))
ADMINS = [int(x) for x in os.environ.get("ADMINS", "YOUR_ADMIN_ID").split()]

FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", "-1003379165829"))
FORCE_SUB_USERNAME = os.environ.get("FORCE_SUB_USERNAME", "kingx_update")

bot = Client(
    "direct_filestore_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

ADMIN_STATES = {}

# --- HELPER FUNCTIONS ---
def natural_sort_key(s: str):
    """Numbers ko natural sequence (1, 2, 10...) me sort karne ke liye"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def extract_file_title(message: Message) -> str:
    """Message se file ka naam, audio title ya caption nikalne ke liye"""
    if message.audio:
        return message.audio.title or message.audio.file_name or message.caption or ""
    elif message.document:
        return message.document.file_name or message.caption or ""
    elif message.video:
        return message.video.file_name or message.caption or ""
    return message.caption or str(message.id)

def encode_ids(id_list: list) -> str:
    raw = ",".join(map(str, id_list))
    b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"LIST_{b64}"

def decode_ids(encoded: str):
    try:
        if encoded.startswith("LIST_"):
            b64 = encoded.replace("LIST_", "")
            padding = "=" * (-len(b64) % 4)
            raw = base64.urlsafe_b64decode((b64 + padding).encode()).decode()
            return [int(x) for x in raw.split(",")]
        elif encoded.startswith("BATCH_"):
            b64 = encoded.replace("BATCH_", "")
            padding = "=" * (-len(b64) % 4)
            raw = base64.urlsafe_b64decode((b64 + padding).encode()).decode()
            first_id, last_id = map(int, raw.split(":"))
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
                    from_chat_id=DB_CHANNEL,
                    message_id=msg_id
                )
                await asyncio.sleep(0.5)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await client.copy_message(
                    chat_id=chat_id,
                    from_chat_id=DB_CHANNEL,
                    message_id=msg_id
                )
            except Exception:
                pass
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit(f"❌ Error: {str(e)}")

# --- COMMAND HANDLERS ---
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    text = message.text.split()
    param = text[1] if len(text) > 1 else ""

    # Force Sub Check
    if not await is_subscribed(client, user_id):
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://telegram.me/{FORCE_SUB_USERNAME}")],
            [InlineKeyboardButton("✅ I Have Joined", callback_data=f"checksub_{param}")]
        ]
        await message.reply(
            "⚠️ **Access Denied!**\n\nFiles lene ke liye pehle update channel join karein, fir **I Have Joined** dabayein:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # Normal Admin / User Start
    if not param:
        if user_id in ADMINS:
            await message.reply(
                "👋 Hello Admin! Naya Batch banane ke liye button dabayein:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Create Batch", callback_data="make_batch")]
                ])
            )
        else:
            await message.reply("👋 Welcome! Send me a valid link to get files.")
        return

    # Link Processing
    file_ids = decode_ids(param)
    if not file_ids:
        await message.reply("❌ Invalid ya corrupted link.")
        return
        
    await send_files_sequence(client, message.chat.id, file_ids)

# --- CALLBACK QUERY HANDLER ---
@bot.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data.startswith("checksub_"):
        param = data.split("_", 1)[1]
        
        if not await is_subscribed(client, user_id):
            await query.answer("❌ Pehle channel join karein!", show_alert=True)
            return

        await query.answer("✅ Verified!", show_alert=False)
        await query.message.delete()

        if not param:
            await client.send_message(user_id, "👋 Channel join karne ke liye shukriya!")
            return

        file_ids = decode_ids(param)
        if file_ids:
            await send_files_sequence(client, user_id, file_ids)
        else:
            await client.send_message(user_id, "❌ Invalid ya corrupted link.")
        return

    if user_id not in ADMINS:
        await query.answer("Access Denied", show_alert=True)
        return

    if data == "make_batch":
        ADMIN_STATES[user_id] = {"collecting": True, "items": []}
        await query.message.edit(
            "📥 Ab aap files send/forward karein.\n\n"
            "✨ **Auto-Sorting On:** Files kisi bhi aage-peeche order me aayengi, bot unhe title/episodes ke sequence (1, 2, 3...) me khud sort kar lega!\n\n"
            "Saari files bhejne ke baad **Done Batch** dabayein.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done Batch", callback_data="done_batch")]
            ])
        )

    elif data == "done_batch":
        state = ADMIN_STATES.get(user_id)
        if not state or not state.get("items"):
            await query.message.edit("❌ Koi file receive nahi hui. Batch cancel.")
            ADMIN_STATES.pop(user_id, None)
            return

        raw_items = state["items"]
        
        # Natural Name/Title ke hisab se sort karega (e.g. Ep 1865, Ep 1866 ya 1, 2, 3...)
        sorted_items = sorted(raw_items, key=lambda x: natural_sort_key(x["title"]))
        sorted_ids = [item["id"] for item in sorted_items]

        encoded_str = encode_ids(sorted_ids)
        link = f"https://telegram.me/{client.me.username}?start={encoded_str}"

        await query.message.edit(
            f"✅ **Perfect Ordered Link Ready!**\n\n"
            f"📁 Total Files: `{len(sorted_ids)}`\n"
            f"🔢 Auto-sorted in exact (1, 2, 3...) order!\n"
            f"🔗 Link:\n`{link}`",
            disable_web_page_preview=True
        )
        ADMIN_STATES.pop(user_id, None)

# --- FORWARD & MESSAGE COLLECTOR ---
@bot.on_message(filters.private & ~filters.command(["start"]))
async def message_collector(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in ADMINS and ADMIN_STATES.get(user_id, {}).get("collecting"):
        title = extract_file_title(message)
        forwarded = await message.copy(chat_id=DB_CHANNEL)
        
        ADMIN_STATES[user_id]["items"].append({
            "id": forwarded.id,
            "title": title
        })
        
        count = len(ADMIN_STATES[user_id]["items"])
        await message.reply(f"✅ Saved! Total Files: {count}")
        await asyncio.sleep(0.3)

if __name__ == "__main__":
    bot.run()
            
