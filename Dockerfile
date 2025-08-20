# Multi-stage build for faster builds
FROM python:3.11-slim as base

# Install system dependencies (cached layer)
RUN apt-get update && apt-get install -y \
    curl \
    git \
    nodejs \
    npm \
    docker.io \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (new launcher structure)
COPY launcher/ ./launcher/
COPY *.py ./

# Create directories for mounted volumes
RUN mkdir -p /mcp-configs /workspace /app/logs /app/session-logs

# Create non-root user for security and add to docker group
RUN groupadd -g 999 docker || true \
    && useradd -m -u 1000 mcpuser \
    && usermod -aG docker mcpuser \
    && chown -R mcpuser:mcpuser /app /workspace
USER mcpuser

# Expose ports for launcher and session containers
EXPOSE 8094 8095 8096 8097 8098 8099

# Health check for the launcher
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8094/ || exit 1

# Default command - run the V2 launcher
CMD ["python", "-m", "launcher.main", "--host", "0.0.0.0", "--port", "8094"]