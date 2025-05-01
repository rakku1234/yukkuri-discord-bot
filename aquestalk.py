import ctypes
import platform
import os
import aiofiles

class AquesTalk1:
    def __init__(self, text, speed=100, voice_name='f1'):
        self.text = text
        self.speed = speed
        self.voice_name = voice_name
        self.temp_file = None
        self.aquestalk = None

    def init(self):
        system = platform.system().lower()
        match system:
            case 'windows':
                lib_name = 'AquesTalk.dll'
            case 'linux':
                lib_name = 'libAquesTalk.so'
            case _:
                raise OSError(f"サポートされていないプラットフォームです: {system}")

        lib_path = os.path.join(os.path.dirname(__file__), 'AquesTalk1', 'lib', self.voice_name, lib_name)
        self.aquestalk = ctypes.CDLL(lib_path)

        self.aquestalk.AquesTalk_Synthe_Utf8.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.aquestalk.AquesTalk_Synthe_Utf8.restype = ctypes.POINTER(ctypes.c_ubyte)
        self.aquestalk.AquesTalk_FreeWave.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        self.aquestalk.AquesTalk_FreeWave.restype = None

    async def get_audio(self):
        if self.aquestalk is None:
            self.init()

        size = ctypes.c_int(0)

        wav_data = self.aquestalk.AquesTalk_Synthe_Utf8(self.text.encode('utf-8'), self.speed, ctypes.byref(size))

        if wav_data is None:
            return None

        try:
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                buffer = ctypes.string_at(wav_data, size.value)
                await temp.write(buffer)
            return self.temp_file
        except Exception as e:
            raise e
        finally:
            self.aquestalk.AquesTalk_FreeWave(wav_data)

class AquesTalk2:
    def __init__(self, text, speed=100, voice_name='f4'):
        self.text = text
        self.speed = speed
        self.voice_name = voice_name
        self.temp_file = None
        self.aquestalk = None

    async def init(self):
        system = platform.system().lower()
        match system:
            case 'windows':
                lib_name = 'AquesTalk2.dll'
            case 'linux':
                lib_name = 'libAquesTalk2.so'
            case _:
                raise OSError(f"サポートされていないプラットフォームです: {system}")

        lib_path = os.path.join(os.path.dirname(__file__), 'AquesTalk2', 'lib', lib_name)
        phont_file = os.path.join(os.path.dirname(__file__), 'AquesTalk2', 'phont', f"{self.voice_name}.phont")

        self.aquestalk = ctypes.CDLL(lib_path)

        self.aquestalk.AquesTalk2_Synthe_Utf8.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_void_p]
        self.aquestalk.AquesTalk2_Synthe_Utf8.restype = ctypes.POINTER(ctypes.c_ubyte)
        self.aquestalk.AquesTalk2_FreeWave.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        self.aquestalk.AquesTalk2_FreeWave.restype = None

        try:
            async with aiofiles.open(phont_file, 'rb') as f:
                data = await f.read()
                self.phont_ptr = ctypes.cast(ctypes.create_string_buffer(data), ctypes.c_void_p)
        except Exception as e:
            raise e

        if self.phont_ptr is None:
            raise RuntimeError(f"Phontファイルの読み込みに失敗しました: {phont_file}")

    async def get_audio(self):
        if self.aquestalk is None:
            await self.init()

        size = ctypes.c_int(0)

        wav_data = self.aquestalk.AquesTalk2_Synthe_Utf8(self.text.encode('utf-8'), self.speed, ctypes.byref(size), self.phont_ptr)

        if wav_data is None:
            return None

        try:
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                buffer = ctypes.string_at(wav_data, size.value)
                await temp.write(buffer)
            return self.temp_file
        except Exception as e:
            raise e
        finally:
            self.aquestalk.AquesTalk2_FreeWave(wav_data)
