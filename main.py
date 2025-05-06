import discord
from discord import app_commands
from discord_cmd import setup_commands
from vc import read_message, db
from config import load_config
from loguru import logger
from voicevox import Voicevox

config = load_config()
debug_mode = config['debug']

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    if debug_mode:
        logger.debug('ボットの起動処理を開始')
    logger.info(f"{client.user} としてログインしました")

    await db.connect()
    if debug_mode:
        logger.debug('データベース接続完了')

    setup_commands(tree)
    await tree.sync()
    if debug_mode:
        logger.debug('コマンドの同期完了')

    read_channels = await db.get_read_channels()
    if debug_mode:
        logger.debug(f"読み上げチャンネル数: {len(read_channels)}")
    for guild_id, (voice_channel_id, _) in read_channels.items():
        if debug_mode:
            logger.debug(f"ギルド {guild_id} の処理開始")
        guild = client.get_guild(guild_id)
        if not guild:
            await db.remove_read_channel(guild_id)
            if debug_mode:
                logger.debug(f"ギルド {guild_id} が見つからないため削除")
            continue
        voice_channel = guild.get_channel(voice_channel_id)
        if not voice_channel:
            await db.remove_read_channel(guild_id)
            if debug_mode:
                logger.debug(f"ボイスチャンネル {voice_channel_id} が見つからないため削除")
            continue
        member_count = len([m for m in voice_channel.members if not m.bot])
        if member_count == 0:
            await db.remove_read_channel(guild_id)
            if debug_mode:
                logger.debug(f"ボイスチャンネル {voice_channel_id} にメンバーがいないため削除")
            continue
        if not guild.voice_client or not guild.voice_client.is_connected():
            await voice_channel.connect(self_deaf=True)
            if debug_mode:
                logger.debug(f"ボイスチャンネル {voice_channel_id} に接続")

    try:
        await Voicevox.init()
        if debug_mode:
            logger.debug('Voicevoxの初期化完了')
    except Exception as e:
        logger.error(f"Voicevoxの初期化に失敗しました: {e}")

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if debug_mode:
        logger.debug(f"{member.display_name} のボイス状態が更新されました")
        logger.debug(f"before: {before.channel}, after: {after.channel}")

    if member.id == client.user.id:
        return

    if before.channel is None and after.channel is not None:
        if debug_mode:
            logger.debug(f"{member.display_name} がボイスチャンネルに参加")
        autojoin = await db.get_autojoin(member.guild.id)
        if autojoin and after.channel.id == autojoin[0]:
            if member.guild.voice_client is None:
                try:
                    await after.channel.connect(self_deaf=True)
                    if debug_mode:
                        logger.debug(f"自動参加で {after.channel.name} に接続")
                except Exception as e:
                    logger.error(f"{member.guild.name}の自動参加に失敗しました: {e}")

        voice_client = member.guild.voice_client
        if voice_client and voice_client.is_connected() and voice_client.channel == after.channel:
            await read_message(f"{member.display_name}が参加しました", member.guild, member, after.channel)

    if before.channel is not None and after.channel is None:
        if debug_mode:
            logger.debug(f"{member.display_name} がボイスチャンネルから退出")
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
    if debug_mode:
        logger.debug(f"現在のメンバー数: {member_count}")

    if member_count == 0:
        await voice_client.disconnect()
        await db.remove_read_channel(voice_client.guild.id)
        if debug_mode:
            logger.debug('メンバーがいなくなったため切断')

@client.event
async def on_message(message):
    if debug_mode:
        logger.debug(f"{message.author.display_name} からのメッセージ: {message.content}")
    if message.author == client.user:
        return

    await read_message(message)

client.run(load_config()['discord']['token'])
