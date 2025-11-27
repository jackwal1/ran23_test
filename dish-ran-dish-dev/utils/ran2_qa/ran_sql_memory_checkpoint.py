from contextlib import asynccontextmanager
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
import os
from dotenv import load_dotenv
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Load environment variables
try:
    # wx_url = os.environ['WATSONX_URL']
    # wx_api_key = os.environ['WATSONX_API_KEY']
    # wx_project_id = os.environ['WATSONX_PROJECT_ID']

    pg_host = os.environ['POSTGRESS_URL']
    pg_db = os.environ['POSTGRES_DB_RAN_SQL_MEMORY']
    pg_user = os.environ['POSTGRESS_USERNAME']
    pg_pass = os.environ['POSTGRESS_PASSWORD']
    pg_port = os.environ['POSTGRES_PORT']
    
except Exception as e:
    print(e)
    print("Loading Environment Variables from local .env file")

    load_dotenv()

    # wx_url = os.environ['WATSONX_URL']
    # wx_api_key = os.environ['WATSONX_API_KEY']
    # wx_project_id = os.environ['WATSONX_PROJECT_ID']

    pg_host = os.environ['POSTGRESS_URL']
    pg_db = os.environ['POSTGRES_DB_RAN_SQL_MEMORY']
    pg_user = os.environ['POSTGRESS_USERNAME']
    pg_pass = os.environ['POSTGRESS_PASSWORD']
    pg_port = os.environ['POSTGRES_PORT']

DB_URI = f'postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}?sslmode=disable'

# Connection pool and checkpointer
pool = None
checkpointer = None

async def setup_postgres_saver():
    global pool, checkpointer
    if checkpointer is not None:
        return checkpointer

    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    }

    pool = AsyncConnectionPool(
        conninfo=DB_URI,
        max_size=10,
        kwargs=connection_kwargs,
    )

    checkpointer = AsyncPostgresSaver(pool)
    print("Postgres Saver setup completed.")
    return checkpointer

async def get_checkpointer():
    global checkpointer
    if checkpointer is None:
        await setup_postgres_saver()
    return checkpointer

async def cleanup():
    global pool
    if pool is not None:
        await pool.close()
        print("Connection pool closed.")

@asynccontextmanager
async def get_connection():
    async with pool.connection() as conn:
        yield conn