import os, json, asyncio, aiohttp, discord
from discord.ext import tasks
from discord import app_commands

API_URL="https://chronicles.wfitapp.xyz/api/raid/leaderboard?limit=25"
INTERVAL=int(os.getenv("UPDATE_INTERVAL_MINUTES","5"))
DATA_FILE="guild_config.json"

intents=discord.Intents.default()
client=discord.Client(intents=intents)
tree=app_commands.CommandTree(client)
configs={}

def load():
    global configs
    try:
        with open(DATA_FILE,encoding="utf-8") as f: configs=json.load(f)
    except (FileNotFoundError,json.JSONDecodeError): configs={}

def save():
    with open(DATA_FILE+".tmp","w",encoding="utf-8") as f: json.dump(configs,f,indent=2)
    os.replace(DATA_FILE+".tmp",DATA_FILE)

def num(v):
    try:return f"{int(v):,}"
    except:return str(v)

def ei(factions):
    for f in factions:
        if str(f.get("factionName","")).strip().lower()=="electric immortals":
            return f

def gap(fs,cur):
    try:
        r=int(cur["rank"])
        if r<=1:return "—"
        a=next((f for f in fs if int(f.get("rank",0))==r-1),None)
        return num(max(0,int(a["points"])-int(cur["points"]))) if a else "—"
    except:return "—"

def embed(data):
    fs=data.get("factions") or []; e=ei(fs)
    x=discord.Embed(title="⚡ FACTION WAR — LEADERBOARD",
                    description="**ELECTRIC IMMORTALS**\nLive standings from WChronicles.",
                    color=0x42F5C5)
    if e:
        x.add_field(name=f"⚡ ELECTRIC IMMORTALS — #{e.get('rank','?')}",
          value=f"**Points:** {num(e.get('points',0))}\n**Damage:** {num(e.get('damage',0))}\n**Attacks:** {num(e.get('attacks',0))}\n**Walkers:** {num(e.get('players',0))}\n**Gap to next rank:** {gap(fs,e)}",inline=False)
    lines=[]
    for f in sorted(fs,key=lambda z:int(z.get("rank",999)) if str(z.get("rank","")).isdigit() else 999):
        r=f.get("rank","?"); n=str(f.get("factionName","Unknown"))
        if n.lower()=="electric immortals": n="⚡ **"+n+"**"
        lines.append(f"**{r}.** {n} — **{num(f.get('points',0))} pts** • {num(f.get('damage',0))} dmg • {num(f.get('attacks',0))} atk • {num(f.get('players',0))} walkers")
    chunk=""
    for line in lines:
        if len(chunk)+len(line)+1>1000:
            x.add_field(name="ALL FACTIONS" if not x.fields else "CONTINUED",value=chunk,inline=False); chunk=""
        chunk+=line+"\n"
    if chunk:x.add_field(name="ALL FACTIONS" if not x.fields else "CONTINUED",value=chunk,inline=False)
    x.add_field(name="RAID",value=f"**{data.get('name','WChronicles Raid')}**\nStatus: **{data.get('status','Unknown')}**",inline=False)
    x.set_footer(text="THE CURRENT FINDS ITS OWN.  •  AUTO-UPDATED")
    return x

async def fetch():
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),headers={"Accept":"application/json","User-Agent":"War-Bunker-Discord-Bot/3.0"}) as s:
        async with s.get(API_URL) as r:r.raise_for_status();return await r.json()

async def update(gid,cfg):
    g=client.get_guild(int(gid))
    if not g:return
    ch=g.get_channel(int(cfg["channel_id"]))
    if not ch:return
    try:
        data=await fetch()
        em=embed(data)
        msg=await ch.send(embed=em)
        cfg["last_message_id"]=str(msg.id)
        save()
        print(f"Posted new leaderboard message in guild {gid}: {msg.id}")
    except Exception as ex:
        print("Update error:",type(ex).__name__,ex)


def faction_name_matches(value, faction):
    if not value or not faction:
        return False
    a = str(value).strip().lower()
    b = str(faction).strip().lower()
    return a == b or a.replace("-", " ") == b.replace("-", " ")


