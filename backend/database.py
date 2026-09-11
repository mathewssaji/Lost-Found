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

import time
import asyncio

try:
    import certifi
    ca_file = certifi.where()
except Exception:
    ca_file = None

logger = logging.getLogger("campus_lost_found.database")

class Database:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    is_connected: bool = False
    is_connecting: bool = False
    last_attempt_time: float = 0.0

db_manager = Database()

async def connect_to_mongo():
    if db_manager.is_connected:
        return
    if db_manager.is_connecting:
        return

    now = time.time()
    if now - db_manager.last_attempt_time < 30.0:
        return

    db_manager.is_connecting = True
    db_manager.last_attempt_time = now
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
    try:
        kwargs = {
            "serverSelectionTimeoutMS": 2500,
            "connectTimeoutMS": 2500,
            "maxPoolSize": 50,
            "minPoolSize": 1,
        }
        if ca_file:
            kwargs["tlsCAFile"] = ca_file

        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            **kwargs
        )
        db_manager.db = db_manager.client[settings.DB_NAME]
        # Ping server with short timeout
        await asyncio.wait_for(db_manager.client.admin.command('ping'), timeout=2.5)
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
            "Engine will maintain ultra-fast in-memory fallback store until MongoDB Atlas Network Access is enabled."
        )
        db_manager.is_connected = False
    finally:
        db_manager.is_connecting = False

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
