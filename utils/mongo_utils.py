from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

class MongoDB:
    def __init__(self, use_local=None):
        """
        Initialize the MongoDB connection.
        :param use_local: Boolean to determine if local MongoDB should be used. If None, defaults to the .env setting.
        """
        if use_local is None:
            use_local = os.getenv('USE_LOCAL_MONGO', 'true').lower() == 'true'
        mongo_uri = os.getenv('MONGO_URI_LOCAL') if use_local else os.getenv('MONGO_URI_ATLAS')
        self.client = MongoClient(mongo_uri)
        self.db = self.client['your_database_name']  # Replace 'your_database_name' with the actual database name

    def get_collection(self, collection_name):
        """
        Retrieve a specific collection from the database.
        :param collection_name: Name of the collection.
        :return: MongoDB collection object.
        """
        return self.db[collection_name]

    def test_connection(self):
        """
        Test the connection by listing collections in the database.
        :return: List of collection names or None if the connection fails.
        """
        try:
            return self.db.list_collection_names()
        except Exception as e:
            print(f"Connection failed: {e}")
            return None
