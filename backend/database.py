import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from backend.config import settings

# Configure public DNS resolvers to prevent Windows SRV lookup timeouts
try:
    import dns.resolver
    resolver = dns.resolver.Resolver(configure=True)
    resolver.nameservers = ['8.8.8.8', '1.1.1.1', '8.8.4.4']
    dns.resolver.default_resolver = resolver
except Exception:
    pass

logger = logging.getLogger("campus_lost_found.database")

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    is_connected: bool = False

db_manager = Database()

async def connect_to_mongo():
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
    try:
        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            maxPoolSize=50,
            minPoolSize=5
        )
        db_manager.db = db_manager.client[settings.DB_NAME]
        # Ping the server to verify connection
        await db_manager.client.admin.command('ping')
        db_manager.is_connected = True
        logger.info(f"Connected to MongoDB database '{settings.DB_NAME}' successfully.")
        
        # Ensure text & metadata indexes on items collection
        items_col = db_manager.db[settings.ITEMS_COLLECTION]
        await items_col.create_index([("item_type", 1), ("status", 1)])
        await items_col.create_index([("category", 1)])
        await items_col.create_index([("location", 1)])
        await items_col.create_index([("created_at", -1)])
        await items_col.create_index([("title", "text"), ("description", "text")])
        logger.info("MongoDB standard indexes initialized.")
    except Exception as e:
        logger.warning(
            f"MongoDB connection notice: Could not connect to {settings.MONGODB_URI} ({e}). "
            "Backend will maintain in-memory fallback store if MongoDB is offline or until MongoDB Atlas URI is provided."
        )
        db_manager.is_connected = False

async def close_mongo_connection():
    if db_manager.client:
        logger.info("Closing MongoDB connection...")
        db_manager.client.close()
        db_manager.is_connected = False
        logger.info("MongoDB connection closed.")

def get_items_collection() -> Optional[AsyncIOMotorCollection]:
    if db_manager.is_connected and db_manager.db is not None:
        return db_manager.db[settings.ITEMS_COLLECTION]
    return None
