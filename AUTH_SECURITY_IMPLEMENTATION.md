# Authentication & Security Phase - Complete Implementation Guide

## Overview

This document details the complete authentication and security implementation for vTailor Backend.

## ✅ Completed Components

### 1. **JWT Token Management** (`app/core/security.py`)

- **`create_access_token()`**: Generates JWT tokens with configurable expiration
- **`verify_token()`**: Validates and decodes JWT tokens
- **Password utilities**: Bcrypt-based password hashing and verification functions
- Configurable via environment variables: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

### 2. **Passwordless Authentication with Stytch** (`app/api/v1/routers/auth.py`)

- **POST `/auth/send-magic-link`**: Send magic link to user email
- **POST `/auth/verify-magic-link`**: Verify magic link and issue JWT token
- **POST `/auth/refresh-token`**: Refresh existing JWT token
- Automatic user creation on first login
- Error handling with proper HTTP status codes

### 3. **User Management System** (`app/api/v1/routers/users.py`)

- **GET `/users/me`**: Get current authenticated user's profile
- **GET `/users/{user_id}`**: Get specific user profile (with permission checks)
- **PUT `/users/{user_id}`**: Update user information
- **DELETE `/users/{user_id}`**: Delete user account
- **GET `/users`**: List all users (Admin only)

### 4. **Role-Based Access Control (RBAC)** (`app/dependencies/auth.py`)

- **`get_current_user()`**: Extract user from JWT token
- **`get_current_active_user()`**: Validate user is active
- **`require_role(*roles)`**: Decorator for role-specific endpoints
- Support for multiple roles: `customer`, `admin`, etc.

### 5. **Data Models & Schemas**

- **User Model** (`app/models/user.py`): UserCreate, UserInDB, UserLogin, CurrentUser
- **Auth Schemas** (`app/schemas/auth.py`):
  - MagicLinkRequest, MagicLinkVerifyRequest
  - TokenResponse, UserProfile, UserUpdate
  - ErrorResponse for consistent error handling

### 6. **Database Integration** (`app/services/user_services.py`)

- **`get_user_by_email()`**: Find user by email
- **`get_user_by_id()`**: Find user by MongoDB ObjectId
- **`create_user()`**: Create new user
- **`update_user()`**: Update user information
- **`delete_user()`**: Delete user account
- **`list_all_users()`**: Paginated user listing

### 7. **Security Features** (`app/main.py`)

- **CORS Middleware**: Configured for localhost development
- **TrustedHostMiddleware**: Whitelist specific hosts
- **Security Headers**: Proper HTTP status codes and error responses
- **Health Check Endpoint**: Monitor API status

### 8. **Configuration Management** (`app/core/config.py`)

- Centralized settings using Pydantic
- Environment-based configuration
- Type-safe settings with defaults

## 🧪 Testing Suite

### Test Files

1. **`tests/test_auth_security.py`**: Core authentication and security tests

   - JWT token creation and verification
   - Magic link authentication flow
   - User profile management
   - Authorization and RBAC tests
   - Health check endpoints

2. **`tests/test_integration.py`**: Integration tests

   - Complete authentication flow
   - Security scenarios (token expiration, tampering)
   - CORS and security headers
   - Error handling and validation
   - Token refresh functionality

3. **`tests/conftest.py`**: Pytest configuration and fixtures
   - Mock MongoDB setup
   - Mock Stytch client
   - Environment variable mocking

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run specific test file
pytest tests/test_auth_security.py

# Run tests with coverage
pytest --cov=app tests/

# Run tests in verbose mode
pytest -v

# Run specific test class
pytest tests/test_auth_security.py::TestSecurityFunctions

# Run specific test
pytest tests/test_auth_security.py::TestSecurityFunctions::test_create_access_token
```

## 🔒 Security Best Practices Implemented

### 1. **Password Security**

- Bcrypt hashing for password storage (for future use)
- Configurable work factor
- Salting handled automatically by passlib

### 2. **Token Security**

- JWT with HS256 algorithm
- Configurable token expiration (default 24 hours)
- Token validation on every protected endpoint
- Expired token rejection

### 3. **Access Control**

- Role-based access control (RBAC)
- Permission verification on protected routes
- Users cannot access other users' data without authorization
- Admin-only endpoints properly protected

### 4. **Network Security**

- CORS middleware for cross-origin requests
- TrustedHostMiddleware to whitelist allowed hosts
- HTTPS ready (configure in production)

### 5. **Error Handling**

- No sensitive data in error messages
- Consistent error response format
- Proper HTTP status codes (401, 403, 404)

### 6. **Authentication Flow**

- Passwordless authentication via magic links
- First-login user creation
- Session management via JWT

## 📋 API Endpoints Reference

### Authentication Endpoints

```
POST   /app/api/v1/auth/send-magic-link
       - Send magic link to email
       - Body: { "email": "user@example.com" }
       - Response: { "status": "success", "message": "...", "request_id": "..." }

POST   /app/api/v1/auth/verify-magic-link
       - Verify magic link and get JWT token
       - Body: { "token": "stytch_token" }
       - Response: { "access_token": "...", "token_type": "bearer", "user_id": "...", "email": "..." }

