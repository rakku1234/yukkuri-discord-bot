import asyncio
import dataclasses
import os
import aiofiles
import platform
from pathlib import Path
from loguru import logger
from voicevox_core.asyncio import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
from config import load_config

config = load_config()
debug_mode = config['debug']

@dataclasses.dataclass
class VoicevoxConfig:
    vvm_path: str = None
    onnxruntime_path: str = None
    dict_dir: str = None
    style_id: int = 0
    system: str = platform.system().lower()

    @staticmethod
    def get_default_config():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        match VoicevoxConfig.system:
            case 'windows':
                onnxruntime_path = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib', 'voicevox_onnxruntime.dll')
            case 'linux':
                onnxruntime_path = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib', 'libvoicevox_onnxruntime.so')
            case _:
                raise RuntimeError("サポートされていないオペレーティングシステムです")

        return VoicevoxConfig(os.path.join(base_dir, 'voicevox', 'models', 'vvms'), onnxruntime_path, os.path.join(base_dir, 'voicevox', 'dict', 'open_jtalk_dic_utf'))

class Voicevox:
    _instance = None
    _synthesizer = None
    _initialized = False
    _initializing = False
    _init_lock = asyncio.Lock()
    _model_loaded = set()

    def __init__(self, text, style_id=0):
        if debug_mode:
            logger.debug(f"インスタンス作成 - テキスト: {text}, スタイルID: {style_id}")
        self.text = text
        self.style_id = int(style_id)
        self.config = VoicevoxConfig.get_default_config()
        self.temp_file = None

        if Voicevox._instance is None:
            Voicevox._instance = self

    @classmethod
    async def init(cls):
        if debug_mode:
            logger.debug('初期化処理を開始')
        if cls._instance is None:
            cls._instance = cls('', 0)

        async with cls._init_lock:
            if not cls._initialized and not cls._initializing:
                cls._initializing = True
                try:
                    if cls._synthesizer is None:
                        if debug_mode:
                            logger.debug('シンセサイザーの初期化を開始')
                        onnxruntime = await Onnxruntime.load_once(filename=cls._instance.config.onnxruntime_path)
                        open_jtalk = await OpenJtalk.new(cls._instance.config.dict_dir)

                        cls._synthesizer = Synthesizer(onnxruntime, open_jtalk)
                        if debug_mode:
                            logger.debug('シンセサイザーの初期化が完了')

                    cls._model_loaded.clear()
                    model_count = 0
                    if debug_mode:
                        logger.debug('音声モデルの読み込みを開始')
                    for model_file in Path(cls._instance.config.vvm_path).glob('*.vvm'):
                        try:
                            model_id = model_file.stem
                            if model_id not in cls._model_loaded:
                                if debug_mode:
                                    logger.debug(f"モデル {model_file.name} の読み込みを開始")
                                async with await VoiceModelFile.open(model_file) as model:
                                    await cls._synthesizer.load_voice_model(model)
                                cls._model_loaded.add(model_id)
                                model_count += 1
                                if debug_mode:
                                    logger.debug(f"モデル {model_file.name} の読み込みが完了")
                        except Exception as e:
                            logger.warning(f"モデル {model_file.name} の読み込みに失敗しました: {e}")
                            continue

                    cls._initialized = True
                    if debug_mode:
                        logger.debug(f"初期化が完了 - 読み込んだモデル数: {model_count}")
                    logger.success('Voicevoxの初期化に成功しました')
                finally:
                    cls._initializing = False

    async def get_audio(self):
        try:
            if debug_mode:
                logger.debug(f"音声生成を開始 - テキスト: {self.text}, スタイルID: {self.style_id}")
            await Voicevox.init()
            if Voicevox._synthesizer is None:
                raise RuntimeError('シンセサイザーが初期化されていません')

            wav = await Voicevox._synthesizer.tts(self.text, self.style_id)
            if debug_mode:
                logger.debug('音声生成が完了')

            async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                await temp.write(wav)
                if debug_mode:
                    logger.debug(f"一時ファイルを作成 - {self.temp_file}")

            return self.temp_file

        except Exception as e:
            if debug_mode:
                logger.debug(f"音声生成でエラーが発生 - {str(e)}")
            raise RuntimeError(e)
