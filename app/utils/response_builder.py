def success_response(data=None, message="Success", status_code=200):
    return {
        "status": "success",
        "message": message,
        "data": data,
        "status_code": status_code
    }

def error_response(message="An error occurred", status_code=400):
    return {
        "status": "error",
        "message": message,
        "status_code": status_code
    }

def not_found_response(message="Resource not found"):
    return error_response(message=message, status_code=404)

def unauthorized_response(message="Unauthorized access"):
    return error_response(message=message, status_code=401)

def validation_error_response(errors):
    return {
        "status": "error",
        "message": "Validation errors",
        "errors": errors,
        "status_code": 422
    }