import asyncio
import dataclasses
import multiprocessing
import os
import tempfile
import platform
from pathlib import Path
from loguru import logger
from voicevox_core.asyncio import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

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
        if VoicevoxConfig.system == 'windows':
            onnxruntime_path = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib', 'voicevox_onnxruntime.dll')
        elif VoicevoxConfig.system == 'linux':
            onnxruntime_path = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib', 'libvoicevox_onnxruntime.so')
        else:
            raise RuntimeError("サポートされていないオペレーティングシステムです")

        return VoicevoxConfig(
            vvm_path=os.path.join(base_dir, 'voicevox', 'models', 'vvms'),
            onnxruntime_path=onnxruntime_path,
            dict_dir=os.path.join(base_dir, 'voicevox', 'dict', 'open_jtalk_dic_utf'),
        )

class Voicevox:
    _instance = None
    _synthesizer = None
    _initialized = False
    _initializing = False
    _init_lock = asyncio.Lock()

    def __init__(self, text, style_id=0, config=None):
        self.text = text
        self.style_id = int(style_id)
        self.config = config or VoicevoxConfig.get_default_config()
        self.temp_file = None

        if Voicevox._instance is None:
            Voicevox._instance = self

    @classmethod
    async def ensure_initialized(cls):
        if not cls._initialized and not cls._initializing:
            async with cls._init_lock:
                if not cls._initialized and not cls._initializing:
                    cls._initializing = True
                    try:
                        await cls._instance.init()
                        cls._initialized = True
                    finally:
                        cls._initializing = False

    async def init(self):
        try:
            onnxruntime = await Onnxruntime.load_once(filename=self.config.onnxruntime_path)
            open_jtalk = await OpenJtalk.new(self.config.dict_dir)

            Voicevox._synthesizer = Synthesizer(
                onnxruntime,
                open_jtalk,
                cpu_num_threads=max(multiprocessing.cpu_count(), 2)
            )

            model_count = 0
            for model_file in Path(self.config.vvm_path).glob("*.vvm"):
                async with await VoiceModelFile.open(model_file) as model:
                    await Voicevox._synthesizer.load_voice_model(model)
                model_count += 1

        except Exception:
            Voicevox._synthesizer = None
            Voicevox._initialized = False
            raise

    async def get_audio(self):
        try:
            await Voicevox.ensure_initialized()
            if Voicevox._synthesizer is None:
                raise RuntimeError("シンセサイザーが初期化されていません")

            audio_query = await Voicevox._synthesizer.create_audio_query(self.text, self.style_id)
            wav = await Voicevox._synthesizer.synthesis(audio_query, self.style_id)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                temp.write(wav)

            return self.temp_file

        except Exception as e:
            logger.error(f"音声合成中にエラーが発生: {e}")
            raise

    #@classmethod
    #def cleanup(cls):
    #    cls._instance = None
    #    cls._synthesizer = None
    #    cls._initialized = False
    #    cls._initializing = False
