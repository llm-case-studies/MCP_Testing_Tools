FROM python:3.11-slim

# Install system dependencies for MCP servers
RUN apt-get update && apt-get install -y \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install UV for Python package management (used by many MCP servers)
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./

# Create directories for mounted volumes
RUN mkdir -p /mcp-configs /workspace /app/logs

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app /workspace
USER mcpuser

# Expose ports for our services
EXPOSE 8000 8001 8002

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Default command (can be overridden in docker-compose)
CMD ["python", "web_interface.py"]