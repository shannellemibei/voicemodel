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

# Configuration - Updated for Swahili
WAKEWORD = ["hujambo eva", "hey eva"]  
STOPWORD = ["kwaheri eva", "bye eva"]  
DONE_WORD = ["nimemaliza eva", "finished eva"]
CANCEL_WORD = ["ghairi", "cancel"]  

DO = os.getenv("DO")
USER = os.getenv("USER")
HOSTNAME = os.getenv("HOSTNAME")

# Audio configuration for noise handling
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5  # seconds
ENERGY_THRESHOLD = 2000  # Adjust based on your environment
DYNAMIC_ENERGY_THRESHOLD = True
PAUSE_THRESHOLD = 2.0  # waits 2 seconds of silence
PHRASE_THRESHOLD = 0.3  # more sensitive to speech start
NON_SPEAKING_DURATION = 1.0  # allows quiet speech

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
    
    def listen_for_segment(self, timeout=None, phrase_time_limit=8):
        """Listen for a segment of speech (part of a longer command)"""
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
            print(f"Error in segment listening: {e}")
            return None
    
    def recognize_with_confidence(self, audio, language='sw-TZ'):  
        """Speech recognition with confidence scoring"""
        try:
            # Try Swahili Speech Recognition with language variants
            languages_to_try = [language, 'sw-KE', 'sw-UG', 'en-US']  
            
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
        # Add instruction to respond in Swahili
        prompt = f"{prompt_text.strip()}\nTafadhali jibu kwa ufupi na wazi kwa Kiswahili."

        response = model.generate_content([prompt])
        raw_text = response.text

        # Remove all punctuation except periods and commas
        cleaned_text = re.sub(r"[^\w\s\.,?!]", "", raw_text)

        return cleaned_text.strip()
    except Exception as e:
        print(f"Error with Vertex AI: {e}")
        return "Nina tatizo la kuchakata ombi lako sasa hivi."  # "I'm having trouble processing that request right now."

def speech(text):
    """Convert text to speech and play it"""
    try:
        text_to_speech = gTTS(text=text, lang='sw')  # Changed to Swahili
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
                        speech(f"Ninasikiliza {USER}. Sema amri yako na useme 'nimemaliza eva' ukimaliza.")  
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
        greet = f"Habari za asubuhi {USER}" 
    elif 12 <= hour <= 16:
        greet = f"Habari za mchana {USER}"   
    elif 16 <= hour < 19:
        greet = f"Habari za jioni {USER}"   
    else:
        greet = f"Hujambo {USER}"            
    
    greet += f". Mimi ni {HOSTNAME}. Sema Hujambo Eva kuniamsha. Nipe amri yako na useme 'nimemaliza eva' ukimaliza. Unaweza pia kusema 'ghairi' kuanza upya. Ukimaliza sema kwaheri eva kunizima."
    # "I am [HOSTNAME]. Say Hello Eva to activate me. Give me your command and say 'finished eva' when finished. You can also say 'cancel' to start over. When you are done say goodbye eva to deactivate."
    
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
    
    # Check for partial matches (kwaheri + eva, stop + eva, etc.)
    eva_mentioned = "eva" in text_lower
    stop_words = ["kwaheri", "simama", "bye", "stop", "goodbye", "sleep", "quiet", "shut up"]
    
    if eva_mentioned:
        for stop_word in stop_words:
            if stop_word in text_lower:
                return True
    
    return False

def check_done_word(text):

    text_lower = text.lower().strip()
    
    for done_word in DONE_WORD:
        if done_word == text_lower or done_word in text_lower:
            return True
    
    return False

def check_cancel_word(text):
    text_lower = text.lower().strip()
    
    for cancel_word in CANCEL_WORD:
        if cancel_word in text_lower:
            return True
    
    return False

def get_command_preview(command_parts):
    if not command_parts:
        return "Hakuna amri bado"  # "No command yet"
    
    preview = " ".join(command_parts)
    if len(preview) > 50:
        return preview[:47] + "..."
    return preview

