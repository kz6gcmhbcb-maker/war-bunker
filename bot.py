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
        msg=None
        mid=cfg.get("message_id","0")
        if mid and str(mid)!="0":
            try:msg=await ch.fetch_message(int(mid))
            except:pass
        if not msg:
            async for m in ch.history(limit=50):
                if m.author.id==client.user.id and m.embeds and m.embeds[0].title=="⚡ FACTION WAR — LEADERBOARD":
                    msg=m;break
        data=await fetch(); em=embed(data)
        if msg: await msg.edit(embed=em)
        else: msg=await ch.send(embed=em)
        cfg["message_id"]=str(msg.id);save()
    except Exception as ex: print("Update error:",type(ex).__name__,ex)

@tree.command(name="setup",description="Set the WChronicles leaderboard channel.")
@app_commands.describe(channel="Channel for the leaderboard.")
@app_commands.default_permissions(manage_guild=True)
async def setup(interaction:discord.Interaction,channel:discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server permission.",ephemeral=True)
    gid=str(interaction.guild_id); old=configs.get(gid,{})
    configs[gid]={"channel_id":str(channel.id),"message_id":old.get("message_id","0")};save()
    await interaction.response.send_message(f"⚡ Leaderboard configured for {channel.mention}.",ephemeral=True)
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
    await tree.sync()
    if not updater.is_running():updater.start()
    print("War Bunker v3 online as",client.user)

load()
token=os.getenv("DISCORD_TOKEN")
if not token: raise RuntimeError("DISCORD_TOKEN environment variable is missing.")
client.run(token)
