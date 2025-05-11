# discord読み上げbot

discord.pyを利用しています

python3.12でテスト済み

## 使用している合成音声エンジン
- [AquesTalk1](https://www.a-quest.com/products/aquestalk_1.html)
- [AquesTalk2](https://www.a-quest.com/products/aquestalk_2.html)
- [AqKanji2Koe](https://www.a-quest.com/products/aqkanji2koe.html)
- [VoiceVox](https://voicevox.hiroshiba.jp/)
- [AivisSpeech](https://aivis-project.com/)

合成音声エンジン、ボイスキャラクターの利用規約に従って使用してください

AquesTalk1, AquesTalk2, AqKanji2Koeのライセンス認証は[これを](https://github.com/rakku1234/yukkuri-discord-bot/tree/aquest-license)使用すればできると思います

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
