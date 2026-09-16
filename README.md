# War Bunker v2

Discord bot for the WChronicles faction leaderboard.

## Included behavior
- Channel ID is preconfigured: 1549878410321461249
- WChronicles API: https://chronicles.wfitapp.xyz/api/raid/leaderboard?limit=25
- Updates every 5 minutes by default
- Shows all factions
- Highlights Electric Immortals
- Shows points, damage, attacks and walkers
- Shows points gap to the faction immediately above
- Edits one existing leaderboard message instead of spamming
- No Administrator permission required

## Railway variables

Required:
DISCORD_TOKEN = your Discord bot token

Optional:
UPDATE_INTERVAL_MINUTES = 5
LEADERBOARD_MESSAGE_ID = existing message ID (optional)

IMPORTANT: Never post your Discord token publicly or send it to anyone.

## Discord permissions

The bot only needs:
- View Channels
- Send Messages
- Embed Links
- Read Message History

No Administrator, Manage Server, Manage Channels or Manage Webhooks permission is required.

## Local test

pip install -r requirements.txt
DISCORD_TOKEN=YOUR_TOKEN python bot.py
