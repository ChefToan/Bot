from datetime import datetime
import pytz
from database.mongo_utils import get_database
from typing import List, Optional, Dict, Any
import pymongo

# Define timezone once as a module-level constant
TIMEZONE = pytz.timezone('America/Phoenix')

async def save_player_link(discord_id: int, player_tag: str):
    """Save player link to database"""
    db = await get_database()
    try:
        await db.player_links.update_one(
            {"discord_id": discord_id},
            {
                "$set": {
                    "discord_id": discord_id,
                    "player_tag": player_tag,
                    "updated_at": datetime.utcnow(),
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        print(f"Error saving player link: {e}")
        raise

async def get_player_by_discord_id(discord_id: int) -> Optional[str]:
    """Get player tag by Discord ID"""
    db = await get_database()
    try:
        result = await db.player_links.find_one({"discord_id": discord_id})
        return result["player_tag"] if result else None
    except Exception as e:
        print(f"Error getting player by discord ID: {e}")
        return None

async def save_tracking_channel(discord_id: int, player_tag: str, channel_id: int):
    """Save tracking channel information"""
    db = await get_database()
    try:
        # Create index for player_tag if it doesn't exist
        await db.tracking_channels.create_index("player_tag", unique=True)

        # Get current time in Phoenix timezone
        current_time = datetime.now(TIMEZONE)

        await db.tracking_channels.insert_one({
            "discord_id": discord_id,
            "player_tag": player_tag,
            "channel_id": channel_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "last_trophy_count": None,
            "daily_start_trophy": None,
            "last_daily_reset": None
        })
    except pymongo.errors.DuplicateKeyError:
        # Update existing channel if player already being tracked
        await db.tracking_channels.update_one(
            {"player_tag": player_tag},
            {
                "$set": {
                    "channel_id": channel_id,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    except Exception as e:
        print(f"Error saving tracking channel: {e}")
        raise

async def get_tracking_channels() -> List[Dict[str, Any]]:
    """Get all tracking channels"""
    db = await get_database()
    try:
        cursor = db.tracking_channels.find({})
        return await cursor.to_list(length=None)
    except Exception as e:
        print(f"Error getting tracking channels: {e}")
        return []

async def update_trophy_count(player_tag: str, trophy_count: int, is_daily: bool = False):
    """Update trophy count for player"""
    db = await get_database()
    try:
        current_time = datetime.now(TIMEZONE)

        update = {
            "updated_at": datetime.utcnow(),
            "last_trophy_count": trophy_count
        }

        # Only update daily_start_trophy if it's exactly 10 PM and is_daily is True
        if is_daily and current_time.hour == 22 and current_time.minute == 0:
            update.update({
                "daily_start_trophy": trophy_count,
                "last_daily_reset": current_time
            })
        # if is_daily and current_time.hour == 17 and current_time.minute == 50:
        #     update.update({
        #         "daily_start_trophy": trophy_count,
        #         "last_daily_reset": current_time
        #     })

        await db.tracking_channels.update_one(
            {"player_tag": player_tag},
            {"$set": update}
        )
    except Exception as e:
        print(f"Error updating trophy count: {e}")
        raise

async def get_tracking_channel(player_tag: str) -> Optional[Dict[str, Any]]:
    """Get tracking channel info for a specific player"""
    db = await get_database()
    try:
        return await db.tracking_channels.find_one({"player_tag": player_tag})
    except Exception as e:
        print(f"Error getting tracking channel: {e}")
        return None

async def remove_tracking_channel(player_tag: str):
    """Remove tracking channel from database"""
    db = await get_database()
    try:
        await db.tracking_channels.delete_one({"player_tag": player_tag})
    except Exception as e:
        print(f"Error removing tracking channel: {e}")
        raise