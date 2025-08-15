# Use Python 3.11 slim image
FROM python:3.11-slim

# working directory
WORKDIR /app

# system dependencies for audio
RUN apt-get update && apt-get install -y \
    alsa-utils \
    pulseaudio \
    pulseaudio-utils \
    portaudio19-dev \
    python3-pyaudio \
    ffmpeg \
    espeak \
    espeak-data \
    libespeak1 \
    libespeak-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# requirements 
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY swahili.py .
COPY english.py .
COPY main.py .
COPY commands.py .

# Create credentials directory
RUN mkdir -p /app/google_credentials.json

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONWARNINGS=ignore

# Expose any necess
# EXPOSE 8095

# Run the voice assistant
CMD ["python", "v2.py"]