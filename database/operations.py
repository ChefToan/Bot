from datetime import datetime
from database.mongo_utils import get_database
from database.models import PlayerLink, TrackingChannel


async def save_player_link(discord_id: int, player_tag: str):
    """Save player link to database"""
    db = await get_database()
    await db.player_links.update_one(
        {"discord_id": discord_id},
        {
            "$set": {
                "discord_id": discord_id,
                "player_tag": player_tag,
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )


async def get_player_by_discord_id(discord_id: int) -> str:
    """Get player tag by Discord ID"""
    db = await get_database()
    result = await db.player_links.find_one({"discord_id": discord_id})
    return result["player_tag"] if result else None


async def save_tracking_channel(discord_id: int, player_tag: str, channel_id: int):
    """Save tracking channel information"""
    db = await get_database()
    # Create new tracking entry without removing others
    await db.tracking_channels.insert_one({
        "discord_id": discord_id,
        "player_tag": player_tag,
        "channel_id": channel_id,
        "created_at": datetime.utcnow(),
        "last_trophy_count": None,
        "daily_start_trophy": None
    })


async def update_trophy_count(player_tag: str, trophy_count: int, is_daily: bool = False):
    """Update trophy count for player"""
    db = await get_database()
    update = {}

    if is_daily:
        update["daily_start_trophy"] = trophy_count
    update["last_trophy_count"] = trophy_count

    await db.tracking_channels.update_one(
        {"player_tag": player_tag},
        {"$set": update}
    )

async def get_tracking_channels():
    """Get all tracking channels"""
    db = await get_database()
    cursor = db.tracking_channels.find({})
    return await cursor.to_list(length=None)

async def get_tracking_channel(player_tag: str):
    """Get tracking channel info for a specific player"""
    db = await get_database()
    return await db.tracking_channels.find_one({"player_tag": player_tag})

async def remove_tracking_channel(player_tag: str):
    """Remove tracking channel from database"""
    db = await get_database()
    await db.tracking_channels.delete_one({"player_tag": player_tag})