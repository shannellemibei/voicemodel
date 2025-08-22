import sys
from english import (
    recognizer, 
    greetings, 
    wake_word, 
    listen, 
    speech, 
    check_stop_words
)

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