import ctypes
import os
import platform

class TextToSpeech:
    def __init__(self, text: str, speaker: int):
        self.text = text
        self.speaker = speaker
        self.system = platform.system().lower()
        self.dll_dir = os.path.join(os.path.dirname(__file__), 'AqKanji2Koe', 'lib')
        self.dic_dir = os.path.join(os.path.dirname(__file__), 'AqKanji2Koe', 'aq_dic')

        match self.system:
            case 'windows':
                self.aq_kanji2koe = ctypes.WinDLL(os.path.join(self.dll_dir, 'AqKanji2Koe.dll'))
            case 'linux':
                self.aq_kanji2koe = ctypes.CDLL(os.path.join(self.dll_dir, 'libAqKanji2Koe.so'))
            case _:
                raise RuntimeError('サポートされていないオペレーティングシステムです')

    def convert_text_to_speech(self) -> str:
        self.aq_kanji2koe.AqKanji2Koe_Create.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        self.aq_kanji2koe.AqKanji2Koe_Create.restype = ctypes.c_void_p

        err_code = ctypes.c_int(0)
        instance = self.aq_kanji2koe.AqKanji2Koe_Create(self.dic_dir.encode('utf-8'), ctypes.byref(err_code))
        if not instance:
            raise Exception(f"AqKanji2Koeインスタンスの作成に失敗しました (エラーコード: {err_code.value})")

        try:
            if self.system == 'windows':
                self.aq_kanji2koe.AqKanji2Koe_Convert_utf8.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
                self.aq_kanji2koe.AqKanji2Koe_Convert_utf8.restype = ctypes.c_int
                output_buffer = ctypes.create_string_buffer(4096)
                result = self.aq_kanji2koe.AqKanji2Koe_Convert_utf8(instance, self.text.encode('utf-8'), output_buffer, 4096)
                if result == 0:
                    return output_buffer.value.decode('utf-8')
                else:
                    raise Exception(f"変換に失敗しました。エラーコード: {result}")
            elif self.system == 'linux':
                self.aq_kanji2koe.AqKanji2Koe_Convert.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
                self.aq_kanji2koe.AqKanji2Koe_Convert.restype = ctypes.c_int
                output_buffer = ctypes.create_string_buffer(4096)
                result = self.aq_kanji2koe.AqKanji2Koe_Convert(instance, self.text.encode('utf-8'), output_buffer, 4096)
                if result == 0:
                    return output_buffer.value.decode('utf-8')
                else:
                    raise Exception(f"変換に失敗しました。エラーコード: {result}")
            else:
                raise RuntimeError(f"サポートされていないプラットフォームです")
        finally:
            if instance:
                try:
                    instance_ptr = ctypes.c_void_p(instance)
                    self.aq_kanji2koe.AqKanji2Koe_Release(instance_ptr)
                except Exception as e:
                    raise Exception(f"開放時にエラーが発生しました: {e}")
