import ctypes
import os
import tempfile
import traceback
import sys
import platform
from loguru import logger


class Voicevox:
    _voicevox_instance = None
    _voicevox_dll = None
    _synthesizer = None
    _reference_count = 0

    def __init__(self, text, style_id=0):
        self.text = text
        self.style_id = int(style_id)
        self.temp_file = None

        Voicevox._reference_count += 1
        if Voicevox._voicevox_instance is None:
            self.init()
        else:
            self.voicevox = Voicevox._voicevox_dll
            self.synthesizer = Voicevox._synthesizer

    def init(self):
        system = platform.system().lower()
        try:
            base_dir = os.path.dirname(__file__)
            voicevox_lib_dir = os.path.join(base_dir, 'voicevox', 'lib')
            onnxruntime_lib_dir = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib')

            os.environ['PATH'] = os.pathsep.join([
                voicevox_lib_dir,
                onnxruntime_lib_dir,
               os.environ.get('PATH', '')
            ])

            if system == 'windows':
                lib_path = os.path.join(voicevox_lib_dir, 'voicevox_core.dll')
            elif system == 'linux':
                lib_path = os.path.join(voicevox_lib_dir, 'libvoicevox_core.so')
            else:
                raise OSError(f"サポートされていないプラットフォームです: {system}")

            if not os.path.exists(lib_path):
                logger.error(f"[VOICEVOX] DLLが見つかりません: {lib_path}")
                raise RuntimeError(f"voicevox_core.dllが見つかりません: {lib_path}")

            self.voicevox = ctypes.CDLL(lib_path)
            Voicevox._voicevox_dll = self.voicevox

            try:
                self.voicevox.voicevox_make_default_initialize_options.restype = ctypes.c_void_p
                self.voicevox.voicevox_make_default_tts_options.restype = ctypes.c_void_p
                self.voicevox.voicevox_make_default_load_onnxruntime_options.restype = ctypes.c_void_p
                self.voicevox.voicevox_error_result_to_message.restype = ctypes.c_char_p
            except Exception as e:
                logger.error(f"[VOICEVOX] 関数設定エラー: {e}")
                traceback.print_exc()
                raise

            self.voicevox.voicevox_get_onnxruntime_lib_versioned_filename.restype = ctypes.c_char_p

            self.voicevox.voicevox_synthesizer_new.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p)
            ]
            self.voicevox.voicevox_synthesizer_new.restype = ctypes.c_int

            self.voicevox.voicevox_onnxruntime_load_once.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p)
            ]
            self.voicevox.voicevox_onnxruntime_load_once.restype = ctypes.c_int

            self.voicevox.voicevox_open_jtalk_rc_new.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_void_p)
            ]
            self.voicevox.voicevox_open_jtalk_rc_new.restype = ctypes.c_int

            self.voicevox.voicevox_voice_model_file_open.argtypes = [
                ctypes.c_char_p,
                ctypes.POINTER(ctypes.c_void_p)
            ]
            self.voicevox.voicevox_voice_model_file_open.restype = ctypes.c_int

            self.voicevox.voicevox_synthesizer_load_voice_model.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p
            ]
            self.voicevox.voicevox_synthesizer_load_voice_model.restype = ctypes.c_int

            self.voicevox.voicevox_synthesizer_tts.argtypes = [
                ctypes.c_void_p,
                ctypes.c_char_p,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))
            ]
            self.voicevox.voicevox_synthesizer_tts.restype = ctypes.c_int

            initialize_options = self.voicevox.voicevox_make_default_initialize_options()

            onnxruntime = ctypes.c_void_p()
            onnxruntime_options = self.voicevox.voicevox_make_default_load_onnxruntime_options()
            result = self.voicevox.voicevox_onnxruntime_load_once(
                onnxruntime_options,
                ctypes.byref(onnxruntime)
            )
            if result != 0:
                error_msg = self.voicevox.voicevox_error_result_to_message(result)
                logger.error(f"[VOICEVOX] onnxruntimeロードエラーコード: {result}, raw_msg={error_msg}")
                if isinstance(error_msg, bytes):
                    try:
                        error_text = error_msg.decode('utf-8')
                    except UnicodeDecodeError:
                        error_text = str(error_msg)
                else:
                    error_text = str(error_msg)
                logger.error(f"[VOICEVOX] onnxruntimeロードエラーメッセージ: {error_text}")
                raise RuntimeError(f"Failed to load onnxruntime: {error_text}")

            open_jtalk = ctypes.c_void_p()
            dict_path = os.path.join(os.path.dirname(__file__), 'voicevox', 'dict', 'open_jtalk_dic_utf')
            if not os.path.exists(dict_path):
                logger.error(f"[VOICEVOX] Open JTalk辞書が見つかりません: {dict_path}")
                raise RuntimeError(f"open_jtalk_dic_utfが見つかりません: {dict_path}")

            result = self.voicevox.voicevox_open_jtalk_rc_new(
                dict_path.encode('utf-8'),
                ctypes.byref(open_jtalk)
            )
            if result != 0:
                error_msg = self.voicevox.voicevox_error_result_to_message(result)
                logger.error(f"[VOICEVOX] Open JTalkロードエラーコード: {result}, raw_msg={error_msg}")
                if isinstance(error_msg, bytes):
                    try:
                        error_text = error_msg.decode('utf-8')
                    except UnicodeDecodeError:
                        error_text = str(error_msg)
                else:
                    error_text = str(error_msg)
                logger.error(f"[VOICEVOX] Open JTalkロードエラーメッセージ: {error_text}")
                raise RuntimeError(f"Failed to create open_jtalk: {error_text}")

            self.synthesizer = ctypes.c_void_p()

            result = self.voicevox.voicevox_synthesizer_new(
                onnxruntime,
                open_jtalk,
                initialize_options,
                ctypes.byref(self.synthesizer)
            )

            if result != 0:
                error_msg = self.voicevox.voicevox_error_result_to_message(result)
                logger.error(f"[VOICEVOX] シンセサイザー作成エラーコード: {result}, raw_msg={error_msg}")
                if isinstance(error_msg, bytes):
                    try:
                        error_text = error_msg.decode('utf-8')
                    except UnicodeDecodeError:
                        error_text = str(error_msg)
                else:
                    error_text = str(error_msg)
                logger.error(f"[VOICEVOX] シンセサイザー作成エラーメッセージ: {error_text}")
                raise RuntimeError(f"Failed to create synthesizer: {error_text}")

            Voicevox._synthesizer = self.synthesizer
            Voicevox._voicevox_instance = self

            self.voicevox.voicevox_open_jtalk_rc_delete(open_jtalk)

            model_dir = os.path.join(os.path.dirname(__file__), 'voicevox', 'models', 'vvms')
            if not os.path.exists(model_dir):
                logger.error(f"[VOICEVOX] モデルディレクトリが見つかりません: {model_dir}")
                raise RuntimeError(f"モデルディレクトリが見つかりません: {model_dir}")

            try:
                model_files = os.listdir(model_dir)
            except Exception as e:
                logger.error(f"[VOICEVOX] モデルファイル一覧取得エラー: {e}")
                model_files = []

            model_count = 0
            for model_file in model_files:
                if model_file.endswith('.vvm'):
                    model_path = os.path.join(model_dir, model_file)
                    if not os.path.exists(model_path):
                        logger.error(f"[VOICEVOX] モデルファイルが存在しません: {model_path}")
                        continue

                    model = ctypes.c_void_p()
                    result = self.voicevox.voicevox_voice_model_file_open(
                        model_path.encode('utf-8'),
                        ctypes.byref(model)
                    )
                    if result != 0:
                        error_msg = self.voicevox.voicevox_error_result_to_message(result)
                        if isinstance(error_msg, bytes):
                            try:
                                error_text = error_msg.decode('utf-8')
                            except UnicodeDecodeError:
                                error_text = str(error_msg)
                        else:
                            error_text = str(error_msg)
                        logger.error(f"[VOICEVOX] モデルオープンエラー: {model_file}: {error_text}")
                        continue

                    result = self.voicevox.voicevox_synthesizer_load_voice_model(
                        self.synthesizer,
                        model
                    )
                    if result != 0:
                        error_msg = self.voicevox.voicevox_error_result_to_message(result)
                        if isinstance(error_msg, bytes):
                            try:
                                error_text = error_msg.decode('utf-8')
                            except UnicodeDecodeError:
                                error_text = str(error_msg)
                        else:
                            error_text = str(error_msg)
                        logger.error(f"[VOICEVOX] モデルロードエラー: {model_file}: {error_text}")
                    else:
                        model_count += 1

                    self.voicevox.voicevox_voice_model_file_delete(model)
        except Exception as e:
            logger.error(f"[VOICEVOX] 初期化中に例外が発生: {e}")
            traceback.print_exc(file=sys.stdout)
            raise

    def get_audio(self):
        try:
            if self.voicevox is None or not self.synthesizer:
                self.init()

            text = self.text.encode('utf-8')
            output_wav_size = ctypes.c_size_t(0)
            output_wav = ctypes.POINTER(ctypes.c_ubyte)()

            tts_options = self.voicevox.voicevox_make_default_tts_options()

            result = self.voicevox.voicevox_synthesizer_tts(
                self.synthesizer,
                text,
                self.style_id,
                tts_options,
                ctypes.byref(output_wav_size),
                ctypes.byref(output_wav)
            )

            if result != 0:
                error_msg = self.voicevox.voicevox_error_result_to_message(result)
                logger.error(f"[VOICEVOX] 音声合成エラーコード: {result}, raw_msg={error_msg}")
                if isinstance(error_msg, bytes):
                    try:
                        error_text = error_msg.decode('utf-8')
                    except UnicodeDecodeError:
                        error_text = str(error_msg)
                else:
                    error_text = str(error_msg)
                raise RuntimeError(f"Failed to synthesize speech: {error_text}")

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                    self.temp_file = temp.name
                    buffer = ctypes.string_at(output_wav, output_wav_size.value)
                    temp.write(buffer)
                return self.temp_file
            except Exception as e:
                logger.error(f"[VOICEVOX] WAVファイル作成エラー: {e}")
                traceback.print_exc(file=sys.stdout)
                raise e
            finally:
                if output_wav:
                    try:
                        self.voicevox.voicevox_wav_free(output_wav)
                    except Exception as e:
                        logger.error(f"[VOICEVOX] 音声データ解放エラー: {e}")
        except Exception as e:
            logger.error(f"[VOICEVOX] 音声合成処理中に例外が発生: {e}")
            traceback.print_exc(file=sys.stdout)
            raise

    def __del__(self):
        Voicevox._reference_count -= 1
        if Voicevox._reference_count == 0:
            if hasattr(self, 'synthesizer') and self.synthesizer and hasattr(self, 'voicevox') and self.voicevox:
                try:
                    self.voicevox.voicevox_synthesizer_delete(self.synthesizer)
                    logger.info("[VOICEVOX] シンセサイザー解放完了")
                    Voicevox._voicevox_instance = None
                    Voicevox._voicevox_dll = None
                    Voicevox._synthesizer = None
                except Exception as e:
                    logger.error(f"[VOICEVOX] シンセサイザー解放エラー: {e}")
                    traceback.print_exc(file=sys.stdout)
