#!/usr/bin/env python3
"""
ECET 35901 - Final Project, RPi Spotify Voice Search | Record, Play, Transcribe
Author: John Danison
Date: Fall 2025
"""

import os
import sys
import subprocess

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


# ==========================================================
# USER INTERFACE
# ==========================================================
print("\n--- Voice Recorder & Speech-to-Text ---")
print("R = Record microphone")
print("P = Play last recording")
print("T = Transcribe recording to text")
print("Q = Quit\n")


# ==========================================================
# MAIN LOOP
# ==========================================================
while True:
    choice = input("Enter command (R/P/T/Q): ").strip().lower()

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

    # ------------------------- QUIT -----------------------
    elif choice == "q":
        print("\nGoodbye!\n")
        break

    # ----------------------- INVALID ----------------------
    else:
        print("Invalid option, use R, P, T, or Q.\n")
