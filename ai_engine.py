"""Shared: Gemini engine + keyword rules (used by bot_ai.py and userbot.py)."""
import json
import logging
import os
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
log = logging.getLogger("ai")

DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
RULES_FILE = DATA_DIR / "rules.json"

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
DEFAULT_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a friendly assistant replying on Telegram. "
    "Reply in the same language as the user. Keep answers short.",
)

DEFAULT_RULES = {
    "enabled": True,
    "ai_enabled": True,
    "whitelist_enabled": False,   # True = reply ONLY in chats listed in "whitelist"
    "whitelist": [],              # chat IDs (users, groups, channels)
    "keywords": {"តម្លៃ": "សូមទាក់ទង admin សម្រាប់តម្លៃ។"},
}


def load_rules() -> dict:
    rules = json.loads(json.dumps(DEFAULT_RULES))
    if RULES_FILE.exists():
        rules.update(json.loads(RULES_FILE.read_text(encoding="utf-8")))
    env_wl = os.getenv("WHITELIST_IDS", "").strip()   # e.g. 123,-100456  (survives restarts)
    if env_wl:
        rules["whitelist_enabled"] = True
        rules["whitelist"] = sorted({int(x) for x in env_wl.split(",") if x.strip()})
    save_rules(rules)
    return rules


def is_allowed(rules: dict, chat_id: int) -> bool:
    return (not rules["whitelist_enabled"]) or chat_id in rules["whitelist"]


def set_allowed(rules: dict, chat_id: int, allow: bool) -> None:
    wl = set(rules["whitelist"])
    (wl.add if allow else wl.discard)(chat_id)
    rules["whitelist"] = sorted(wl)
    save_rules(rules)


def save_rules(rules: dict) -> None:
    RULES_FILE.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def match_keyword(rules: dict, text: str):
    t = (text or "").lower()
    for k, v in rules["keywords"].items():
        if k.lower() in t:
            return v
    return None


class AIEngine:
    def __init__(self, max_turns: int = 10):
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.system_prompt = DEFAULT_PROMPT
        self.history = defaultdict(lambda: deque(maxlen=max_turns * 2))

    async def reply(self, chat_id, text: str):
        h = self.history[chat_id]
        h.append(types.Content(role="user", parts=[types.Part(text=text)]))
        try:
            r = await self.client.aio.models.generate_content(
                model=MODEL,
                contents=list(h),
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    max_output_tokens=800,
                ),
            )
            out = (r.text or "").strip()
        except Exception as e:
            log.error("Gemini error: %s", e)
            h.pop()
            return None
        if out:
            h.append(types.Content(role="model", parts=[types.Part(text=out)]))
        return out or None

    def reset(self, chat_id):
        self.history.pop(chat_id, None)
