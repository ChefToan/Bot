from dataclasses import dataclass
from datetime import datetime

@dataclass
class PlayerLink:
    discord_id: int
    player_tag: str
    created_at: datetime

@dataclass
class TrackingChannel:
    discord_id: int
    player_tag: str
    channel_id: int
    created_at: datetime
    last_trophy_count: int = None
    daily_start_trophy: int = None