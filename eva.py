import speech_recognition as sr
import os
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
from commands import COMMANDS
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import aiplatform
import sys
import time
import threading
import queue
import subprocess
import re

# Load environment variables
load_dotenv()

# Set up Google Cloud credentials
try:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    aiplatform.init(project=os.getenv("PROJECT_ID"))
    model = GenerativeModel(os.getenv("MODEL_NAME"))
except Exception as e:
    print(f"Error initializing Google Cloud services: {e}")
    sys.exit(1)

# Suppress warnings
os.environ["PYTHONWARNINGS"] = "ignore"

# Configuration
WAKEWORD = ["hey eva", "eva"]
STOPWORD = ["bye eva", "stop eva", "sleep eva", "goodbye eva"]

DO = os.getenv("DO")
USER = os.getenv("USER", "User")
HOSTNAME = os.getenv("HOSTNAME", "Eva")

# Audio configuration for noise handling - UPDATED FOR LONG COMMANDS
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5  # seconds
ENERGY_THRESHOLD = 2000  # Adjust based on your environment
DYNAMIC_ENERGY_THRESHOLD = True
PAUSE_THRESHOLD = 2.0  # INCREASED from 0.8 - waits 2 seconds of silence
PHRASE_THRESHOLD = 0.3  # DECREASED from 0.5 - more sensitive to speech start
NON_SPEAKING_DURATION = 1.0  # INCREASED from 0.5 - allows quiet speech

class NoiseRobustRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone(sample_rate=SAMPLE_RATE)
        self.setup_microphone()
        
    def setup_microphone(self):
        """Configure microphone with noise handling"""
        print("Calibrating microphone for ambient noise...")
        with self.microphone as source:
            # Longer calibration for better noise baseline
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            
        # Enhanced audio settings
        self.recognizer.energy_threshold = ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = DYNAMIC_ENERGY_THRESHOLD
        self.recognizer.pause_threshold = PAUSE_THRESHOLD
        self.recognizer.phrase_threshold = PHRASE_THRESHOLD
        self.recognizer.non_speaking_duration = NON_SPEAKING_DURATION
        
        print(f"Energy threshold set to: {self.recognizer.energy_threshold}")
        
    def listen_with_noise_filtering(self, timeout=None, phrase_time_limit=None):
        """Enhanced listening with noise filtering"""
        try:
            with self.microphone as source:
                # Quick ambient noise adjustment
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                
                # Listen with enhanced settings
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
                
            return audio
            
        except Exception as e:
            print(f"Error in noise filtering: {e}")
            return None
    
    def listen_for_command(self, timeout=15, phrase_time_limit=12):
        """Specialized listening for longer commands"""
        try:
            with self.microphone as source:
                # Temporarily adjust settings for longer commands
                original_pause = self.recognizer.pause_threshold
                original_non_speaking = self.recognizer.non_speaking_duration
                
                # Use longer thresholds for commands
                self.recognizer.pause_threshold = 2.0
                self.recognizer.non_speaking_duration = 1.0
                
                # Quick ambient noise adjustment
                self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
                
                # Listen with enhanced settings
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit
                )
                
                # Restore original settings
                self.recognizer.pause_threshold = original_pause
                self.recognizer.non_speaking_duration = original_non_speaking
                
                return audio
                
        except Exception as e:
            print(f"Error in command listening: {e}")
            return None
    
    def recognize_with_confidence(self, audio, language='en-US'):
        """Speech recognition with confidence scoring"""
        try:
            # Try Google Speech Recognition with language variants
            languages_to_try = [language, 'en-US', 'en-GB', 'en-IN']
            
            for lang in languages_to_try:
                try:
                    # Get recognition results
                    result = self.recognizer.recognize_google(audio, language=lang, show_all=True)
                    
                    if result and isinstance(result, dict) and 'alternative' in result:
                        # Get the best alternative with confidence
                        alternatives = result['alternative']
                        if alternatives:
                            best_result = alternatives[0]
                            confidence = best_result.get('confidence', 0)
                            transcript = best_result.get('transcript', '')
                            
                            # Only return if confidence is reasonable
                            if confidence > 0.3 or len(alternatives) == 1:
                                return transcript.lower(), confidence
                                
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    continue
            
            # Fallback to simple recognition
            result = self.recognizer.recognize_google(audio, language=language)
            return result.lower(), 0.8
            
        except sr.UnknownValueError:
            return None, 0
        except sr.RequestError as e:
            print(f"Recognition service error: {e}")
            return None, 0

# Global recognizer instance
recognizer = NoiseRobustRecognizer()

def vertex(prompt_text):
    try:
        # Add instruction to keep response short
        prompt = f"{prompt_text.strip()}\nPlease respond briefly and clearly."

        response = model.generate_content([prompt])
        raw_text = response.text

        # Remove all punctuation except periods and commas
        cleaned_text = re.sub(r"[^\w\s\.,?!]", "", raw_text)

        return cleaned_text.strip()
    except Exception as e:
        print(f"Error with Vertex AI: {e}")
        return "I'm having trouble processing that request right now."

def speech(text):
    """Convert text to speech and play it"""
    try:
        text_to_speech = gTTS(text=text, lang='en')
        filename = 'sound.mp3'
        text_to_speech.save(filename)
        sound = AudioSegment.from_file(filename)
        play(sound)
        os.remove(filename)
    except Exception as e:
        print(f"Error with text-to-speech: {e}")

