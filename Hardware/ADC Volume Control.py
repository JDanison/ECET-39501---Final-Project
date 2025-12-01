#!/usr/bin/env python3
"""
ECET 35901 - Final Project, RPi Spotify Voice Search | Volume Control
Author: John Danison
Date: Fall 2025
"""

from gpiozero import MCP3008
from time import sleep
import subprocess

# === CONFIGURATION ===
CHANNEL = 0
UPDATE_DELAY = 0.2  # seconds between updates

# === INITIALIZE COMPONENTS ===
adc = MCP3008(channel=CHANNEL)

print("============================================")
print("ECET 35901 - Final Project")
print("ADC Volume Control")
print("Press Ctrl+C to exit.")
print("============================================\n")

def set_volume(volume_percent):
    """Set system volume using amixer (0-100)."""
    try:
        subprocess.run(['amixer', 'set', 'Master', f'{volume_percent}%'], 
                      check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

try:
    while True:
        # Read analog value (0.0 to 1.0)
        adc_value = adc.value
        
        # Scale to display value 0-100%
        display_volume = int(adc_value * 100)
        
        # Map to actual system volume 9-100% (avoid cutout at low end)
        actual_volume = int(adc_value * 91) + 9
        
        # Set system volume
        set_volume(actual_volume)
        
        # Print to terminal
        print(f"ADC Value: {adc_value:.3f} → Volume: {display_volume}%")
        
        sleep(UPDATE_DELAY)

except KeyboardInterrupt:
    print("\nExiting program.")