POST   /app/api/v1/auth/refresh-token
       - Refresh existing token
       - Body: { "token": "jwt_token" }
       - Response: { "access_token": "...", "token_type": "bearer", ... }
```

### User Endpoints

```
GET    /app/api/v1/users/me
       - Get current user profile
       - Headers: Authorization: Bearer <token>
       - Response: UserProfile object

GET    /app/api/v1/users/{user_id}
       - Get user profile by ID
       - Headers: Authorization: Bearer <token>

PUT    /app/api/v1/users/{user_id}
       - Update user profile
       - Headers: Authorization: Bearer <token>
       - Body: { "email": "...", "role": "...", "is_active": ... }

DELETE /app/api/v1/users/{user_id}
       - Delete user account
       - Headers: Authorization: Bearer <token>

GET    /app/api/v1/users (Admin only)
       - List all users
       - Headers: Authorization: Bearer <admin_token>
       - Query: skip=0, limit=10
```

### Health Check

```
GET    /health
       - API health status
       - Response: { "status": "healthy", "service": "VTailor Backend" }

GET    /
       - Root endpoint
       - Response: { "status": "VTailor Backend running", ... }
```

## 🌍 Environment Configuration

Required environment variables (`.env`):

```
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

MONGODB_URL=mongodb://localhost:27017
MONGO_DB_NAME=vtailor_db

STYTCH_PROJECT_ID=your-stytch-project-id
STYTCH_SECRET=your-stytch-secret
```

## 🚀 Usage Example

### 1. Request Magic Link

```bash
curl -X POST "http://localhost:8000/app/api/v1/auth/send-magic-link" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

### 2. Verify Magic Link (get JWT)

```bash
curl -X POST "http://localhost:8000/app/api/v1/auth/verify-magic-link" \
  -H "Content-Type: application/json" \
  -d '{"token": "stytch_token_from_email"}'
```

### 3. Access Protected Endpoint

```bash
curl -X GET "http://localhost:8000/app/api/v1/users/me" \
  -H "Authorization: Bearer jwt_token_from_step_2"
```

## ✨ Features Implemented

| Feature              | Status | Details                                |
| -------------------- | ------ | -------------------------------------- |
| JWT Token Management | ✅     | Create, verify, refresh tokens         |
| Passwordless Auth    | ✅     | Magic link via Stytch                  |
| User Creation        | ✅     | Auto-create on first login             |
| User Profiles        | ✅     | Get, update, delete profiles           |
| RBAC                 | ✅     | Role-based access control              |
| CORS                 | ✅     | Configured for development             |
| Security Headers     | ✅     | HTTPS-ready middleware                 |
| Error Handling       | ✅     | Consistent error responses             |
| Input Validation     | ✅     | Pydantic schemas                       |
| Testing Suite        | ✅     | Comprehensive unit & integration tests |
| API Documentation    | ✅     | OpenAPI/Swagger at `/docs`             |

## 🧬 Testing Coverage

### Authentication Tests

- ✅ Token creation and verification
- ✅ Magic link flow
- ✅ JWT expiration handling
- ✅ Token tampering detection
- ✅ Token refresh

### Authorization Tests

- ✅ Missing/invalid tokens
- ✅ Permission checks
- ✅ Role-based access
- ✅ Cross-user access prevention
- ✅ Admin-only endpoints

### Security Tests

- ✅ Password hashing
- ✅ Email validation
- ✅ CORS headers
- ✅ Error message leakage
- ✅ Inactive user handling

### Integration Tests

- ✅ Complete auth flow
- ✅ User management flow
- ✅ Error scenarios
- ✅ RBAC enforcement

## 📝 Next Steps (Optional Enhancements)

1. **Rate Limiting**: Add endpoint rate limiting
2. **Audit Logging**: Log all auth events
3. **Two-Factor Authentication**: Add 2FA support
4. **Session Management**: Track active sessions
5. **OAuth Integration**: Google, GitHub authentication
6. **Email Verification**: Verify email ownership
7. **Password Reset**: Self-service password reset
8. **Account Lockout**: Prevent brute force attacks

## 🐛 Troubleshooting

### Token Not Working

- Check token expiration: Default is 24 hours
- Verify JWT_SECRET_KEY matches in all instances
- Check Authorization header format: `Bearer <token>`

### User Not Found

- Verify MongoDB connection
- Check ObjectId format in database
- Ensure user creation was successful

### CORS Issues

- Add domain to allowed_origins in main.py
- Check request headers match CORS configuration

### Stytch Integration Issues

- Verify STYTCH_PROJECT_ID and STYTCH_SECRET
- Check Stytch environment setting (test vs live)
- Review Stytch dashboard for errors

## 📚 Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- PyJWT Documentation: https://pyjwt.readthedocs.io/
- Stytch Documentation: https://stytch.com/docs
- Motor (Async MongoDB): https://motor.readthedocs.io/

---

**Last Updated**: December 25, 2025
**Version**: 1.0.0
**Status**: ✅ Authentication & Security Phase Complete
