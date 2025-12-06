FROM python:3.9-slim

# Do not write pyc files and ensure stdout/stderr is unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies required by some packages (bcrypt, cryptography, etc.)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
	   build-essential \
	   libffi-dev \
	   libssl-dev \
	&& rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker layer cache
COPY requirements.txt /app/

# Upgrade pip and install python dependencies
RUN pip install --upgrade pip \
	&& pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY . /app

# Create a non-root user and give ownership of the app directory
RUN useradd --create-home appuser \
	&& chown -R appuser:appuser /app

# Run as non-root user (good security practice). Docker Compose can override user if needed.
USER appuser

ENV PYTHONPATH=/app

EXPOSE 8000

# Default command (no --reload here; docker-compose development overrides with --reload)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]