FROM python:3.11-alpine

WORKDIR /app

# Upgrade Alpine base packages to ensure zero base vulnerabilities
RUN apk update && apk upgrade && rm -rf /var/cache/apk/*

# Copy dependency definition
COPY pyproject.toml .

# Install temporary build dependencies to compile wheels, install app, then purge build tools
# Keeps final image clean with zero compilers or unneeded packages
RUN apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev \
    && pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir . \
    && apk del .build-deps

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Native Python healthcheck (zero curl or external binaries needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn (exact same runtime command)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
