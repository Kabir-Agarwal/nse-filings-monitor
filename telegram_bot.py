import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from dotenv import load_dotenv
load_dotenv()

import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes,
)
from supabase import create_client

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── User data state keys ──────────────────────────────────────────────
# context.user_data["sub_step"]       : "CATEGORY" | "SYMBOLS" | "FILING_TYPES" | None
# context.user_data["sub_categories"] : list[str]
# context.user_data["sub_watchlist"]  : list[str]
# context.user_data["awaiting_wl"]    : bool

# ── Supabase helpers ─────────────────────────────────────────────────

def get_subscriber(chat_id: str):
    try:
        r = supabase.table("subscribers").select("*").eq("chat_id", chat_id).execute()
        return r.data[0] if r.data else None
    except Exception as e:
        print(f"DB get error: {e}")
        return None


def save_subscriber(chat_id: str, username: str = None, first_name: str = None, **fields):
    """Insert or update a subscriber row."""
    try:
        row = {"chat_id": chat_id, "updated_at": datetime.now().isoformat()}
        if username is not None:
            row["username"] = username
        if first_name is not None:
            row["first_name"] = first_name
        row.update(fields)
        supabase.table("subscribers").upsert(row, on_conflict="chat_id").execute()
        return True
    except Exception as e:
        print(f"DB save error: {e}")
        return False


def count_active_subscribers():
    try:
        r = supabase.table("subscribers").select("id", count="exact").eq("is_active", True).limit(1).execute()
        return getattr(r, "count", 0) or 0
    except Exception:
        return 0

# ── Keyboards ────────────────────────────────────────────────────────

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Subscribe / Edit Alerts", callback_data="menu_subscribe")],
        [
            InlineKeyboardButton("⭐ Watchlist", callback_data="menu_watchlist"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
        [
            InlineKeyboardButton("⏸ Pause", callback_data="menu_pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="menu_resume"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="menu_help"),
            InlineKeyboardButton("🚫 Unsubscribe", callback_data="menu_stop"),
        ],
    ])

# ── /start ────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    save_subscriber(chat_id, user.username, user.first_name, is_active=True)
    name = user.first_name or "Trader"
    await update.message.reply_text(
        f"🔔 *NSE + BSE Filings Monitor*\n\n"
        f"Welcome, {name}! You're now registered for corporate filing alerts.\n\n"
        f"*Default settings:*\n"
        f"📊 Categories: HIGH impact only\n"
        f"🏢 Symbols: All companies\n"
        f"📁 Filing Types: All types\n\n"
        f"Use the menu below to customize your alerts:",
        parse_mode="Markdown",
        reply_markup=main_menu_kb(),
    )

# ── /subscribe wizard helpers ─────────────────────────────────────────

def _subscribe_step1_text():
    return (
        "📊 *Step 1 of 3 — Alert Categories*\n\n"
        "Which filing impact levels should I alert you for?\n\n"
        "• *HIGH* — Acquisitions, mergers, fund raises, new orders (with Gemini AI analysis)\n"
        "• *MODERATE* — Board meetings, results, appointments\n"
        "• *ALL* — Everything including routine filings"
    )

def _subscribe_step1_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 HIGH only (recommended)", callback_data="sub_cat_HIGH")],
        [InlineKeyboardButton("🟡 HIGH + MODERATE", callback_data="sub_cat_HIGH_MODERATE")],
        [InlineKeyboardButton("📋 ALL Categories", callback_data="sub_cat_ALL")],
        [InlineKeyboardButton("❌ Cancel", callback_data="sub_cancel")],
    ])

def _subscribe_step2_text(cats: list):
    return (
        f"✅ Categories: *{', '.join(cats)}*\n\n"
        f"📊 *Step 2 of 3 — Company Filter*\n\n"
        f"Type NSE/BSE symbols separated by spaces to watch specific stocks, "
        f"or click *All Companies* to receive alerts for everyone.\n\n"
        f"*Example:* `HDFC INFY TCS RELIANCE`"
    )

def _subscribe_step2_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 All Companies", callback_data="sub_sym_ALL")],
        [InlineKeyboardButton("❌ Cancel", callback_data="sub_cancel")],
    ])

