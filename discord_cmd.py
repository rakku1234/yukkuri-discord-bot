import discord
import json
from discord import app_commands
from database import Database
from vc import update_voice_settings, message_queues, reading_tasks
from loguru import logger
from config import Config
from typing import Dict, List, Tuple

db = Database()
engine_key = {
    'aquestalk1': 'AquesTalk1',
    'aquestalk2': 'AquesTalk2',
    'voicevox': 'voicevox',
    'aivisspeech': 'aivisspeech'
}

def load_voice_characters() -> List[Dict]:
    try:
        with open('voice_character.json', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception:
        logger.error('音声キャラクターの設定を読み込めませんでした')
        return []

async def ensure_db_connection():
    if db.pool is None:
        await db.connect()

def setup_commands(tree: app_commands.CommandTree):
    @tree.command(name='join', description='ボイスチャンネルに参加')
    async def join(interaction: discord.Interaction):
        await ensure_db_connection()

        if interaction.user.voice is None:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='ボイスチャンネルに接続していません。'), ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        try:
            await voice_channel.connect(self_deaf=True)
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.green(), description=f"{voice_channel.name}に参加しました！このチャンネルのメッセージを読み上げます。"))

            await db.set_read_channel(interaction.guild_id, voice_channel.id, interaction.channel_id)
        except discord.ClientException:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='すでにボイスチャンネルに接続しています。'), ephemeral=True)

    @tree.command(name='leave', description='ボイスチャンネルから退出')
    async def leave(interaction: discord.Interaction):
        await ensure_db_connection()

        if interaction.guild.voice_client is None:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='ボイスチャンネルに接続していません。'), ephemeral=True)
            return

        try:
            if interaction.guild_id in message_queues:
                await message_queues[interaction.guild_id].put(None)
                if interaction.guild_id in reading_tasks and not reading_tasks[interaction.guild_id].done():
                    await reading_tasks[interaction.guild_id]
                if interaction.guild_id in reading_tasks:
                    del reading_tasks[interaction.guild_id]
                del message_queues[interaction.guild_id]
            await interaction.guild.voice_client.disconnect()
            await db.remove_read_channel(interaction.guild_id)

            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.green(), description='ボイスチャンネルから退出しました！'))
        except discord.ClientException:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='ボイスチャンネルから退出できませんでした。'), ephemeral=True)

    autojoin_group = app_commands.Group(name='autojoin', description='自動参加機能の設定')

    @autojoin_group.command(name='add', description='自動参加するボイスチャンネルと読み上げるテキストチャンネルを設定します')
    @app_commands.describe(voice='参加するボイスチャンネル', text='読み上げるテキストチャンネル')
    async def autojoin_add(interaction: discord.Interaction, voice: discord.VoiceChannel, text: discord.TextChannel):
        await ensure_db_connection()

        try:
            await db.set_autojoin(interaction.guild_id, voice.id, text.id)
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.green(), description=f"自動参加設定を更新しました。\n"f"ボイスチャンネル: {voice.name}\n"f"テキストチャンネル: {text.name}"))
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"設定の更新に失敗しました: {str(e)}"))

    @autojoin_group.command(name='remove', description='自動参加設定を削除します')
    @app_commands.describe(voice='削除するボイスチャンネル')
    async def autojoin_remove(interaction: discord.Interaction, voice: discord.VoiceChannel):
        await ensure_db_connection()

        try:
            autojoin = await db.get_autojoin(interaction.guild_id)
            if not autojoin:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.dark_orange(), description='自動参加設定はありません。'), ephemeral=True)
                return

            if voice.id != autojoin[0]:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f'指定されたボイスチャンネル {voice.name} の自動参加設定はありません。'), ephemeral=True)
                return

            await db.remove_autojoin(interaction.guild_id)
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.green(), description=f'ボイスチャンネル {voice.name} の自動参加設定を削除しました。'))
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"設定の削除に失敗しました: {str(e)}"))

    @autojoin_group.command(name='list', description='現在の自動参加設定一覧を表示します')
    async def autojoin_list(interaction: discord.Interaction):
        await ensure_db_connection()

        autojoin = await db.get_autojoin(interaction.guild_id)
        if not autojoin:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.dark_orange(), description='自動参加設定はありません。'), ephemeral=True)
            return

        voice_channel = interaction.guild.get_channel(autojoin[0])
        text_channel = interaction.guild.get_channel(autojoin[1])

        if not voice_channel or not text_channel:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='設定されたチャンネルが見つかりません。'), ephemeral=True)
            return

        await interaction.response.send_message(embed=discord.Embed(color=discord.Color.green(), description=f"現在の自動参加設定:\nボイスチャンネル: {voice_channel.name}\nテキストチャンネル: {text_channel.name}"))

    tree.add_command(autojoin_group)

    voice_characters = load_voice_characters()

    @tree.command(name='setvoice', description='ボイスキャラクターと読み上げ速度を設定します')
    @app_commands.describe(
        engine='音声エンジンの選択',
        voice='声の指定',
        speed='読み上げ速度（AquesTalk: 50-200, VOICEVOX/AivisSpeech: 0.5-5）'
    )
    @app_commands.choices(
        engine=[
            app_commands.Choice(name='AquesTalk1', value='aquestalk1'),
            app_commands.Choice(name='AquesTalk2', value='aquestalk2'),
            app_commands.Choice(name='VOICEVOX', value='voicevox'),
            app_commands.Choice(name='AivisSpeech', value='aivisspeech')
        ]
    )
    async def setvoice(interaction: discord.Interaction, engine: str, voice: str, speed: float = 1.0):
        await ensure_db_connection()

        if engine.startswith('aquestalk'):
            if speed == 1.0:
                speed = 100
            if speed < 50 or speed > 200:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='AquesTalkの速度は50から200の間で指定してください。'), ephemeral=True)
                return
        else:
            if speed < 0.5 or speed > 5:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='VOICEVOX/AivisSpeechの速度は0.5から10の間で指定してください。'), ephemeral=True)
                return

        config = await Config.async_load_config()

        match engine:
            case 'aquestalk1':
                is_valid, error_message = validate_voice_engine(engine, voice, config, voice_characters)
                if not is_valid:
                    await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=error_message), ephemeral=True)
                    return
            case 'aquestalk2':
                is_valid, error_message = validate_voice_engine(engine, voice, config, voice_characters)
                if not is_valid:
                    await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=error_message), ephemeral=True)
                    return
            case 'voicevox':
                is_valid, error_message = validate_voice_engine(engine, voice, config, voice_characters)
                if not is_valid:
                    await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=error_message), ephemeral=True)
                    return
            case 'aivisspeech':
                is_valid, error_message = validate_voice_engine(engine, voice, config, voice_characters)
                if not is_valid:
                    await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=error_message), ephemeral=True)
                    return

        try:
            await db.set_voice_settings(interaction.guild_id, interaction.user.id, voice, speed, engine)
            await update_voice_settings(interaction.guild_id, interaction.user.id, voice, speed, engine)

            voice_name = get_voice_name(engine, voice, voice_characters)

            message = (
                f"ボイス設定を更新しました。\n"
                f"エンジン: {engine}\n"
                f"キャラクター: {voice_name}\n"
                f"速度: {speed}\n"
            )
            if engine == 'voicevox':
                message += f"VOICEVOX: {voice_name}"

            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.blue(), description=message))
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"設定の更新に失敗しました: {str(e)}"))

    @setvoice.autocomplete('voice')
    async def voice_autocomplete(interaction: discord.Interaction, current: str,) -> List[app_commands.Choice[str]]:
        engine = interaction.namespace.engine
        if not engine:
            return []

        voices = voice_characters[engine_key[engine]]
        choices = [
            app_commands.Choice(name=voice['name'], value=voice['value'])
            for voice in voices
            if current.lower() in voice['name'].lower()
        ]
        return choices[:25]

    @tree.command(name='skip', description='現在の読み上げを停止します')
    async def skip(interaction: discord.Interaction):
        if interaction.guild.voice_client is None:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description='ボイスチャンネルに接続していません。'), ephemeral=True)
            return

        voice_client = interaction.guild.voice_client
        if not voice_client.is_playing():
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.dark_orange(), description='現在読み上げ中の音声はありません。'), ephemeral=True)
            return

        voice_client.stop()
        await interaction.response.send_message(embed=discord.Embed(color=discord.Color.green(), description='読み上げを停止しました。'))

    dict_group = app_commands.Group(name='dict', description='辞書機能の設定')

    @dict_group.command(name='add', description='単語の読み方を登録します')
    @app_commands.describe(word='登録する単語', to='変換後の読み方')
    async def dict_add(interaction: discord.Interaction, word: str, to: str):
        await ensure_db_connection()

        try:
            await db.set_dictionary_replacement(interaction.guild_id, word, to)
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.blue(), description=f"単語を登録しました。\n「{word}」→「{to}」"))
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"単語の登録に失敗しました: {str(e)}"), ephemeral=True)

    @dict_group.command(name='list', description='登録されている単語の一覧を表示します')
    async def dict_list(interaction: discord.Interaction):
        await ensure_db_connection()

        try:
            replacements = await db.get_dictionary_replacements(interaction.guild_id)

            if not replacements:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.dark_orange(), description='登録されている単語はありません。'), ephemeral=True)
                return

            message = "登録されている単語一覧:\n"
            for original, replacement in replacements.items():
                message += f"- 「{original}」→「{replacement}」\n"

            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.purple(), description=message), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"単語一覧の取得に失敗しました: {str(e)}"), ephemeral=True)

    @dict_group.command(name='remove', description='登録されている単語を削除します')
    @app_commands.describe(word='削除する単語')
    async def dict_remove(interaction: discord.Interaction, word: str):
        await ensure_db_connection()

        try:
            replacements = await db.get_dictionary_replacements(interaction.guild_id)
            if word not in replacements:
                await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"単語「{word}」は登録されていません。"), ephemeral=True)
                return

            await db.remove_dictionary_replacement(interaction.guild_id, word)
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.purple(), description=f"単語「{word}」を削除しました。"))
        except Exception as e:
            await interaction.response.send_message(embed=discord.Embed(color=discord.Color.red(), description=f"単語の削除に失敗しました: {str(e)}"), ephemeral=True)

    tree.add_command(dict_group)

def validate_voice_engine(engine: str, voice: str, config: Dict, voice_characters: Dict) -> Tuple[bool, str]:
    if not config['engine_enabled'][engine]:
        return False, f'{engine}は無効になっています。'
    valid_voices = [v['value'] for v in voice_characters[engine_key[engine]]]
    if voice not in valid_voices:
        return False, f'無効な{engine}の音声が指定されました。'
    return True, ''

def get_voice_name(engine: str, voice: str, voice_characters: Dict) -> str:
    for v in voice_characters[engine_key[engine]]:
        if v['value'] == voice:
            return v['name']
    return ''
