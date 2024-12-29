import os
from dotenv import load_dotenv

load_dotenv()

# Discord Bot Token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Clash of Clans API credentials
COC_EMAIL = os.getenv('COC_EMAIL')
COC_PASSWORD = os.getenv('COC_PASSWORD')

# MongoDB connection string
MONGO_URI = os.getenv('MONGO_URI')