import base64
import os
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", "YOUR_API_ID"))
API_HASH = os.environ.get("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN")
DB_CHANNEL = int(os.environ.get("DB_CHANNEL", "-100XXXXXXXXXX"))
ADMINS = [int(x) for x in os.environ.get("ADMINS", "YOUR_ADMIN_ID").split()]

# Force Subscribe Details
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
def encode_batch(first_id: int, last_id: int) -> str:
    raw = f"{first_id}:{last_id}"
    b64 = base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")
    return f"BATCH_{b64}"

def decode_batch(encoded: str):
    try:
        b64 = encoded.replace("BATCH_", "")
        padding = "=" * (-len(b64) % 4)
        raw = base64.urlsafe_b64decode((b64 + padding).encode()).decode()
        first_id, last_id = map(int, raw.split(":"))
        return first_id, last_id
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

async def send_batch_files(client: Client, chat_id: int, first_id: int, last_id: int):
    status_msg = await client.send_message(chat_id, "⏳ Files send ki ja rahi hain...")
    try:
        for msg_id in range(first_id, last_id + 1):
            try:
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
            "⚠️ **Access Denied!**\n\nFiles pane ke liye pehle hamara update channel join karein, fir **I Have Joined** button dabayein:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return

    # Normal Start
    if not param:
        if user_id in ADMINS:
            await message.reply(
                "👋 Hello Admin! Batch link banane ke liye neeche button dabayein.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 Create Batch", callback_data="make_batch")]
                ])
            )
        else:
            await message.reply("👋 Welcome! Send me a valid link to get files.")
        return

    # Batch Process Logic
    if param.startswith("BATCH_"):
        first_id, last_id = decode_batch(param)
        if not first_id or not last_id:
            await message.reply("❌ Invalid ya corrupted link.")
            return
        await send_batch_files(client, message.chat.id, first_id, last_id)
    else:
        await message.reply("❌ Invalid Link format.")

# --- CALLBACK QUERY HANDLER ---
@bot.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    # Check Subscription Callback
    if data.startswith("checksub_"):
        param = data.split("_", 1)[1]
        
        if not await is_subscribed(client, user_id):
            await query.answer("❌ Aapne abhi tak channel join nahi kiya hai! Pehle join karein.", show_alert=True)
            return

        await query.answer("✅ Channel verification successful!", show_alert=False)
        await query.message.delete()

        if not param:
            await client.send_message(user_id, "👋 Channel join karne ke liye shukriya!")
            return

        if param.startswith("BATCH_"):
            first_id, last_id = decode_batch(param)
            if first_id and last_id:
                await send_batch_files(client, user_id, first_id, last_id)
            else:
                await client.send_message(user_id, "❌ Invalid ya corrupted link.")
        return

    # Admin Batch Logic
    if user_id not in ADMINS:
        await query.answer("Access Denied", show_alert=True)
        return

    if data == "make_batch":
        ADMIN_STATES[user_id] = {"collecting": True, "ids": []}
        await query.message.edit(
            "📥 Ab aap jo files bhejna chahte hain, unhe forward karein ya send karein.\n\n"
            "Saari files upload hone ke baad **Done** dabayein.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Done Batch", callback_data="done_batch")]
            ])
        )

    elif data == "done_batch":
        state = ADMIN_STATES.get(user_id)
        if not state or not state.get("ids"):
            await query.message.edit("❌ Koi file send nahi ki gayi. Batch cancel.")
            ADMIN_STATES.pop(user_id, None)
            return

        ids = sorted(state["ids"])
        first_id = ids[0]
        last_id = ids[-1]

        batch_str = encode_batch(first_id, last_id)
        bot_username = client.me.username
        link = f"https://telegram.me/{bot_username}?start={batch_str}"

        await query.message.edit(
            f"✅ **Batch Link Ready!**\n\n"
            f"📁 Total Files: `{len(ids)}`\n"
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

if __name__ == "__main__":
    bot.run()
