#!/usr/bin/env python3
import sys
import subprocess

print("🌐 Manual Web Interface Test")
print("=" * 40)

print("Starting Streamlit web interface...")
print("This will open in your browser at http://localhost:8501")
print("Press Ctrl+C to stop")

try:
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", 
        "src/enhanced_fda_explorer/web.py",
        "--server.address", "localhost",
        "--server.port", "8501"
    ])
except KeyboardInterrupt:
    print("\nWeb interface stopped")
