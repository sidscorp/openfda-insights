#!/usr/bin/env python3
"""
Web interface testing for Enhanced FDA Explorer
"""

import sys
import time
import threading
import requests
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

def test_streamlit_import():
    """Test Streamlit and web module import"""
    print("🌐 Testing Web Module Import...")
    
    try:
        import streamlit as st
        print("✅ Streamlit imported successfully")
        
        from enhanced_fda_explorer.web import main
        print("✅ Web module imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("Run: pip install streamlit")
        return False
    except Exception as e:
        print(f"❌ Web module test failed: {e}")
        return False

def test_web_dependencies():
    """Test web interface dependencies"""
    print("\n📦 Testing Web Dependencies...")
    
    required_packages = ['streamlit', 'plotly', 'pandas']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"Install missing packages: pip install {' '.join(missing)}")
        return False
    
    return True

def test_api_server_start():
    """Test API server startup"""
    print("\n🚀 Testing API Server...")
    
    try:
        from enhanced_fda_explorer.api import create_app
        
        app = create_app()
        print("✅ API server can be created")
        
        # Test that key routes exist
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/health", "/search"]
        
        for route in expected_routes:
            if route in routes:
                print(f"✅ Route {route} exists")
            else:
                print(f"❌ Route {route} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ API server test failed: {e}")
        return False

def test_visualization_module():
    """Test visualization module"""
    print("\n📊 Testing Visualization Module...")
    
    try:
        from enhanced_fda_explorer.visualization import DataVisualizer
        
        visualizer = DataVisualizer()
        print("✅ DataVisualizer imported successfully")
        
        # Test that key methods exist
        methods = ['create_timeline_chart', 'create_risk_assessment_chart', 'create_summary_dashboard']
        for method in methods:
            if hasattr(visualizer, method):
                print(f"✅ Method {method} exists")
            else:
                print(f"❌ Method {method} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Visualization module test failed: {e}")
        return False

def create_test_script():
    """Create a test script for manual web testing"""
    test_script = """#!/usr/bin/env python3
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
    print("\\nWeb interface stopped")
"""
    
    with open('test_web_manual.py', 'w') as f:
        f.write(test_script)
    
    print("✅ Created test_web_manual.py for manual testing")

def main():
    """Run web interface tests"""
    print("🌐 Enhanced FDA Explorer - Web Interface Tests")
    print("=" * 60)
    
    tests = [
        test_web_dependencies,
        test_streamlit_import,
        test_visualization_module,
        test_api_server_start,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    # Create manual test script
    create_test_script()
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"🎉 All {total} web tests passed!")
        print("\nWeb interface is ready!")
        print("\nManual testing options:")
        print("1. Run: python3 test_web_manual.py")
        print("2. Or directly: streamlit run src/enhanced_fda_explorer/web.py")
        print("3. For API: fda-explorer serve")
    else:
        print(f"⚠️  {passed}/{total} web tests passed")
        print("Fix the issues above before running the web interface")

if __name__ == "__main__":
    main()