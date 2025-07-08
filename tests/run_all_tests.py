#!/usr/bin/env python3
"""
Complete test suite runner for Enhanced FDA Explorer
"""

import subprocess
import sys
import os
from pathlib import Path
import time

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"🧪 {title}")
    print("=" * 70)

def run_test_script(script_name, description):
    """Run a test script and return success status"""
    print(f"\n🔧 Running {description}...")
    print("-" * 50)
    
    try:
        result = subprocess.run([
            sys.executable, script_name
        ], timeout=120)  # 2 minute timeout per test
        
        success = result.returncode == 0
        if success:
            print(f"✅ {description} completed successfully")
        else:
            print(f"❌ {description} failed with exit code {result.returncode}")
        
        return success
        
    except subprocess.TimeoutExpired:
        print(f"⚠️  {description} timed out (may still be working)")
        return False
    except FileNotFoundError:
        print(f"❌ Test script {script_name} not found")
        return False
    except Exception as e:
        print(f"❌ {description} failed: {e}")
        return False

def check_prerequisites():
    """Check prerequisites for testing"""
    print_header("Prerequisites Check")
    
    # Check Python version
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires 3.8+")
        return False
    
    # Check if we're in the right directory
    if not Path("setup.py").exists():
        print("❌ setup.py not found. Please run from project root directory.")
        return False
    
    print("✅ Project structure looks correct")
    
    # Check for .env file
    if Path(".env").exists():
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found. Copy .env.example to .env and configure API keys")
    
    return True

def run_installation():
    """Run installation"""
    print_header("Installation")
    
    print("📦 Installing Enhanced FDA Explorer in development mode...")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", "-e", "."
        ], timeout=300)  # 5 minute timeout for installation
        
        if result.returncode == 0:
            print("✅ Installation successful")
            return True
        else:
            print("❌ Installation failed")
            return False
            
    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

def main():
    """Run complete test suite"""
    print_header("Enhanced FDA Explorer - Complete Test Suite")
    
    start_time = time.time()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites check failed. Please fix the issues above.")
        sys.exit(1)
    
    # Run installation
    if not run_installation():
        print("\n❌ Installation failed. Cannot proceed with tests.")
        sys.exit(1)
    
    # Define test stages
    test_stages = [
        ("test_setup.py", "Setup Test"),
        ("test_basic.py", "Basic Functionality Tests"),
        ("test_cli.py", "CLI Tests"),
        ("test_web.py", "Web Interface Tests"),
    ]
    
    # Optional tests (require API keys)
    optional_tests = [
        ("test_with_api.py", "API Integration Tests (requires API keys)"),
    ]
    
    # Run core tests
    print_header("Core Tests")
    core_results = []
    
    for script, description in test_stages:
        if Path(script).exists():
            result = run_test_script(script, description)
            core_results.append((description, result))
        else:
            print(f"⚠️  {script} not found, skipping {description}")
            core_results.append((description, False))
    
    # Run optional tests
    print_header("Optional Tests")
    optional_results = []
    
    for script, description in optional_tests:
        if Path(script).exists():
            print(f"\n🔍 {description}")
            print("These tests require API keys in your .env file")
            
            # Check if user wants to run optional tests
            try:
                response = input("Run optional tests? (y/N): ").strip().lower()
                if response in ['y', 'yes']:
                    result = run_test_script(script, description)
                    optional_results.append((description, result))
                else:
                    print("⏭️  Skipping optional tests")
                    optional_results.append((description, None))
            except KeyboardInterrupt:
                print("\n⏭️  Skipping optional tests")
                optional_results.append((description, None))
        else:
            print(f"⚠️  {script} not found, skipping {description}")
            optional_results.append((description, False))
    
    # Summary
    end_time = time.time()
    total_time = end_time - start_time
    
    print_header("Test Results Summary")
    
    print("📊 Core Tests:")
    core_passed = 0
    for description, result in core_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {description}")
        if result:
            core_passed += 1
    
    print(f"\n📊 Optional Tests:")
    optional_passed = 0
    optional_total = 0
    for description, result in optional_results:
        if result is None:
            status = "⏭️  SKIP"
        elif result:
            status = "✅ PASS"
            optional_passed += 1
            optional_total += 1
        else:
            status = "❌ FAIL"
            optional_total += 1
        print(f"   {status} {description}")
    
    # Overall status
    print(f"\n⏱️  Total test time: {total_time:.1f} seconds")
    print(f"📈 Core tests: {core_passed}/{len(core_results)} passed")
    
    if optional_total > 0:
        print(f"📈 Optional tests: {optional_passed}/{optional_total} passed")
    
    if core_passed == len(core_results):
        print(f"\n🎉 All core tests passed! Enhanced FDA Explorer is working correctly.")
        
        if optional_passed == optional_total and optional_total > 0:
            print("🎉 All optional tests passed too! Full functionality confirmed.")
        elif optional_total > 0:
            print("⚠️  Some optional tests failed. Check API keys and network connectivity.")
        
        print(f"\n🚀 Next steps:")
        print("1. Configure API keys in .env file")
        print("2. Try the CLI: fda-explorer --help")
        print("3. Start web interface: fda-explorer web")
        print("4. Start API server: fda-explorer serve")
        
    else:
        print(f"\n❌ Some core tests failed. Please review the errors above.")
        failed_tests = [desc for desc, result in core_results if not result]
        print(f"Failed tests: {failed_tests}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        sys.exit(1)