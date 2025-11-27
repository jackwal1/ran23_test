from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import os
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
from contextlib import asynccontextmanager

try:

    pg_host = os.environ['POSTGRESS_URL']
    pg_db = os.environ['POSTGRES_DB']
    pg_user = os.environ['POSTGRESS_USERNAME']
    pg_pass = os.environ['POSTGRESS_PASSWORD']
    pg_port = os.environ['POSTGRES_PORT']
except Exception as e:
    print(e)
    print("Loading Environmment Variables from local .env file")

    load_dotenv()



    pg_host = os.environ['POSTGRESS_URL']
    pg_db = os.environ['POSTGRES_DB']
    pg_user = os.environ['POSTGRESS_USERNAME']
    pg_pass = os.environ['POSTGRESS_PASSWORD']
    pg_port = os.environ['POSTGRES_PORT']


# Postgres connection string
DATABASE_URL = f'postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}'

# SQLite connection string
#DATABASE_URL = 'sqlite+aiosqlite:///./test.db'

print(DATABASE_URL)
# Create an async engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a sessionmaker factory
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False, 
    autoflush=False
)

@asynccontextmanager
async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session

Base = declarative_base()
