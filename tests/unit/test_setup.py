#!/usr/bin/env python3
"""
Quick setup test for Enhanced FDA Explorer
"""

import sys
import subprocess
import importlib.util

def test_python_version():
    """Test Python version compatibility"""
    print("🐍 Testing Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires Python 3.8+")
        return False

def test_package_imports():
    """Test core package imports"""
    print("\n📦 Testing package imports...")
    
    required_packages = [
        'pandas', 'numpy', 'requests', 'pydantic', 
        'fastapi', 'streamlit', 'click', 'plotly'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n🔧 Install missing packages:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def test_config_loading():
    """Test configuration loading"""
    print("\n⚙️ Testing configuration...")
    
    try:
        # Test basic config import
        from enhanced_fda_explorer.config import get_config
        config = get_config()
        print(f"✅ Configuration loaded: {config.app_name}")
        return True
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False

def test_core_imports():
    """Test core module imports"""
    print("\n🔧 Testing core modules...")
    
    modules_to_test = [
        'enhanced_fda_explorer.core',
        'enhanced_fda_explorer.client', 
        'enhanced_fda_explorer.ai',
        'enhanced_fda_explorer.models'
    ]
    
    for module in modules_to_test:
        try:
            importlib.import_module(module)
            print(f"✅ {module}")
        except Exception as e:
            print(f"❌ {module} - {e}")
            return False
    
    return True

def main():
    """Run all setup tests"""
    print("🚀 Enhanced FDA Explorer - Setup Test\n")
    
    tests = [
        test_python_version,
        test_package_imports, 
        test_config_loading,
        test_core_imports
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "="*50)
    if all(results):
        print("🎉 All tests passed! Enhanced FDA Explorer is ready to use.")
        print("\nNext steps:")
        print("1. Set up environment: cp .env.example .env")
        print("2. Add API keys to .env file")
        print("3. Run: fda-explorer --help")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()