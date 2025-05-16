import aiomysql
import aiosqlite
import discord
from typing import Dict, Tuple
from config import Config

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.pool = None
            cls._instance.connection = None
            cls._instance.config = Config.load_config()
        return cls._instance

    async def connect(self) -> None:
        db_config = self.config['database']
        connection_type = db_config.get('connection', 'mysql')

        if connection_type == 'sqlite':
            self.connection = await aiosqlite.connect(db_config.get('database', 'bot.db'))
            await self.create_tables_sqlite()
        else:
            db_config = {
                'host': db_config['host'],
                'user': db_config['user'],
                'password': db_config['password'],
                'db': db_config['database'],
                'port': db_config['port']
            }
            self.pool = await aiomysql.create_pool(**db_config)
            await self.create_tables_mysql()

    async def create_tables_sqlite(self) -> None:
        async with self.connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS read_channels (
                    server_id INTEGER PRIMARY KEY,
                    voice_channel INTEGER NOT NULL,
                    chat_channel INTEGER NOT NULL
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS autojoin (
                    server_id INTEGER PRIMARY KEY,
                    voice_channel INTEGER NOT NULL,
                    text_channel INTEGER NOT NULL
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_settings (
                    server_id INTEGER,
                    user_id INTEGER,
                    voice_name TEXT NOT NULL,
                    speed INTEGER NOT NULL DEFAULT 100,
                    engine TEXT NOT NULL DEFAULT 'voicevox',
                    PRIMARY KEY (server_id, user_id)
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS dictionary_replacements (
                    server_id INTEGER NOT NULL,
                    original_text TEXT NOT NULL,
                    replacement_text TEXT NOT NULL,
                    PRIMARY KEY (server_id, original_text)
                )
            """)
            await self.connection.commit()

    async def create_tables_mysql(self) -> None:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'read_channels'
                """, (self.config['database']['database'],))
                table_exists = await cursor.fetchone()

                if not table_exists[0]:
                    await cursor.execute("""
                        CREATE TABLE read_channels (
                            server_id BIGINT PRIMARY KEY,
                            voice_channel BIGINT NOT NULL,
                            chat_channel BIGINT NOT NULL
                        )
                    """)

                await cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'autojoin'
                """, (self.config['database']['database'],))
                table_exists = await cursor.fetchone()

                if not table_exists[0]:
                    await cursor.execute("""
                        CREATE TABLE autojoin (
                            server_id BIGINT PRIMARY KEY,
                            voice_channel BIGINT NOT NULL,
                            text_channel BIGINT NOT NULL
                        )
                    """)

                await cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'voice_settings'
                """, (self.config['database']['database'],))
                table_exists = await cursor.fetchone()

                if not table_exists[0]:
                    await cursor.execute("""
                        CREATE TABLE voice_settings (
                            server_id BIGINT,
                            user_id BIGINT,
                            voice_name VARCHAR(255) NOT NULL,
                            speed INT NOT NULL DEFAULT 100,
                            engine VARCHAR(50) NOT NULL DEFAULT 'voicevox',
                            PRIMARY KEY (server_id, user_id)
                        )
                    """)

                await cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'dictionary_replacements'
                """, (self.config['database']['database'],))
                table_exists = await cursor.fetchone()

                if not table_exists[0]:
                    await cursor.execute("""
                        CREATE TABLE dictionary_replacements (
                            server_id BIGINT NOT NULL,
                            original_text VARCHAR(255) NOT NULL,
                            replacement_text VARCHAR(255) NOT NULL,
                            PRIMARY KEY (server_id, original_text)
                        )
                    """)
                await conn.commit()

    async def get_read_channels(self) -> Dict[discord.Guild, Tuple[discord.VoiceChannel, discord.TextChannel]]:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("SELECT server_id, voice_channel, chat_channel FROM read_channels")
                rows = await cursor.fetchall()
                return {row[0]: (row[1], row[2]) for row in rows}
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT server_id, voice_channel, chat_channel FROM read_channels")
                    rows = await cursor.fetchall()
                    return {row[0]: (row[1], row[2]) for row in rows}

    async def get_read_channel(self, server_id: discord.Guild) -> Tuple[discord.VoiceChannel, discord.TextChannel] | None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    SELECT voice_channel, chat_channel 
                    FROM read_channels 
                    WHERE server_id = ?
                """, (server_id,))
                result = await cursor.fetchone()
                return result if result else None
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT voice_channel, chat_channel 
                        FROM read_channels 
                        WHERE server_id = %s
                    """, (server_id,))
                    result = await cursor.fetchone()
                    return result if result else None

    async def set_read_channel(self, server_id: discord.Guild, voice_channel: discord.VoiceChannel, chat_channel: discord.TextChannel) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR REPLACE INTO read_channels (server_id, voice_channel, chat_channel)
                    VALUES (?, ?, ?)
                """, (server_id, voice_channel, chat_channel))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO read_channels (server_id, voice_channel, chat_channel)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                        voice_channel = %s,
                        chat_channel = %s
                    """, (server_id, voice_channel, chat_channel, voice_channel, chat_channel))
                    await conn.commit()

    async def remove_read_channel(self, server_id: discord.Guild) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("DELETE FROM read_channels WHERE server_id = ?", (server_id,))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM read_channels WHERE server_id = %s", (server_id,))
                    await conn.commit()

    async def set_autojoin(self, server_id: discord.Guild, voice_channel: discord.VoiceChannel, text_channel: discord.TextChannel) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR REPLACE INTO autojoin (server_id, voice_channel, text_channel)
                    VALUES (?, ?, ?)
                """, (server_id, voice_channel, text_channel))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO autojoin (server_id, voice_channel, text_channel)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                        voice_channel = %s,
                        text_channel = %s
                    """, (server_id, voice_channel, text_channel, voice_channel, text_channel))
                    await conn.commit()

    async def get_autojoin(self, server_id: discord.Guild) -> Tuple[discord.VoiceChannel, discord.TextChannel] | None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    SELECT voice_channel, text_channel 
                    FROM autojoin 
                    WHERE server_id = ?
                """, (server_id,))
                result = await cursor.fetchone()
                return result if result else None
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT voice_channel, text_channel 
                        FROM autojoin 
                        WHERE server_id = %s
                    """, (server_id,))
                    result = await cursor.fetchone()
                    return result if result else None

    async def remove_autojoin(self, server_id: discord.Guild) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("DELETE FROM autojoin WHERE server_id = ?", (server_id,))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM autojoin WHERE server_id = %s", (server_id,))
                    await conn.commit()

    async def set_voice_settings(self, server_id: discord.Guild, user_id: discord.Member, voice_name: str, speed: int, engine: str) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR REPLACE INTO voice_settings (server_id, user_id, voice_name, speed, engine)
                    VALUES (?, ?, ?, ?, ?)
                """, (server_id, user_id, voice_name, speed, engine))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO voice_settings (server_id, user_id, voice_name, speed, engine)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE 
                        voice_name = %s,
                        speed = %s,
                        engine = %s
                    """, (server_id, user_id, voice_name, speed, engine, voice_name, speed, engine))
                    await conn.commit()

    async def get_voice_settings(self, server_id: discord.Guild, user_id: discord.Member) -> Tuple[str, int, str] | None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    SELECT voice_name, speed, engine 
                    FROM voice_settings 
                    WHERE server_id = ? AND user_id = ?
                """, (server_id, user_id))
                result = await cursor.fetchone()
                return result if result else None
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT voice_name, speed, engine 
                        FROM voice_settings 
                        WHERE server_id = %s AND user_id = %s
                    """, (server_id, user_id))
                    result = await cursor.fetchone()
                    return result if result else None

    async def set_dictionary_replacement(self, server_id: discord.Guild, original_text: str, replacement_text: str) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    INSERT OR REPLACE INTO dictionary_replacements (server_id, original_text, replacement_text)
                    VALUES (?, ?, ?)
                """, (server_id, original_text, replacement_text))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO dictionary_replacements (server_id, original_text, replacement_text)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE replacement_text = %s
                    """, (server_id, original_text, replacement_text, replacement_text))
                    await conn.commit()

    async def get_dictionary_replacements(self, server_id: discord.Guild) -> Dict[str, str]:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    SELECT original_text, replacement_text 
                    FROM dictionary_replacements 
                    WHERE server_id = ?
                """, (server_id,))
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT original_text, replacement_text 
                        FROM dictionary_replacements 
                        WHERE server_id = %s
                    """, (server_id,))
                    rows = await cursor.fetchall()
                    return {row[0]: row[1] for row in rows}

    async def remove_dictionary_replacement(self, server_id: discord.Guild, original_text: str) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            async with self.connection.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM dictionary_replacements 
                    WHERE server_id = ? AND original_text = ?
                """, (server_id, original_text))
                await self.connection.commit()
        else:
            async with self.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        DELETE FROM dictionary_replacements 
                        WHERE server_id = %s AND original_text = %s
                    """, (server_id, original_text))
                    await conn.commit()

    async def close(self) -> None:
        if self.config['database'].get('connection') == 'sqlite':
            if self.connection:
                await self.connection.close()
        else:
            if self.pool:
                self.pool.close()
                await self.pool.wait_closed()
