#!/usr/bin/env python3
"""
ECET 35901 - Final Project, RPi Spotify Voice Search | Combined Voice & Volume Control
Author: John Danison
Date: Fall 2025
"""

import os
import sys
import subprocess
import threading
from gpiozero import MCP3008
from time import sleep

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
    "soundrequest.wav"
]

PLAY_CMD = [
    "aplay",
    "-D", "plughw:3,0",    # USB speakers
    "soundrequest.wav"
]

AUDIO_FILE = "soundrequest.wav"

# ADC Volume Control
ADC_CHANNEL = 0
UPDATE_DELAY = 0.2  # seconds between updates

# Global flag to control volume monitoring thread
volume_monitoring = False


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
# USER INTERFACE
# ==========================================================
print("\n============================================")
print("ECET 35901 - Final Project")
print("Voice Recorder & Volume Control")
print("============================================\n")
print("R = Record microphone")
print("P = Play last recording")
print("T = Transcribe recording to text")
if adc_available:
    print("V = Toggle volume monitoring (ADC)")
print("Q = Quit\n")


# ==========================================================
# MAIN LOOP
# ==========================================================
volume_thread = None

while True:
    choice = input("Enter command (R/P/T/V/Q): ").strip().lower()

    # ---------------------- RECORD ------------------------
    if choice == "r":
        print("\nRecording... speak now!")
        print("Press CTRL+C to stop.\n")
        try:
            subprocess.run(RECORD_CMD)
        except KeyboardInterrupt:
            print("\nRecording manually stopped.")

        print("Saved as soundrequest.wav\n")

    # ---------------------- PLAYBACK ----------------------
    elif choice == "p":
        print("\nPlaying back...")
        subprocess.run(PLAY_CMD)
        print("Done.\n")

    # ---------------------- TRANSCRIBE --------------------
    elif choice == "t":
        if not os.path.exists(AUDIO_FILE):
            print("\nNo recording found! Record audio first.\n")
            continue

        print("\nTranscribing audio... please wait.\n")

        WHISPER_PATH = os.path.join(os.path.dirname(__file__), "whisper.cpp", "build", "bin", "whisper-cli")
        MODEL_PATH = os.path.join(os.path.dirname(__file__), "whisper.cpp", "models", "ggml-tiny.en.bin")

        try:
            result = subprocess.check_output([
                WHISPER_PATH,
                "-m", MODEL_PATH,
                "-f", AUDIO_FILE,
                "-nt"  # no timestamps
            ], text=True)

            print("=== TRANSCRIPTION RESULT ===")
            print(result.strip())
            print("============================\n")

        except Exception as e:
            print("\nError during transcription:")
            print(e)
            print()

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
        else:
            # Stop volume monitoring
            volume_monitoring = False
            if volume_thread:
                volume_thread.join(timeout=1.0)
            print("Volume monitoring stopped.\n")

    # ------------------------- QUIT -----------------------
    elif choice == "q":
        print("\nShutting down...")
        
        # Stop volume monitoring if running
        if volume_monitoring:
            volume_monitoring = False
            if volume_thread:
                volume_thread.join(timeout=1.0)
        
        print("Goodbye!\n")
        break

    # ----------------------- INVALID ----------------------
    else:
        print("Invalid option, use R, P, T, V, or Q.\n")
