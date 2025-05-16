import discord
import platform
import sys
from discord import app_commands
from discord_cmd import setup_commands
from vc import read_message, db
from config import Config
from loguru import logger
from voicevox import voicevox

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
debug = Config.load_config()['debug']

@client.event
async def on_ready():
    if debug:
        logger.debug('デバッグモードが有効です')
    logger.info(f"{client.user} としてログインしました")

    await db.connect()
    if debug:
        logger.debug('データベース接続完了')

    setup_commands(tree)
    await tree.sync()
    if debug:
        logger.debug('コマンド同期完了')

    read_channels = await db.get_read_channels()
    if debug:
        logger.debug('読み上げチャンネル一覧取得完了')
    for guild_id, (voice_channel_id, _) in read_channels.items():
        guild = client.get_guild(guild_id)
        if not guild:
            await db.remove_read_channel(guild_id)
            if debug:
                logger.debug(f"{guild_id}のサーバーが見つかりませんでした")
            continue
        voice_channel = guild.get_channel(voice_channel_id)
        if not voice_channel:
            await db.remove_read_channel(guild_id)
            if debug:
                logger.debug(f"{guild_id}のボイスチャンネルが見つかりませんでした")
            continue
        member_count = len([m for m in voice_channel.members if not m.bot])
        if member_count == 0:
            await db.remove_read_channel(guild_id)
            if debug:
                logger.debug(f"{guild_id}のボイスチャンネルのメンバーはいないため読み上げチャンネルから削除しました")
            continue
        if not guild.voice_client or not guild.voice_client.is_connected():
            await voice_channel.connect(self_deaf=True)
            if debug:
                logger.debug(f"{guild_id}のボイスチャンネルに接続しました")

    try:
        config = await Config.async_load_config()
        if config['engine_enabled']['voicevox'] and config['voicevox']['edition']['core']:
            await voicevox.init()
    except Exception as e:
        logger.error(f"voicevoxの初期化に失敗しました: {e}")

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.id == client.user.id:
        if before.channel is not None and after.channel is None:
            await db.remove_read_channel(member.guild.id)
            if debug:
                logger.debug(f"{member.guild.id}の読み上げチャンネルを削除しました")
        if before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            read_channel = await db.get_read_channel(member.guild.id)
            if read_channel:
                await db.set_read_channel(member.guild.id, after.channel.id, read_channel[1])
                if debug:
                    logger.debug(f"{member.guild.id}の読み上げチャンネルを更新しました")
        return

    if before.channel is None and after.channel is not None:
        autojoin = await db.get_autojoin(member.guild.id)
        if autojoin and after.channel.id == autojoin[0]:
            member_count = len([m for m in after.channel.members if not m.bot])
            if member_count == 1 and member.guild.voice_client is None:
                try:
                    await after.channel.connect(self_deaf=True)
                    await db.set_read_channel(member.guild.id, after.channel.id, autojoin[1])
                    if debug:
                        logger.debug(f"{member.guild.id}の自動参加に成功しました")
                except Exception as e:
                    logger.error(f"{member.guild.name}の自動参加に失敗しました: {e}")

        voice_client = member.guild.voice_client
        if voice_client and voice_client.is_connected() and voice_client.channel == after.channel:
            await read_message(f"{member.display_name}が参加しました", member.guild, member, after.channel)
            if debug:
                logger.debug(f"{member.guild.id}に{member.display_name}が参加しました")

    if before.channel is not None and after.channel is None:
        voice_client = member.guild.voice_client
        if voice_client and voice_client.is_connected() and voice_client.channel == before.channel:
            await read_message(f"{member.display_name}が退出しました", member.guild, member, before.channel)

    voice_client = member.guild.voice_client
    if voice_client is None:
        return

    channel = voice_client.channel
    if channel is None:
        return

    member_count = len([m for m in channel.members if not m.bot])

    if member_count == 0:
        await voice_client.disconnect()
        await db.remove_read_channel(voice_client.guild.id)
        if debug:
            logger.debug(f"{voice_client.guild.id}のボイスチャンネルのメンバーはいないため読み上げチャンネルから削除しました")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if len(message.content) > 0:
        await read_message(message)

if platform.system().lower() not in ['windows', 'linux']:
    logger.critical('サポートされていないオペレーティングシステムです')
    sys.exit(1)

client.run(Config.load_config()['discord']['token'])
