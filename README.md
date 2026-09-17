# War Bunker v6.1 — Command Center

Universal WChronicles Discord raid bot.

## Setup
`/setup #channel faction:<name>` configures BOTH the automatic posting channel and the faction tracked by that server. The faction field has live autocomplete.

Each Discord server can select a different channel and faction.

## Commands
`/top5` — Top 5 players.
`/top5 faction:<name>` — Top 5 for a faction.
`/top10` — Top 10 players, optionally filtered.
`/topfactions` — all factions.
`/raid` — overall raid status.
`/stats faction:<name>` — faction stats.
`/gap` — gap to faction above.
`/intel` — tactical view.
`/status` — server configuration.
`/update` — manual update.
`/disable` — disable automatic updates.

## Automation
The bot posts a NEW leaderboard message every `UPDATE_INTERVAL_MINUTES`. If a server has a tracked faction, it also watches that faction for rank changes and major Points changes.

## Railway variables
`DISCORD_TOKEN` and `UPDATE_INTERVAL_MINUTES`.
