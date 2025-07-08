#!/usr/bin/env python3
"""
Simple test without installation - works in any environment
"""

import sys
import os
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that we can import the core modules"""
    print("🔧 Testing Core Module Imports...")
    
    try:
        # Test config
        from enhanced_fda_explorer.config import get_config
        config = get_config()
        print(f"✅ Config: {config.app_name}")
        
        # Test models
        from enhanced_fda_explorer.models import SearchRequest
        request = SearchRequest(query="test", query_type="device")
        print(f"✅ Models: SearchRequest created")
        
        # Test client
        from enhanced_fda_explorer.client import EnhancedFDAClient
        print(f"✅ Client: EnhancedFDAClient imported")
        
        # Test AI engine
        from enhanced_fda_explorer.ai import AIAnalysisEngine
        print(f"✅ AI Engine: AIAnalysisEngine imported")
        
        # Test core
        from enhanced_fda_explorer.core import FDAExplorer
        print(f"✅ Core: FDAExplorer imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_dependencies():
    """Test that required dependencies are available"""
    print("\n📦 Testing Dependencies...")
    
    required = {
        'pandas': 'Data processing',
        'numpy': 'Numerical computing', 
        'requests': 'HTTP client',
        'pydantic': 'Data validation',
        'fastapi': 'API framework',
        'streamlit': 'Web interface',
        'click': 'CLI framework',
        'plotly': 'Visualizations'
    }
    
    available = []
    missing = []
    
    for package, description in required.items():
        try:
            __import__(package)
            print(f"✅ {package}: {description}")
            available.append(package)
        except ImportError:
            print(f"❌ {package}: {description} - Not installed")
            missing.append(package)
    
    if missing:
        print(f"\n🔧 To install missing packages:")
        print(f"pip install {' '.join(missing)}")
        
    return len(missing) == 0, available, missing

def test_configuration():
    """Test configuration loading"""
    print("\n⚙️ Testing Configuration...")
    
    try:
        from enhanced_fda_explorer.config import get_config
        
        config = get_config()
        
        # Test config values
        assert config.app_name == "Enhanced FDA Explorer"
        assert config.app_version == "1.0.0"
        
        print(f"✅ App Name: {config.app_name}")
        print(f"✅ Version: {config.app_version}")
        print(f"✅ Environment: {config.environment}")
        
        # Test API configuration
        openfda_config = config.get_openfda_client_config()
        print(f"✅ OpenFDA Config: {len(openfda_config)} settings")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality without API calls"""
    print("\n🎯 Testing Basic Functionality...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        from enhanced_fda_explorer.config import get_config
        
        # Test explorer creation
        config = get_config()
        explorer = FDAExplorer(config)
        print("✅ FDAExplorer created successfully")
        
        # Test that methods exist
        methods = ['search', 'get_device_intelligence', 'compare_devices']
        for method in methods:
            if hasattr(explorer, method):
                print(f"✅ Method {method} exists")
            else:
                print(f"❌ Method {method} missing")
                return False
        
        # Cleanup
        explorer.close()
        print("✅ Explorer closed successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False

def show_manual_testing_guide():
    """Show manual testing instructions"""
    print("\n📋 Manual Testing Guide")
    print("=" * 50)
    
    print("\n🔧 If dependencies are missing:")
    print("pip install --user pydantic fastapi streamlit plotly click rich")
    
    print("\n💻 Test CLI (if packages installed):")
    print("python3 -c \"")
    print("import sys; sys.path.insert(0, 'src');")
    print("from enhanced_fda_explorer.cli import cli;")
    print("cli(['--help'])\"")
    
    print("\n🌐 Test Web Interface (if streamlit installed):")
    print("PYTHONPATH=src streamlit run src/enhanced_fda_explorer/web.py")
    
    print("\n🚀 Test API Server (if fastapi installed):")
    print("python3 -c \"")
    print("import sys; sys.path.insert(0, 'src');")
    print("from enhanced_fda_explorer.api import create_app;")
    print("app = create_app(); print('API app created successfully')\"")
    
    print("\n📝 Configuration:")
    print("1. Copy .env.example to .env")
    print("2. Add your API keys to .env")
    print("3. Rerun tests")

def main():
    """Run simple tests"""
    print("🧪 Enhanced FDA Explorer - Simple Test (No Installation Required)")
    print("=" * 70)
    
    # Test imports first
    imports_ok = test_imports()
    
    if not imports_ok:
        print("\n❌ Core imports failed. Check the project structure.")
        return
    
    # Test dependencies
    deps_ok, available, missing = test_dependencies()
    
    # Test configuration
    config_ok = test_configuration()
    
    # Test basic functionality
    basic_ok = test_basic_functionality()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Test Results Summary")
    print("=" * 70)
    
    print(f"Core Imports: {'✅ PASS' if imports_ok else '❌ FAIL'}")
    print(f"Dependencies: {'✅ PASS' if deps_ok else f'⚠️  PARTIAL ({len(available)}/{len(available)+len(missing)})'}")
    print(f"Configuration: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"Basic Functionality: {'✅ PASS' if basic_ok else '❌ FAIL'}")
    
    if imports_ok and config_ok and basic_ok:
        print(f"\n🎉 Core functionality is working!")
        
        if deps_ok:
            print("🎉 All dependencies available - Full functionality ready!")
            print("\n🚀 Next steps:")
            print("1. Add API keys to .env file")
            print("2. Try: python3 test_with_api.py")
            print("3. Start web interface: PYTHONPATH=src streamlit run src/enhanced_fda_explorer/web.py")
        else:
            print(f"⚠️  Some dependencies missing. Install them for full functionality.")
            print(f"Missing: {', '.join(missing)}")
    else:
        print(f"\n❌ Some core tests failed. Check the errors above.")
    
    # Show manual testing guide
    show_manual_testing_guide()

if __name__ == "__main__":
    main()