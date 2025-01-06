import aiohttp
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_token_generator():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8080/token') as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info("Token generator is working!")
                    logger.info(f"Response structure: {list(data.keys())}")

                    # Check if we have either potoken or po_token
                    po_token = data.get('potoken') or data.get('po_token')
                    visitor_data = data.get('visitor_data')

                    if po_token and visitor_data:
                        logger.info("Token response contains all required fields!")
                    else:
                        logger.warning("Token response is missing some fields!")

                    return True
                else:
                    logger.error(f"Token generator returned status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Could not connect to token generator: {e}")
        return False


async def check_lavalink():
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': 'youshallnotpass'}
            async with session.get('http://localhost:2333/version', headers=headers) as response:
                if response.status == 200:
                    try:
                        text = await response.text()
                        logger.info(f"Lavalink raw response: {text}")
                        logger.info("Lavalink is responding!")
                        return True
                    except Exception as e:
                        logger.error(f"Error reading Lavalink response: {e}")
                        return False
                else:
                    logger.error(f"Lavalink returned status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Could not connect to Lavalink: {e}")
        return False


async def check_lavalink_info():
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'Authorization': 'youshallnotpass'}
            # Try a different endpoint
            async with session.get('http://localhost:2333/v4/info', headers=headers) as response:
                if response.status == 200:
                    try:
                        text = await response.text()
                        logger.info(f"Lavalink info response: {text}")
                        return True
                    except Exception as e:
                        logger.error(f"Error reading Lavalink info: {e}")
                        return False
                else:
                    logger.error(f"Lavalink info returned status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Could not get Lavalink info: {e}")
        return False


async def main():
    logger.info("Checking services...")

    token_generator_ok = await check_token_generator()
    lavalink_ok = await check_lavalink()
    lavalink_info_ok = await check_lavalink_info()

    if token_generator_ok and (lavalink_ok or lavalink_info_ok):
        logger.info("All services are running correctly!")
    else:
        logger.error("Some services are not running correctly!")

        if not token_generator_ok:
            logger.error("Token generator is not working properly!")
        if not lavalink_ok and not lavalink_info_ok:
            logger.error("Lavalink is not responding properly!")


if __name__ == "__main__":
    asyncio.run(main())