def faction_choices_from_data(data):
    out = []
    seen = set()
    for f in (data.get("factions") or []):
        name = str(f.get("factionName", "")).strip()
        if name and name.lower() not in seen:
            out.append(name)
            seen.add(name.lower())
    return out


async def faction_autocomplete(interaction: discord.Interaction, current: str):
    try:
        data = await fetch()
        names = faction_choices_from_data(data)
    except Exception:
        names = [
            "Electric Immortals", "Neon Hive", "Binary Minds",
            "Fixers", "Glow Wave", "Code Shifters"
        ]
    current = current.lower().strip()
    return [
        app_commands.Choice(name=name, value=name)
        for name in names
        if not current or current in name.lower()
    ][:25]


def player_sort_key(e):
    # Prefer Points, with Damage/Attacks as tie-breakers.
    def n(k):
        try:
            return int(e.get(k, 0) or 0)
        except Exception:
            return 0
    return (n("factionPoints"), n("totalDamage"), n("attacks"))


def top5_embed(data, faction=None):
    entries = list(data.get("entries") or [])

    if faction:
        matches = [
            e for e in entries
            if faction_name_matches(e.get("factionName"), faction)
        ]
        actual_name = str(
            matches[0].get("factionName", faction)
        ) if matches else faction
        title = f"⚡ TOP 5 — {actual_name.upper()}"
        description = f"Top 5 individual players in **{actual_name}**."
        entries = matches
    else:
        title = "⚡ TOP 5 PLAYERS"
        description = "Top 5 individual players across all factions."
        entries = entries

    # Exclude the three non-player / special faction entries if present.
    # Matching is done by faction/entry names so the filter remains usable
    # if the API returns different ordering.
    skip_names = {
        "factions", "total", "all factions"
    }
    entries = [
        e for e in entries
        if str(e.get("factionName", "")).strip().lower() not in skip_names
    ]

    entries.sort(key=player_sort_key, reverse=True)
    entries = entries[:5]

    x = discord.Embed(
        title=title,
        description=description,
        color=0x42F5C5
    )

    if not entries:
        x.add_field(
            name="NO DATA",
            value="No players were found for that faction.",
            inline=False
        )
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, e in enumerate(entries):
            name = str(
                e.get("displayName")
                or e.get("username")
                or e.get("uid")
                or "Unknown"
            )
            faction_name = str(e.get("factionName") or "Unknown")
            value = (
                f"**Damage:** {num(e.get('totalDamage', e.get('damage', 0)))}\n"
                f"**Points:** {num(e.get('factionPoints', e.get('points', 0)))}\n"
                f"**Attacks:** {num(e.get('attacks', 0))}\n"
                f"**Raid XP:** {num(e.get('raidXp', e.get('xp', 0)))}"
            )
            if not faction:
                value += f"\n**Faction:** {faction_name}"
            x.add_field(name=f"{medals[i]} {name}", value=value, inline=False)

    x.add_field(
        name="RAID",
        value=(
            f"**{data.get('name','WChronicles Raid')}**\n"
            f"Status: **{data.get('status','Unknown')}**"
        ),
        inline=False
    )
    x.set_footer(text="THE CURRENT FINDS ITS OWN.  •  LIVE DATA")
    return x


@tree.command(
    name="top5",
    description="Show the top 5 players, optionally filtered by faction."
)
@app_commands.describe(
    faction="Optional faction filter. Leave empty for all factions."
)
@app_commands.autocomplete(faction=faction_autocomplete)
async def top5(interaction: discord.Interaction, faction: str = None):
    try:
        await interaction.response.defer(ephemeral=False)
        data = await fetch()
        await interaction.followup.send(embed=top5_embed(data, faction))
    except Exception as ex:
        if interaction.response.is_done():
            await interaction.followup.send(
                f"Could not load leaderboard: `{type(ex).__name__}`.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Could not load leaderboard: `{type(ex).__name__}`.",
                ephemeral=True
            )


