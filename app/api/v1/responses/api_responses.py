class APIResponse:
    @staticmethod
    def success(data=None, message="Request was successful"):
        return {
            "status": "success",
            "message": message,
            "data": data
        }

    @staticmethod
    def error(message="An error occurred", code=400):
        return {
            "status": "error",
            "message": message,
            "code": code
        }

    @staticmethod
    def not_found(message="Resource not found"):
        return APIResponse.error(message, code=404)

    @staticmethod
    def unauthorized(message="Unauthorized access"):
        return APIResponse.error(message, code=401)

    @staticmethod
    def forbidden(message="Access forbidden"):
        return APIResponse.error(message, code=403)

    @staticmethod
    def validation_error(errors):
        return {
            "status": "error",
            "message": "Validation failed",
            "errors": errors,
            "code": 422
        }