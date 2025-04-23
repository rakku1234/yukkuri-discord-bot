import discord
from discord import app_commands
from discord_cmd import setup_commands
from vc import read_message, db
from config import load_config

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    print(f'{client.user} としてログインしました')

    await db.connect()

    setup_commands(tree)
    await tree.sync()

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.id == client.user.id:
        return

    if before.channel is None and after.channel is not None:
        autojoin = await db.get_autojoin(member.guild.id)
        if autojoin and after.channel.id == autojoin[0]:
            if member.guild.voice_client is None:
                try:
                    await after.channel.connect(self_deaf=True)
                except Exception as e:
                    print(f"{member.guild.name}の自動参加に失敗しました: {e}")

    voice_client = member.guild.voice_client
    if voice_client is None:
        return

    channel = voice_client.channel
    if channel is None:
        return

    member_count = len([m for m in channel.members if not m.bot])

    if member_count <= 0:
        await voice_client.disconnect()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    await read_message(message)

client.run(load_config()["discord"]["token"])
