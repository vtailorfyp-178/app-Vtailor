from pymongo import MongoClient

class DatabaseCollections:
    def __init__(self, db_name, mongo_uri="mongodb://localhost:27017/"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collections = {}

    def create_collection(self, collection_name):
        if collection_name not in self.collections:
            self.collections[collection_name] = self.db[collection_name]
        return self.collections[collection_name]

    def get_collection(self, collection_name):
        return self.collections.get(collection_name, self.create_collection(collection_name))

    def close(self):
        self.client.close()

# Example usage:
# db_collections = DatabaseCollections("vtailor_db")
# user_collection = db_collections.get_collection("users")