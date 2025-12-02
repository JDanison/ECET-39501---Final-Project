#!/usr/bin/env python3
"""
ECET 35901 - Final Project: Spotify Voice Control System
Author: John Danison
Date: Fall 2025

One-stop application for:
- Voice recording and transcription
- Volume control via ADC potentiometer
- Spotify search integration via Node-RED
"""

import os
import sys
import subprocess
import threading
from gpiozero import MCP3008
from time import sleep
import paho.mqtt.client as mqtt

# ==========================================================
# AUTO-ACTIVATE VIRTUAL ENVIRONMENT
# ==========================================================
VENV_ACTIVATE = os.path.join(os.path.dirname(__file__), "venv", "bin", "activate_this.py")

if os.path.exists(VENV_ACTIVATE):
    if sys.prefix == sys.base_prefix:  # Not already in venv
        print("Activating virtual environment...")
        with open(VENV_ACTIVATE) as f:
            exec(f.read(), dict(__file__=VENV_ACTIVATE))
else:
    print("WARNING: venv not found — Whisper may not import.")
    print(f"Expected at: {VENV_ACTIVATE}\n")


# ==========================================================
# IMPORT WHISPERCPP (after venv activation)
# ==========================================================
try:
    from whispercpp import Whisper
    whisper_available = True
except Exception as e:
    print("\nWhisper not available. Transcription will be disabled.")
    print("Error:", e)
    whisper_available = False


# ==========================================================
# CONFIGURATION
# ==========================================================
# Audio Recording/Playback
RECORD_CMD = [
    "arecord",
    "-D", "plughw:4,0",    # I2S microphone
    "-c1",
    "-r", "48000",
    "-f", "S32_LE",
    "songrequest.wav"
]

PLAY_CMD = [
    "aplay",
    "-D", "plughw:3,0",    # USB speakers
    "songrequest.wav"
]

AUDIO_FILE = "songrequest.wav"

# ADC Volume Control
ADC_CHANNEL = 0
UPDATE_DELAY = 0.2  # seconds between updates

# MQTT Configuration
MQTT_BROKER = "localhost"  # Use localhost since script runs on same Pi as broker
MQTT_PORT = 1883
MQTT_TOPIC = "voice/spotify"
MQTT_CONTROL_TOPIC = "voice/control"  # Topic for button commands
MQTT_STATUS_TOPIC = "voice/status"  # Topic for status updates

# Global flags
volume_monitoring = False
recording_process = None
mqtt_control_enabled = False


# ==========================================================
# MQTT FUNCTIONS
# ==========================================================
def parse_voice_command(transcript):
    """
    Parse voice command to extract song and artist.
    Expected format: "Play Song_Name by Artist_Name"
    Returns: "Song_Name Artist_Name" (without 'Play' and 'by')
    """
    # Convert to lowercase for case-insensitive matching
    text = transcript.strip()
    text_lower = text.lower()
    
    # Remove "play," or "play" from the beginning
    if text_lower.startswith("play, "):
        text = text[6:].strip()  # Remove "play, " (6 characters)
    elif text_lower.startswith("play "):
        text = text[5:].strip()  # Remove "play " (5 characters)
    
    # Remove any leading/trailing commas and periods
    text = text.strip(',.')
    
    # Find and remove " by " (case-insensitive)
    by_index = text.lower().find(" by ")
    if by_index != -1:
        song_name = text[:by_index].strip()
        artist_name = text[by_index + 4:].strip()  # +4 to skip " by "
        
        # Capitalize first letter of each word properly (avoiding apostrophe issue)
        song_name = ' '.join(word.capitalize() for word in song_name.split())
        artist_name = ' '.join(word.capitalize() for word in artist_name.split())
        
        result = f"{song_name} {artist_name}"
    else:
        # If no " by " found, just return the text as-is (without "play")
        result = ' '.join(word.capitalize() for word in text.split())
    
    return result


