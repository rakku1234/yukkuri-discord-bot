import aiofiles
from voicevox import voicevox

class aivisspeech(voicevox):
    def __init__(self, text: str, speaker: int):
        super().__init__(text, speaker)
        self.url = self.config['aivisspeech']['url']
        self.params = {
            'text': text,
            'speaker': speaker
        }

    async def get_audio(self) -> str:
        try:
            wav = await self._get_engine()
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
                await temp_file.write(wav)
            return temp_file.name
        except Exception as e:
            raise RuntimeError(e)
