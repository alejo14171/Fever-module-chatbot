FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv first
RUN pip install --no-cache-dir uv

# Copy only dependency files (for better caching)
COPY pyproject.toml uv.lock ./

# Create src directory structure (will be replaced by volume in dev)
RUN mkdir -p src

# Install dependencies (this layer will be cached)
RUN uv pip install --system --no-cache --prerelease=allow -e .

# Copy application code (only for production builds)
# In development, this will be overridden by the volume mount
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
