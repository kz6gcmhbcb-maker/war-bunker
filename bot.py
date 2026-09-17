import os, json
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

API_URL = "https://chronicles.wfitapp.xyz/api/raid/leaderboard?limit=25"
TOKEN = os.getenv("DISCORD_TOKEN")
POLL_SECONDS = max(20, int(os.getenv("POLL_SECONDS", "60")))
DATA_FILE = Path("config.json")

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
client = commands.Bot(command_prefix="!", intents=intents)
tree = client.tree

configs = {}
previous_state = None


def load_data():
    global configs, previous_state
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            configs = d.get("configs", {})
            previous_state = d.get("previous_state")
        except Exception:
            configs, previous_state = {}, None


def save_data():
    DATA_FILE.write_text(
        json.dumps({"configs": configs, "previous_state": previous_state}, indent=2),
        encoding="utf-8",
    )


def iv(x):
    try:
        return int(x or 0)
    except Exception:
        return 0


def fmt(x):
    return f"{iv(x):,}"


def pname(p):
    return str(p.get("displayName") or p.get("username") or p.get("uid") or "Unknown")


def pfaction(p):
    return str(p.get("factionName") or "Unknown")


def ppoints(p):
    return iv(p.get("factionPoints", p.get("points")))


def pdamage(p):
    return iv(p.get("totalDamage", p.get("damage")))


def pattacks(p):
    return iv(p.get("attacks"))


async def fetch():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://chronicles.wfitapp.xyz/",
    }
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get(API_URL, headers=headers) as r:
            r.raise_for_status()
            return await r.json()


def factions(data):
    return sorted(
        data.get("factions", []),
        key=lambda f: iv(f.get("rank")) or 999999,
    )


def get_faction(data, name):
    q = str(name or "").strip().lower()
    return next(
        (f for f in data.get("factions", []) if str(f.get("factionName", "")).strip().lower() == q),
        None,
    )


def players(data, faction=None):
    rows = list(data.get("entries", []))
    if faction:
        q = faction.strip().lower()
        rows = [p for p in rows if pfaction(p).strip().lower() == q]
    return sorted(
        rows,
        key=lambda p: (ppoints(p), pdamage(p), pattacks(p)),
        reverse=True,
    )


def state(data):
    fs = []
    for f in factions(data):
        fs.append((
            str(f.get("factionName", "")),
            iv(f.get("rank")),
            iv(f.get("points")),
            iv(f.get("damage")),
            iv(f.get("attacks")),
            iv(f.get("players")),
            iv(f.get("wins")),
        ))
    ps = []
    for p in sorted(data.get("entries", []), key=lambda x: str(x.get("uid") or pname(x))):
        ps.append((
            str(p.get("uid") or pname(p)),
            pfaction(p),
            ppoints(p),
            pdamage(p),
            pattacks(p),
        ))
    return {"status": str(data.get("status", "")), "factions": fs, "players": ps}


def changes(old, new):
    if not old:
        return ["Raid baseline established"]

    events = []
    of = {x[0]: x for x in old.get("factions", [])}
    nf = {x[0]: x for x in new.get("factions", [])}

    for name, n in nf.items():
        o = of.get(name)
        if not o:
            events.append(f"**{name}** appeared in the leaderboard")
            continue
        if n[1] != o[1]:
            arrow = "↑" if n[1] < o[1] else "↓"
            events.append(f"**{name}** moved {arrow} #{o[1]} → #{n[1]}")
        if n[4] > o[4]:
            events.append(f"**{name}** made **{n[4]-o[4]}** new attack(s)")

    op = {x[0]: x for x in old.get("players", [])}
    np = {x[0]: x for x in new.get("players", [])}

    old_order = [x[0] for x in sorted(old.get("players", []), key=lambda x:(x[2],x[3],x[4]), reverse=True)]
    new_order = [x[0] for x in sorted(new.get("players", []), key=lambda x:(x[2],x[3],x[4]), reverse=True)]
    orank = {u:i+1 for i,u in enumerate(old_order)}
    nrank = {u:i+1 for i,u in enumerate(new_order)}

    for uid, n in np.items():
        o = op.get(uid)
        if not o:
            continue
        if n[4] > o[4]:
            events.append(f"**{uid}** made **{n[4]-o[4]}** new attack(s)")
        if uid in orank and uid in nrank and orank[uid] != nrank[uid]:
            arrow = "↑" if nrank[uid] < orank[uid] else "↓"
            events.append(f"Player **{uid}** moved {arrow} #{orank[uid]} → #{nrank[uid]}")

    # If points/damage changed without an explicit rank/attack event, still notify.
    if not events:
        for name, n in nf.items():
            o = of.get(name)
            if o and (n[2] != o[2] or n[3] != o[3]):
                events.append(f"**{name}** leaderboard totals changed")
                break

    return list(dict.fromkeys(events))[:15]


