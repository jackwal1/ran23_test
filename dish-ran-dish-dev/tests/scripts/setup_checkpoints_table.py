#!/usr/bin/env python3
"""
Script to create the checkpoints table required by LangGraph's AsyncPostgresSaver.
"""

import asyncio
import os
from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

# Load environment variables
try:
    pg_host = os.environ['POSTGRESS_URL']
    pg_db = os.environ['POSTGRES_DB_RAN_SQL_MEMORY']
    pg_user = os.environ['POSTGRESS_USERNAME']
    pg_pass = os.environ['POSTGRESS_PASSWORD']
    pg_port = os.environ['POSTGRES_PORT']
except Exception as e:
    print(e)
    print("Loading Environment Variables from local .env file")
    load_dotenv()
    pg_host = os.environ['POSTGRESS_URL']
    pg_db = os.environ['POSTGRES_DB_RAN_SQL_MEMORY']
    pg_user = os.environ['POSTGRESS_USERNAME']
    pg_pass = os.environ['POSTGRESS_PASSWORD']
    pg_port = os.environ['POSTGRES_PORT']

DB_URI = f'postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}?sslmode=disable'

# SQL to create the checkpoints table
CREATE_CHECKPOINTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL,
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT NOT NULL,
    checkpoint JSONB NOT NULL,
    metadata JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
"""

async def setup_checkpoints_table():
    """Create the checkpoints table if it doesn't exist."""
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    }

    pool = AsyncConnectionPool(
        conninfo=DB_URI,
        max_size=5,
        kwargs=connection_kwargs,
    )

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                print("Creating checkpoints table...")
                await cur.execute(CREATE_CHECKPOINTS_TABLE_SQL)
                print("✓ Checkpoints table created successfully!")
                
                # Verify the table exists
                await cur.execute("SELECT COUNT(*) FROM checkpoints")
                result = await cur.fetchone()
                if result:
                    print(f"✓ Table verified - {result[0]} rows currently in table")
                else:
                    print("✓ Table verified - 0 rows currently in table")
                
    except Exception as e:
        print(f"✗ Error creating checkpoints table: {e}")
        raise
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(setup_checkpoints_table()) 