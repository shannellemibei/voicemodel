from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import asyncio
import speech_recognition as sr
from gtts import gTTS
import io
import base64
from pydub import AudioSegment
import tempfile
import os
from datetime import datetime
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI()

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize Google Cloud (same as original)
try:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    from google.cloud import aiplatform
    aiplatform.init(project=os.getenv("PROJECT_ID"))
    model = GenerativeModel(os.getenv("MODEL_NAME"))
except Exception as e:
    print(f"Error initializing Google Cloud services: {e}")

USER = os.getenv("USER", "User")

class VoiceProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
    def recognize_audio(self, audio_data, language='en-US'):
        """Convert audio bytes to text"""
        try:
            # Convert base64 to audio
            audio_bytes = base64.b64decode(audio_data)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name
            
            # Load and recognize
            with sr.AudioFile(temp_path) as source:
                audio = self.recognizer.record(source)
                result = self.recognizer.recognize_google(audio, language=language)
                
            # Cleanup
            os.unlink(temp_path)
            return result.lower()
            
        except Exception as e:
            print(f"Recognition error: {e}")
            return None
    
    def text_to_speech(self, text, language='en'):
        """Convert text to speech and return base64 audio"""
        try:
            tts = gTTS(text=text, lang=language)
            
            # Save to memory buffer
            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            buffer.seek(0)
            
            # Convert to base64
            audio_base64 = base64.b64encode(buffer.read()).decode()
            return audio_base64
            
        except Exception as e:
            print(f"TTS error: {e}")
            return None

voice_processor = VoiceProcessor()

def vertex_ai_response(prompt_text, language='en'):
    """Get response from Vertex AI"""
    try:
        lang_instruction = "Respond in English." if language == 'en' else "Respond in Swahili."
        prompt = f"{prompt_text.strip()}\n{lang_instruction} Please respond briefly and clearly."
        
        response = model.generate_content([prompt])
        return response.text.strip()
    except Exception as e:
        print(f"Error with Vertex AI: {e}")
        return "I'm having trouble processing that request right now."

@app.get("/")
async def get_index():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "text_input":
                # Process text input
                user_text = message["text"]
                language = message.get("language", "en")
                
                # Log the input
                timestamp = datetime.now().strftime("%H:%M:%S")
                await websocket.send_text(json.dumps({
                    "type": "log",
                    "message": f"[{timestamp}] User: {user_text}"
                }))
                
                # Get AI response
                ai_response = vertex_ai_response(user_text, language)
                
                # Send text response
                await websocket.send_text(json.dumps({
                    "type": "ai_response",
                    "text": ai_response
                }))
                
                # Generate and send audio
                tts_lang = 'sw' if language == 'sw' else 'en'
                audio_data = voice_processor.text_to_speech(ai_response, tts_lang)
                
                if audio_data:
                    await websocket.send_text(json.dumps({
                        "type": "audio_response",
                        "audio": audio_data
                    }))
            
            elif message["type"] == "audio_input":
                # Process audio input
                audio_data = message["audio"]
                language = message.get("language", "en-US")
                
                # Convert audio to text
                recognized_text = voice_processor.recognize_audio(audio_data, language)
                
                if recognized_text:
                    # Send recognized text
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    await websocket.send_text(json.dumps({
                        "type": "log",
                        "message": f"[{timestamp}] User (voice): {recognized_text}"
                    }))
                    
                    # Get AI response
                    lang_code = 'sw' if 'sw' in language else 'en'
                    ai_response = vertex_ai_response(recognized_text, lang_code)
                    
                    # Send response
                    await websocket.send_text(json.dumps({
                        "type": "ai_response",
                        "text": ai_response
                    }))
                    
                    # Generate and send audio
                    tts_lang = 'sw' if lang_code == 'sw' else 'en'
                    audio_response = voice_processor.text_to_speech(ai_response, tts_lang)
                    
                    if audio_response:
                        await websocket.send_text(json.dumps({
                            "type": "audio_response",
                            "audio": audio_response
                        }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Could not recognize speech. Please try again."
                    }))
    
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    import uvicorn
    
    # Create static directory if it doesn't exist
    os.makedirs("static", exist_ok=True)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)