def activity_embed(data, events, tracked=None):
    e = discord.Embed(
        title="⚡ RAID ACTIVITY",
        description="\n".join("• " + x for x in events),
        color=0x42F5C5,
    )
    if tracked:
        f = get_faction(data, tracked)
        if f:
            e.add_field(
                name=f"TRACKED FACTION — {tracked}",
                value=(
                    f"Rank: **#{iv(f.get('rank'))}**\n"
                    f"Points: **{fmt(f.get('points'))}**\n"
                    f"Damage: **{fmt(f.get('damage'))}**\n"
                    f"Attacks: **{fmt(f.get('attacks'))}**"
                ),
                inline=False,
            )
    e.set_footer(text="THE CURRENT FINDS ITS OWN. • EVENT-DRIVEN")
    return e


def factions_embed(data):
    e = discord.Embed(title="⚡ FACTION LEADERBOARD", color=0x42F5C5)
    for i, f in enumerate(factions(data), 1):
        rank = iv(f.get("rank")) or i
        medal = ["🥇","🥈","🥉"][i-1] if i <= 3 else f"#{rank}"
        e.add_field(
            name=f"{medal} {f.get('factionName','Unknown')}",
            value=(
                f"Points: **{fmt(f.get('points'))}** • "
                f"Damage: **{fmt(f.get('damage'))}**\n"
                f"Attacks: **{fmt(f.get('attacks'))}** • "
                f"Walkers: **{fmt(f.get('players'))}** • "
                f"Wins: **{fmt(f.get('wins'))}**"
            ),
            inline=False,
        )
    e.set_footer(text="THE CURRENT FINDS ITS OWN. • LIVE DATA")
    return e


def top_embed(data, count=5, faction=None):
    rows = players(data, faction)[:count]
    title = f"⚡ TOP {count} PLAYERS"
    if faction:
        title += f" — {faction.upper()}"
    e = discord.Embed(title=title, color=0x42F5C5)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    for i, p in enumerate(rows, 1):
        e.add_field(
            name=f"{medals[i-1] if i <= len(medals) else '#'+str(i)} {pname(p)}",
            value=(
                f"Points: **{fmt(ppoints(p))}** • Damage: **{fmt(pdamage(p))}** • "
                f"Attacks: **{fmt(pattacks(p))}**"
                + (f" • Faction: **{pfaction(p)}**" if not faction else "")
            ),
            inline=False,
        )
    if not rows:
        e.description = "No players found."
    e.set_footer(text="THE CURRENT FINDS ITS OWN. • LIVE DATA")
    return e


def raid_embed(data):
    fs = data.get("factions", [])
    e = discord.Embed(
        title=f"⚡ {str(data.get('name') or 'RAID').upper()}",
        description=f"Status: **{data.get('status','Unknown')}**",
        color=0x42F5C5,
    )
    e.add_field(name="FACTIONS", value=fmt(len(fs)), inline=True)
    e.add_field(name="TOTAL POINTS", value=fmt(sum(iv(f.get("points")) for f in fs)), inline=True)
    e.add_field(name="TOTAL DAMAGE", value=fmt(sum(iv(f.get("damage")) for f in fs)), inline=True)
    e.add_field(name="TOTAL ATTACKS", value=fmt(sum(iv(f.get("attacks")) for f in fs)), inline=True)
    return e


def stats_embed(data, faction):
    f = get_faction(data, faction)
    e = discord.Embed(title=f"⚡ {faction.upper()} — STATS", color=0x42F5C5)
    if not f:
        e.description = "Faction not found."
        return e
    e.description = f"Rank **#{iv(f.get('rank'))}**"
    for n,k in [("POINTS","points"),("DAMAGE","damage"),("ATTACKS","attacks"),("WALKERS","players"),("WINS","wins")]:
        e.add_field(name=n, value=fmt(f.get(k)), inline=True)
    return e


