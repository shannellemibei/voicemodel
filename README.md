# Eva Voice Assistant

A Python voice assistant using Google Cloud Vertex AI for intelligent responses.

## Features

- Wake word detection ("Hey Eva")
- Voice recognition and text-to-speech
- AI-powered responses via Google Cloud
- Predefined commands support

## Quick Setup with Docker

### 1. Prerequisites
- Docker and Docker Compose installed
- Google Cloud service account JSON file
- Microphone and speakers

### 2. Project Structure
```
voice-assistant/
├── v1.py
├── commands.py
├── .env
├── docker-compose.yml
├── Dockerfile
└── google_credentials.json
```

### 3. Create Environment File
Create `.env`:
```env
GOOGLE_APPLICATION_CREDENTIALS=./google_credentials.json
PROJECT_ID=your-project-id
MODEL_NAME=gemini-pro
USER=YourName
HOSTNAME=Eva
```

### 4. Create Commands File
Add to `commands.py`:
```python
COMMANDS = {
    "hello": "Hello! How can I help you?",
    "time": "Let me check the time for you.",
    "joke": "Why don't scientists trust atoms? Because they make up everything!"
}
```

### 5. Run with Docker
```bash
# Build and run
docker-compose up --build

# Or run directly
docker build -t eva-assistant .
docker run --rm -it \
  --device /dev/snd \
  -v $(pwd)/credentials:/app/credentials \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -e DISPLAY=$DISPLAY \
  eva-assistant
```

## Usage

1. Container starts automatically
2. Say "Hey Eva" to wake up
3. Ask questions or give commands
4. Say "bye eva" to pause
5. Ctrl+C to stop container

## Docker Files

The repository includes:
- `Dockerfile` - Container configuration
- `docker-compose.yml` - Easy orchestration
- Audio device mounting for microphone/speaker access

## Troubleshooting

- **Audio issues**: Ensure Docker has access to audio devices
- **Permissions**: Check microphone permissions on host system
- **Credentials**: Verify Google Cloud JSON file is mounted correctly

## Requirements

- Docker & Docker Compose
- Google Cloud account with Vertex AI enabled
- Audio hardware (microphone/speakers)