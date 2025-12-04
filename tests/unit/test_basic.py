#!/usr/bin/env python3
"""
Basic functionality tests for Enhanced FDA Explorer
"""

import asyncio
import sys
import os
from datetime import datetime
import pytest

# Add src to path for testing
sys.path.insert(0, 'src')

def test_config():
    """Test configuration loading"""
    print("🔧 Testing Configuration...")
    
    try:
        from enhanced_fda_explorer.config import get_config, load_config
        
        # Test default config
        config = get_config()
        print(f"✅ Default config loaded: {config.app_name}")
        
        # Test config values
        assert config.app_name == "Enhanced FDA Explorer"
        assert config.app_version == "1.0.0"
        print("✅ Config values correct")
        
        return True
        
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False

def test_models():
    """Test data models"""
    print("\n📊 Testing Data Models...")
    
    try:
        from enhanced_fda_explorer.models import SearchRequest, SearchResponse
        
        # Test SearchRequest
        request = SearchRequest(
            query="test device",
            query_type="device",
            limit=10
        )
        print("✅ SearchRequest model works")
        
        # Test validation
        try:
            invalid_request = SearchRequest(
                query="test",
                query_type="invalid_type"
            )
            print("❌ Model validation failed - should have caught invalid type")
            return False
        except Exception:
            print("✅ Model validation works")
        
        return True
        
    except Exception as e:
        print(f"❌ Models test failed: {e}")
        return False

def test_client_basic():
    """Test basic client functionality (without API calls)"""
    print("\n🔗 Testing Client Initialization...")
    
    try:
        from enhanced_fda_explorer.client import EnhancedFDAClient
        from enhanced_fda_explorer.config import get_config
        
        # Test client initialization
        config = get_config()
        client = EnhancedFDAClient(config)
        print("✅ Client initialized successfully")
        
        # Test client has required methods
        required_methods = ['search', 'get_device_events', 'get_device_classifications']
        for method in required_methods:
            if hasattr(client, method):
                print(f"✅ Client has {method} method")
            else:
                print(f"❌ Client missing {method} method")
                return False
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Client test failed: {e}")
        return False

def test_ai_engine():
    """Test AI engine initialization"""
    print("\n🤖 Testing AI Engine...")
    
    try:
        from enhanced_fda_explorer.ai import AIAnalysisEngine
        from enhanced_fda_explorer.config import get_config
        
        # Test AI engine initialization
        config = get_config()
        ai_engine = AIAnalysisEngine(config)
        print("✅ AI Engine initialized successfully")
        
        # Test AI engine has required methods
        required_methods = ['analyze_search_results', 'generate_risk_assessment']
        for method in required_methods:
            if hasattr(ai_engine, method):
                print(f"✅ AI Engine has {method} method")
            else:
                print(f"❌ AI Engine missing {method} method")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ AI Engine test failed: {e}")
        return False

def test_core_explorer():
    """Test core FDAExplorer"""
    print("\n🎯 Testing Core Explorer...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        from enhanced_fda_explorer.config import get_config
        
        # Test explorer initialization
        config = get_config()
        explorer = FDAExplorer(config)
        print("✅ FDAExplorer initialized successfully")
        
        # Test explorer has required methods
        required_methods = ['search', 'get_device_intelligence', 'compare_devices']
        for method in required_methods:
            if hasattr(explorer, method):
                print(f"✅ Explorer has {method} method")
            else:
                print(f"❌ Explorer missing {method} method")
                return False
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ Core Explorer test failed: {e}")
        return False

@pytest.mark.asyncio
async def test_async_functionality():
    """Test async functionality"""
    print("\n⚡ Testing Async Functionality...")

    try:
        from enhanced_fda_explorer.core import FDAExplorer
        from enhanced_fda_explorer.config import get_config

        config = get_config()
        explorer = FDAExplorer(config)

        # Test that async methods exist and are callable
        # Note: We're not actually calling them to avoid API calls in basic test
        assert asyncio.iscoroutinefunction(explorer.search)
        assert asyncio.iscoroutinefunction(explorer.get_device_intelligence)
        print("✅ Async methods are properly defined")

        explorer.close()
        return True

    except Exception as e:
        print(f"❌ Async test failed: {e}")
        return False

def test_cli_import():
    """Test CLI module import"""
    print("\n💻 Testing CLI Module...")
    
    try:
        from enhanced_fda_explorer.cli import cli
        print("✅ CLI module imported successfully")
        
        # Test that CLI has main commands
        if hasattr(cli, 'commands'):
            commands = list(cli.commands.keys())
            print(f"✅ CLI commands available: {commands}")
        
        return True
        
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
        return False

def test_api_import():
    """Test API module import"""
    print("\n🌐 Testing API Module...")
    
    try:
        from enhanced_fda_explorer.api import create_app
        print("✅ API module imported successfully")
        
        # Test app creation
        app = create_app()
        print("✅ FastAPI app created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def main():
    """Run all basic tests"""
    print("🧪 Enhanced FDA Explorer - Basic Functionality Tests")
    print("=" * 60)
    
    tests = [
        test_config,
        test_models,
        test_client_basic,
        test_ai_engine,
        test_core_explorer,
        test_cli_import,
        test_api_import,
    ]
    
    results = []
    for test in tests:
        try:
            if asyncio.iscoroutinefunction(test):
                result = asyncio.run(test())
            else:
                result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    # Run async test separately
    try:
        async_result = asyncio.run(test_async_functionality())
        results.append(async_result)
    except Exception as e:
        print(f"❌ Async test crashed: {e}")
        results.append(False)
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"🎉 All {total} basic tests passed!")
        print("\nYour Enhanced FDA Explorer is working correctly!")
        print("\nNext steps for full testing:")
        print("1. Add API keys to .env file")
        print("2. Run: python3 test_with_api.py")
        print("3. Test web interface: python3 test_web.py")
        print("4. Test CLI: fda-explorer --help")
    else:
        print(f"⚠️  {passed}/{total} tests passed")
        print("Some basic functionality issues need to be resolved.")
        
        # Show which tests failed
        failed_tests = [test.__name__ for test, result in zip(tests + [test_async_functionality], results) if not result]
        print(f"Failed tests: {failed_tests}")

if __name__ == "__main__":
    main()