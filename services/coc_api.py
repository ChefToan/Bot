import coc
from utils.config import COC_EMAIL, COC_PASSWORD
import asyncio
import aiohttp

# Global client instance
_coc_client = None
_lock = asyncio.Lock()


async def get_coc_client():
    """Get or create COC client with rate limiting"""
    global _coc_client

    async with _lock:
        if _coc_client is None:
            try:
                _coc_client = coc.Client(key_names="Discord Bot", key_count=1)
                await _coc_client.login(
                    email=COC_EMAIL,
                    password=COC_PASSWORD
                )
            except Exception as e:
                print(f"Failed to initialize COC client: {e}")
                raise

    return _coc_client


async def close_coc_client():
    """Close the COC client"""
    global _coc_client
    if _coc_client:
        await _coc_client.close()
        _coc_client = None


async def get_player_info(tag: str):
    """Get player info with error handling and rate limiting"""
    try:
        client = await get_coc_client()

        # Add small delay between requests
        await asyncio.sleep(0.1)

        try:
            return await client.get_player(tag)
        except coc.exceptions.NotFound:
            print(f"Player {tag} not found")
            return None
        except aiohttp.ClientResponseError as e:
            print(f"API Error for {tag}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error getting player {tag}: {e}")
            return None

    except Exception as e:
        print(f"Error with COC client: {e}")
        return None