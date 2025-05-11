import ctypes
import os
import sys

def aqkanji2ko_lisence(key: str) -> bool:
    match sys.platform.lower():
        case 'windows':
            DLL_PATH = os.path.join(os.path.dirname(__file__), 'AqKanji2Koe', 'lib', 'AqKanji2Koe.dll')
        case 'linux':
            DLL_PATH = os.path.join(os.path.dirname(__file__), 'AqKanji2Koe', 'lib', 'libAqKanji2Koe.so')
        case _:
            raise NotImplementedError('このOSはサポートされていません。')

    kanji2koe = ctypes.CDLL(DLL_PATH)
    kanji2koe.AqKanji2Koe_SetDevKey.argtypes = [ctypes.c_char_p]
    kanji2koe.AqKanji2Koe_SetDevKey.restype = ctypes.c_int

    result = kanji2koe.AqKanji2Koe_SetDevKey(key.encode('utf-8'))
    if result == 0:
        return True
    else:
        return False

if __name__ == '__main__':
    key = sys.argv[1]
    if aqkanji2ko_lisence(key):
        print('ライセンスキーを設定しました。')
    else:
        print('ライセンスキーを設定できませんでした。')
