import os
import discord
import re
import asyncio
import time
from collections import defaultdict
from database import Database
from text_to_speech import TextToSpeech
from loguru import logger
from aquestalk import AquesTalk1, AquesTalk2
from voicevox import voicevox
from aivisspeech import aivisspeech
from config import Config

current_voice_settings = {}
message_queues = defaultdict(asyncio.Queue)
reading_tasks = {}

async def speak_in_voice_channel(voice_client: discord.VoiceClient, message: discord.Message, voice_name: str, speed: int, engine: str):
    if not voice_client or not voice_client.is_connected():
        return

    config = await Config.async_load_config()
    debug = config['debug']
    if debug:
        logger.debug(f"音声合成開始: {message}\n使用する音声合成エンジン: {engine}")
        start_time = time.time()

    try:
        match engine:
            case 'voicevox':
                if not config['engine_enabled']['voicevox']:
                    return
                audio = voicevox(message, int(voice_name))
            case 'aivisspeech':
                if not config['engine_enabled']['aivisspeech']:
                    return
                audio = aivisspeech(message, int(voice_name))
            case 'aquestalk1':
                if not config['engine_enabled']['aquestalk1']:
                    return
                audio = AquesTalk1(message, speed, voice_name)
            case 'aquestalk2':
                if not config['engine_enabled']['aquestalk2']:
                    return
                audio = AquesTalk2(message, speed, voice_name)
            case _:
                raise ValueError(f"無効なエンジン: {engine}")

        audio_file = await audio.get_audio()
        if debug:
            end_time = time.time()
            logger.debug(f"音声合成完了 - 所要時間: {end_time - start_time}秒")

        future = asyncio.Future()
        if debug:
            logger.debug('音声再生が完了しました')
        def after_playing(error):
            if error:
                future.set_exception(error)
            else:
                future.set_result(None)
            os.unlink(audio_file)

        while voice_client.is_playing():
            await asyncio.sleep(0.1)

        voice_client.play(discord.FFmpegPCMAudio(audio_file, before_options='-guess_layout_max 0'), after=after_playing)
        await future
    except Exception as e:
        logger.error(f"音声合成エラー: {e}\n入力メッセージ: {message}")

db = Database()

async def process_message_queue(guild_id: int):
    while True:
        try:
            message_data = await message_queues[guild_id].get()
            if message_data is None:
                break

            text, voice_name, speed, voice_client, engine = message_data

            await speak_in_voice_channel(voice_client, text, voice_name, speed, engine)

            message_queues[guild_id].task_done()
        except Exception as e:
            logger.error(f"メッセージキュー処理エラー: {e}")
            continue

async def read_message(message: str | discord.Message, guild: discord.Guild = None, author: discord.Member = None, channel: discord.TextChannel = None):
    if isinstance(message, str):
        text = message
    else:
        if message.author.bot:
            return

        channels = await db.get_read_channels()
        if message.guild.id not in channels or message.channel.id != channels[message.guild.id][1]:
            return

        guild = message.guild
        author = message.author
        channel = message.channel
        text = message.content.replace('\n', '').replace(' ', '')

    voice_client = guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        return

    dictionary_replacements = await db.get_dictionary_replacements(guild.id)
    for original, replacement in dictionary_replacements.items():
        text = text.replace(original, replacement)

    voice_settings = current_voice_settings.get((guild.id, author.id if author else 0))
    if voice_settings is None and author:
        voice_settings = await db.get_voice_settings(guild.id, author.id)
        if voice_settings:
            current_voice_settings[(guild.id, author.id)] = voice_settings

    voice_name = '2'
    speed = 100
    engine = 'voicevox'

    if voice_settings:
        voice_name, speed, engine = voice_settings

    for match in re.finditer(r'<@!?(\d+)>', text):
        user_id = int(match.group(1))
        user = guild.get_member(user_id)
        if user:
            text = text.replace(match.group(0), user.display_name)
    
    for channel_id_str in re.findall(r'<#(\d+)>', text):
        channel_id = int(channel_id_str)
        channel = guild.get_channel(channel_id)
        if channel:
            cleaned_channel_name = re.sub(r'[\U0001F300-\U0001F64F\U0001F680-\U0001F6FF\u2600-\u26FF\u2700-\u27BF]', '', channel.name)
            text = text.replace(f'<#{channel_id_str}>', cleaned_channel_name)

    text = re.sub(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:\/[^\s]*)?', 'URL省略', text)

    text = re.sub(r'<:[a-zA-Z0-9_]+:[0-9]+>', '', text)

    if engine.startswith('aquestalk'):
        text = TextToSpeech(text).convert_text_to_speech()

    await message_queues[guild.id].put((text, voice_name, speed, voice_client, engine))

    if guild.id not in reading_tasks or reading_tasks[guild.id].done():
        reading_tasks[guild.id] = asyncio.create_task(process_message_queue(guild.id))

async def update_voice_settings(guild_id: int, user_id: int, voice_name: str, speed: int, engine: str):
    current_voice_settings[(guild_id, user_id)] = (voice_name, speed, engine)
