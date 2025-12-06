from pymongo import MongoClient
from gridfs import GridFS

class GridFSManager:
    def __init__(self, db_name, mongo_uri="mongodb://localhost:27017/"):
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.fs = GridFS(self.db)

    def upload_file(self, file_data, filename, content_type):
        """Uploads a file to GridFS."""
        file_id = self.fs.put(file_data, filename=filename, content_type=content_type)
        return file_id

    def download_file(self, file_id):
        """Downloads a file from GridFS."""
        file_data = self.fs.get(file_id).read()
        return file_data

    def delete_file(self, file_id):
        """Deletes a file from GridFS."""
        self.fs.delete(file_id)

    def get_file_metadata(self, file_id):
        """Retrieves metadata for a file stored in GridFS."""
        return self.fs.get(file_id).metadata

    def list_files(self):
        """Lists all files stored in GridFS."""
        return self.fs.find()