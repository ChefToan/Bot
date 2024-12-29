from motor.motor_asyncio import AsyncIOMotorClient
from utils.config import MONGO_URI

_client = None

async def get_database():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client.coc_bot

async def close_database():
    global _client
    if _client:
        _client.close()
        _client = None