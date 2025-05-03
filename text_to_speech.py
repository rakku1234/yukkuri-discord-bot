import ctypes
import os
import platform

def convert_text_to_speech(text: str) -> str:
    system = platform.system().lower()
    base_dir = os.path.dirname(__file__)
    dll_dir = os.path.join(base_dir, 'AqKanji2Koe', 'lib')
    dic_dir = os.path.join(base_dir, 'AqKanji2Koe', 'aq_dic')

    match system:
        case 'windows':
            kanji2koe_lib = os.path.join(dll_dir, 'AqKanji2Koe.dll')
            aq_kanji2koe = ctypes.WinDLL(kanji2koe_lib)
        case 'linux':
            kanji2koe_lib = os.path.join(dll_dir, 'libAqKanji2Koe.so')
            aq_kanji2koe = ctypes.CDLL(kanji2koe_lib)
        case _:
            raise OSError(f"サポートされていないプラットフォームです")

    aq_kanji2koe.AqKanji2Koe_Create.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
    aq_kanji2koe.AqKanji2Koe_Create.restype = ctypes.c_void_p

    err_code = ctypes.c_int(0)
    instance = aq_kanji2koe.AqKanji2Koe_Create(dic_dir.encode('utf-8'), ctypes.byref(err_code))
    if not instance:
        raise Exception(f"AqKanji2Koeインスタンスの作成に失敗しました (エラーコード: {err_code.value})")

    try:
        if system == 'windows':
            aq_kanji2koe.AqKanji2Koe_Convert_utf8.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int
            ]
            aq_kanji2koe.AqKanji2Koe_Convert_utf8.restype = ctypes.c_int
            input_text = text.encode('utf-8')
            output_buffer = ctypes.create_string_buffer(4096)
            result = aq_kanji2koe.AqKanji2Koe_Convert_utf8(instance, input_text, output_buffer, 4096)
            if result == 0:
                return output_buffer.value.decode('utf-8')
            else:
                raise Exception(f"変換に失敗しました。エラーコード: {result}")
        elif system == 'linux':
            aq_kanji2koe.AqKanji2Koe_Convert.argtypes = [
                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int
            ]
            aq_kanji2koe.AqKanji2Koe_Convert.restype = ctypes.c_int
            input_text = text.encode('utf-8')
            output_buffer = ctypes.create_string_buffer(4096)
            result = aq_kanji2koe.AqKanji2Koe_Convert(instance, input_text, output_buffer, 4096)
            if result == 0:
                return output_buffer.value.decode('utf-8')
            else:
                raise Exception(f"変換に失敗しました。エラーコード: {result}")
    finally:
        if instance:
            try:
                instance_ptr = ctypes.c_void_p(instance)
                aq_kanji2koe.AqKanji2Koe_Release(instance_ptr)
            except Exception as e:
                raise Exception(f"開放時にエラーが発生しました: {e}")
