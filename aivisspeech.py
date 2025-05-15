import aiohttp
import aiofiles
from config import Config

class aivisspeech:
    def __init__(self, text: str, speaker: int):
        config = Config.load_config()
        self.url = config['aivisspeech']['url']
        self.params = {
            'text': text,
            'speaker': speaker
        }

    async def get_audio(self) -> str:
        async with aiohttp.ClientSession(self.url) as session:
            json_response = await session.post(
                '/audio_query',
                headers={
                    'Content-Type': 'application/json'
                },
                params=self.params
            )
            json_data = await json_response.json()
            if json_response.status != 200:
                raise Exception(f"audio_queryのリクエストに失敗しました: {json_data['detail'][0]['msg']}")
            del self.params['text']
            response = await session.post(
                '/synthesis',
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'audio/wav'
                },
                params=self.params,
                json=json_data
            )
            if response.status != 200:
                raise Exception(f"synthesisのリクエストに失敗しました: {await response.json()['detail'][0]['msg']}")
            content = await response.read()
            async with aiofiles.tempfile.NamedTemporaryFile(delete=False) as temp_file:
                await temp_file.write(content)
            return temp_file.name
