# Telegram AI Auto Reply (Bot + Userbot) — Gemini

## Local
    pip install -r requirements.txt
    cp .env.example .env     # fill values
    python bot_ai.py         # BotFather bot
    python userbot.py        # your own account (first run: phone + code)

## VPS (Ubuntu) with Docker
    git clone/upload this folder, then:
    cp .env.example .env && nano .env
    docker compose up -d --build bot
    # userbot: login once interactively, then run in background
    docker compose --profile userbot run --rm userbot     # enter phone + code, Ctrl+C
    docker compose --profile userbot up -d userbot
    docker compose logs -f

## VPS without Docker (systemd)
    python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
    # /etc/systemd/system/tgbot.service
    [Unit]
    Description=Telegram AI bot
    After=network.target
    [Service]
    WorkingDirectory=/opt/tg-ai-bot
    ExecStart=/opt/tg-ai-bot/venv/bin/python bot_ai.py
    Restart=always
    [Install]
    WantedBy=multi-user.target
    # then: systemctl enable --now tgbot

## Whitelist (reply only in chosen chats)
Bot (admin):  /wl on   then inside a chat: /allow   (or /allow -100123456789)   /deny   /wl list
Userbot:      .wl on   then inside a chat: .allow   .deny
Stored in data/rules.json ("whitelist"). When whitelist is ON, all other chats are ignored.

## Webhook mode (bot only, needs a domain pointing to your VPS, ports 80/443 open)
    # .env: WEBHOOK_URL=https://bot.yourdomain.com  WEBHOOK_SECRET=<random>  DOMAIN=bot.yourdomain.com
    docker compose --profile webhook up -d --build bot caddy
Remove WEBHOOK_URL to go back to polling. Userbot always uses MTProto (no webhook).

## GitHub + Render
    git init && git add . && git commit -m "init"      # .gitignore already excludes .env, data/, *.session
    # create a PRIVATE repo on GitHub, then:
    git remote add origin https://github.com/<you>/tg-ai-bot.git && git branch -M main && git push -u origin main
Render: New -> Blueprint -> select repo -> fill BOT_TOKEN, ADMIN_IDS, GEMINI_API_KEY -> Deploy.
The bot sets its own webhook on start (uses RENDER_EXTERNAL_URL). Test: message your bot.
Free plan: no disk -> rules.json resets on restart. Keep a fixed whitelist with env WHITELIST_IDS=123,-100456.
Userbot on Render: python make_session.py (locally) -> put TG_SESSION in Render env -> uncomment worker in render.yaml.
