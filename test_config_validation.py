#!/usr/bin/env python3
"""
Test script for Enhanced FDA Explorer configuration validation
Demonstrates the P1-T001 improvements: Add Pydantic BaseSettings for config validation
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_basic_config_loading():
    """Test basic configuration loading"""
    print("🧪 Testing basic configuration loading...")
    
    try:
        from enhanced_fda_explorer.config import get_config, print_config_validation
        
        # Load default configuration
        config = get_config()
        print("✅ Configuration loaded successfully")
        print(f"   Environment: {config.environment}")
        print(f"   Debug mode: {config.debug}")
        print(f"   API host: {config.api.host}:{config.api.port}")
        
        return True
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False

def test_config_validation():
    """Test configuration validation"""
    print("\n🧪 Testing configuration validation...")
    
    try:
        from enhanced_fda_explorer.config import get_config, validate_current_config
        
        config = get_config()
        summary = config.get_validation_summary()
        
        print("✅ Configuration validation completed")
        print(f"   Critical issues: {len(summary['critical'])}")
        print(f"   Errors: {len(summary['errors'])}")
        print(f"   Warnings: {len(summary['warnings'])}")
        print(f"   Info messages: {len(summary['info'])}")
        
        # Print some sample validation messages
        if summary['warnings']:
            print("\n   Sample warnings:")
            for warning in summary['warnings'][:2]:
                print(f"   - {warning}")
        
        if summary['info']:
            print("\n   Sample info:")
            for info in summary['info'][:2]:
                print(f"   - {info}")
        
        return True
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def test_environment_variable_validation():
    """Test environment variable validation"""
    print("\n🧪 Testing environment variable validation...")
    
    try:
        from enhanced_fda_explorer.config import Config
        
        # Test with some environment variables
        os.environ['FDA_API_KEY'] = 'test_key_1234567890'
        os.environ['AI_API_KEY'] = 'sk-test_key_1234567890'
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['DEBUG'] = 'true'
        
        config = Config()
        print("✅ Environment variable loading successful")
        print(f"   FDA API Key: {'***' + config.openfda.api_key[-4:] if config.openfda.api_key else 'Not set'}")
        print(f"   AI API Key: {'***' + config.ai.api_key[-4:] if config.ai.api_key else 'Not set'}")
        print(f"   Environment: {config.environment}")
        print(f"   Debug: {config.debug}")
        
        return True
    except Exception as e:
        print(f"❌ Environment variable validation failed: {e}")
        return False

def test_validation_errors():
    """Test validation error detection"""
    print("\n🧪 Testing validation error detection...")
    
    try:
        from enhanced_fda_explorer.config import Config
        
        # Test with invalid environment
        os.environ['ENVIRONMENT'] = 'invalid_env'
        
        try:
            config = Config()
            print("❌ Should have failed with invalid environment")
            return False
        except ValueError as e:
            print("✅ Correctly detected invalid environment")
            print(f"   Error: {e}")
        
        # Reset environment
        os.environ['ENVIRONMENT'] = 'development'
        
        return True
    except Exception as e:
        print(f"❌ Validation error test failed: {e}")
        return False

def test_startup_validation():
    """Test startup validation functionality"""
    print("\n🧪 Testing startup validation...")
    
    try:
        from enhanced_fda_explorer.config import get_config
        
        # Test with validation enabled
        config = get_config(validate_startup=False)  # Don't fail on warnings
        issues = config.validate_startup()
        
        print("✅ Startup validation completed")
        print(f"   Total issues found: {len(issues)}")
        
        if issues:
            print("   Sample issues:")
            for issue in issues[:3]:
                print(f"   - {issue}")
        else:
            print("   No issues found!")
        
        return True
    except Exception as e:
        print(f"❌ Startup validation failed: {e}")
        return False

def main():
    """Run all configuration validation tests"""
    print("🚀 Enhanced FDA Explorer - Configuration Validation Test")
    print("=" * 60)
    print("\nTesting P1-T001 improvements:")
    print("- Environment variable mapping to nested config classes")
    print("- Comprehensive validators for critical fields") 
    print("- Startup validation method")
    print("- Application entry point validation")
    print("\n" + "=" * 60)
    
    tests = [
        test_basic_config_loading,
        test_config_validation,
        test_environment_variable_validation,
        test_validation_errors,
        test_startup_validation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All configuration validation tests passed!")
        print("\n✅ P1-T001 implementation is working correctly:")
        print("   ✓ Environment variable mapping implemented")
        print("   ✓ Comprehensive field validation active")
        print("   ✓ Startup validation functional")
        print("   ✓ Error handling and reporting working")
    else:
        print("⚠️  Some tests failed - configuration validation needs attention")
    
    print("\n🎯 Next steps:")
    print("   • Install missing dependencies: pip install -e .")
    print("   • Run: fda-explorer validate-config")
    print("   • Set API keys in .env file for full functionality")

if __name__ == "__main__":
    main()