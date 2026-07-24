FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psycopg and other libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

RUN chmod 755 /app/entrypoint.sh

# Create storage directory
RUN mkdir -p /app/storage

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
