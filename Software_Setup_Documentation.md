# Software Setup – Chronological Order

## Project Overview: Spotify Voice Control System
This project implements a voice-controlled Spotify music player on a Raspberry Pi, featuring ADC volume control and MQTT integration with Node-RED for Spotify API communication.

---

## 1. System Architecture & Code Flow

### Step-by-Step Logic:

```
┌─────────────────────────────────────────────────────────────┐
│                    SYSTEM INITIALIZATION                     │
├─────────────────────────────────────────────────────────────┤
│ 1. Auto-activate Python virtual environment (venv)          │
│ 2. Import Whisper for speech-to-text transcription          │
│ 3. Initialize MCP3008 ADC for volume control                │
│ 4. Start spotifyd daemon (Spotify Connect client)           │
│ 5. Launch MQTT listener (for Node-RED integration)          │
│ 6. Start volume monitoring thread (background process)      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    MAIN OPERATION LOOP                       │
├─────────────────────────────────────────────────────────────┤
│  User Input (Manual or MQTT Button Trigger)                 │
│     ↓                                                        │
│  ┌──────────────────────────────────────────┐               │
│  │  Option R: Record Voice Command          │               │
│  │  - Use arecord to capture audio via I2S  │               │
│  │  - Save as songrequest.wav               │               │
│  └──────────────────────────────────────────┘               │
│     ↓                                                        │
│  ┌──────────────────────────────────────────┐               │
│  │  Option T: Transcribe & Process          │               │
│  │  1. Run Whisper on recorded audio        │               │
│  │  2. Parse command: "Play [Song] by [Artist]" │          │
│  │  3. Format: "[Song Name] [Artist Name]"  │               │
│  │  4. Publish to MQTT topic: voice/spotify │               │
│  └──────────────────────────────────────────┘               │
│     ↓                                                        │
│  ┌──────────────────────────────────────────┐               │
│  │  Node-RED Flow (External)                │               │
│  │  1. Receive MQTT message                 │               │
│  │  2. Query Spotify API for song           │               │
│  │  3. Play song on spotifyd                │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │  Option P: Playback Last Recording       │               │
│  │  - Use aplay to play songrequest.wav     │               │
│  └──────────────────────────────────────────┘               │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │  Option V: Toggle Volume Monitoring      │               │
│  │  - Enable/disable ADC volume control     │               │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              BACKGROUND PROCESSES (Parallel)                 │
├─────────────────────────────────────────────────────────────┤
│  Thread 1: MQTT Control Listener                            │
│  - Listens on topic: voice/control                          │
│  - Handles button_pressed (toggle record/stop)              │
│  - Publishes status on: voice/status                        │
│                                                              │
│  Thread 2: Volume Monitoring                                │
│  - Read MCP3008 ADC (channel 0) every 0.2 seconds           │
│  - Convert to 0-100% display range                          │
│  - Map to system volume 9-100% (avoid cutout)               │
│  - Execute: amixer set Master [volume]%                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Programming Languages & Tools Used

### Primary Language:
- **Python 3** (version 3.9+)

### Key Libraries & Packages:

#### Audio Processing:
- **whispercpp** - OpenAI Whisper speech-to-text engine (Python bindings)
- **arecord** - ALSA audio recording tool (I2S microphone interface)
- **aplay** - ALSA audio playback tool (USB speaker output)

#### Hardware Control:
- **gpiozero** - MCP3008 ADC interface for volume potentiometer
  - Reads analog voltage (0-3.3V) from potentiometer
  - Converts to digital volume control (0-100%)

#### MQTT Communication:
- **paho-mqtt** - MQTT client library
  - Publishes voice commands to Node-RED
  - Subscribes to control commands from dashboard
  - Sends status updates (recording, processing, errors)

#### System Utilities:
- **subprocess** - Execute shell commands (arecord, aplay, amixer)
- **threading** - Parallel execution for volume monitoring & MQTT listener
- **os, sys** - Virtual environment activation and file path management

### External Tools:

#### Node-RED:
- **Purpose**: Spotify API integration
- **Function**: Receives MQTT messages, searches Spotify catalog, plays songs
- **Flow Files**: 
  - `Node-Red Spotify Flow vFinal.json`
  - `Spotify Test 2 Updated 2.json`
- **Topics**:
  - `voice/spotify` (search queries)
  - `voice/control` (button commands)
  - `voice/status` (system status)

#### Spotifyd:
- **Purpose**: Spotify Connect daemon
- **Function**: Allows Raspberry Pi to appear as Spotify playback device
- **Auto-start**: Launched by Python script if not running

#### MQTT Broker (Mosquitto):
- **Port**: 1883 (local)
- **Function**: Message broker between Python script and Node-RED

---

## 3. Installation & Configuration

### Prerequisites:
```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install ALSA audio tools
sudo apt install alsa-utils -y

