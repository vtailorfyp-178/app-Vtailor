from datetime import datetime, timedelta
import jwt

class PasswordlessTokenManager:
    def __init__(self, secret_key, algorithm='HS256', expiration_minutes=10):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expiration_minutes = expiration_minutes

    def create_token(self, user_id):
        expiration = datetime.utcnow() + timedelta(minutes=self.expiration_minutes)
        token = jwt.encode({'user_id': user_id, 'exp': expiration}, self.secret_key, algorithm=self.algorithm)
        return token

    def verify_token(self, token):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload['user_id']
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

# Example usage:
# manager = PasswordlessTokenManager(secret_key='your_secret_key')
# token = manager.create_token(user_id='123')
# user_id = manager.verify_token(token)