
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

ADMIN_IDS = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
    if x
}

CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.abspath(
    os.getenv("DB_PATH") or os.path.join(BASE_DIR, "bot.db")
)
