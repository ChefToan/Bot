import coc
import os
from dotenv import load_dotenv


class CocService:
    def __init__(self):
        load_dotenv()
        self.client = coc.Client(key_names="Discord Bot", key_count=1)

    async def initialize(self):
        await self.client.login(
            email=os.getenv('COC_EMAIL'),
            password=os.getenv('COC_PASSWORD')
        )

    async def get_player_info(self, tag: str):
        try:
            player = await self.client.get_player(tag)
            return {
                "name": player.name,
                "trophy_count": player.trophies,
                "best_trophies": player.best_trophies,
                "town_hall_level": player.town_hall,
                "league": player.league.name if player.league else "Unranked",
                "clan_name": player.clan.name if player.clan else None,
                "clan_tag": player.clan.tag if player.clan else None
            }
        except coc.errors.NotFound:
            return None
        except Exception as e:
            print(f"Error fetching player info: {e}")
            return None

    async def close(self):
        await self.client.close()