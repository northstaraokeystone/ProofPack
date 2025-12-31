# Dockerfile.tool - Minimal container for sandboxed tool execution
# Per CLAUDEME §13: Containerized execution for all external tool calls

FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install minimal dependencies for HTTP tools
RUN pip install --no-cache-dir requests httpx

# Create tool directory
WORKDIR /tool

# Copy execution script (will be mounted at runtime)
COPY run.py /tool/run.py 2>/dev/null || echo "# Placeholder" > /tool/run.py

# Security: Set ownership and permissions
RUN chown -R appuser:appuser /tool && \
    chmod -R 755 /tool

# Switch to non-root user
USER appuser

# Resource limits enforced at container runtime:
# - Memory: 512MB (--memory=512m)
# - CPU: 1 core (--cpus=1)
# - Network: restricted to allowlist domains
# - Timeout: 30 seconds default

ENTRYPOINT ["python", "/tool/run.py"]
