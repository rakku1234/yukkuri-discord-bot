import os
import ctypes
import tempfile
import discord
import platform
from database import Database

current_voice_settings = {}

class AquesTalkAudio:
    def __init__(self, text, speed=100, voice_name="f1"):
        self.text = text
        self.speed = speed
        self.voice_name = voice_name
        self.temp_file = None
        self.aquestalk = None

    def _init_aquestalk(self):
        system = platform.system().lower()
        if system == "windows":
            lib_name = "AquesTalk.dll"
        elif system == "linux":
            lib_name = "libAquesTalk.so"
        else:
            raise OSError(f"Unsupported operating system: {system}")

        lib_path = os.path.join(os.path.dirname(__file__), "lib64", self.voice_name, lib_name)
        self.aquestalk = ctypes.CDLL(lib_path)

        self.aquestalk.AquesTalk_Synthe_Utf8.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.aquestalk.AquesTalk_Synthe_Utf8.restype = ctypes.POINTER(ctypes.c_ubyte)
        self.aquestalk.AquesTalk_FreeWave.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        self.aquestalk.AquesTalk_FreeWave.restype = None

    # 音声合成
    def get_audio(self):
        if self.aquestalk is None:
            self._init_aquestalk()

        text_utf8 = self.text.encode('utf-8')
        size = ctypes.c_int(0)

        wav_data = self.aquestalk.AquesTalk_Synthe_Utf8(text_utf8, self.speed, ctypes.byref(size))

        if wav_data is None:
            return None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                buffer = ctypes.string_at(wav_data, size.value)
                temp.write(buffer)
            return self.temp_file
        except Exception as e:
            raise e
        finally:
            self.aquestalk.AquesTalk_FreeWave(wav_data)

# ボイスチャンネルで音声を再生する関数
async def speak_in_voice_channel(voice_client: discord.VoiceClient, text: str, speed: int = 100, voice_name: str = "f1"):
    if not voice_client or not voice_client.is_connected():
        return False

    try:
        audio = AquesTalkAudio(text, speed, voice_name)
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

    voice_settings = current_voice_settings.get(message.guild.id)
    if voice_settings is None:
        voice_settings = await db.get_voice_settings(message.guild.id)
        if voice_settings:
            current_voice_settings[message.guild.id] = voice_settings

    voice_name = "f1"
    speed = 100
    if voice_settings:
        voice_name, speed = voice_settings

    text = message.content.replace('\n', '').replace(' ', '')

    await speak_in_voice_channel(voice_client, text, speed, voice_name)

async def update_voice_settings(guild_id: int, voice_name: str, speed: int):
    current_voice_settings[guild_id] = (voice_name, speed)
