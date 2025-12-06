from models.message_model import Message
from db.collections import chat_collection
from utils.custom_exceptions import ChatNotFoundException

class ChatService:
    @staticmethod
    def send_message(sender_id, receiver_id, content):
        message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content)
        chat_collection.insert_one(message.to_dict())
        return message

    @staticmethod
    def get_messages(chat_id):
        messages = chat_collection.find({"chat_id": chat_id})
        if not messages:
            raise ChatNotFoundException("Chat not found.")
        return [Message.from_dict(msg) for msg in messages]

    @staticmethod
    def delete_message(message_id):
        result = chat_collection.delete_one({"_id": message_id})
        if result.deleted_count == 0:
            raise ChatNotFoundException("Message not found.")
        return True

    @staticmethod
    def get_chat_history(user_id):
        chat_history = chat_collection.find({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]})
        return [Message.from_dict(msg) for msg in chat_history]