# 3. Install MQTT broker
sudo apt install mosquitto mosquitto-clients -y

# 4. Install Python dependencies
pip3 install gpiozero paho-mqtt

# 5. Configure I2S microphone (add to /boot/firmware/config.txt)
sudo nano /boot/firmware/config.txt
# Add line: dtoverlay=googlevoicehat-soundcard
sudo reboot now
```

### Virtual Environment Setup:
```bash
cd ~/Documents/Final Project
python3 -m venv venv
source venv/bin/activate
pip install whispercpp gpiozero paho-mqtt
```

### Whisper.cpp Installation:
```bash
cd ~/Documents/Final Project
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp
make
# Download tiny.en model
bash ./models/download-ggml-model.sh tiny.en
```

### Spotifyd Configuration:
- Placed in project root directory
- Runs as foreground process (--no-daemon flag)
- Configured via ~/.config/spotifyd/spotifyd.conf (not shown in code)

---

## 4. Hardware Configuration

### Audio Devices:
- **I2S Microphone**: `plughw:4,0` (Adafruit I2S MEMS Microphone)
  - Format: S32_LE (32-bit signed little-endian)
  - Sample Rate: 48000 Hz
  - Channels: 1 (mono)

- **USB Speakers**: `plughw:3,0` (USB Audio Device)
  - Playback device for recorded audio & Spotify

### ADC Configuration:
- **Chip**: MCP3008 (8-channel 10-bit ADC)
- **Channel**: 0 (potentiometer input)
- **Update Rate**: 200ms (0.2 seconds)
- **Volume Mapping**: 
  - ADC: 0.0-1.0 → Display: 0-100%
  - System Volume: 9-100% (prevents audio cutout at low end)

---

## 5. Code Structure & Key Functions

### Main File: `SpotifyVoiceControl.py` (524 lines)

#### Voice Command Processing:
```python
parse_voice_command(transcript)
# Input: "Play, Stairway to Heaven by Led Zeppelin"
# Output: "Stairway To Heaven Led Zeppelin"
# Logic:
#   - Remove "Play," or "play" prefix
#   - Remove " by " separator
#   - Capitalize each word
#   - Combine song + artist
```

#### MQTT Functions:
- `send_to_nodered()` - Publish formatted search query
- `send_status_update()` - Update dashboard status display
- `on_mqtt_message()` - Handle button press commands
- `start_mqtt_listener()` - Background thread for control topic

#### Recording Functions:
- `start_recording()` - Spawn arecord process (background)
- `stop_recording_and_transcribe()` - Terminate recording, run transcription
- `transcribe_audio()` - Execute whisper-cli, parse output, send to Node-RED

#### Volume Control:
- `set_volume(volume_percent)` - Execute amixer command
- `volume_monitor_thread()` - Continuous ADC polling loop

---

## 6. Terminal Command Examples

### Recording Audio:
```bash
arecord -D plughw:4,0 -c1 -r 48000 -f S32_LE songrequest.wav
# Output: Recording... (Press CTRL+C to stop)
```

### Playing Audio:
```bash
aplay -D plughw:3,0 songrequest.wav
# Output: Playing WAVE 'songrequest.wav' : Signed 32 bit Little Endian, Rate 48000 Hz, Mono
```

### Transcription (Whisper):
```bash
./whisper.cpp/build/bin/whisper-cli -m ./whisper.cpp/models/ggml-tiny.en.bin -f songrequest.wav -nt
# Output: play, Stairway to Heaven by Led Zeppelin
```

### Volume Control:
```bash
amixer set Master 75%
# Output: Simple mixer control 'Master',0
#         Mono: Playback 75 [75%] [-7.50dB] [on]
```

### MQTT Testing:
```bash
# Publish test command
mosquitto_pub -h localhost -t voice/control -m "button_pressed"

# Subscribe to status updates
mosquitto_sub -h localhost -t voice/status
# Output: Recording
#         Processing Request
```

### Check System Status:
```bash
# Verify MQTT broker
sudo systemctl status mosquitto

# Confirm spotifyd running
pgrep -x spotifyd

# List audio devices
arecord -l
```

---

## 7. Running the Application

### Location:
```
~/Documents/Final Project/SpotifyVoiceControl.py
```

### Execute Command:
```bash
cd ~/Documents/Final Project
python3 SpotifyVoiceControl.py
```

### Expected Startup Output:
```
==================================================
ECET 35901 - Final Project
Spotify Voice Control System
==================================================

