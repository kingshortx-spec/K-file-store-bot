import asyncio
import base64
import os
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
def encode_ids(id_list: list) -> str:
    # Saari exact IDs ko comma separated string banakar base64 encode karte hain
    raw = ",".join(map(str, id_list))
    b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"LIST_{b64}"

def decode_ids(encoded: str):
    try:
        # Dono support karega: Naya LIST format bhi aur purana BATCH format bhi
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

    if not await is_subscribed(client, user_id):
        buttons = [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://telegram.me/{FORCE_SUB_USERNAME}")],
            [InlineKeyboardButton("✅ I Have Joined", callback_data=f"checksub_{param}")]
        ]
        await message.reply(
            "⚠️ **Access Denied!**\n\nFiles lene ke liye pehle update channel join karein, fir **I Have Joined** par click karein:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    if not param:
        if user_id in ADMINS:
            await message.reply(
                "👋 Hello Admin! Naya link banane ke liye button dabayein:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Create Batch", callback_data="make_batch")]
                ])
            )
        else:
            await message.reply("👋 Welcome! Send me a valid link to get files.")
        return

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
        ADMIN_STATES[user_id] = {"collecting": True, "ids": []}
        await query.message.edit(
            "📥 Ab aap files bhejein (jis order me bhejenge usi exact order me user ko milengi).\n\n"
            "Saari files aane ke baad **Done Batch** dabayein.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done Batch", callback_data="done_batch")]
            ])
        )

    elif data == "done_batch":
        state = ADMIN_STATES.get(user_id)
        if not state or not state.get("ids"):
            await query.message.edit("❌ Koi file receive nahi hui. Batch cancel.")
            ADMIN_STATES.pop(user_id, None)
            return

        exact_ids = state["ids"]
        encoded_str = encode_ids(exact_ids)
        link = f"https://telegram.me/{client.me.username}?start={encoded_str}"

        await query.message.edit(
            f"✅ **Perfect Link Ready!**\n\n"
            f"📁 Total Files: `{len(exact_ids)}`\n"
            f"🔗 Link:\n`{link}`",
            disable_web_page_preview=True
        )
        ADMIN_STATES.pop(user_id, None)

# --- FORWARD COLLECTOR ---
@bot.on_message(filters.private & ~filters.command(["start"]))
async def message_collector(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in ADMINS and ADMIN_STATES.get(user_id, {}).get("collecting"):
        forwarded = await message.copy(chat_id=DB_CHANNEL)
        ADMIN_STATES[user_id]["ids"].append(forwarded.id)
        await asyncio.sleep(0.4)

if __name__ == "__main__":
    bot.run()
