import os
import discord
import re
import asyncio
import json
from collections import defaultdict
from database import Database
from text_to_speech import convert_text_to_speech
from loguru import logger
from aquestalk import AquesTalk1
from voicevox import Voicevox

current_voice_settings = {}
message_queues = defaultdict(asyncio.Queue)
reading_tasks = {}

with open('voice_character.json', 'r', encoding='utf-8') as f:
    voice_characters = json.load(f)

async def speak_in_voice_channel(voice_client: discord.VoiceClient, text: str, voice_name: str = "f1", speed: int = 100, engine: str = "aquestalk"):
    if not voice_client or not voice_client.is_connected():
        return False

    try:
        if engine == "voicevox":
            audio = Voicevox(text, int(voice_name))
        else:
            audio = AquesTalk1(text, speed, voice_name)

        audio_file = audio.get_audio()

        if audio_file is None:
            return False

        future = asyncio.Future()
        def after_playing(error):
            if error:
                future.set_exception(error)
            else:
                future.set_result(None)
            os.unlink(audio_file)

        voice_client.play(discord.FFmpegPCMAudio(audio_file), after=after_playing)
        await future
        return True
    except Exception as e:
        logger.error(f"音声合成エラー: {e}")
        return False

db = Database()

# メッセージキューを処理する関数
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

# メッセージを読み上げる関数
async def read_message(message_or_text, guild=None, author=None, channel=None):
    if isinstance(message_or_text, str):
        text = message_or_text
        if guild is None or channel is None:
            return
    else:
        message = message_or_text
        if message.author.bot:
            return

        channels = await db.get_read_channels()
        if message.guild.id not in channels or message.channel.id != channels[message.guild.id]:
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

    voice_name = "f1"
    speed = 100
    engine = "aquestalk"

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

    if engine == "aquestalk":
        text = convert_text_to_speech(text)

    await message_queues[guild.id].put((text, voice_name, speed, voice_client, engine))

    if guild.id not in reading_tasks or reading_tasks[guild.id].done():
        reading_tasks[guild.id] = asyncio.create_task(process_message_queue(guild.id))

async def update_voice_settings(guild_id: int, user_id: int, voice_name: str, speed: int = 100, engine: str = "aquestalk"):
    current_voice_settings[(guild_id, user_id)] = (voice_name, speed, engine)
