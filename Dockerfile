# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Install dependencies in a separate layer so they're cached by Docker.
# If only code changes, Docker reuses the dep layer → faster rebuilds.
FROM python:3.11-slim AS builder

WORKDIR /app

# Copy requirements first (cache layer — only invalidated if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder (avoids reinstalling)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY api/        ./api/
COPY scripts/    ./scripts/
COPY data/       ./data/
COPY delivery/   ./delivery/
COPY multimodal/ ./multimodal/
COPY infra/      ./infra/
COPY main.py     .

# Create logs dir (mounted as volume in production)
RUN mkdir -p logs

# Non-root user for security (best practice)
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# Expose port (Railway reads this)
EXPOSE 8000

# Health check — Railway uses this to confirm the container is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen('http://localhost:' + port + '/')"

# Start the server
# --host 0.0.0.0  → listen on all interfaces (required in containers)
# --port $PORT    → dynamic port assignment for Railway (defaults to 8000)
# --workers 2     → 2 processes for concurrent requests
CMD uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 2
