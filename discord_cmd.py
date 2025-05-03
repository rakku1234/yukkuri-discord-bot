import discord
import json
from discord import app_commands
from database import Database
from vc import update_voice_settings, message_queues, reading_tasks
from loguru import logger

db = Database()

def load_voice_characters() -> list[dict]:
    try:
        with open('voice_character.json', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except Exception:
        logger.error("音声キャラクターの設定を読み込めませんでした")
        return []

async def ensure_db_connection():
    if db.pool is None:
        await db.connect()

def setup_commands(tree: app_commands.CommandTree):
    @tree.command(name='join', description='ボイスチャンネルに参加')
    async def join(interaction: discord.Interaction):
        await ensure_db_connection()

        if interaction.user.voice is None:
            await interaction.response.send_message('ボイスチャンネルに接続していません。', ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        try:
            await voice_channel.connect(self_deaf=True)
            await interaction.response.send_message(f"{voice_channel.name}に参加しました！このチャンネルのメッセージを読み上げます。")

            await db.set_read_channel(interaction.guild_id, voice_channel.id, interaction.channel_id)
        except discord.ClientException:
            await interaction.response.send_message('すでにボイスチャンネルに接続しています。', ephemeral=True)

    @tree.command(name='leave', description='ボイスチャンネルから退出')
    async def leave(interaction: discord.Interaction):
        await ensure_db_connection()

        if interaction.guild.voice_client is None:
            await interaction.response.send_message('ボイスチャンネルに接続していません。', ephemeral=True)
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

            await interaction.response.send_message('ボイスチャンネルから退出しました！読み上げを停止しました。')
        except discord.ClientException:
            await interaction.response.send_message('ボイスチャンネルから退出できませんでした。', ephemeral=True)

    autojoin_group = app_commands.Group(name='autojoin', description='自動参加機能の設定')

    @autojoin_group.command(name='add', description='自動参加するボイスチャンネルと読み上げるテキストチャンネルを設定します')
    @app_commands.describe(
        voice='参加するボイスチャンネル',
        text='読み上げるテキストチャンネル'
    )
    async def autojoin_add(
        interaction: discord.Interaction,
        voice: discord.VoiceChannel,
        text: discord.TextChannel
    ):
        await ensure_db_connection()

        try:
            await db.set_autojoin(interaction.guild_id, voice.id, text.id)
            await interaction.response.send_message(f"自動参加設定を更新しました。\n"f"ボイスチャンネル: {voice.name}\n"f"テキストチャンネル: {text.name}",)
        except Exception as e:
            await interaction.response.send_message(f"設定の更新に失敗しました: {str(e)}")

    @autojoin_group.command(name='remove', description='自動参加設定を削除します')
    async def autojoin_remove(interaction: discord.Interaction):
        await ensure_db_connection()

        try:
            await db.remove_autojoin(interaction.guild_id)
            await interaction.response.send_message('自動参加設定を削除しました。')
        except Exception as e:
            await interaction.response.send_message(f"設定の削除に失敗しました: {str(e)}")

    @autojoin_group.command(name='get', description='現在の自動参加設定を表示します')
    async def autojoin_get(interaction: discord.Interaction):
        await ensure_db_connection()

        autojoin = await db.get_autojoin(interaction.guild_id)
        if not autojoin:
            await interaction.response.send_message('自動参加設定はありません。')
            return

        voice_channel = interaction.guild.get_channel(autojoin[0])
        text_channel = interaction.guild.get_channel(autojoin[1])

        if not voice_channel or not text_channel:
            await interaction.response.send_message('設定されたチャンネルが見つかりません。', ephemeral=True)
            return

        await interaction.response.send_message(f"現在の自動参加設定:\n"f"ボイスチャンネル: {voice_channel.name}\n"f"テキストチャンネル: {text_channel.name}",)

    tree.add_command(autojoin_group)

    voice_characters = load_voice_characters()

    @tree.command(name='setvoice', description='ボイスキャラクターと読み上げ速度を設定します')
    @app_commands.describe(
        engine='音声エンジンの選択',
        voice='声の指定',
        speed='読み上げ速度（デフォルト: 100）'
    )
    @app_commands.choices(
        engine=[
            app_commands.Choice(name='AquesTalk1', value='aquestalk1'),
            app_commands.Choice(name='AquesTalk2', value='aquestalk2'),
            app_commands.Choice(name='VOICEVOX', value='voicevox')
        ]
    )
    async def setvoice(
        interaction: discord.Interaction,
        engine: str,
        voice: str,
        speed: int = 100
    ):
        await ensure_db_connection()

        if speed < 50 or speed > 200:
            await interaction.response.send_message('速度は50から200の間で指定してください。', ephemeral=True)
            return

        match engine:
            case 'aquestalk1':
                valid_voices = [v['value'] for v in voice_characters['AquesTalk1']]
                if voice not in valid_voices:
                    await interaction.response.send_message('無効なAquesTalk1の音声が指定されました。', ephemeral=True)
                    return
            case 'aquestalk2':
                valid_voices = [v['value'] for v in voice_characters['AquesTalk2']]
                if voice not in valid_voices:
                    await interaction.response.send_message('無効なAquesTalk2の音声が指定されました。', ephemeral=True)
                    return
            case 'voicevox':
                valid_voices = [v['value'] for v in voice_characters['voicevox']]
                if voice not in valid_voices:
                    await interaction.response.send_message('無効なVOICEVOXの音声が指定されました。', ephemeral=True)
                    return

        try:
            await db.set_voice_settings(interaction.guild_id, interaction.user.id, voice, speed, engine)
            await update_voice_settings(interaction.guild_id, interaction.user.id, voice, speed, engine)

            voice_name = ''
            match engine:
                case 'aquestalk1':
                    for v in voice_characters['AquesTalk1']:
                        if v['value'] == voice:
                            voice_name = v['name']
                            break
                case 'aquestalk2':
                    for v in voice_characters['AquesTalk2']:
                        if v['value'] == voice:
                            voice_name = v['name']
                            break
                case 'voicevox':
                    for v in voice_characters['voicevox']:
                        if v['value'] == voice:
                            voice_name = v['name']
                            break

            await interaction.response.send_message(
                f"ボイス設定を更新しました。\n"
                f"エンジン: {engine}\n"
                f"キャラクター: {voice_name}\n"
                f"速度: {speed}"
            )
        except Exception as e:
            await interaction.response.send_message(f"設定の更新に失敗しました: {str(e)}")

    @setvoice.autocomplete('voice')
    async def voice_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        engine = interaction.namespace.engine
        if not engine:
            return []

        match engine:
            case 'aquestalk1':
                voices = voice_characters['AquesTalk1']
            case 'aquestalk2':
                voices = voice_characters['AquesTalk2']
            case 'voicevox':
                voices = voice_characters['voicevox']

        choices = [
            app_commands.Choice(name=voice['name'], value=voice['value'])
            for voice in voices
            if current.lower() in voice['name'].lower()
        ]
        return choices[:25]

    @tree.command(name='skip', description='現在の読み上げを停止します')
    async def skip(interaction: discord.Interaction):
        if interaction.guild.voice_client is None:
            await interaction.response.send_message('ボイスチャンネルに接続していません。', ephemeral=True)
            return

        voice_client = interaction.guild.voice_client
        if not voice_client.is_playing():
            await interaction.response.send_message('現在読み上げ中の音声はありません。', ephemeral=True)
            return

        voice_client.stop()
        await interaction.response.send_message('読み上げを停止しました。')

    dict_group = app_commands.Group(name='dict', description='辞書機能の設定')

    @dict_group.command(name='add', description='単語の読み方を登録します')
    @app_commands.describe(
        word='登録する単語',
        to='変換後の読み方'
    )
    async def dict_add(
        interaction: discord.Interaction,
        word: str,
        to: str
    ):
        await ensure_db_connection()

        try:
            await db.set_dictionary_replacement(interaction.guild_id, word, to)
            await interaction.response.send_message(f"単語を登録しました。\n「{word}」→「{to}」")
        except Exception as e:
            await interaction.response.send_message(f"単語の登録に失敗しました: {str(e)}", ephemeral=True)

    @dict_group.command(name='list', description='登録されている単語の一覧を表示します')
    async def dict_list(interaction: discord.Interaction):
        await ensure_db_connection()

        try:
            replacements = await db.get_dictionary_replacements(interaction.guild_id)

            if not replacements:
                await interaction.response.send_message('登録されている単語はありません。', ephemeral=True)
                return

            message = "登録されている単語一覧:\n"
            for original, replacement in replacements.items():
                message += f"- 「{original}」→「{replacement}」\n"

            await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"単語一覧の取得に失敗しました: {str(e)}", ephemeral=True)

    @dict_group.command(name='remove', description='登録されている単語を削除します')
    @app_commands.describe(
        word='削除する単語'
    )
    async def dict_remove(
        interaction: discord.Interaction,
        word: str
    ):
        await ensure_db_connection()

        try:
            replacements = await db.get_dictionary_replacements(interaction.guild_id)
            if word not in replacements:
                await interaction.response.send_message(f"単語「{word}」は登録されていません。", ephemeral=True)
                return

            await db.remove_dictionary_replacement(interaction.guild_id, word)
            await interaction.response.send_message(f"単語「{word}」を削除しました。")
        except Exception as e:
            await interaction.response.send_message(f"単語の削除に失敗しました: {str(e)}", ephemeral=True)

    tree.add_command(dict_group)
