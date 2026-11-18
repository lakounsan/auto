"""Run LOCALLY once to get TG_SESSION for hosting without a disk (Render).
   python make_session.py   -> enter phone + code -> copy the printed TG_SESSION.
   Treat it like a password: never commit it to git."""
import os

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.sessions import StringSession

load_dotenv()
with TelegramClient(StringSession(), int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"]) as c:
    print("\nTG_SESSION=" + c.session.save())
