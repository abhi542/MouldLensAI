import motor.motor_asyncio
import logging
from config import settings

logger = logging.getLogger(__name__)

class Database:
    client: motor.motor_asyncio.AsyncIOMotorClient = None
    db = None

    @classmethod
    def connect(cls):
        logger.info(f"Connecting to MongoDB at {settings.mongodb_uri}")
        cls.client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_uri)
        cls.db = cls.client[settings.mongodb_db_name]

    @classmethod
    def disconnect(cls):
        if cls.client:
            logger.info("Disconnecting from MongoDB")
            cls.client.close()

db = Database()

async def save_mould_reading(reading_data: dict) -> str | None:
    """
    Saves the given reading data into the `mould_readings` collection.
    Returns the inserted ID as a string, or None if the DB is not connected.
    """
    if db.db is not None:
        try:
            collection = db.db["mould_readings"]
            result = await collection.insert_one(reading_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Failed to save reading to MongoDB: {e}")
            return None
    return None
