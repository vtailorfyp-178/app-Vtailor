class APIResponse:
    @staticmethod
    def success(data=None, message="Success"):
        return {
            "status": "success",
            "message": message,
            "data": data,
        }

    @staticmethod
    def error(message="Error", code=400):
        return {
            "status": "error",
            "message": message,
            "code": code,
        }
