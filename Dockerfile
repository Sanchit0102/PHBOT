FROM python:3.11-slim

# -------------------------------
# System dependencies
# -------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------
# Environment
# -------------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# -------------------------------
# Working directory
# -------------------------------
WORKDIR /app

# -------------------------------
# Install Python dependencies
# -------------------------------
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# -------------------------------
# Copy bot source
# -------------------------------
COPY stream_bot.py .
COPY extractor.py .
COPY search.py .
COPY db.py .

# -------------------------------
# Runtime command
# -------------------------------
CMD ["python", "stream_bot.py"]