def gap_embed(data, faction):
    fs = factions(data)
    f = get_faction(data, faction)
    e = discord.Embed(title=f"⚡ {faction.upper()} — GAP", color=0x42F5C5)
    if not f:
        e.description = "Faction not found."
        return e
    idx = next((i for i,x in enumerate(fs) if str(x.get("factionName")).lower() == str(f.get("factionName")).lower()), None)
    if idx == 0:
        e.description = "Rank **#1** — no faction ahead."
        return e
    if idx is None:
        e.description = "Rank data unavailable."
        return e
    a = fs[idx-1]
    e.description = (
        f"Current: **#{iv(f.get('rank'))} {f.get('factionName')}**\n"
        f"Next: **{a.get('factionName')}**\n"
        f"Points gap: **{fmt(max(0,iv(a.get('points'))-iv(f.get('points'))))}**"
    )
    return e


def intel_embed(data, faction):
    f = get_faction(data, faction)
    e = discord.Embed(title=f"⚡ {faction.upper()} — WAR INTEL", color=0x42F5C5)
    if not f:
        e.description = "Faction not found."
        return e
    e.description = f"Rank **#{iv(f.get('rank'))}**"
    fs = factions(data)
    idx = next((i for i,x in enumerate(fs) if x.get("factionName")==f.get("factionName")), None)
    if idx and idx > 0:
        a = fs[idx-1]
        e.add_field(
            name="NEXT FACTION",
            value=f"**{a.get('factionName')}**\nPoints gap: **{fmt(max(0,iv(a.get('points'))-iv(f.get('points'))))}**",
            inline=False,
        )
    rows = players(data, faction)[:3]
    e.add_field(
        name="TOP 3",
        value="\n".join(f"{i}. **{pname(p)}** — {fmt(ppoints(p))} Points" for i,p in enumerate(rows,1)) or "No player data.",
        inline=False,
    )
    return e


async def faction_autocomplete(interaction: discord.Interaction, current: str):
    try:
        data = await fetch()
        names = [str(f.get("factionName","")).strip() for f in data.get("factions",[])]
    except Exception:
        names = []
    q = current.lower().strip()
    return [app_commands.Choice(name=n,value=n) for n in names if n and (not q or q in n.lower())][:25]


def configured_faction(gid, faction=None):
    return faction or configs.get(str(gid),{}).get("faction")


@tree.command(name="setup", description="Configure the automatic activity channel and tracked faction.")
@app_commands.describe(channel="Automatic activity channel.", faction="Faction to track on this server.")
@app_commands.autocomplete(faction=faction_autocomplete)
@app_commands.checks.has_permissions(manage_guild=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel, faction: str):
    configs[str(interaction.guild_id)] = {
        "channel_id": str(channel.id),
        "faction": faction,
        "alerts": True,
    }
    save_data()
    await interaction.response.send_message(
        f"⚡ Setup complete.\nChannel: {channel.mention}\nFaction: **{faction}**\n"
        f"Mode: **event-driven** — no message unless the raid changes.",
        ephemeral=True,
    )


