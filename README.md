# War Bunker v5

Discord bot for the WChronicles raid leaderboard.

## Commands
- `/setup #channel` — configure the leaderboard channel.
- `/status` — show configuration.
- `/update` — post the current faction leaderboard immediately.
- `/disable` — disable automatic updates.
- `/top5` — top 5 individual players across all factions.
- `/top5 faction:<name>` — top 5 individual players from one selected faction.
- `/topfactions` — show ALL factions (not Top 5).

The faction selector for `/top5` uses autocomplete and reads faction names from the live WChronicles API.

Player Top 5 is sorted by Points, then Damage, then Attacks.

The bot posts a NEW leaderboard message every configured interval; it does not edit old leaderboard messages.

## Railway variables
- `DISCORD_TOKEN` — your Discord bot token
- `UPDATE_INTERVAL_MINUTES` — e.g. `5` or `10`
