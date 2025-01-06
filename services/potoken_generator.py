import aiohttp
import asyncio
import logging
import json
from datetime import datetime, timedelta
import os
import socket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TokenManager:
    def __init__(self):
        self.token_data = None
        self.last_update = None
        self.update_interval = timedelta(hours=1)
        self.lock = asyncio.Lock()
        self.token_generator_url = 'http://localhost:8080/token'
        logger.info(f"Using token generator URL: {self.token_generator_url}")

    async def get_token(self):
        async with self.lock:
            if (not self.token_data or
                    not self.last_update or
                    datetime.now() - self.last_update > self.update_interval):
                await self.update_token()
            return self.token_data

    async def update_token(self):
        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(3):
                    try:
                        logger.info(f"Attempting to get token from {self.token_generator_url}")
                        async with session.get(self.token_generator_url) as response:
                            if response.status == 200:
                                response_text = await response.text()
                                logger.info(f"Raw response: {response_text}")

                                try:
                                    data = json.loads(response_text)
                                    logger.info(f"Parsed response: {data}")

                                    # Handle both possible key names
                                    po_token = data.get('potoken') or data.get('po_token')
                                    visitor_data = data.get('visitor_data')

                                    if not po_token or not visitor_data:
                                        logger.error("Response missing required fields")
                                        logger.error(f"Available keys: {list(data.keys())}")
                                        return None

                                    # Store normalized data
                                    self.token_data = {
                                        'po_token': po_token,
                                        'visitor_data': visitor_data
                                    }

                                    # Update environment variables
                                    os.environ['YOUTUBE_POT_TOKEN'] = po_token
                                    os.environ['YOUTUBE_VISITOR_DATA'] = visitor_data

                                    self.last_update = datetime.now()
                                    logger.info(f"Successfully updated tokens. PO token prefix: {po_token[:10]}...")

                                    return self.token_data
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse JSON response: {e}")
                                    return None
                            else:
                                logger.error(f"Failed to update token: {response.status}")
                    except aiohttp.ClientError as e:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        if attempt == 2:
                            raise
                        await asyncio.sleep(5)
                return None
        except Exception as e:
            logger.error(f"Error updating token: {str(e)}")
            return None


# Create token manager instance
token_manager = TokenManager()


async def background_token_update():
    while True:
        await token_manager.get_token()
        await asyncio.sleep(3600)


async def start_token_manager():
    asyncio.create_task(background_token_update())
    return token_manager