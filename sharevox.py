import aiofiles
from sharevox_core import SharevoxCore

class Sharevox:
    _instance = None
    _initialized = False
    _sharevox = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, text: str = "", style_id: int = 0):
        self.text = text
        self.style_id = style_id

    @classmethod
    def init(cls):
        if not cls._initialized:
            cls._sharevox = SharevoxCore('sharevox/models', load_all_models=True, open_jtalk_dict_dir='sharevox/dict/open_jtalk_dic_utf')
            cls._initialized = True

    async def get_audio(self) -> str:
        if not self._initialized:
            self.init()
            
        wav = self._sharevox.tts(self.text, self.style_id)
        async with aiofiles.tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp:
            self.temp_file = temp.name
            await temp.write(wav)

        return self.temp_file
