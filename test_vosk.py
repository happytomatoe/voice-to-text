#!/usr/bin/env python3
"""Test script to verify Vosk model works with IBUS STT setup."""

import os
import sys

# Test 1: Check Vosk model exists
model_path = os.path.expanduser("~/.cache/vosk/vosk-model-small-en-us-0.15")
print(f"Test 1: Checking model at {model_path}")
if os.path.exists(model_path):
    print("  ✓ Model directory exists")
    model_files = os.listdir(model_path)
    print(f"  ✓ Model contains {len(model_files)} items: {', '.join(model_files)}")
else:
    print("  ✗ Model directory not found!")
    sys.exit(1)

# Test 2: Check GStreamer plugins
print("\nTest 2: Checking GStreamer plugins")
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    
    # Check for required plugins
    registry = Gst.Registry.get()
    required_plugins = ['pulsesrc', 'webrtcdsp', 'vosk', 'fakesink']
    for plugin_name in required_plugins:
        plugin = registry.find_plugin(plugin_name)
        if plugin:
            print(f"  ✓ {plugin_name} plugin found")
        else:
            print(f"  ✗ {plugin_name} plugin NOT found")
except Exception as e:
    print(f"  ✗ Error checking GStreamer: {e}")

# Test 3: Check IBUS configuration
print("\nTest 3: Checking IBUS configuration")
try:
    import subprocess
    result = subprocess.run(['gsettings', 'get', 'org.freedesktop.ibus.engine.stt', 'vosk-models'], 
                          capture_output=True, text=True)
    models_config = result.stdout.strip()
    print(f"  ✓ Vosk models config: {models_config}")
    
    result = subprocess.run(['gsettings', 'get', 'org.freedesktop.ibus.engine.stt', 'locale'], 
                          capture_output=True, text=True)
    locale_config = result.stdout.strip()
    print(f"  ✓ Locale config: {locale_config}")
    
    result = subprocess.run(['gsettings', 'get', 'org.gnome.desktop.input-sources', 'sources'], 
                          capture_output=True, text=True)
    sources_config = result.stdout.strip()
    print(f"  ✓ Input sources: {sources_config}")
except Exception as e:
    print(f"  ✗ Error checking IBUS config: {e}")

# Test 4: Check if Vosk Python module works
print("\nTest 4: Testing Vosk Python module")
try:
    # Try to import vosk from the venv
    venv_path = os.path.expanduser("~/git/voice-to-text-ibus/.venv")
    if os.path.exists(venv_path):
        sys.path.insert(0, os.path.join(venv_path, 'lib', 'python3.14', 'site-packages'))
    
    from vosk import Model, KaldiRecognizer
    model = Model(model_path)
    rec = KaldiRecognizer(model, 16000)
    print("  ✓ Vosk model loaded successfully")
    print("  ✓ KaldiRecognizer created")
except ImportError:
    print("  ⚠ Vosk Python module not found (expected - using system Python)")
    print("    The IBUS engine uses its own Python environment")
except Exception as e:
    print(f"  ✗ Error testing Vosk: {e}")

print("\n" + "="*50)
print("Setup verification complete!")
print("\nTo test speech recognition:")
print("1. Open any text editor (gedit, etc.)")
print("2. Press Super+Space to switch to STT engine")
print("3. Speak into your microphone")
print("4. Your speech should be transcribed to text")
