import json
import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')

    try:
        with open(config_path, encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"設定ファイルの形式が正しくありません: {config_path}")
