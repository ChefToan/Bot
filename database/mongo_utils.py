from motor.motor_asyncio import AsyncIOMotorClient
from utils.config import MONGO_URI
import asyncio
from typing import Optional


class MongoManager:
    _instance: Optional[AsyncIOMotorClient] = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_client(cls) -> AsyncIOMotorClient:
        """Get MongoDB client with connection pooling"""
        async with cls._lock:
            if cls._instance is None:
                try:
                    # Connect with connection pooling settings
                    cls._instance = AsyncIOMotorClient(
                        MONGO_URI,
                        maxPoolSize=50,
                        minPoolSize=10,
                        maxIdleTimeMS=50000,
                        retryWrites=True,
                        serverSelectionTimeoutMS=5000
                    )
                    # Test connection
                    await cls._instance.admin.command('ping')
                    print("Successfully connected to MongoDB Atlas!")
                except Exception as e:
                    print(f"Error connecting to MongoDB: {e}")
                    raise

        return cls._instance


async def get_database():
    """Get database instance"""
    client = await MongoManager.get_client()
    return client.coc_bot  # Use your database name


async def close_database():
    """Close database connection"""
    if MongoManager._instance:
        MongoManager._instance.close()
        MongoManager._instance = None
        print("Closed MongoDB connection")