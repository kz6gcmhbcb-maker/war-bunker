# War Bunker v7 — EVENT DRIVEN

The bot polls WChronicles in the background but DOES NOT post every minute.
It posts only when the raid leaderboard changes.

Detected:
- new attacks
- faction rank changes
- player rank changes
- meaningful point/damage changes

Each Discord server can configure its own channel and faction with:
`/setup channel:#channel faction:<faction>`

Commands:
`/setup`, `/status`, `/update`, `/disable`, `/top5`, `/top10`,
`/topfactions`, `/raid`, `/stats`, `/gap`, `/intel`.

The first poll after startup creates a baseline and intentionally sends no
automatic message.

Duplicate command fix:
commands are synced to guilds and legacy global commands are cleared.

Railway:
- DISCORD_TOKEN = existing token
- POLL_SECONDS = optional, default 60

Do not change/share the bot token.
