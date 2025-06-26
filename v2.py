import speech_recognition as sr
import os
import subprocess as sp
from datetime import datetime
from dotenv import load_dotenv
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
from commands import COMMANDS
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import aiplatform
import sys


load_dotenv()


try:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    aiplatform.init(project=os.getenv("PROJECT_ID"))
    model = GenerativeModel(os.getenv("MODEL_NAME"))
except Exception as e:
    print(f"Error initializing Google Cloud services: {e}")
    sys.exit(1)


os.environ["PYTHONWARNINGS"] = "ignore"

WAKEWORD = ["hey eva", "eva"]
STOPWORD = ["bye eva", "stop eva"]

DO = os.getenv("DO")
USER = os.getenv("USER", "User")  # Default fallback
HOSTNAME = os.getenv("HOSTNAME", "Eva")  # Default fallback

def vertex(prompt_text):
    try:
        response = model.generate_content([prompt_text])
        return response.text
    except Exception as e:
        print(f"Error with Vertex AI: {e}")
        return "I'm having trouble processing that request right now."

def speech(text):
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
    
    r = sr.Recognizer()
    print("Listening for wakeword...")
    
    while True:
        try:
            with sr.Microphone(device_index=0) as source:
                r.adjust_for_ambient_noise(source, duration=1)
                print("Listening...")
                audio = r.listen(source, phrase_time_limit=4, timeout=1)
            
            query = r.recognize_google(audio).lower()
            print("Heard:", query)
            
            for word in WAKEWORD:
                if word in query:
                    print("Wakeword detected!")
                    return
                    
        except sr.WaitTimeoutError:
            # Timeout is normal, continue listening
            continue
        except sr.UnknownValueError:
            # Couldn't understand audio, continue listening
            continue
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
            continue
        except Exception as e:
            print(f"Error in wake_word: {e}")
            continue

def greetings():

    hour = datetime.now().hour
    
    if 6 <= hour < 12:
        greet = f"Good morning {USER}"
    elif 12 <= hour <= 16:
        greet = f"Good afternoon {USER}"    
    elif 16 <= hour < 19:
        greet = f"Good evening {USER}"    
    else:
        greet = f"Hello {USER}"    
    
    greet += f". I am {HOSTNAME}. How may I assist you? Say Hey Eva to start me up!"
    
    speech(greet)
    print(greet)
    return greet

def listen():
    r = sr.Recognizer()
    
    try:
        with sr.Microphone(device_index=0) as source:
            print("Listening for command...")
            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=10, phrase_time_limit=5)

        query = r.recognize_google(audio, language='en-in')
        print(f"You said: {query}")
        
        # Check for exit commands
        if any(word in query.lower() for word in ['leave', 'exit', 'quit']):
            farewell = f'Good bye {USER}, have an amazing day!'
            speech(farewell)
            print(farewell)
            return farewell
        
        response = process_command(query)
        return response
    
    except sr.WaitTimeoutError:
        speech("I didn't hear anything. Please try again.")
        return None
        
    except sr.UnknownValueError:
        speech("Sorry, I couldn't understand what you said. Can you please repeat that?")
        return None

    except sr.RequestError as e:
        speech("Sorry I am having trouble connecting to the recognition service.")
        print(f"Request error: {e}")
        return None
        
    except Exception as e:
        print(f"Error in listen(): {e}")
        return None

def process_command(query):
    query = query.lower().strip()
    print(f"Processing command: {query}")
    
    # Check predefined commands first
    for key in COMMANDS:
        if key in query:
            response = COMMANDS[key]
            speech(response)
            print(f"Response: {response}")
            return response
    
    # Use Vertex AI for other queries
    response = vertex(query)
    speech(response)
    print(f"AI Response: {response}")
    return response   

def main():

    print("Voice Assistant Starting...")
    
    # Check if microphone is available
    try:
        r = sr.Recognizer()
        with sr.Microphone(device_index=0) as source:
            print("Microphone test successful")
    except Exception as e:
        print(f"Microphone error: {e}")
        return
    
    # Start with greetings
    greetings()
    
    try:
        while True:
            # Wait for wake word
            wake_word()
            
            # Main command loop
            while True:
                command = listen()
                
                if command is None:
                    continue
                
                # Check for stop words
                if any(stopword in command.lower() for stopword in STOPWORD):
                    speech("Okay. Just say Hey Eva when you need me again.")
                    break
                    
                # Check for exit commands
                if any(word in command.lower() for word in ['leave', 'exit', 'quit']):
                    print("Exiting...")
                    return
                    
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        speech("Goodbye!")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()