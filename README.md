# vtailor_backend

## Overview
vtailor_backend is a backend application designed to support a tailoring service platform. It provides a RESTful API and WebSocket connections for real-time communication, enabling functionalities such as user authentication, order management, chat services, and payment processing.

## Features
- **User Authentication**: Secure login and registration processes.
- **Tailor Management**: List and retrieve details of tailors.
- **Order Processing**: Create, retrieve, and update orders.
- **Chat Functionality**: Real-time messaging between users and tailors.
- **Payment Integration**: Process payments and manage payment history.
- **File Management**: Upload and retrieve files related to orders and user profiles.

## Project Structure
```
vtailor_backend/
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routers/
│   │   │   ├── dependencies/
│   │   │   └── responses/
│   │   └── websocket/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   ├── middleware/
│   ├── main.py
│   └── __init__.py
├── tests/
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   cd vtailor_backend
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up the database and run migrations if necessary.

## Running the Application
To start the application, run:
```
python app/main.py
```

## Testing
To run the tests, use:
```
pytest tests/
```

## Docker
To build and run the application using Docker, use:
```
docker-compose up --build
```

## License
This project is licensed under the MIT License. See the LICENSE file for details.