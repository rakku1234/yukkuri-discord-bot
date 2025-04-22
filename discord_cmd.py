import discord
from discord import app_commands
from database import Database

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
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("ボイスチャンネルから退出しました！読み上げを停止しました。")

            await db.remove_read_channel(interaction.guild_id)
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
