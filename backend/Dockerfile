FROM python:3.11-slim-bookworm

WORKDIR /app

# Apply latest security patches from Debian stable security updates
# and remove unnecessary libraries (eliminates krb5, cyrus-sasl2, glibc/zlib CVEs)
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get purge -y --auto-remove libkrb5-3 libsasl2-2 2>/dev/null || true \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file and install
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check using built-in Python standard library (zero curl / krb5 / sasl dependencies needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