@tree.command(name="status", description="Show War Bunker configuration.")
async def status(interaction: discord.Interaction):
    c = configs.get(str(interaction.guild_id))
    if not c:
        await interaction.response.send_message("Not configured. Use `/setup`.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(iv(c.get("channel_id")))
    await interaction.response.send_message(
        f"Channel: {ch.mention if ch else 'not found'}\n"
        f"Faction: **{c.get('faction','not set')}**\n"
        f"Alerts: **{'ON' if c.get('alerts',True) else 'OFF'}**\n"
        f"Mode: **event-driven**",
        ephemeral=True,
    )


@tree.command(name="update", description="Post the full faction leaderboard now.")
@app_commands.checks.has_permissions(manage_guild=True)
async def update_cmd(interaction: discord.Interaction):
    c = configs.get(str(interaction.guild_id))
    if not c:
        await interaction.response.send_message("Use `/setup` first.", ephemeral=True)
        return
    ch = interaction.guild.get_channel(iv(c.get("channel_id")))
    if not ch:
        await interaction.response.send_message("Configured channel not found.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await ch.send(embed=factions_embed(await fetch()))
    await interaction.followup.send("⚡ Manual update posted.", ephemeral=True)


@tree.command(name="disable", description="Disable automatic event posts.")
@app_commands.checks.has_permissions(manage_guild=True)
async def disable(interaction: discord.Interaction):
    c = configs.get(str(interaction.guild_id))
    if c:
        c["alerts"] = False
        save_data()
    await interaction.response.send_message("⚡ Automatic event posts disabled.", ephemeral=True)


@tree.command(name="top5", description="Show top 5 players, optionally filtered by faction.")
@app_commands.describe(faction="Optional faction filter.")
@app_commands.autocomplete(faction=faction_autocomplete)
async def top5(interaction: discord.Interaction, faction: Optional[str]=None):
    await interaction.response.defer()
    await interaction.followup.send(embed=top_embed(await fetch(),5,faction))


@tree.command(name="top10", description="Show top 10 players, optionally filtered by faction.")
@app_commands.describe(faction="Optional faction filter.")
@app_commands.autocomplete(faction=faction_autocomplete)
async def top10(interaction: discord.Interaction, faction: Optional[str]=None):
    await interaction.response.defer()
    await interaction.followup.send(embed=top_embed(await fetch(),10,faction))


@tree.command(name="topfactions", description="Show all factions ranked.")
async def topfactions(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send(embed=factions_embed(await fetch()))


@tree.command(name="raid", description="Show overall raid status.")
async def raid(interaction: discord.Interaction):
    await interaction.response.defer()
    await interaction.followup.send(embed=raid_embed(await fetch()))


@tree.command(name="stats", description="Show stats for a faction.")
@app_commands.describe(faction="Faction to inspect.")
@app_commands.autocomplete(faction=faction_autocomplete)
async def stats(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()
    await interaction.followup.send(embed=stats_embed(await fetch(),faction))


@tree.command(name="gap", description="Show a faction's gap to the faction above.")
@app_commands.describe(faction="Optional; defaults to server faction.")
@app_commands.autocomplete(faction=faction_autocomplete)
async def gap(interaction: discord.Interaction, faction: Optional[str]=None):
    faction=configured_faction(interaction.guild_id,faction)
    if not faction:
        await interaction.response.send_message("Choose a faction or use `/setup`.",ephemeral=True); return
    await interaction.response.defer()
    await interaction.followup.send(embed=gap_embed(await fetch(),faction))


@tree.command(name="intel", description="Show tactical intel for a faction.")
@app_commands.describe(faction="Optional; defaults to server faction.")
@app_commands.autocomplete(faction=faction_autocomplete)
async def intel(interaction: discord.Interaction, faction: Optional[str]=None):
    faction=configured_faction(interaction.guild_id,faction)
    if not faction:
        await interaction.response.send_message("Choose a faction or use `/setup`.",ephemeral=True); return
    await interaction.response.defer()
    await interaction.followup.send(embed=intel_embed(await fetch(),faction))


@tasks.loop(seconds=POLL_SECONDS)
async def monitor():
    global previous_state
    try:
        data = await fetch()
        current = state(data)
        if previous_state is None:
            previous_state = current
            save_data()
            print("Baseline stored; no automatic message.")
            return
        if current == previous_state:
            return

        events = changes(previous_state,current)
        previous_state = current
        save_data()

        if not events:
            return

        for gid,c in list(configs.items()):
            if not c.get("alerts",True):
                continue
            guild=client.get_guild(iv(gid))
            if not guild:
                continue
            channel=guild.get_channel(iv(c.get("channel_id")))
            if not channel:
                continue
            try:
                await channel.send(embed=activity_embed(data,events,c.get("faction")))
            except Exception as ex:
                print("Post error:",gid,type(ex).__name__,ex)

        print("Raid change detected; event message posted.")
    except Exception as ex:
        print("Monitor error:",type(ex).__name__,ex)


@monitor.before_loop
async def before_monitor():
    await client.wait_until_ready()


async def sync_commands():
    # Register one guild copy, then remove the legacy global copies.
    for guild in client.guilds:
        try:
            tree.copy_global_to(guild=guild)
            synced=await tree.sync(guild=guild)
            print(f"Guild sync: {guild.name} -> {len(synced)} commands")
        except Exception as ex:
            print("Guild sync error:",guild.id,type(ex).__name__,ex)
    try:
        tree.clear_commands(guild=None)
        await tree.sync()
        print("Legacy global commands cleared.")
    except Exception as ex:
        print("Global cleanup error:",type(ex).__name__,ex)


@client.event
async def on_ready():
    load_data()
    print(f"Logged in as {client.user}. Servers: {len(client.guilds)}")
    await sync_commands()
    if not monitor.is_running():
        monitor.start()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")

client.run(TOKEN)
