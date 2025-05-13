import os
import aiofiles
import platform
from pathlib import Path
from loguru import logger
from voicevox_core.asyncio import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile

class VoicevoxConfig:
    def get_default_config():
        base_dir = os.path.dirname(os.path.abspath(__file__))
        match platform.system().lower():
            case 'windows':
                onnxruntime_path = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib', 'voicevox_onnxruntime.dll')
            case 'linux':
                onnxruntime_path = os.path.join(base_dir, 'voicevox', 'onnxruntime', 'lib', 'libvoicevox_onnxruntime.so')
            case _:
                raise RuntimeError("サポートされていないオペレーティングシステムです")

        return {
            'vvm_path': os.path.join(base_dir, 'voicevox', 'models', 'vvms'),
            'onnxruntime_path': onnxruntime_path,
            'dict_dir': os.path.join(base_dir,'voicevox', 'dict', 'open_jtalk_dic_utf')
        }

class Voicevox:
    _instance = None
    _synthesizer = None
    _initialized = False

    def __init__(self, text, style_id=0):
        self.text = text
        self.style_id = int(style_id)
        self.config = VoicevoxConfig.get_default_config()
        self.temp_file = None

        if Voicevox._instance is None:
            Voicevox._instance = self

    @classmethod
    async def init(cls):
        if cls._instance is None:
            cls._instance = cls('', 0)

        if not cls._initialized:
            if cls._synthesizer is None:
                onnxruntime = await Onnxruntime.load_once(filename=cls._instance.config['onnxruntime_path'])
                open_jtalk = await OpenJtalk.new(cls._instance.config['dict_dir'])

                cls._synthesizer = Synthesizer(onnxruntime, open_jtalk)

            model_count = 0
            model_loaded = set()
            for model_file in Path(cls._instance.config['vvm_path']).glob('*.vvm'):
                try:
                    model_id = model_file.stem
                    if model_id not in model_loaded:
                        async with await VoiceModelFile.open(model_file) as model:
                            await cls._synthesizer.load_voice_model(model)
                        model_count += 1
                        model_loaded.add(model_id)
                except Exception as e:
                    logger.warning(f"モデル {model_file.name} の読み込みに失敗しました: {e}")
                    continue

            cls._initialized = True
            logger.success('Voicevoxの初期化に成功しました')

    async def get_audio(self):
        try:
            if Voicevox._synthesizer is None:
                raise RuntimeError('シンセサイザーが初期化されていません')

            wav = await Voicevox._synthesizer.tts(self.text, self.style_id)

            async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
                self.temp_file = temp.name
                await temp.write(wav)

            return self.temp_file

        except Exception as e:
            raise RuntimeError(e)
