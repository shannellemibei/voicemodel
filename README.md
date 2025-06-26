# Eva Voice Assistant

A Python voice assistant using Google Cloud Vertex AI for intelligent responses.

## Features

- Wake word detection ("Hey Eva")
- Voice recognition and text-to-speech
- AI-powered responses via Google Cloud
- Predefined commands support

## Quick Setup

### 1. Install Dependencies
```bash
pip install speechrecognition gtts pydub google-cloud-aiplatform python-dotenv vertexai pyaudio
```

### 2. Google Cloud Setup
1. Create a GCP project and enable Vertex AI API
2. Create service account and download JSON credentials
3. Create `.env` file:
```env
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
PROJECT_ID=your-project-id
MODEL_NAME=gemini-pro
USER=YourName
HOSTNAME=Eva
```

### 3. Create Commands File
Create `commands.py`:
```python
COMMANDS = {
    "hello": "Hello! How can I help you?",
    "time": "Let me check the time for you.",
    "joke": "Why don't scientists trust atoms? Because they make up everything!"
}
```

### 4. Run
```bash
python voice_assistant.py
```

## Usage

1. Say "Hey Eva" to wake up
2. Ask questions or give commands
3. Say "bye eva" to pause
4. Say "exit" to quit

## Troubleshooting

- **Microphone issues**: Check permissions and device index
- **Google Cloud errors**: Verify credentials and API access
- **Audio problems**: Install ffmpeg and check speakers

## Requirements

- Python 3.7+
- Microphone and speakers
- Internet connection
- Google Cloud account