def _subscribe_step3_text(cats: list, symbols: list):
    sym_str = ", ".join(symbols) if symbols else "All Companies"
    return (
        f"✅ Categories: *{', '.join(cats)}*\n"
        f"✅ Symbols: *{sym_str}*\n\n"
        f"📊 *Step 3 of 3 — Filing Types*\n\n"
        f"Which types of filings interest you?"
    )

def _subscribe_step3_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 All Filing Types", callback_data="sub_ft_ALL")],
        [InlineKeyboardButton("💰 Dividends", callback_data="sub_ft_DIVIDENDS")],
        [InlineKeyboardButton("📊 Financial Results", callback_data="sub_ft_RESULTS")],
        [InlineKeyboardButton("🏢 Acquisitions / Mergers", callback_data="sub_ft_ACQUISITIONS")],
        [InlineKeyboardButton("❌ Cancel", callback_data="sub_cancel")],
    ])

# ── /subscribe command ────────────────────────────────────────────────

async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sub_step"] = "CATEGORY"
    await update.message.reply_text(
        _subscribe_step1_text(),
        parse_mode="Markdown",
        reply_markup=_subscribe_step1_kb(),
    )

# ── /watchlist ────────────────────────────────────────────────────────

async def cmd_watchlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    sub = get_subscriber(chat_id)
    if not sub:
        await update.message.reply_text(
            "You're not registered yet. Use /start to join.", parse_mode="Markdown"
        )
        return
    watchlist = sub.get("watchlist") or []
    if watchlist:
        watch_text = "Your watched symbols:\n" + "\n".join(f"• `{s}`" for s in watchlist)
    else:
        watch_text = "Receiving alerts for *all companies* (no symbol filter)."
    await update.message.reply_text(
        f"⭐ *Your Watchlist*\n\n{watch_text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Edit Watchlist", callback_data="wl_edit")],
            [InlineKeyboardButton("🗑️ Clear — Watch All", callback_data="wl_clear")],
        ]),
    )

# ── /settings ─────────────────────────────────────────────────────────

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    sub = get_subscriber(chat_id)
    if not sub:
        await update.message.reply_text("You're not registered yet. Use /start to join.")
        return
    await update.message.reply_text(
        _settings_text(sub),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Edit Preferences", callback_data="menu_subscribe")],
            [InlineKeyboardButton("⭐ Edit Watchlist", callback_data="wl_edit")],
        ]),
    )

def _settings_text(sub: dict) -> str:
    cats = ", ".join(sub.get("categories") or ["HIGH"])
    wl = sub.get("watchlist") or []
    sym_str = ", ".join(wl) if wl else "All Companies"
    fts = sub.get("filing_types") or []
    ft_str = ", ".join(fts).title() if fts else "All Types"
    status = "✅ Active" if sub.get("is_active", True) else "⏸ Paused"
    joined = (sub.get("created_at") or "")[:10] or "N/A"
    return (
        f"⚙️ *Your Alert Settings*\n\n"
        f"Status: {status}\n"
        f"📊 Categories: *{cats}*\n"
        f"🏢 Symbols: *{sym_str}*\n"
        f"📁 Filing Types: *{ft_str}*\n"
        f"📅 Joined: {joined}"
    )

# ── /pause, /resume, /stop, /help ─────────────────────────────────────

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_subscriber(str(update.effective_chat.id), is_active=False)
    await update.message.reply_text(
        "⏸ *Alerts paused.*\n\nUse /resume to turn them back on.",
        parse_mode="Markdown",
    )

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_subscriber(str(update.effective_chat.id), is_active=True)
    await update.message.reply_text(
        "▶️ *Alerts resumed!* You'll receive filings based on your preferences.",
        parse_mode="Markdown",
    )

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚫 *Unsubscribe*\n\nWhat would you like to do?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏸ Just Pause (keep settings)", callback_data="stop_pause")],
            [InlineKeyboardButton("🗑️ Full Unsubscribe (delete data)", callback_data="stop_delete")],
            [InlineKeyboardButton("❌ Cancel", callback_data="stop_cancel")],
        ]),
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *NSE + BSE Filings Monitor — Commands*\n\n"
        "/start — Register & see main menu\n"
        "/subscribe — Set up alert preferences (wizard)\n"
        "/watchlist — View & edit your company watchlist\n"
        "/settings — View all current settings\n"
        "/pause — Pause all alerts temporarily\n"
        "/resume — Resume alerts\n"
        "/stop — Pause or fully unsubscribe\n"
        "/help — This message\n\n"
        "*What you'll receive:*\n"
        "🔴 HIGH — Full Gemini AI analysis, verdict & confidence score\n"
        "🟡 MODERATE — Filing details & live price info\n"
        "📈 Price alerts when a stock moves >2% within 10 min of a HIGH filing",
        parse_mode="Markdown",
    )