def wake_word():
    """Listen for wake word with noise robustness"""
    print("Listening for wakeword... (Speak clearly)")
    
    consecutive_failures = 0
    max_failures = 5
    
    while True:
        try:
            # Listen with shorter timeout for responsiveness
            audio = recognizer.listen_with_noise_filtering(timeout=2, phrase_time_limit=4)
            
            if audio is None:
                continue
                
            # Recognize with confidence
            query, confidence = recognizer.recognize_with_confidence(audio)
            
            if query is None:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print("Recalibrating microphone due to poor recognition...")
                    recognizer.setup_microphone()
                    consecutive_failures = 0
                continue
            
            consecutive_failures = 0
            print(f"Heard: '{query}' (confidence: {confidence:.2f})")
            
            # Check for wake words with partial matching
            for word in WAKEWORD:
                if word in query or any(w in query for w in word.split()):
                    if confidence > 0.4 or word in query:  # Lower threshold for exact matches
                        print("Wakeword detected!")
                        speech(f"I'm Listening {USER}")
                        return
                        
        except sr.WaitTimeoutError:
            continue
        except Exception as e:
            print(f"Error in wake_word: {e}")
            time.sleep(0.5)
            continue

def greetings():
    """Generate and speak greeting"""
    hour = datetime.now().hour
    
    if 6 <= hour < 12:
        greet = f"Good morning {USER}"
    elif 12 <= hour <= 16:
        greet = f"Good afternoon {USER}"    
    elif 16 <= hour < 19:
        greet = f"Good evening {USER}"    
    else:
        greet = f"Hello {USER}"    
    
    greet += f". I am {HOSTNAME}. Say Hey Eva to activate me. When you are done say bye eva to deactivate."
    
    speech(greet)
    print(greet)
    return greet

def check_stop_words(text):
    """Check if text contains stop words"""
    text_lower = text.lower()
    
    # Check for exact stopword matches
    for stopword in STOPWORD:
        if stopword in text_lower:
            return True
    
    # Check for partial matches (bye + eva, stop + eva, etc.)
    eva_mentioned = "eva" in text_lower
    stop_words = ["bye", "stop", "goodbye", "sleep", "quiet", "shut up"]
    
    if eva_mentioned:
        for stop_word in stop_words:
            if stop_word in text_lower:
                return True
    
    return False

def listen():
    """Listen for user commands with enhanced noise handling - UPDATED FOR LONG COMMANDS"""
    try:
        print("Listening for command... (Speak clearly, I'll wait for you to finish)")
        
        # Use specialized command listening with longer timeouts
        audio = recognizer.listen_for_command(timeout=15, phrase_time_limit=12)
        
        if audio is None:
            return None
            
        query, confidence = recognizer.recognize_with_confidence(audio, language='en-IN')
        
        if query is None:
            speech("I couldn't hear you clearly. Please try again.")
            return None
            
        print(f"You said: '{query}' (confidence: {confidence:.2f})")
        
        # Lower confidence threshold for longer commands (was 0.3, now 0.2)
        if confidence < 0.2:
            speech("I'm not sure I understood correctly. Could you repeat that?")
            return None
        
        # Check for exit commands
        exit_words = ['leave', 'exit', 'quit', 'goodbye']
        if any(word in query for word in exit_words):
            farewell = f'Good bye {USER}, have an amazing day!'
            speech(farewell)
            print(farewell)
            return farewell
        
        # Process the command
        response = process_command(query)
        return response
    
    except sr.WaitTimeoutError:
        speech("I didn't hear anything. Please try again.")
        return None
        
    except Exception as e:
        print(f"Error in listen(): {e}")
        speech("Sorry, I had trouble hearing you. Let's try again.")
        return None

def process_command(query):
    """Process user command and generate response"""
    query = query.lower().strip()
    print(f"Processing command: {query}")
    
    # Check predefined commands first (with partial matching)
    for key in COMMANDS:
        if key in query or any(word in query for word in key.split()):
            response = COMMANDS[key]
            speech(response)
            print(f"Response: {response}")
            return response
    
    response = vertex(query)
    speech(response)
    print(f"AI Response: {response}")
    return response   

def main():
    """Main function """
    print("=== Eva Voice Assistant Starting ===")
    print("Optimized for noisy environments and long commands")
    
    # Test microphone
    try:
        print("Testing microphone...")
        test_audio = recognizer.listen_with_noise_filtering(timeout=1, phrase_time_limit=1)
        print("Microphone test successful!")
    except:
        print("Microphone test failed - but continuing anyway")
    
    # Start with greetings
    greetings()
    
    try:
        while True:
            # Wait for wake word
            wake_word()
            
            # Give audio feedback
            print("*BEEP* Activated! Listening for commands...")
            
            # Main command loop
            command_timeout = 0
            max_command_timeout = 3
            
            while True:
                command = listen()
                
                if command is None:
                    command_timeout += 1
                    if command_timeout >= max_command_timeout:
                        speech("Going back to sleep. Say Hey Eva to wake me up.")
                        break
                    continue
                
                command_timeout = 0  # Reset timeout on successful command
                
                if check_stop_words(command):
                    speech("Okay. Just say Hey Eva when you need me again.")
                    break
                    
                # Check for exit commands
                exit_words = ['leave', 'exit', 'quit', 'goodbye']
                if any(word in command.lower() for word in exit_words):
                    print("Exiting...")
                    return
                    
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        speech("Goodbye!")
    except Exception as e:
        print(f"Unexpected error: {e}")
        speech("I'm having some trouble. Please restart me.")

if __name__ == "__main__":
    main()