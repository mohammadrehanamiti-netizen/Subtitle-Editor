
#!/usr/bin/env python3
import os
import tempfile
import logging

from flask import Flask, request, abort
from dotenv import load_dotenv
import pysubs2

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Dispatcher,
    MessageHandler,
    Filters,
    CommandHandler,
    CallbackQueryHandler,
)

from styles import STYLES  # <-- your theme registry

# Load env – Koyeb injects BOT_TOKEN & WEBHOOK_URL
load_dotenv()
BOT_TOKEN   = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT        = int(os.getenv("PORT", 8080))

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN & WEBHOOK_URL must be set as env vars")

# Flask + Bot setup
app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(bot, None, workers=0, use_context=True)
logging.basicConfig(level=logging.INFO)

# Register webhook
bot.set_webhook(WEBHOOK_URL)

@app.route("/", methods=["GET"])
def health():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    if not request.is_json:
        abort(400)
    upd = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(upd)
    return "", 200

# ─── In-memory store of each chat's chosen theme ──────────────────
user_selected_theme = {}  # defaults to "Pikasub" if never set



def start_command(update, context):
    text = (
        "Hey! I’m your Subtitle Stylist 🎬✨\n\n"
        "What I do:\n"
        "• Convert .srt or .vtt or .ass → styled .ass\n"
        "• Ready-made themes: Pika 1080p / 720p / 480p, Shrouding The Heavens, Tales Of Herding Gods\n"
        "• Auto title cards & soft watermark (theme-specific)\n\n"
        "How to use:\n"
        "1) Send me a .srt or .vtt or .ass file\n"
        "2) Choose your style via /setting\n"
        "3) I’ll return the .ass file—ready to mux\n\n"
        "Tips:\n"
        "• Use /setting anytime to switch styles\n"
        "• If something fails, just resend the file\n\n"
        "Ready when you are. Drop your subtitle file now ⬇️"
        "📩 Contact @THe_vK_3 if any problem or Query"
    )
    update.message.reply_text(text)

def help_command(update, context):
    update.message.reply_text(
        "Need help?\n\n"
        "• Use /setting to pick a theme\n"
        "• Send .srt or .vtt or .ass files only\n"
        "• I’ll return a themed .ass file\n"
    )

# ─── /setting command to pick your theme ─────────────────────────
def settings_command(update, context):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"set_theme|{name}")]
        for name in STYLES.keys()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Choose a subtitle style:", reply_markup=reply_markup)

# ─── Callback when a theme button is pressed ────────────────────
def theme_callback(update, context):
    query = update.callback_query
    query.answer()
    _, theme_name = query.data.split("|", 1)

    if theme_name not in STYLES:
        query.edit_message_text("❌ Unknown style.")
        return

    chat_id = query.message.chat_id
    user_selected_theme[chat_id] = theme_name
    query.edit_message_text(f"✅ Style set to *{theme_name}*", parse_mode="Markdown")

