import os
import discord
import re
import asyncio
import json
from collections import defaultdict
from database import Database
from text_to_speech import convert_text_to_speech
from loguru import logger
from aquestalk import AquesTalk1, AquesTalk2
from voicevox import Voicevox
from config import load_config

config = load_config()
debug_mode = config['debug']

current_voice_settings = {}
message_queues = defaultdict(asyncio.Queue)
reading_tasks = {}

with open('voice_character.json', encoding='utf-8') as f:
    voice_characters = json.load(f)

async def speak_in_voice_channel(voice_client: discord.VoiceClient, text: str, voice_name: str, speed: int, engine: str):
    if debug_mode:
        logger.debug(f"音声再生を開始 - テキスト: {text}, ボイス: {voice_name}, 速度: {speed}, エンジン: {engine}")
    if not voice_client or not voice_client.is_connected():
        if debug_mode:
            logger.debug('ボイスクライアントが接続されていません')
        return False

    try:
        match engine:
            case 'voicevox':
                audio = Voicevox(text, int(voice_name))
            case 'aquestalk1':
                audio = AquesTalk1(text, speed, voice_name)
            case 'aquestalk2':
                audio = AquesTalk2(text, speed, voice_name)
            case _:
                raise ValueError(f"無効なエンジン: {engine}")

        audio_file = await audio.get_audio()

        if audio_file is None:
            if debug_mode:
                logger.debug('音声ファイルの生成に失敗しました')
            return False

        future = asyncio.Future()
        def after_playing(error):
            if error:
                future.set_exception(error)
            else:
                future.set_result(None)
            os.unlink(audio_file)

        while voice_client.is_playing():
            await asyncio.sleep(0.1)

        voice_client.play(discord.FFmpegPCMAudio(audio_file), after=after_playing)
        await future
        if debug_mode:
            logger.debug('音声再生が完了しました')
        return True
    except Exception as e:
        logger.error(f"音声合成エラー: {e}")
        return False

db = Database()

async def process_message_queue(guild_id: int):
    if debug_mode:
        logger.debug(f"メッセージキューの処理を開始 - ギルドID: {guild_id}")
    while True:
        try:
            message_data = await message_queues[guild_id].get()
            if message_data is None:
                if debug_mode:
                    logger.debug(f"メッセージキューが終了しました - ギルドID: {guild_id}")
                break

            text, voice_name, speed, voice_client, engine = message_data
            if debug_mode:
                logger.debug(f"メッセージを処理中 - テキスト: {text}")

            await speak_in_voice_channel(voice_client, text, voice_name, speed, engine)

            message_queues[guild_id].task_done()
        except Exception as e:
            logger.error(f"メッセージキュー処理エラー: {e}")
            continue

async def read_message(message_or_text, guild=None, author=None, channel=None):
    if debug_mode:
        logger.debug('メッセージ読み上げ処理を開始')
    if isinstance(message_or_text, str):
        text = message_or_text
        if guild is None or channel is None:
            if debug_mode:
                logger.debug('ギルドまたはチャンネルが指定されていません')
            return
    else:
        message = message_or_text
        if message.author.bot:
            if debug_mode:
                logger.debug('ボットからのメッセージは無視します')
            return

        channels = await db.get_read_channels()
        if message.guild.id not in channels or message.channel.id != channels[message.guild.id][1]:
            if debug_mode:
                logger.debug(f"読み上げ対象外のチャンネルです - ギルドID: {message.guild.id}, チャンネルID: {message.channel.id}")
            return

        guild = message.guild
        author = message.author
        channel = message.channel
        text = message.content.replace('\n', '').replace(' ', '')

    voice_client = guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        if debug_mode:
            logger.debug('ボイスクライアントが接続されていません')
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
        if debug_mode:
            logger.debug(f"ユーザー設定を使用 - ボイス: {voice_name}, 速度: {speed}, エンジン: {engine}")

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
        text = convert_text_to_speech(text)

    if debug_mode:
        logger.debug(f"処理後のテキスト: {text}")

    await message_queues[guild.id].put((text, voice_name, speed, voice_client, engine))

    if guild.id not in reading_tasks or reading_tasks[guild.id].done():
        reading_tasks[guild.id] = asyncio.create_task(process_message_queue(guild.id))
        if debug_mode:
            logger.debug(f"メッセージキュー処理タスクを開始 - ギルドID: {guild.id}")

async def update_voice_settings(guild_id: int, user_id: int, voice_name: str, speed: int, engine: str):
    if debug_mode:
        logger.debug(f"ボイス設定を更新 - ギルドID: {guild_id}, ユーザーID: {user_id}, ボイス: {voice_name}, 速度: {speed}, エンジン: {engine}")
    current_voice_settings[(guild_id, user_id)] = (voice_name, speed, engine)
