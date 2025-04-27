import discord
from discord import app_commands
from database import Database
from vc import update_voice_settings, message_queues, reading_tasks

db = Database()

async def ensure_db_connection():
    if db.pool is None:
        await db.connect()

def setup_commands(tree: app_commands.CommandTree):
    @tree.command(name="join", description="ボイスチャンネルに参加し、テキストチャンネルのメッセージを読み上げます")
    async def join(interaction: discord.Interaction):
        await ensure_db_connection()

        if interaction.user.voice is None:
            await interaction.response.send_message("ボイスチャンネルに接続していません。", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel
        try:
            await voice_channel.connect(self_deaf=True)
            await interaction.response.send_message(f"{voice_channel.name}に参加しました！このチャンネルのメッセージを読み上げます。")

            await db.set_read_channel(interaction.guild_id, interaction.channel_id)
        except discord.ClientException:
            await interaction.response.send_message("すでにボイスチャンネルに接続しています。", ephemeral=True)

    @tree.command(name="leave", description="ボイスチャンネルから退出し、読み上げを停止します")
    async def leave(interaction: discord.Interaction):
        await ensure_db_connection()

        if interaction.guild.voice_client is None:
            await interaction.response.send_message("ボイスチャンネルに接続していません。", ephemeral=True)
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

            await interaction.response.send_message("ボイスチャンネルから退出しました！読み上げを停止しました。")
        except discord.ClientException:
            await interaction.response.send_message("ボイスチャンネルから退出できませんでした。", ephemeral=True)

    @tree.command(name="get_read_channels", description="読み上げ対象のチャンネルを取得します")
    async def get_read_channels(interaction: discord.Interaction):
        await ensure_db_connection()

        channels = await db.get_read_channels()

        if not channels:
            await interaction.response.send_message("読み上げ対象のチャンネルはありません。", ephemeral=True)
            return

        message = "読み上げ対象のチャンネル:\n"
        for server_id, chat_channel in channels.items():
            server = interaction.client.get_guild(server_id)
            if server:
                channel = server.get_channel(chat_channel)
                if channel:
                    message += f"- {server.name}: {channel.name}\n"

        await interaction.response.send_message(message, ephemeral=True)

    @tree.command(name="autojoin", description="自動参加するボイスチャンネルと読み上げるテキストチャンネルを設定します")
    @app_commands.describe(
        voice="参加するボイスチャンネル",
        text="読み上げるテキストチャンネル"
    )
    async def autojoin(
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

    @tree.command(name="remove_autojoin", description="自動参加設定を削除します")
    async def remove_autojoin(interaction: discord.Interaction):
        from vc import db
        await ensure_db_connection()

        try:
            await db.remove_autojoin(interaction.guild_id)
            await interaction.response.send_message("自動参加設定を削除しました。")
        except Exception as e:
            await interaction.response.send_message(f"設定の削除に失敗しました: {str(e)}")

    @tree.command(name="get_autojoin", description="現在の自動参加設定を表示します")
    async def get_autojoin(interaction: discord.Interaction):
        await ensure_db_connection()

        autojoin = await db.get_autojoin(interaction.guild_id)
        if not autojoin:
            await interaction.response.send_message("自動参加設定はありません。")
            return

        voice_channel = interaction.guild.get_channel(autojoin[0])
        text_channel = interaction.guild.get_channel(autojoin[1])

        if not voice_channel or not text_channel:
            await interaction.response.send_message("設定されたチャンネルが見つかりません。", ephemeral=True)
            return

        await interaction.response.send_message(f"現在の自動参加設定:\n"f"ボイスチャンネル: {voice_channel.name}\n"f"テキストチャンネル: {text_channel.name}",)

    @tree.command(name="setvoice", description="ボイスキャラクターと読み上げ速度を設定します")
    @app_commands.describe(
        voice="声の指定",
        speed="読み上げ速度（デフォルト: 100）"
    )
    @app_commands.choices(voice=[
        app_commands.Choice(name="f1", value="f1"),
        app_commands.Choice(name="f2", value="f2"),
        app_commands.Choice(name="imd1", value="diva"),
        app_commands.Choice(name="igr", value="igr"),
        app_commands.Choice(name="m1", value="m1"),
        app_commands.Choice(name="m2", value="m2"),
        app_commands.Choice(name="r1", value="r1"),
    ])
    async def setvoice(
        interaction: discord.Interaction,
        voice: str,
        speed: int = 100
    ):
        await ensure_db_connection()

        if speed < 50 or speed > 200:
            await interaction.response.send_message("速度は50から200の間で指定してください。", ephemeral=True)
            return

        try:
            await db.set_voice_settings(interaction.guild_id, interaction.user.id, voice, speed)
            await update_voice_settings(interaction.guild_id, interaction.user.id, voice, speed)
            await interaction.response.send_message(f"ボイス設定を更新しました。\n"f"キャラクター: {voice}\n"f"速度: {speed}")
        except Exception as e:
            await interaction.response.send_message(f"設定の更新に失敗しました: {str(e)}")

    @tree.command(name="skip", description="現在の読み上げを停止します")
    async def skip(interaction: discord.Interaction):
        if interaction.guild.voice_client is None:
            await interaction.response.send_message("ボイスチャンネルに接続していません。", ephemeral=True)
            return

        voice_client = interaction.guild.voice_client
        if not voice_client.is_playing():
            await interaction.response.send_message("現在読み上げ中の音声はありません。", ephemeral=True)
            return

        voice_client.stop()
        await interaction.response.send_message("読み上げを停止しました。")

    dict_group = app_commands.Group(name="dict", description="辞書機能の設定")

    @dict_group.command(name="add", description="単語の読み方を登録します")
    @app_commands.describe(
        word="登録する単語",
        to="変換後の読み方"
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

    @dict_group.command(name="list", description="登録されている単語の一覧を表示します")
    async def dict_list(interaction: discord.Interaction):
        await ensure_db_connection()

        try:
            replacements = await db.get_dictionary_replacements(interaction.guild_id)

            if not replacements:
                await interaction.response.send_message("登録されている単語はありません。", ephemeral=True)
                return

            message = "登録されている単語一覧:\n"
            for original, replacement in replacements.items():
                message += f"- 「{original}」→「{replacement}」\n"

            await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"単語一覧の取得に失敗しました: {str(e)}", ephemeral=True)

    @dict_group.command(name="remove", description="登録されている単語を削除します")
    @app_commands.describe(
        word="削除する単語"
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
