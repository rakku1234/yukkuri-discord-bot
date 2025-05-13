import json
import os
import aiofiles
from typing import Dict, Any

class Config:
    _config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    _ERROR_MESSAGES = {
        'file_not_found': "設定ファイルが見つかりません: {}",
        'invalid_format': "設定ファイルの形式が正しくありません: {}"
    }

    @classmethod
    def _handle_config_errors(cls, error: Exception) -> None:
        if isinstance(error, FileNotFoundError):
            raise FileNotFoundError(cls._ERROR_MESSAGES['file_not_found'].format(cls._config_path))
        if isinstance(error, json.JSONDecodeError):
            raise ValueError(cls._ERROR_MESSAGES['invalid_format'].format(cls._config_path))
        raise error

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        try:
            with open(cls._config_path, encoding='utf-8') as f:
                return json.loads(f.read())
        except Exception as e:
            cls._handle_config_errors(e)

    @classmethod
    async def async_load_config(cls) -> Dict[str, Any]:
        try:
            async with aiofiles.open(cls._config_path, encoding='utf-8') as f:
                return json.loads(await f.read())
        except Exception as e:
            cls._handle_config_errors(e)
