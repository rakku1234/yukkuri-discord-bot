import os
import discord
import re
import asyncio
from collections import defaultdict
from database import Database
from text_to_speech import convert_text_to_speech
from loguru import logger
from aquestalk import AquesTalk1

current_voice_settings = {}
message_queues = defaultdict(asyncio.Queue)
reading_tasks = {}

# ボイスチャンネルで音声を再生する関数
async def speak_in_voice_channel(voice_client: discord.VoiceClient, text: str, speed: int = 100, voice_name: str = "f1"):
    if not voice_client or not voice_client.is_connected():
        return False

    try:
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

            text, speed, voice_name, voice_client = message_data

            await speak_in_voice_channel(voice_client, text, speed, voice_name)

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

    voice_name = 'f1'
    speed = 100
    if voice_settings:
        voice_name, speed = voice_settings

    mention_pattern = r'<@!?(\d+)>'
    for match in re.finditer(mention_pattern, text):
        user_id = int(match.group(1))
        user = guild.get_member(user_id)
        if user:
            text = text.replace(match.group(0), user.display_name)

    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:\/[^\s]*)?'
    text = re.sub(url_pattern, 'URL省略', text)

    custom_emoji_pattern = r'<:[a-zA-Z0-9_]+:[0-9]+>'
    text = re.sub(custom_emoji_pattern, '', text)

    text = convert_text_to_speech(text)

    await message_queues[guild.id].put((text, speed, voice_name, voice_client))

    if guild.id not in reading_tasks or reading_tasks[guild.id].done():
        reading_tasks[guild.id] = asyncio.create_task(process_message_queue(guild.id))

async def update_voice_settings(guild_id: int, user_id: int, voice_name: str, speed: int):
    current_voice_settings[(guild_id, user_id)] = (voice_name, speed)
