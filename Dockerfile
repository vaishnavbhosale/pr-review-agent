# Step 1 — Choose the base image
# We use Python 3.11 slim — a minimal Python installation
# slim means it does not include unnecessary tools, keeping the image small
FROM python:3.11-slim

# Step 2 — Set the working directory inside the container
# All commands from here run inside /app
# All files will be copied into /app
WORKDIR /app

# Step 3 — Copy requirements first
# We copy requirements.txt before the rest of the code
# This is a Docker optimization called layer caching
# If requirements.txt has not changed, Docker reuses the cached
# installation layer and does not reinstall packages on every build
COPY requirements.txt .

# Step 4 — Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 5 — Copy the rest of the application code
COPY app/ ./app/

# Step 6 — Create a non-root user for security
# Running as root inside a container is a security risk
# If the container is compromised, the attacker gets root access
# We create a limited user called appuser instead
RUN adduser --disabled-password --gecos "" appuser
USER appuser

# Step 7 — Tell Docker which port the app uses
# This is documentation — it does not actually open the port
# The actual port mapping happens in docker-compose
EXPOSE 8000

# Step 8 — Health check
# Docker periodically runs this command to verify the container is healthy
# If it fails 3 times in a row, Docker marks the container as unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Step 9 — Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]