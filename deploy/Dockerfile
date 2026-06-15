FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including supervisor
RUN apt-get update && apt-get install -y \
    supervisor \
    build-essential \
    libpq-dev \
    gcc \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Ensure redis is installed since we swapped kafka for redis pubsub
RUN pip install --no-cache-dir redis

# Copy the rest of the application
COPY . .

# Copy supervisor config
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose FastAPI port
EXPOSE 8000

# Run supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
