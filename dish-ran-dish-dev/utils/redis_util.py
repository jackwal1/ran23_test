from typing import Optional
from redis.asyncio import Redis
from redis.asyncio.lock import Lock
import asyncio
import utils.constants as CONST
import logging

# Setup the logging configuration
log_level = getattr(logging, CONST.LOG_LEVEL, logging.INFO)  # Fallback to INFO if not found

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(filename)s - %(funcName)s - Line: %(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("RAN")
class AsyncRedisClient:
    def __init__(self, host: str, port: int, db: int, password:str):
        self.host = host
        self.port = port
        self.db = db
        self.password= password
        self.client: Redis | None = None
    async def connect(self):
        """Connect to Redis."""
        self.client = Redis(host=self.host, port=self.port, db=self.db,password=self.password,decode_responses=True)
    async def close(self):
        """Close the Redis connection."""
        if self.client:
            await self.client.close()
    async def get(self, key: str):
        """Get a value from Redis."""
        return await self.client.get(key)

    async def set(self, key: str, value: str, expire_seconds=None):
        """
        Set a value in Redis with optional expiry time.
        Args:
            key: The key to set
            value: The value to set
            expire_seconds: Optional expiry time in seconds
        """
        if expire_seconds is not None:
            await self.client.set(key, value, ex=expire_seconds)
        else:
            await self.client.set(key, value)

    # New locking methods
    async def get_lock(self, lock_name: str, timeout: int = 10) -> Lock:
        """
        Get a Redis lock object.
        Args:
            lock_name: The name of the lock
            timeout: The lock timeout in seconds
        Returns:
            A Lock object that can be acquired and released
        """
        if not self.client:
            raise RuntimeError("Redis client not connected")
        return Lock(self.client, lock_name, timeout=timeout)

    async def acquire_lock(self, lock_name: str, timeout: int = 10, blocking_timeout: Optional[float] = None) -> bool:
        """
        Acquire a lock.
        Args:
            lock_name: The name of the lock
            timeout: The lock timeout in seconds
            blocking_timeout: Maximum time to wait for lock acquisition (None for non-blocking)
        Returns:
            True if lock was acquired, False otherwise
        """
        lock = self.get_lock(lock_name, timeout=timeout)
        return await lock.acquire(blocking=blocking_timeout)

    async def release_lock(self, lock: Lock):
        """
        Release a lock.
        Args:
            lock: The lock object to release
        """
        await lock.release()


# Create a global Redis client instance with default settings
redis_client = AsyncRedisClient(host=CONST.redis_host, port=CONST.redis_port, db=CONST.redis_db,password=CONST.redis_password)
# Create the connection using an event loop
async def _connect_redis():
    await redis_client.connect()
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(_connect_redis())
    else:
        loop.run_until_complete(_connect_redis())
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_connect_redis())
def get_redis_client() -> AsyncRedisClient:
    """Get the global Redis client instance."""
    return redis_client