def listen():
    try:
        print("Listening for command... (Say 'nimemaliza eva' when you finish your command)")
        
        full_command = ""
        command_parts = []
        silence_count = 0
        max_silence = 3  # Allow 3 periods of silence before prompting
        
        while True:
            # Listen for a segment of the command
            audio = recognizer.listen_for_segment(timeout=15, phrase_time_limit=10)
            
            if audio is None:
                silence_count += 1
                if command_parts:
                    if silence_count >= max_silence:
                        # Long silence with partial command - offer options
                        preview = get_command_preview(command_parts)
                        speech(f"Nina: {preview}. Sema 'nimemaliza eva' kuchakata, 'ghairi' kuanza upya, au endelea na amri yako.")
                        # "I have: [preview]. Say 'finished eva' to process, 'cancel' to start over, or continue your command."
                        silence_count = 0
                        continue
                    else:
                        # Short silence - gentle prompt
                        speech("Bado ninasikiliza. Endelea au sema 'nimemaliza eva'.")  # "I'm still listening. Continue or say 'finished eva'."
                        continue
                else:
                    # No command started yet, timeout
                    speech("Sikuskia chochote. Tafadhali jaribu tena.")  # "I didn't hear anything. Please try again."
                    return None
            
            silence_count = 0  # Reset silence counter on successful audio
            segment, confidence = recognizer.recognize_with_confidence(audio, language='sw-KE')
            
            if segment is None:
                if command_parts:
                    speech("Sikuskia sehemu hiyo. Tafadhali endelea au sema 'nimemaliza'.")  # "I didn't catch that part. Please continue or say 'done'."
                    continue
                else:
                    speech("Sikuskia vizuri. Tafadhali jaribu tena.")  # "I couldn't hear you clearly. Please try again."
                    return None
            
            print(f"Heard segment: '{segment}' (confidence: {confidence:.2f})")
            
            # Check for cancel command
            if check_cancel_word(segment):
                speech("Amri imeghairiwa. Nipe amri mpya.")  # "Command cancelled. Give me a new command."
                return None
            
            # Check if this segment contains "done"
            if check_done_word(segment):
                if command_parts:
                    # Command is complete
                    full_command = " ".join(command_parts)
                    print(f"Complete command: '{full_command}'")
                    
                    # Confirm before processing long commands
                    if len(full_command) > 100:
                        preview = get_command_preview(command_parts)
                        speech(f"Ninachakata: {preview}")  # "Processing: [preview]"
                    
                    break
                else:
                    # User said "done" without giving a command
                    speech("Hukunitia amri. Tafadhali jaribu tena.")  # "You didn't give me a command. Please try again."
                    return None
            
            # Check for exit commands in this segment
            exit_words = ['ondoka', 'toka', 'kwaheri', 'leave', 'exit', 'quit', 'goodbye']
            if any(word in segment for word in exit_words):
                farewell = f'Kwaheri {USER}, uwe na siku njema!'  # "Goodbye [USER], have a great day!"
                speech(farewell)
                print(farewell)
                return farewell
            
            # Add this segment to the command parts
            command_parts.append(segment)
            
            # Give contextual feedback
            if len(command_parts) == 1:
                speech("Sawa. Endelea au sema 'nimemaliza'.")  # "Got it. Continue or say 'done'."
            elif len(command_parts) % 3 == 0:  # Every 3rd segment
                speech("Bado ninasikiliza...")  # "Still listening..."
            else:
                # Just print to console to avoid too much audio feedback
                print("Continuing to listen...")
        
        # Process the complete command
        if full_command:
            response = process_command(full_command)
            return response
        else:
            speech("Sikupokea amri kamili. Tafadhali jaribu tena.")  # "I didn't receive a complete command. Please try again."
            return None
    
    except Exception as e:
        print(f"Error in listen(): {e}")
        speech("Samahani, nilitata kukusikia. Hebu tujaribu tena.")  # "Sorry, I had trouble hearing you. Let's try again."
        return None

def process_command(query):
    
    """Process user command and generate response"""
    query = query.lower().strip()
    print(f"Processing command: {query}")
    
    # Log command for debugging/analytics
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] User command: {query}")
    
    # Check predefined commands first (with partial matching)
    for key in COMMANDS:
        if key in query or any(word in query for word in key.split()):
            response = COMMANDS[key]
            speech(response)
            print(f"Response: {response}")
            return response
    
    # Show processing indicator for longer commands
    if len(query) > 50:
        speech("Ninachakata ombi lako...")  # "Processing your request..."
    
    response = vertex(query)
    speech(response)
    print(f"AI Response: {response}")
    return response   

def main():
    
    print("=== Eva Voice Assistant Starting ===")
    print("New flow: Say 'Hujambo Eva' -> Give command -> Say 'nimemaliza eva' to finish")
    
    # Test microphone
    try:
        test_audio = recognizer.listen_with_noise_filtering(timeout=1, phrase_time_limit=1)
        print("Microphone test successful!")
    except:
        print("Microphone test failed - restart execution please !")
    

    greetings()
    
    try:
        while True:
        
            wake_word()
            
        
            print("*BEEP* Activated! Listening for commands...")
            
            # Main command loop
            command_timeout = 0
            max_command_timeout = 3
            
            while True:
                command = listen()
                
                if command is None:
                    command_timeout += 1
                    if command_timeout >= max_command_timeout:
                        speech("Naenda kulala. Sema Hujambo Eva kuniamsha.")  # "Going back to sleep. Say Hello Eva to wake me up."
                        break
                    continue
                
                command_timeout = 0  # Reset timeout on successful command
                
                if check_stop_words(command):
                    speech("Sawa. Sema tu Hujambo Eva ukihitaji msaada.")  # "Okay. Just say Hello Eva when you need me again."
                    break
                    
                # Check for exit commands
                exit_words = ['ondoka', 'toka', 'kwaheri', 'leave', 'exit', 'quit', 'goodbye']
                if any(word in command.lower() for word in exit_words):
                    print("Exiting...")
                    return
                    
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        speech("Kwaheri!")  # "Goodbye!"
    except Exception as e:
        print(f"Unexpected error: {e}")
        speech("Nina tatizo. Tafadhali nianzishe upya.")  # "I'm having some trouble. Please restart me."

if __name__ == "__main__":
    main()