def send_to_nodered(transcript):
    """Send transcription to Node-RED via MQTT."""
    try:
        # Parse the voice command to extract song and artist
        search_query = parse_voice_command(transcript)
        
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        print(f"  Original: '{transcript}'")
        print(f"  Formatted: '{search_query}'")
        print(f"  Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"  Publishing to topic: {MQTT_TOPIC}")
        mqtt_client.publish(MQTT_TOPIC, search_query)
        mqtt_client.disconnect()
        print(f"✓ Sent to Node-RED: '{search_query}'\n")
        return True
    except ConnectionRefusedError:
        print(f"✗ Connection refused - Is MQTT broker running on {MQTT_BROKER}?\n")
        print(f"  Try: sudo systemctl status mosquitto\n")
        return False
    except Exception as e:
        print(f"✗ Error sending to Node-RED: {e}\n")
        return False


def send_status_update(status):
    """Send status update to Node-RED via MQTT."""
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.publish(MQTT_STATUS_TOPIC, status)
        mqtt_client.disconnect()
    except Exception as e:
        print(f"Error sending status: {e}")


# ==========================================================
# MQTT CONTROL FUNCTIONS
# ==========================================================
def start_recording():
    """Start recording audio in background."""
    global recording_process
    
    if recording_process and recording_process.poll() is None:
        print("Recording already in progress...")
        return False
    
    print("\n🎤 Recording started... (waiting for stop command)")
    send_status_update("Recording")
    
    # Clear any previous search results
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.publish(MQTT_TOPIC, "")  # Clear search
        mqtt_client.disconnect()
    except:
        pass
    
    try:
        recording_process = subprocess.Popen(RECORD_CMD, 
                                            stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"Error starting recording: {e}")
        send_status_update("error")
        return False


def stop_recording_and_transcribe():
    """Stop recording and automatically transcribe."""
    global recording_process
    
    if not recording_process or recording_process.poll() is not None:
        print("No active recording to stop.")
        return False
    
    # Stop the recording process
    print("🛑 Stopping recording...")
    recording_process.terminate()
    recording_process.wait()
    recording_process = None
    print(f"✓ Saved as {AUDIO_FILE}\n")
    
    # Auto-transcribe
    transcribe_audio()
    return True


def transcribe_audio():
    """Transcribe the recorded audio and send to Node-RED."""
    if not os.path.exists(AUDIO_FILE):
        print("\nNo recording found! Record audio first.\n")
        send_status_update("error")
        return False
    
    print("\nTranscribing audio... please wait.\n")
    send_status_update("Processing Request")
    
    WHISPER_PATH = os.path.join(os.path.dirname(__file__), "whisper.cpp", "build", "bin", "whisper-cli")
    MODEL_PATH = os.path.join(os.path.dirname(__file__), "whisper.cpp", "models", "ggml-tiny.en.bin")
    
    try:
        result = subprocess.check_output([
            WHISPER_PATH,
            "-m", MODEL_PATH,
            "-f", AUDIO_FILE,
            "-nt"  # no timestamps
        ], text=True)
        
        transcript = result.strip()
        
        print("=== TRANSCRIPTION RESULT ===")
        print(transcript)
        print("============================\n")
        
        # Send to Node-RED via MQTT
        print("Sending to Node-RED...")
        send_to_nodered(transcript)
        send_status_update("")  # Clear status
        return True
        
    except Exception as e:
        print("\nError during transcription:")
        print(e)
        print()
        send_status_update("error")
        return False


def on_mqtt_connect(client, userdata, flags, rc):
    """Callback when MQTT client connects."""
    if rc == 0:
        print("✓ MQTT control listener connected")
        client.subscribe(MQTT_CONTROL_TOPIC)
        print(f"  Listening on: {MQTT_CONTROL_TOPIC}\n")
    else:
        print(f"✗ MQTT connection failed with code {rc}")


def on_mqtt_message(client, userdata, msg):
    """Callback when MQTT message is received."""
    global recording_process
    
    command = msg.payload.decode().strip().lower()
    print(f"\n📨 Received command: '{command}'")
    
    # Handle toggle command
    if command == "button_pressed":
        # Check if currently recording
        if recording_process and recording_process.poll() is None:
            # Currently recording, so stop and transcribe
            stop_recording_and_transcribe()
        else:
            # Not recording, so start
            start_recording()
    # Handle boolean values
    elif command == "true":
        start_recording()
    elif command == "false":
        stop_recording_and_transcribe()
    # Also support text commands for compatibility
    elif command == "record" or command == "start":
        start_recording()
    elif command == "stop" or command == "transcribe":
        stop_recording_and_transcribe()
    else:
        print(f"Unknown command: {command}")


def start_mqtt_listener():
    """Start MQTT listener in background thread."""
    global mqtt_control_enabled
    
    def mqtt_loop():
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            client.on_connect = on_mqtt_connect
            client.on_message = on_mqtt_message
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print(f"MQTT listener error: {e}")
    
    mqtt_thread = threading.Thread(target=mqtt_loop, daemon=True)
    mqtt_thread.start()
    mqtt_control_enabled = True
    return mqtt_thread


# ==========================================================
# VOLUME CONTROL FUNCTIONS
# ==========================================================
def set_volume(volume_percent):
    """Set system volume using amixer (0-100)."""
    try:
        subprocess.run(['amixer', 'set', 'Master', f'{volume_percent}%'], 
                      check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def volume_monitor_thread(adc):
    """Background thread to continuously monitor and adjust volume."""
    global volume_monitoring
    print("Volume monitoring started (running in background).\n")
    
    while volume_monitoring:
        try:
            # Read analog value (0.0 to 1.0)
            adc_value = adc.value
            
            # Scale to display value 0-100%
            display_volume = int(adc_value * 100)
            
            # Map to actual system volume 9-100% (avoid cutout at low end)
            actual_volume = int(adc_value * 91) + 9
            
            # Set system volume
            set_volume(actual_volume)
            
            sleep(UPDATE_DELAY)
        except Exception as e:
            print(f"Volume monitoring error: {e}")
            break


# ==========================================================
# INITIALIZE ADC
# ==========================================================
try:
    adc = MCP3008(channel=ADC_CHANNEL)
    adc_available = True
except Exception as e:
    print(f"WARNING: ADC not available - {e}")
    adc_available = False


# ==========================================================
# STARTUP FUNCTIONS
# ==========================================================
def start_spotifyd():
    """Start spotifyd daemon if not already running."""
    try:
        # Check if spotifyd is already running
        result = subprocess.run(['pgrep', '-x', 'spotifyd'], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ spotifyd already running")
            return True
        
        # Start spotifyd from current directory
        print("Starting spotifyd...")
        spotifyd_path = os.path.join(os.path.dirname(__file__), 'spotifyd')
        subprocess.Popen([spotifyd_path, '--no-daemon'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL,
                        cwd=os.path.dirname(__file__))
        sleep(2)  # Give it time to start
        print("✓ spotifyd started")
        return True
    except Exception as e:
        print(f"✗ Error starting spotifyd: {e}")
        return False


# ==========================================================
# SYSTEM INITIALIZATION
# ==========================================================
print("\n" + "="*50)
print("ECET 35901 - Final Project")
print("Spotify Voice Control System")
print("="*50 + "\n")
print("Initializing system...\n")

# Start spotifyd
start_spotifyd()

# Start MQTT control listener
print("Starting MQTT control listener...")
start_mqtt_listener()

# Auto-start volume monitoring if ADC is available
volume_thread = None
if adc_available:
    print("Starting volume control...")
    volume_monitoring = True
    volume_thread = threading.Thread(target=volume_monitor_thread, args=(adc,), daemon=True)
    volume_thread.start()
else:
    print("Volume control not available (ADC not found)")

print("\nSystem ready!\n")

# ==========================================================
# USER INTERFACE
# ==========================================================
print("Commands:")
print("  R = Record voice command")
print("  P = Play last recording")
print("  T = Transcribe & send to Spotify")
if adc_available:
    print("  V = Toggle volume monitoring (currently ON)")
print("  Q = Quit")
print("\nMQTT Control:")
print("  Topic: voice/control")
print("  Commands: 'button_pressed' (toggle record/stop)")
print("\nMQTT Status:")
print("  Topic: voice/status")
print("  Messages: recording, Processing Request, error\n")


# ==========================================================
# MAIN LOOP
# ==========================================================

while True:
    choice = input("Enter command (R/P/T/V/Q): ").strip().lower()

    # ---------------------- RECORD ------------------------
    if choice == "r":
        print("\nRecording... speak now!")
        print("Say: 'Play [Song Name] by [Artist Name]'")
        print("Press CTRL+C to stop.\n")
        try:
            subprocess.run(RECORD_CMD)
        except KeyboardInterrupt:
            print("\nRecording manually stopped.")

        print("Saved as songrequest.wav\n")

    # ---------------------- PLAYBACK ----------------------
    elif choice == "p":
        print("\nPlaying back...")
        subprocess.run(PLAY_CMD)
        print("Done.\n")

    # ---------------------- TRANSCRIBE --------------------
    elif choice == "t":
        transcribe_audio()

    # ---------------------- VOLUME CONTROL ----------------
    elif choice == "v":
        if not adc_available:
            print("\nADC not available on this system.\n")
            continue
            
        if not volume_monitoring:
            # Start volume monitoring
            volume_monitoring = True
            volume_thread = threading.Thread(target=volume_monitor_thread, args=(adc,), daemon=True)
            volume_thread.start()
            print("Volume monitoring: ON\n")
        else:
            # Stop volume monitoring
            volume_monitoring = False
            if volume_thread:
                volume_thread.join(timeout=1.0)
            print("Volume monitoring: OFF\n")

    # ------------------------- QUIT -----------------------
    elif choice == "q":
        print("\nShutting down...")
        
        # Clear voice status and query
        try:
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.publish(MQTT_STATUS_TOPIC, "")  # Clear status
            mqtt_client.publish(MQTT_TOPIC, "")  # Clear query
            mqtt_client.disconnect()
            print("✓ Cleared dashboard displays")
        except:
            pass
        
        # Stop volume monitoring if running
        if volume_monitoring:
            volume_monitoring = False
            if volume_thread:
                volume_thread.join(timeout=1.0)
            print("✓ Volume monitoring stopped")
        
        # Stop spotifyd
        try:
            subprocess.run(['pkill', 'spotifyd'], capture_output=True)
            print("✓ spotifyd stopped")
        except:
            pass
        
        print("\nGoodbye!\n")
        break

    # ----------------------- INVALID ----------------------
    else:
        print("Invalid option, use R, P, T, V, or Q.\n")
