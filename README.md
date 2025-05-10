# discord読み上げbot

discord.pyを利用しています

python3.12でテスト済み

## 使用している合成音声エンジン
- [AquesTalk1](https://www.a-quest.com/products/aquestalk_1.html)
- [AquesTalk2](https://www.a-quest.com/products/aquestalk_2.html)
- [VoiceVox](https://voicevox.hiroshiba.jp/)
- [SHAREVOX](https://www.sharevox.app/)

デフォルトではvoicevoxを使用します

## インストール方法

```
windowsの場合
pip install -r windows-requirements.txt
linuxの場合
pip install -r linux-requirements.txt
```

https://github.com/VOICEVOX/voicevox_core/releases
からダウンローダを使って、voicevoxフォルダに必要なファイルを入れてください

ダウンローダを使わずにvoicevoxフォルダに必要なファイルの入れ方

- [lib(voicevox_core)](https://github.com/VOICEVOX/voicevox_core)
- [onnxruntime](https://github.com/VOICEVOX/onnxruntime-builder)
- [models(vvm)](https://github.com/VOICEVOX/voicevox_vvm)
- [dict(open_jtalk)](https://github.com/r9y9/open_jtalk)

`config-example.json`から`config.json`に名前を変更し、
tokenにdiscord botのトークンを入れる

### 起動方法

```
python main.py
```
