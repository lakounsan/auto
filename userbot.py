"""Telegram USERBOT (your own account, Telethon) with keyword rules + Gemini.
Control from any chat by sending:  .on  .off  .ai on|off  .reset
Whitelist: .wl on|off  .allow (this chat)  .deny (this chat)
First run asks phone number + login code (run interactively once)."""
import asyncio
import logging
import os
import random

from telethon import TelegramClient, events
from telethon.sessions import StringSession

from ai_engine import (DATA_DIR, AIEngine, is_allowed, load_rules, match_keyword,
                       save_rules, set_allowed)

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
RULES = load_rules()
ai = AIEngine()
IGNORE = {int(x) for x in os.getenv("IGNORE_CHATS", "").split(",") if x.strip()}

SESSION = os.getenv("TG_SESSION")  # string session (no disk needed, e.g. on Render)
client = TelegramClient(
    StringSession(SESSION) if SESSION else str(DATA_DIR / "userbot_session"),
    int(os.environ["TG_API_ID"]),
    os.environ["TG_API_HASH"],
)


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.(on|off|reset|allow|deny|ai (on|off)|wl (on|off))$"))
async def control(event):
    cmd = event.raw_text.strip()
    if cmd == ".on":
        RULES["enabled"] = True
    elif cmd == ".off":
        RULES["enabled"] = False
    elif cmd == ".reset":
        ai.reset(event.chat_id)
    elif cmd == ".allow":
        set_allowed(RULES, event.chat_id, True)
    elif cmd == ".deny":
        set_allowed(RULES, event.chat_id, False)
    elif cmd.startswith(".wl"):
        RULES["whitelist_enabled"] = cmd.endswith("on")
    else:
        RULES["ai_enabled"] = cmd.endswith("on")
    save_rules(RULES)
    await event.edit(f"✅ {cmd} | bot={'ON' if RULES['enabled'] else 'OFF'} "
                     f"ai={'ON' if RULES['ai_enabled'] else 'OFF'} "
                     f"whitelist={'ON' if RULES['whitelist_enabled'] else 'OFF'}")


@client.on(events.NewMessage(incoming=True))
async def handler(event):
    if not RULES["enabled"] or not event.raw_text or event.chat_id in IGNORE:
        return
    if not is_allowed(RULES, event.chat_id):
        return
    sender = await event.get_sender()
    if getattr(sender, "bot", False):
        return

    if event.is_private:
        pass
    elif event.is_group:  # reply in groups only if mentioned or someone replies to me
        replied_to_me = False
        if event.is_reply:
            r = await event.get_reply_message()
            replied_to_me = bool(r and r.out)
        if not (event.message.mentioned or replied_to_me):
            return
    else:
        return  # broadcast channels: ignore

    reply = match_keyword(RULES, event.raw_text)
    async with client.action(event.chat_id, "typing"):
        await asyncio.sleep(random.uniform(1.5, 4))  # human-like delay
        if reply is None and RULES["ai_enabled"]:
            reply = await ai.reply(event.chat_id, event.raw_text)
    if reply:
        await event.reply(reply)


async def main():
    await client.start()  # asks phone/code on first run
    logging.info("Userbot running...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
