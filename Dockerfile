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

# Copy all application directories and files
COPY . .

# Create logs directory
RUN mkdir -p logs

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# Expose default port
EXPOSE 8000

# Health check — uses 127.0.0.1 explicitly to avoid IPv6 localhost resolution mismatch
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen('http://127.0.0.1:' + port + '/')"

# Start the server with dynamic PORT support for Railway
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
