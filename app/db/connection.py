from pymongo import MongoClient
import os

def get_database_connection():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    return db

# Example usage
if __name__ == "__main__":
    db = get_database_connection()
    print("Database connection established:", db)