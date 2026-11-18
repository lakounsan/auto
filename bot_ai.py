"""Telegram BOT (BotFather) with keyword rules + Gemini AI fallback."""
import hashlib
import logging
import os

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from ai_engine import AIEngine, is_allowed, load_rules, match_keyword, save_rules, set_allowed

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
RULES = load_rules()
ai = AIEngine()


async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg, chat = update.effective_message, update.effective_chat
    if not RULES["enabled"] or not msg or not chat:
        return
    if not is_allowed(RULES, chat.id):
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    text = msg.text or msg.caption or ""
    if not text:
        return

    reply = match_keyword(RULES, text)
    if reply is None and RULES["ai_enabled"]:
        me = context.bot.username.lower()
        if chat.type == ChatType.PRIVATE:
            trigger = True
        elif chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            r = msg.reply_to_message
            trigger = f"@{me}" in text.lower() or bool(
                r and r.from_user and r.from_user.id == context.bot.id
            )
        else:
            trigger = False  # channels: keywords only
        if trigger:
            clean = text.replace(f"@{context.bot.username}", "").strip()
            await context.bot.send_chat_action(chat.id, "typing")
            reply = await ai.reply(chat.id, clean)

    if reply:
        await msg.reply_text(reply)


def admin_only(fn):
    async def w(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user and update.effective_user.id in ADMIN_IDS:
            return await fn(update, context)
        await update.effective_message.reply_text("⛔ Admin only.")
    return w


def _arg(update: Update) -> str:
    return update.message.text.partition(" ")[2].strip()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Commands (admin)\n/on /off — បើក/បិទ bot\n/ai on|off — បើក/បិទ AI\n"
        "/prompt text — កំណត់ system prompt\n/reset — លុប memory chat នេះ\n"
        "/add keyword | reply\n/del keyword\n/list\n"
        "/wl on|off|list — whitelist\n/allow [chat_id] — អនុញ្ញាត chat នេះ\n/deny [chat_id]"
    )


@admin_only
async def cmd_on(u, c):
    RULES["enabled"] = True; save_rules(RULES); await u.message.reply_text("✅ ON")


@admin_only
async def cmd_off(u, c):
    RULES["enabled"] = False; save_rules(RULES); await u.message.reply_text("⏸ OFF")


@admin_only
async def cmd_ai(u, c):
    RULES["ai_enabled"] = _arg(u).lower() != "off"
    save_rules(RULES)
    await u.message.reply_text(f"AI: {'ON' if RULES['ai_enabled'] else 'OFF'}")


@admin_only
async def cmd_prompt(u, c):
    if not _arg(u):
        return await u.message.reply_text(ai.system_prompt)
    ai.system_prompt = _arg(u)
    await u.message.reply_text("✅ Prompt updated (resets on restart; set SYSTEM_PROMPT in .env to keep)")


@admin_only
async def cmd_reset(u, c):
    ai.reset(u.effective_chat.id); await u.message.reply_text("🧹 Done")


@admin_only
async def cmd_list(u, c):
    await u.message.reply_text("\n".join(f"• {k} → {v}" for k, v in RULES["keywords"].items()) or "(empty)")


@admin_only
async def cmd_add(u, c):
    if "|" not in _arg(u):
        return await u.message.reply_text("Usage: /add keyword | reply")
    k, v = [p.strip() for p in _arg(u).split("|", 1)]
    RULES["keywords"][k] = v; save_rules(RULES)
    await u.message.reply_text(f"✅ {k}")


@admin_only
async def cmd_del(u, c):
    if RULES["keywords"].pop(_arg(u), None) is None:
        return await u.message.reply_text("Not found")
    save_rules(RULES); await u.message.reply_text("🗑 Deleted")


def _chat_arg(u) -> int:
    a = _arg(u)
    return int(a) if a.lstrip("-").isdigit() else u.effective_chat.id


@admin_only
async def cmd_allow(u, c):
    cid = _chat_arg(u); set_allowed(RULES, cid, True)
    await u.message.reply_text(f"✅ Allowed: {cid}")


@admin_only
async def cmd_deny(u, c):
    cid = _chat_arg(u); set_allowed(RULES, cid, False)
    await u.message.reply_text(f"🚫 Removed: {cid}")


@admin_only
async def cmd_wl(u, c):
    a = _arg(u).lower()
    if a in ("on", "off"):
        RULES["whitelist_enabled"] = a == "on"; save_rules(RULES)
    await u.message.reply_text(
        f"Whitelist: {'ON' if RULES['whitelist_enabled'] else 'OFF'}\n"
        + ("\n".join(map(str, RULES["whitelist"])) or "(empty)"))


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    for name, fn in [("start", start), ("on", cmd_on), ("off", cmd_off), ("ai", cmd_ai),
                     ("prompt", cmd_prompt), ("reset", cmd_reset), ("list", cmd_list),
                     ("add", cmd_add), ("del", cmd_del), ("allow", cmd_allow),
                     ("deny", cmd_deny), ("wl", cmd_wl)]:
        app.add_handler(CommandHandler(name, fn))
    app.add_handler(MessageHandler(
        (filters.ChatType.PRIVATE | filters.ChatType.GROUPS) & ~filters.COMMAND, auto_reply))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, auto_reply))
    # WEBHOOK_URL (own domain) or RENDER_EXTERNAL_URL (set automatically by Render)
    url = (os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if url:
        # hash it so any generated value is valid for Telegram (A-Z a-z 0-9 _ -)
        secret = hashlib.sha256(os.environ["WEBHOOK_SECRET"].encode()).hexdigest()[:48]
        path = f"hook-{secret}"
        logging.info("Webhook mode: %s/%s", url, path)
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.getenv("PORT") or os.getenv("WEBHOOK_PORT", "8443")),
            url_path=path,
            webhook_url=f"{url}/{path}",
            secret_token=secret,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
    else:
        logging.info("Polling mode")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
