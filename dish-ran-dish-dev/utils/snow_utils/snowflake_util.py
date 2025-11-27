"""
Snowflake SQLAlchemy Utility
===========================

This utility provides basic testing for your Snowflake connection using SQLAlchemy.

Usage:
------
1. Make sure your environment variables (Snowflake credentials, etc.) are set in a `.env` file or your shell.
2. From the project root, set the Python path and run the utility:

   # To test connection and list tables in the current schema:
   PYTHONPATH=. python utils/snow_utils/snowflake_util.py

   # To run a sample query (edit the query in the script as needed):
   PYTHONPATH=. python utils/snow_utils/snowflake_util.py run_query

Notes:
------
- The utility uses async SQLAlchemy sessions and runs blocking DB calls in a thread pool.
- Make sure your `utils/constants.py` and `.env` file have all required Snowflake connection variables.
- You can modify or extend this script for more advanced testing or automation.

"""

import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from snowflake.sqlalchemy import URL
from contextlib import contextmanager
from sqlalchemy.ext.declarative import declarative_base
from utils import constants as CONST
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List
from concurrent.futures import ThreadPoolExecutor

# Create Snowflake SQLAlchemy connection string
DATABASE_URL = URL(
    user=CONST.snowflake_user,
    password=CONST.snowflake_pass,
    account=CONST.snowflake_account,
    warehouse=CONST.snowflake_warehouse,
    database=CONST.snowflake_db,
    schema=CONST.snowflake_schema,
    role = CONST.snowflake_role,
    # Add these connection parameters
    connect_timeout=10,  # Connection timeout in seconds
    retry_on_timeout=True,
    client_session_keep_alive=True  # Keeps session alive during long-running queries
)

print(DATABASE_URL)

# Creating SQLAlchemy engine and session maker
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,  # Timeout for getting connection from pool
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={
        'client_session_keep_alive_heartbeat_frequency': 3600,
        'login_timeout': 30,  # Login timeout in seconds
        'ocsp_fail_open': True,
        'insecure_mode': True
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[Session, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        await asyncio.to_thread(session.close)


# Run synchronous function in a thread pool to achieve async behavior
async def run_in_threadpool(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool,func, *args, **kwargs)


async def test_snowflake_connection_and_list_tables():
    """Test connection to Snowflake and list tables in the current schema."""
    from sqlalchemy import inspect
    try:
        async with get_db_session() as session:
            inspector = inspect(session.bind)
            tables = await asyncio.to_thread(inspector.get_table_names)
            print("Successfully connected to Snowflake!")
            print("Tables in current schema:")
            for table in tables:
                print(f"- {table}")
    except Exception as e:
        print(f"Error connecting to Snowflake or listing tables: {e}")

async def run_sample_query():
    """Run a sample query against Snowflake and print the results."""
    query = text(
        "select * from DISH_MNO_OUTBOUND.GENAI_APP_HYBRID.VOICE_USAGE_30MIN_SUB_AGG_FACT "
        "order by CALL_START_DT_MST desc limit 2"
    )
    try:
        async with get_db_session() as session:
            result = await asyncio.to_thread(session.execute, query)
            rows = result.fetchall()
            print(f"Query returned {len(rows)} rows:")
            for row in rows:
                print(row)
    except Exception as e:
        print(f"Error running sample query: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "run_query":
        asyncio.run(run_sample_query())
    else:
        asyncio.run(test_snowflake_connection_and_list_tables())