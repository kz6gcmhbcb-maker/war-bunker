import os
import asyncio
import aiohttp
import discord
from discord.ext import tasks

CHANNEL_ID = 1549878410321461249
API_URL = "https://chronicles.wfitapp.xyz/api/raid/leaderboard?limit=25"
UPDATE_INTERVAL_MINUTES = int(os.getenv("UPDATE_INTERVAL_MINUTES", "5"))
MESSAGE_ID = int(os.getenv("LEADERBOARD_MESSAGE_ID", "0"))

INTENTS = discord.Intents.default()
client = discord.Client(intents=INTENTS)
leaderboard_message = None


def find_electric_immortals(factions):
    for faction in factions:
        name = str(faction.get("factionName", "")).strip().lower()
        faction_id = str(faction.get("factionId", "")).strip().lower()
        if name == "electric immortals" or faction_id in {
            "electricimmortals", "electric-immortals", "electric_immortals"
        }:
            return faction
    return None


def fmt_num(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def get_gap(factions, current):
    try:
        rank = int(current.get("rank", 0))
        if rank <= 1:
            return "—"
        above = next((f for f in factions if int(f.get("rank", 0)) == rank - 1), None)
        if not above:
            return "—"
        return fmt_num(max(0, int(above.get("points", 0)) - int(current.get("points", 0))))
    except (TypeError, ValueError):
        return "—"


async def fetch_data():
    headers = {
        "Accept": "application/json",
        "User-Agent": "War-Bunker-Discord-Bot/2.0"
    }
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(API_URL) as response:
            response.raise_for_status()
            return await response.json()


def make_embed(data):
    factions = data.get("factions") or []
    raid_name = data.get("name", "WChronicles Raid")
    status = data.get("status", "Unknown")
    ei = find_electric_immortals(factions)

    embed = discord.Embed(
        title="⚡ FACTION WAR — LEADERBOARD",
        description="**ELECTRIC IMMORTALS**\nLive standings from WChronicles.",
        color=0x42F5C5
    )

    if ei:
        rank = ei.get("rank", "?")
        points = ei.get("points", 0)
        damage = ei.get("damage", 0)
        attacks = ei.get("attacks", 0)
        players = ei.get("players", 0)
        gap = get_gap(factions, ei)

        embed.add_field(
            name=f"⚡ ELECTRIC IMMORTALS — #{rank}",
            value=(
                f"**Points:** {fmt_num(points)}\n"
                f"**Damage:** {fmt_num(damage)}\n"
                f"**Attacks:** {fmt_num(attacks)}\n"
                f"**Walkers:** {fmt_num(players)}\n"
                f"**Gap to next rank:** {gap}"
            ),
            inline=False
        )
    else:
        embed.add_field(
            name="⚡ ELECTRIC IMMORTALS",
            value="Faction not found in the current API response.",
            inline=False
        )

    lines = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for faction in sorted(factions, key=lambda x: int(x.get("rank", 999))):
        try:
            rank = int(faction.get("rank", 999))
        except (TypeError, ValueError):
            rank = 999
        prefix = medals.get(rank, f"**{rank}.**")
        name = str(faction.get("factionName", "Unknown"))
        points = fmt_num(faction.get("points", 0))
        damage = fmt_num(faction.get("damage", 0))
        attacks = fmt_num(faction.get("attacks", 0))
        players = fmt_num(faction.get("players", 0))
        if name.lower() == "electric immortals":
            name = f"⚡ **{name}**"
        lines.append(
            f"{prefix} {name} — **{points} pts** • {damage} dmg • {attacks} atk • {players} walkers"
        )

    if lines:
        # Discord embed field value limit is 1024 characters.
        chunk = ""
        chunks = []
        for line in lines:
            if len(chunk) + len(line) + 1 > 1000:
                chunks.append(chunk)
                chunk = ""
            chunk += line + "\n"
        if chunk:
            chunks.append(chunk)
        for i, value in enumerate(chunks[:3], start=1):
            embed.add_field(
                name="ALL FACTIONS" if i == 1 else "CONTINUED",
                value=value,
                inline=False
            )

    embed.add_field(
        name="RAID",
        value=f"**{raid_name}**\nStatus: **{status}**",
        inline=False
    )
    embed.set_footer(text="THE CURRENT FINDS ITS OWN.  •  AUTO-UPDATED")
    return embed


async def get_or_create_message(channel):
    global leaderboard_message

    if MESSAGE_ID:
        try:
            return await channel.fetch_message(MESSAGE_ID)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass

    try:
        async for message in channel.history(limit=50):
            if message.author.id == client.user.id and message.embeds:
                if message.embeds[0].title == "⚡ FACTION WAR — LEADERBOARD":
                    return message
    except discord.HTTPException:
        pass

    return await channel.send(embed=discord.Embed(
        title="⚡ FACTION WAR — LEADERBOARD",
        description="Starting..."
    ))


@tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)
async def update_leaderboard():
    global leaderboard_message
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(CHANNEL_ID)
        except discord.HTTPException as exc:
            print(f"Could not access channel {CHANNEL_ID}: {exc}")
            return

    try:
        data = await fetch_data()
        embed = make_embed(data)
        if leaderboard_message is None:
            leaderboard_message = await get_or_create_message(channel)
        await leaderboard_message.edit(embed=embed)
        print("Leaderboard updated.")
        print(f"Message ID: {leaderboard_message.id}")
    except Exception as exc:
        print(f"Update failed: {type(exc).__name__}: {exc}")


@update_leaderboard.before_loop
async def before_update():
    await client.wait_until_ready()


@client.event
async def on_ready():
    global leaderboard_message
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(CHANNEL_ID)
        except discord.HTTPException as exc:
            print(f"Could not access channel {CHANNEL_ID}: {exc}")
            return

    try:
        leaderboard_message = await get_or_create_message(channel)
        if not update_leaderboard.is_running():
            update_leaderboard.start()
    except Exception as exc:
        print(f"Startup error: {type(exc).__name__}: {exc}")


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("DISCORD_TOKEN environment variable is missing.")

client.run(token)
