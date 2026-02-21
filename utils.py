import motor.motor_asyncio
import logging
import cv2
import numpy as np
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


def contains_potential_digits(image_bytes: bytes) -> bool:
    """
    Uses OpenCV to quickly check if an image contains shapes that could potentially be text/digits.
    Useful for filtering out completely blank images or photos of things like dogs/walls.
    """
    try:
        # Convert bytes to numpy array then to cv2 image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        
        if img is None:
            return False

        # Apply adaptive thresholding to find edges/shapes
        thresh = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        valid_shapes = 0
        img_area = img.shape[0] * img.shape[1]

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = w * h
            aspect_ratio = float(w)/h if h > 0 else 0
            
            # Digits are usually not massive (like a dog) and not microscopic,
            # and they tend to have a certain aspect ratio height > width or similar.
            # We enforce a maximum area of 10% of the image (blocks large dogs/posters)
            if 50 < area < (img_area * 0.1):
                # Digits generally shouldn't be insanely wide or insanely tall
                if 0.1 < aspect_ratio < 10.0:
                    valid_shapes += 1

                # If we found at least a few decent shapes, it has *something* on it
                if valid_shapes >= 3:
                    return True
                    
        # Log to debug so we can see why it rejected
        logger.info(f"OpenCV Check Failed: Only found {valid_shapes} valid text-like shapes.")
        return False
    except Exception as e:
        logger.error(f"Error during OpenCV pre-processing: {str(e)}")
        # If OpenCV fails unexpectedly, return True to let the LLM try anyway
        return True
