class NotFoundException(Exception):
    """Exception raised for not found errors."""
    def __init__(self, message="Resource not found"):
        self.message = message
        super().__init__(self.message)

class UnauthorizedException(Exception):
    """Exception raised for unauthorized access."""
    def __init__(self, message="Unauthorized access"):
        self.message = message
        super().__init__(self.message)

class BadRequestException(Exception):
    """Exception raised for bad request errors."""
    def __init__(self, message="Bad request"):
        self.message = message
        super().__init__(self.message)

class ConflictException(Exception):
    """Exception raised for conflict errors."""
    def __init__(self, message="Conflict occurred"):
        self.message = message
        super().__init__(self.message)

class InternalServerErrorException(Exception):
    """Exception raised for internal server errors."""
    def __init__(self, message="Internal server error"):
        self.message = message
        super().__init__(self.message)
        
class PaymentException(Exception):
    """Exception raised for Payment failure."""
    def __init__(self, message="Payment Failed"):
        self.message = message
        super().__init__(self.message)