def handle_document(update, context):
    doc      = update.message.document
    filename = doc.file_name
    ext      = os.path.splitext(filename)[1].lower()

    if ext not in (".srt", ".vtt", ".ass"):
        return update.message.reply_text("🚫 Please send a .srt or .vtt or .ass file.")

    in_path = out_path = None
    try:
        # Download incoming file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
            in_path = tmp_in.name
        bot.getFile(doc.file_id).download(custom_path=in_path)

        # Load subtitles
        subs = pysubs2.load(in_path)

        # ─── figure out which theme this chat has chosen ───────────────
        chat_id = update.message.chat_id
        theme   = user_selected_theme.get(chat_id, "Pikasub")
        styles  = STYLES.get(theme, [])
        # Force 1920×1080 resolution
        if theme == "Pika 480p":
            subs.info["PlayResX"] = "640"
            subs.info["PlayResY"] = "480"

        elif theme == "Pika 720p":
            subs.info["PlayResX"] = "1280"
            subs.info["PlayResY"] = "720"

        elif theme == "Immortal Doctor":
            subs.info["PlayResX"] = "1920"
            subs.info["PlayResY"] = "800"
             
        else:
            subs.info["PlayResX"] = "1920"
            subs.info["PlayResY"] = "1080"
            
        # Register each style under its .name
        for style in styles:
            subs.styles[style.name] = style

        # ─── Theme‐specific logic ─────────────────────────────────────
        if theme == "Pika 1080p":
            # 1) Prepend your “site” event (0→5min)
            site_tag = r"{\fad(4000,3000)\fn@Arial Unicode MS\fs31.733"\
                       r"\c&H00FFFFFF&\alpha&H99&\b1\a1\fscy60}"
            start_ms = 0
            end_ms   = 5 * 60 * 1000
            site_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="site",
                text=site_tag + "PikaSub.com"
            )
            subs.events.insert(0, site_event)

            Telegram_title = r"{\an8}Hindi Translation by: PikaSub.com\NTelegram Channel: @PikaSub"
            start_ms = 0
            end_ms   = 10 * 1000
            Tele_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="Default",
                text=Telegram_title
            )
            subs.events.insert(0, Tele_event)

            Middle_title = r"{\fad(0,2000)\move(2505.6,52.5,-750.9,53.1)\fs42\c&H00F0FF&\1a&H00&\b1}{\fscy100\fnCorbel\shad2.5}For more Animes in Hindi Sub join our Telegram Channel: @PikaSub"
            start_ms = 180000
            end_ms   = 200000
            Middle_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="site",
                text=Middle_title
            )
            subs.events.insert(0, Middle_event)

            # 2) Apply Default to the rest
            for line in subs.events[3:]:
                line.style = "Default"


        elif theme == "Pika 720p":
            # 1) Prepend your “site” event (0→5min)
            site_tag = r"{\fad(4000,3000)\fn@Arial Unicode MS\fs25.733"\
                       r"\c&H00FFFFFF&\alpha&H99&\b1\a1\fscy60}"
            start_ms = 0
            end_ms   = 5 * 60 * 1000
            site_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="site",
                text=site_tag + "PikaSub.com"
            )
            subs.events.insert(0, site_event)

            Telegram_title = r"{\an8}Hindi Translation by: PikaSub.com\NTelegram Channel: @PikaSub"
            start_ms = 0
            end_ms   = 10 * 1000
            Tele_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="Default",
                text=Telegram_title
            )
            subs.events.insert(0, Tele_event)

            Middle_title = r"{\fad(0,2000)\move(2505.6,52.5,-750.9,53.1)\fs32\c&H00F0FF&\1a&H00&\b1}{\fscy100\fnCorbel\shad2.5}For more Animes in Hindi Sub join our Telegram Channel: @PikaSub"
            start_ms = 180000
            end_ms   = 200000
            Middle_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="site",
                text=Middle_title
            )
            subs.events.insert(0, Middle_event)

            # 2) Apply Default to the rest
            for line in subs.events[3:]:
                line.style = "Default"

        
        elif theme == "Pika 480p":
            # 1) Prepend your “site” event (0→5min)
            site_tag = r"{\fad(4000,3000)\fn@Arial Unicode MS\fs15.733"\
                       r"\c&H00FFFFFF&\alpha&H99&\b1\a1\fscy60}"
            start_ms = 0
            end_ms   = 5 * 60 * 1000
            site_event = pysubs2.SSAEvent(
                start=start_ms,
                end=end_ms,
                style="site",
                text=site_tag + "PikaSub.com"
            )
            subs.events.insert(0, site_event)

            # 2) Apply Default to the rest
            for line in subs.events[1:]:
                line.style = "Pika 480p"

        elif theme == "Shrouding The Heavens":
            # 1) Insert Telegram event from 0 → first subtitle start
            if subs.events:
                first_start = subs.events[0].start
            else:
                first_start = 0
            telegram_event = pysubs2.SSAEvent(
                start=0,
                end=first_start,
                style=styles[0].name,
                text="Telegram :- Facky_Hindi_Donghua"
            )
            subs.events.insert(0, telegram_event)

            # 2) Apply the Shrouding style to every other line
            for line in subs.events[1:]:
                line.style = styles[0].name

        elif theme == "Tales Of Herding Gods":
            # 0) Delete the very first subtitle line if it exists
            if subs.events:
                subs.events.pop(0)
        
            # 1) Insert Telegram event from 0 → first subtitle start (same behavior as Shrouding)
            if subs.events:
                first_start = subs.events[0].start
            else:
                first_start = 0
        
            telegram_event = pysubs2.SSAEvent(
                start=0,
                end=first_start,
                style=styles[0].name,
                text="Telegram :- Facky_Hindi_Donghua"
            )
            subs.events.insert(0, telegram_event)
        
            # 2) Apply this style to every other line
            for line in subs.events[1:]:
                line.style = styles[0].name

        elif theme == "Big Brother":
            # 1) Insert Telegram event from 0 → first subtitle start
            if subs.events:
                first_start = subs.events[0].start
            else:
                first_start = 0
            telegram_event = pysubs2.SSAEvent(
                start=0,
                end=first_start,
                style=styles[0].name,
                text="Telegram :- Facky_Hindi_Donghua"
            )
            subs.events.insert(0, telegram_event)

            # 2) Apply the Shrouding style to every other line
            for line in subs.events[1:]:
                line.style = styles[0].name

        elif theme == "Immortal Doctor":
            # (a) Delete the first TWO subtitle lines if present
            for _ in range(3):
                if subs.events:
                    subs.events.pop(0)
        
            # (b) Insert the same “title/telegram” line behavior used in Tales
            if subs.events:
                first_start = subs.events[0].start
            else:
                first_start = 0
        
            telegram_event = pysubs2.SSAEvent(
                start=0,
                end=first_start,
                style=styles[0].name,                   # use Immortal Doctor style
                text="Telegram :- Facky_Hindi_Donghua"  # same as Tales title line
            )
            subs.events.insert(0, telegram_event)
        
            # (c) Apply this style to every remaining line (same as Tales)
            for line in subs.events[1:]:
                line.style = styles[0].name

        else:
            # Fallback for any future styles: just apply the first style
            for line in subs.events:
                line.style = styles[0].name

        # ─── Now apply semi-transparent tag to *all* lines ────────────
        alpha_tag = r"{\4a&H50&}"
        for line in subs.events:
            line.text = alpha_tag + line.text

        # Save out to .ass
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ass") as tmp_out:
            out_path = tmp_out.name
        subs.save(out_path)

        # Reply with converted file
        with open(out_path, "rb") as f:
            reply_name = os.path.splitext(filename)[0] + ".ass"
            update.message.reply_document(f, filename=reply_name)

    except Exception:
        logging.exception("Conversion failed")
        update.message.reply_text("❌ Conversion error—please try again.")
    finally:
        for p in (in_path, out_path):
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass

# ─── Register handlers ─────────────────────────────────────────────
dp.add_handler(CommandHandler("start", start_command))
dp.add_handler(CommandHandler("help", help_command))
dp.add_handler(CommandHandler("setting", settings_command))
dp.add_handler(CallbackQueryHandler(theme_callback, pattern=r"^set_theme\|"))
dp.add_handler(MessageHandler(Filters.document, handle_document))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
