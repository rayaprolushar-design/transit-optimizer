FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (libgomp1 is required for OpenMP in scipy/sklearn/numpy/prophet)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
 && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy all application code and built assets
COPY . .

# Create logs directory and ensure full permissions for SQLite and logs
RUN mkdir -p logs && chmod -R 777 /app

# Expose default port
EXPOSE 8000

# Start single worker uvicorn to stay well within Railway memory limits
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