@tree.command(
    name="topfactions",
    description="Show all factions in the current raid."
)
async def topfactions(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=False)
        data = await fetch()
        fs = list(data.get("factions") or [])
        fs.sort(key=lambda f: int(f.get("rank", 999999) or 999999))

        x = discord.Embed(
            title="⚡ FACTION LEADERBOARD",
            description="All current factions — sorted by rank.",
            color=0x42F5C5
        )

        medals = ["🥇", "🥈", "🥉"]
        for i, f in enumerate(fs):
            name = str(f.get("factionName", "Unknown"))
            rank = f.get("rank", i + 1)
            prefix = medals[i] if i < 3 else f"#{rank}"
            value = (
                f"**Points:** {num(f.get('points', 0))}\n"
                f"**Damage:** {num(f.get('damage', 0))}\n"
                f"**Attacks:** {num(f.get('attacks', 0))}\n"
                f"**Walkers:** {num(f.get('players', 0))}\n"
                f"**Wins:** {num(f.get('wins', 0))}"
            )
            x.add_field(
                name=f"{prefix} {name}",
                value=value,
                inline=False
            )

        x.set_footer(text="THE CURRENT FINDS ITS OWN.  •  LIVE DATA")
        await interaction.followup.send(embed=x)
    except Exception as ex:
        if interaction.response.is_done():
            await interaction.followup.send(
                f"Could not load leaderboard: `{type(ex).__name__}`.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Could not load leaderboard: `{type(ex).__name__}`.",
                ephemeral=True
            )


@tree.command(name="setup",description="Set the WChronicles leaderboard channel.")
@app_commands.describe(channel="Channel for the leaderboard.")
@app_commands.default_permissions(manage_guild=True)
async def setup(interaction:discord.Interaction,channel:discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server permission.",ephemeral=True)
    gid=str(interaction.guild_id); old=configs.get(gid,{})
    configs[gid]={"channel_id":str(channel.id)};save()
    await interaction.response.send_message(f"⚡ Leaderboard configured for {channel.mention}. A new leaderboard message will be posted every {INTERVAL} minutes.",ephemeral=True)
    await update(gid,configs[gid])

@tree.command(name="status",description="Show War Bunker configuration.")
async def status(interaction:discord.Interaction):
    c=configs.get(str(interaction.guild_id))
    if not c:return await interaction.response.send_message("Not configured. Use `/setup`.",ephemeral=True)
    await interaction.response.send_message(f"⚡ Channel: <#{c['channel_id']}>\nUpdate interval: **{INTERVAL} minutes**",ephemeral=True)

@tree.command(name="update",description="Update the leaderboard now.")
async def update_now(interaction:discord.Interaction):
    c=configs.get(str(interaction.guild_id))
    if not c:return await interaction.response.send_message("Not configured. Use `/setup`.",ephemeral=True)
    await interaction.response.defer(ephemeral=True);await update(str(interaction.guild_id),c)
    await interaction.followup.send("⚡ Leaderboard updated.",ephemeral=True)

@tree.command(name="disable",description="Disable leaderboard updates.")
@app_commands.default_permissions(manage_guild=True)
async def disable(interaction:discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server permission.",ephemeral=True)
    configs.pop(str(interaction.guild_id),None);save()
    await interaction.response.send_message("Leaderboard disabled.",ephemeral=True)

@tasks.loop(minutes=INTERVAL)
async def updater():
    for gid,c in list(configs.items()): await update(gid,c); await asyncio.sleep(1)

@updater.before_loop
async def before(): await client.wait_until_ready()

@client.event
async def on_ready():
    load()
    # Sync slash commands directly to every server for immediate availability.
    # This avoids waiting for Discord's global command propagation.
    for guild in client.guilds:
        try:
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
            print(f"Commands synced to {guild.name} ({guild.id})")
        except Exception as ex:
            print("Command sync error:", guild.id, type(ex).__name__, ex)
    if not updater.is_running():updater.start()
    print("War Bunker v3 online as",client.user)

load()
token=os.getenv("DISCORD_TOKEN")
if not token: raise RuntimeError("DISCORD_TOKEN environment variable is missing.")
client.run(token)
