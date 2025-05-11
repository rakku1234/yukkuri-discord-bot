import ctypes
import os
import sys

def aquestalk_lisence(dir: str, key: str) -> bool:
    match sys.platform.lower():
        case 'windows':
            DLL_PATH = os.path.join(os.path.dirname(__file__), 'AquesTalk1', 'lib', dir, 'AquesTalk.dll')
        case 'linux':
            DLL_PATH = os.path.join(os.path.dirname(__file__), 'AquesTalk1', 'lib', dir, 'libAquesTalk.so')
        case _:
            raise NotImplementedError('このOSはサポートされていません。')

    aqtalk = ctypes.CDLL(DLL_PATH)
    aqtalk.AquesTalk_SetUsrKey.argtypes = [ctypes.c_char_p]
    aqtalk.AquesTalk_SetUsrKey.restype = ctypes.c_int

    result = aqtalk.AquesTalk_SetUsrKey(key.encode('utf-8'))
    if result == 0:
        return True
    else:
        return False

if __name__ == '__main__':
    dir = sys.argv[1]
    key = sys.argv[2]
    if aquestalk_lisence(dir, key):
        print('ライセンスキーを設定しました。')
    else:
        print('ライセンスキーを設定できませんでした。')
