FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /docker_app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into WORKDIR (/docker_app)
COPY . .

# Ensure python can import packages from WORKDIR (helpful with reload subprocesses)
ENV PYTHONPATH=/docker_app

EXPOSE 8000

# Keep the same uvicorn target if package import path is app.main:app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]