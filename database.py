import aiomysql
from typing import Dict
from config import load_config

class Database:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.pool = None
            cls._instance.config = load_config()
        return cls._instance

    async def connect(self):
        db_config = {
            'host': self.config['database']['host'],
            'user': self.config['database']['user'],
            'password': self.config['database']['password'],
            'db': self.config['database']['database'],
            'port': self.config['database']['port']
        }

        self.pool = await aiomysql.create_pool(**db_config)

        await self.create_tables()

    async def create_tables(self):
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
                            chat_channel BIGINT NOT NULL
                        )
                    """)
                else:
                    await cursor.execute("""
                        SELECT COLUMN_NAME
                        FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = %s
                        AND TABLE_NAME = 'read_channels'
                    """, (self.config['database']['database'],))

                    columns = await cursor.fetchall()
                    column_names = [col[0] for col in columns]

                    if 'server_id' not in column_names:
                        await cursor.execute("""
                            ALTER TABLE read_channels
                            ADD COLUMN server_id BIGINT PRIMARY KEY
                        """)

                    if 'chat_channel' not in column_names:
                        await cursor.execute("""
                            ALTER TABLE read_channels
                            ADD COLUMN chat_channel BIGINT NOT NULL
                        """)

                await cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'autojoin'
                """, (self.config['database']['database'],))

                autojoin_exists = await cursor.fetchone()

                if not autojoin_exists[0]:
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

                voice_settings_exists = await cursor.fetchone()

                if not voice_settings_exists[0]:
                    await cursor.execute("""
                        CREATE TABLE voice_settings (
                            server_id BIGINT,
                            user_id BIGINT,
                            voice_name VARCHAR(255) NOT NULL,
                            speed INT NOT NULL DEFAULT 100,
                            engine VARCHAR(50) NOT NULL DEFAULT 'aquestalk',
                            PRIMARY KEY (server_id, user_id)
                        )
                    """)

                await cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    AND table_name = 'dictionary_replacements'
                """, (self.config['database']['database'],))

                dictionary_replacements_exists = await cursor.fetchone()

                if not dictionary_replacements_exists[0]:
                    await cursor.execute("""
                        CREATE TABLE dictionary_replacements (
                            server_id BIGINT NOT NULL,
                            original_text VARCHAR(255) NOT NULL,
                            replacement_text VARCHAR(255) NOT NULL,
                            PRIMARY KEY (server_id, original_text)
                        )
                    """)

                await conn.commit()

    async def get_read_channels(self) -> Dict[int, int]:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT server_id, chat_channel FROM read_channels")
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

    async def set_read_channel(self, server_id: int, chat_channel: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO read_channels (server_id, chat_channel)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE chat_channel = %s
                """, (server_id, chat_channel, chat_channel))
                await conn.commit()

    async def remove_read_channel(self, server_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM read_channels WHERE server_id = %s", (server_id,))
                await conn.commit()

    async def set_autojoin(self, server_id: int, voice_channel: int, text_channel: int):
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

    async def get_autojoin(self, server_id: int) -> tuple[int, int] | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT voice_channel, text_channel 
                    FROM autojoin 
                    WHERE server_id = %s
                """, (server_id,))
                result = await cursor.fetchone()
                return result if result else None

    async def remove_autojoin(self, server_id: int):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM autojoin WHERE server_id = %s", (server_id,))
                await conn.commit()

    async def set_voice_settings(self, server_id: int, user_id: int, voice_name: str, speed: int, engine: str = "aquestalk"):
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

    async def get_voice_settings(self, server_id: int, user_id: int) -> tuple[str, int, str] | None:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT voice_name, speed, engine 
                    FROM voice_settings 
                    WHERE server_id = %s AND user_id = %s
                """, (server_id, user_id))
                result = await cursor.fetchone()
                return result if result else None

    async def set_dictionary_replacement(self, server_id: int, original_text: str, replacement_text: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO dictionary_replacements (server_id, original_text, replacement_text)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE replacement_text = %s
                """, (server_id, original_text, replacement_text, replacement_text))
                await conn.commit()

    async def get_dictionary_replacements(self, server_id: int) -> Dict[str, str]:
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT original_text, replacement_text 
                    FROM dictionary_replacements 
                    WHERE server_id = %s
                """, (server_id,))
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

    async def remove_dictionary_replacement(self, server_id: int, original_text: str):
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM dictionary_replacements 
                    WHERE server_id = %s AND original_text = %s
                """, (server_id, original_text))
                await conn.commit()

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
