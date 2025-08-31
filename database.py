# database.py

from pymongo import MongoClient
from datetime import datetime
from config import MONGO_URI # Import MONGO_URI from your config.py

class Database:
    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client["movie_bot_db"] # You can choose your database name here
        self.movies_collection = self.db["movies"]
        self.users_collection = self.db["users"] # Optional: for tracking bot users, not strictly needed for auto-filter

        # Optional: Create indexes for faster searching
        self.movies_collection.create_index([("title", "text")], name="title_text_index")
        self.movies_collection.create_index("title", unique=False) # Or a regular index for efficient prefix matching
        self.movies_collection.create_index("imdb_id", unique=True) # Ensure IMDb IDs are unique

    def add_movie(self, title, year, imdb_id, file_id=None, direct_link=None, thumbnail_id=None):
        movie_doc = {
            "title": title.lower(),         # Store lowercased for easier, consistent searching
            "original_title": title,        # Keep original case for display
            "year": year,
            "imdb_id": imdb_id,
            "file_id": file_id,             # Telegram file_id for forwarding
            "direct_link": direct_link,     # External link for watching/downloading
            "thumbnail_id": thumbnail_id,   # Telegram file_id for a custom thumbnail
            "added_at": datetime.utcnow()
        }
        # Using update_one with upsert=True to either insert or update (useful if adding same movie again)
        # Or, just insert_one if you expect unique entries and handle duplicates elsewhere
        self.movies_collection.update_one({"imdb_id": imdb_id}, {"$set": movie_doc}, upsert=True)
        # If you prefer strict insertion and want to prevent duplicates:
        # try:
        #     self.movies_collection.insert_one(movie_doc)
        # except pymongo.errors.DuplicateKeyError:
        #     print(f"Movie with IMDb ID {imdb_id} already exists.")


    def get_movie_by_title(self, query):
        # Using a case-insensitive regex for partial matches
        return self.movies_collection.find_one({"title": {"$regex": query.lower(), "$options": "i"}})

    def get_movies_by_title_regex(self, query, limit=10):
        # For multiple results (e.g., inline search suggestions)
        return list(self.movies_collection.find({"title": {"$regex": query.lower(), "$options": "i"}}).limit(limit))

    # Optional: User tracking methods
    def add_or_update_user(self, user_id, username):
        self.users_collection.update_one(
            {"_id": user_id},
            {"$set": {"username": username, "last_active": datetime.utcnow()}},
            upsert=True
        )
