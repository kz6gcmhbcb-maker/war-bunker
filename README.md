# War Bunker v6 — Command Center

Universal WChronicles raid bot for all factions.

### Commands
`/setup #channel faction:<name>` — configure the automatic channel and the faction tracked on that server.
`/status` — configuration.
`/update` — manual leaderboard post.
`/disable` — disable automatic updates.
`/top5` — top 5 players.
`/top5 faction:<name>` — top 5 for a faction.
`/top10` — top 10 players, optionally filtered.
`/topfactions` — all factions.
`/raid` — overall raid status.
`/stats faction:<name>` — faction stats.
`/gap` — points gap to faction above; defaults to server's tracked faction.
`/intel` — tactical faction view; defaults to server's tracked faction.

Each Discord server can choose its own channel and tracked faction. The same bot can serve all factions and multiple servers.

Railway variables: `DISCORD_TOKEN`, `UPDATE_INTERVAL_MINUTES`.
