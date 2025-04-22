import os
import ctypes
import tempfile
import discord
from discord import app_commands
from database import Database

lib_path = os.path.join(os.path.dirname(__file__), "lib64", "f1", "AquesTalk.dll")
aquestalk = ctypes.CDLL(lib_path)

aquestalk.AquesTalk_Synthe_Utf8.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
aquestalk.AquesTalk_Synthe_Utf8.restype = ctypes.POINTER(ctypes.c_ubyte)
aquestalk.AquesTalk_FreeWave.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
aquestalk.AquesTalk_FreeWave.restype = None

class AquesTalkAudio:
    def __init__(self, text, speed=100):
        self.text = text
        self.speed = speed
        self.temp_file = None

    # 音声合成
    def get_audio(self):
        text_utf8 = self.text.encode('utf-8')

        size = ctypes.c_int(0)

        wav_data = aquestalk.AquesTalk_Synthe_Utf8(text_utf8, self.speed, ctypes.byref(size))

        if wav_data is None:
            return None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                buffer = ctypes.string_at(wav_data, size.value)
                temp.write(buffer)

            aquestalk.AquesTalk_FreeWave(wav_data)

            return self.temp_file
        except Exception as e:
            aquestalk.AquesTalk_FreeWave(wav_data)
            raise e

# ボイスチャンネルで音声を再生する関数
async def speak_in_voice_channel(voice_client: discord.VoiceClient, text: str, speed: int = 100):
    if not voice_client or not voice_client.is_connected():
        return False

    try:
        audio = AquesTalkAudio(text, speed)
        audio_file = audio.get_audio()

        if audio_file is None:
            return False

        voice_client.play(discord.FFmpegPCMAudio(audio_file), after=lambda e: os.unlink(audio_file))
        return True
    except Exception as e:
        print(f"音声合成エラー: {e}")
        return False

db = Database()

# メッセージを読み上げる関数
async def read_message(message: discord.Message):
    if message.author.bot:
        return

    if db.pool is None:
        await db.connect()

    channels = await db.get_read_channels()
    if message.guild.id not in channels or message.channel.id != channels[message.guild.id]:
        return

    voice_client = message.guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        return

    text = message.content.replace('\n', '').replace(' ', '')

    await speak_in_voice_channel(voice_client, text)
