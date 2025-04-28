import ctypes
import tempfile
import platform
import os

class AquesTalk1:
    def __init__(self, text, speed=100, voice_name='f1'):
        self.text = text
        self.speed = speed
        self.voice_name = voice_name
        self.temp_file = None
        self.aquestalk = None

    def _init_aquestalk(self):
        system = platform.system().lower()
        if system == 'windows':
            lib_name = 'AquesTalk.dll'
        elif system == 'linux':
            lib_name = 'libAquesTalk.so'
        else:
            raise OSError(f"サポートされていないプラットフォームです: {system}")

        lib_path = os.path.join(os.path.dirname(__file__), 'AquesTalk1', 'lib', self.voice_name, lib_name)
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
