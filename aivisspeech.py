import aiohttp
import aiofiles
from config import Config
from loguru import logger

class aivisspeech:
    def __init__(self, text: str, speaker: int):
        config = Config.load_config()
        self.url = config['aivisspeech']['url']
        self.params = {
            'text': text,
            'speaker': speaker
        }

    async def get_audio(self) -> str:
        async with aiohttp.ClientSession() as session:
            json_response = await session.post(
                f"{self.url}/audio_query",
                headers={
                    'Content-Type': 'application/json'
                },
                params=self.params
            )
            json_data = await json_response.json()
            if json_response.status != 200:
                raise Exception(f"audio_queryのリクエストに失敗しました: {json_data['detail'][0]['msg']}")
            response = await session.post(
                f"{self.url}/synthesis",
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'audio/wav'
                },
                params={'speaker': self.params['speaker']},
                json=json_data
            )
            if response.status != 200:
                logger.error(await response.json())
                error_data = await response.json()
                raise Exception(f"synthesisのリクエストに失敗しました: {error_data['detail'][0]['msg']}")
            content = await response.read()
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
                await temp_file.write(content)
            return temp_file.name