Initializing system...

Activating virtual environment...
✓ spotifyd already running
Starting MQTT control listener...
✓ MQTT control listener connected
  Listening on: voice/control

Starting volume control...
Volume monitoring started (running in background).

System ready!

Commands:
  R = Record voice command
  P = Play last recording
  T = Transcribe & send to Spotify
  V = Toggle volume monitoring (currently ON)
  Q = Quit

MQTT Control:
  Topic: voice/control
  Commands: 'button_pressed' (toggle record/stop)

MQTT Status:
  Topic: voice/status
  Messages: recording, Processing Request, error

Enter command (R/P/T/V/Q): 
```

---

## 8. User Interaction Examples

### Manual Recording:
```
Enter command (R/P/T/V/Q): r

Recording... speak now!
Say: 'Play [Song Name] by [Artist Name]'
Press CTRL+C to stop.

^C
Recording manually stopped.
Saved as songrequest.wav

Enter command (R/P/T/V/Q): t

Transcribing audio... please wait.

=== TRANSCRIPTION RESULT ===
play, Stairway to Heaven by Led Zeppelin
============================

Sending to Node-RED...
  Original: 'play, Stairway to Heaven by Led Zeppelin'
  Formatted: 'Stairway To Heaven Led Zeppelin'
  Connecting to localhost:1883...
  Publishing to topic: voice/spotify
✓ Sent to Node-RED: 'Stairway To Heaven Led Zeppelin'
```

### MQTT Button Control:
```
📨 Received command: 'button_pressed'

🎤 Recording started... (waiting for stop command)

📨 Received command: 'button_pressed'
🛑 Stopping recording...
✓ Saved as songrequest.wav

Transcribing audio... please wait.
[... transcription process ...]
✓ Sent to Node-RED: 'Bohemian Rhapsody Queen'
```

### Volume Control (Background):
```
# ADC continuously reads potentiometer
# Automatically adjusts system volume
# No terminal output unless error occurs
```

---

## 9. File Structure

```
Final Project/
│
├── SpotifyVoiceControl.py          # Main application (524 lines)
├── HardwareFuncations.py           # Alternative/test version (289 lines)
├── songrequest.wav                 # Recorded audio buffer
│
├── venv/                           # Python virtual environment
│   └── bin/activate_this.py        # Auto-activation script
│
├── whisper.cpp/                    # Whisper.cpp repository
│   ├── build/bin/whisper-cli       # Transcription executable
│   └── models/ggml-tiny.en.bin     # Tiny English model
│
├── spotifyd                        # Spotify Connect daemon binary
│
├── Node-Red Spotify Flow vFinal.json   # Node-RED flow export
├── Spotify Test 2 Updated 2.json       # Alternative flow version
│
├── Commands.txt                    # Setup commands reference
└── README.md                       # Project description
```

---

## 10. Troubleshooting Tips

### Issue: "Whisper not available"
**Solution**: Verify virtual environment is activated and whispercpp is installed
```bash
source venv/bin/activate
pip install whispercpp
```

### Issue: "Connection refused - MQTT broker"
**Solution**: Start Mosquitto broker
```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

### Issue: "No audio devices found"
**Solution**: Check I2S microphone configuration
```bash
arecord -l  # Should show plughw:4,0
sudo nano /boot/firmware/config.txt  # Verify dtoverlay=googlevoicehat-soundcard
```

### Issue: "ADC not available"
**Solution**: Check SPI interface enabled
```bash
sudo raspi-config
# Interface Options → SPI → Enable
```

### Issue: Spotifyd not connecting to Spotify
**Solution**: Verify credentials in config file
```bash
nano ~/.config/spotifyd/spotifyd.conf
# Check username, password, device_name
```

---

## 11. System Requirements

- **Platform**: Raspberry Pi 4 Model B (tested)
- **OS**: Raspberry Pi OS (Debian-based, 64-bit recommended)
- **Python**: 3.9 or higher
- **Network**: WiFi or Ethernet (for Spotify API access)
- **Storage**: ~500MB for Whisper model + dependencies
- **RAM**: 2GB minimum (4GB recommended for Whisper processing)

---

## 12. Credits & References

- **Whisper.cpp**: https://github.com/ggerganov/whisper.cpp
- **I2S Microphone Setup**: https://learn.adafruit.com/adafruit-i2s-mems-microphone-breakout/raspberry-pi-wiring-test
- **Spotifyd**: https://github.com/Spotifyd/spotifyd
- **Paho MQTT Python**: https://pypi.org/project/paho-mqtt/

---

**Author**: John Danison  
**Course**: ECET 35901 - Final Project  
**Date**: Fall 2025