# ── Callback query router ─────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = str(update.effective_chat.id)
    user = update.effective_user

    # ── Subscribe wizard callbacks ────────────────────────────────
    if data == "sub_cancel":
        context.user_data.pop("sub_step", None)
        context.user_data.pop("sub_categories", None)
        context.user_data.pop("sub_watchlist", None)
        await query.edit_message_text("❌ Subscription setup cancelled.")
        return

    if data.startswith("sub_cat_") and context.user_data.get("sub_step") == "CATEGORY":
        if data == "sub_cat_ALL":
            cats = ["HIGH", "MODERATE", "ROUTINE"]
        elif data == "sub_cat_HIGH_MODERATE":
            cats = ["HIGH", "MODERATE"]
        else:
            cats = ["HIGH"]
        context.user_data["sub_categories"] = cats
        context.user_data["sub_step"] = "SYMBOLS"
        await query.edit_message_text(
            _subscribe_step2_text(cats),
            parse_mode="Markdown",
            reply_markup=_subscribe_step2_kb(),
        )
        return

    if data == "sub_sym_ALL" and context.user_data.get("sub_step") == "SYMBOLS":
        context.user_data["sub_watchlist"] = []
        context.user_data["sub_step"] = "FILING_TYPES"
        cats = context.user_data.get("sub_categories", ["HIGH"])
        await query.edit_message_text(
            _subscribe_step3_text(cats, []),
            parse_mode="Markdown",
            reply_markup=_subscribe_step3_kb(),
        )
        return

    if data.startswith("sub_ft_") and context.user_data.get("sub_step") == "FILING_TYPES":
        ft_map = {
            "sub_ft_ALL": [],
            "sub_ft_DIVIDENDS": ["dividend"],
            "sub_ft_RESULTS": ["results", "financial results"],
            "sub_ft_ACQUISITIONS": ["acquisition", "merger", "demerger", "amalgamation"],
        }
        filing_types = ft_map.get(data, [])
        categories = context.user_data.get("sub_categories", ["HIGH"])
        watchlist = context.user_data.get("sub_watchlist", [])
        save_subscriber(
            chat_id, user.username, user.first_name,
            categories=categories,
            watchlist=watchlist,
            filing_types=filing_types,
            is_active=True,
        )
        cat_str = ", ".join(categories)
        sym_str = ", ".join(watchlist) if watchlist else "All Companies"
        ft_str = ", ".join(filing_types).title() if filing_types else "All Types"
        await query.edit_message_text(
            f"✅ *Alert preferences saved!*\n\n"
            f"📊 Categories: *{cat_str}*\n"
            f"🏢 Symbols: *{sym_str}*\n"
            f"📁 Filing Types: *{ft_str}*\n\n"
            f"You'll receive personalized alerts based on these preferences.\n"
            f"Use /settings to view or /subscribe to change anytime.",
            parse_mode="Markdown",
        )
        context.user_data.pop("sub_step", None)
        context.user_data.pop("sub_categories", None)
        context.user_data.pop("sub_watchlist", None)
        return

    # ── Watchlist callbacks ───────────────────────────────────────
    if data == "wl_clear":
        save_subscriber(chat_id, watchlist=[])
        await query.edit_message_text(
            "✅ Watchlist cleared. You'll receive alerts for *all companies*.",
            parse_mode="Markdown",
        )
        return

    if data == "wl_edit":
        context.user_data["awaiting_wl"] = True
        await query.edit_message_text(
            "📝 *Edit Watchlist*\n\n"
            "Type your watchlist as space-separated NSE/BSE symbols:\n\n"
            "*Example:* `HDFC INFY TCS RELIANCE`\n\n"
            "Send /cancel to abort.",
            parse_mode="Markdown",
        )
        return

    # ── Stop callbacks ────────────────────────────────────────────
    if data == "stop_pause":
        save_subscriber(chat_id, is_active=False)
        await query.edit_message_text(
            "⏸ Alerts paused. Your settings are kept. Use /resume anytime."
        )
        return

    if data == "stop_delete":
        try:
            supabase.table("subscribers").delete().eq("chat_id", chat_id).execute()
        except Exception as e:
            print(f"Delete error: {e}")
        await query.edit_message_text(
            "🗑️ You've been fully unsubscribed. Use /start to rejoin anytime."
        )
        return

    if data == "stop_cancel":
        await query.edit_message_text("Cancelled. Your alerts are still active.")
        return

    # ── Main menu callbacks ───────────────────────────────────────
    if data == "menu_subscribe":
        context.user_data["sub_step"] = "CATEGORY"
        await query.edit_message_text(
            _subscribe_step1_text(),
            parse_mode="Markdown",
            reply_markup=_subscribe_step1_kb(),
        )
        return

    if data == "menu_watchlist":
        sub = get_subscriber(chat_id)
        wl = (sub or {}).get("watchlist") or []
        if wl:
            watch_text = "Watched: " + ", ".join(f"`{s}`" for s in wl)
        else:
            watch_text = "Receiving alerts for *all companies*."
        await query.edit_message_text(
            f"⭐ *Your Watchlist*\n\n{watch_text}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit Watchlist", callback_data="wl_edit")],
                [InlineKeyboardButton("🗑️ Clear — Watch All", callback_data="wl_clear")],
            ]),
        )
        return

    if data == "menu_settings":
        sub = get_subscriber(chat_id)
        if sub:
            await query.edit_message_text(
                _settings_text(sub),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Edit Preferences", callback_data="menu_subscribe")]
                ]),
            )
        else:
            await query.edit_message_text("Not registered. Use /start.")
        return

    if data == "menu_pause":
        save_subscriber(chat_id, is_active=False)
        await query.edit_message_text("⏸ Alerts paused. Use /resume to turn back on.")
        return

    if data == "menu_resume":
        save_subscriber(chat_id, is_active=True)
        await query.edit_message_text("▶️ Alerts resumed!")
        return

    if data == "menu_help":
        await query.edit_message_text(
            "❓ *Commands*\n\n"
            "/start — Main menu\n"
            "/subscribe — Set preferences\n"
            "/watchlist — Manage symbols\n"
            "/settings — View settings\n"
            "/pause — Pause alerts\n"
            "/resume — Resume alerts\n"
            "/stop — Unsubscribe\n"
            "/help — This message",
            parse_mode="Markdown",
        )
        return

    if data == "menu_stop":
        await query.edit_message_text(
            "🚫 *Unsubscribe*\n\nWhat would you like to do?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏸ Just Pause", callback_data="stop_pause")],
                [InlineKeyboardButton("🗑️ Full Unsubscribe", callback_data="stop_delete")],
                [InlineKeyboardButton("❌ Cancel", callback_data="stop_cancel")],
            ]),
        )
        return

