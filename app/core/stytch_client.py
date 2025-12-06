from stytch import Client

class StytchClient:
    def __init__(self, project_id: str, secret: str):
        self.client = Client(project_id=project_id, secret=secret)

    def authenticate_user(self, email: str):
        response = self.client.magic_links.create(email=email)
        return response

    def verify_token(self, token: str):
        response = self.client.magic_links.authenticate(token=token)
        return response

    def get_user(self, user_id: str):
        response = self.client.users.get(user_id=user_id)
        return response

    def update_user(self, user_id: str, data: dict):
        response = self.client.users.update(user_id=user_id, data=data)
        return response

    def delete_user(self, user_id: str):
        response = self.client.users.delete(user_id=user_id)
        return response