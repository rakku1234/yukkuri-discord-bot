import aiomysql
from typing import Dict
from config import load_config

class Database:
    def __init__(self):
        self.pool = None
        self.config = load_config()

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

    async def close(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