# ── Text message handler (watchlist edit + subscribe symbols step) ────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # Watchlist editing
    if context.user_data.get("awaiting_wl"):
        if text.lower() in ("/cancel", "cancel"):
            context.user_data.pop("awaiting_wl", None)
            await update.message.reply_text("Cancelled.")
            return
        symbols = [s.upper() for s in text.split() if s.strip()]
        save_subscriber(str(update.effective_chat.id), watchlist=symbols)
        context.user_data.pop("awaiting_wl", None)
        await update.message.reply_text(
            f"✅ Watchlist updated: *{', '.join(symbols)}*",
            parse_mode="Markdown",
        )
        return

    # Subscribe wizard — symbols step
    if context.user_data.get("sub_step") == "SYMBOLS":
        if text.lower() in ("/cancel", "cancel"):
            context.user_data.pop("sub_step", None)
            context.user_data.pop("sub_categories", None)
            await update.message.reply_text("❌ Subscription setup cancelled.")
            return
        symbols = [s.upper() for s in text.split() if s.strip()]
        context.user_data["sub_watchlist"] = symbols
        context.user_data["sub_step"] = "FILING_TYPES"
        cats = context.user_data.get("sub_categories", ["HIGH"])
        await update.message.reply_text(
            _subscribe_step3_text(cats, symbols),
            parse_mode="Markdown",
            reply_markup=_subscribe_step3_kb(),
        )
        return

# ── Main ──────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_TOKEN not set in .env")
        return

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Telegram bot started. Polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
