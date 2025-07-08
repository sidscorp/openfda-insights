#!/usr/bin/env python3
"""
API integration tests for Enhanced FDA Explorer
These tests make actual API calls and require API keys
"""

import asyncio
import sys
import os
from datetime import datetime

# Add src to path for testing
sys.path.insert(0, 'src')

def check_api_keys():
    """Check if API keys are configured"""
    print("🔑 Checking API Keys...")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    fda_key = os.getenv('FDA_API_KEY')
    ai_key = os.getenv('AI_API_KEY')
    
    print(f"FDA API Key: {'✅ Set' if fda_key else '⚠️  Not set (optional)'}")
    print(f"AI API Key: {'✅ Set' if ai_key else '❌ Not set (required for AI features)'}")
    
    return ai_key is not None  # AI key is required for most tests

async def test_simple_search():
    """Test basic search functionality"""
    print("\n🔍 Testing Simple Search...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        
        explorer = FDAExplorer()
        
        # Test simple search without AI analysis
        response = await explorer.search(
            query="pacemaker",
            query_type="device",
            endpoints=["classification"],  # Start with classification (most reliable)
            limit=5,
            include_ai_analysis=False
        )
        
        print(f"✅ Search completed successfully")
        print(f"   Query: {response.query}")
        print(f"   Total results: {response.total_results}")
        print(f"   Response time: {response.response_time:.2f}s")
        
        if response.results:
            for endpoint, df in response.results.items():
                print(f"   {endpoint}: {len(df)} records")
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ Simple search failed: {e}")
        return False

async def test_search_with_ai():
    """Test search with AI analysis"""
    print("\n🤖 Testing Search with AI Analysis...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        
        explorer = FDAExplorer()
        
        # Test search with AI analysis
        response = await explorer.search(
            query="insulin pump",
            query_type="device",
            endpoints=["classification", "event"],
            limit=3,
            include_ai_analysis=True
        )
        
        print(f"✅ AI search completed successfully")
        print(f"   Query: {response.query}")
        print(f"   Total results: {response.total_results}")
        print(f"   AI analysis included: {'✅' if response.ai_analysis else '❌'}")
        
        if response.ai_analysis:
            analysis = response.ai_analysis
            if isinstance(analysis, dict) and analysis.get('summary'):
                print(f"   AI Summary: {analysis['summary'][:100]}...")
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ AI search failed: {e}")
        print("   This might be due to missing AI API key or AI service issues")
        return False

async def test_device_intelligence():
    """Test device intelligence feature"""
    print("\n📱 Testing Device Intelligence...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        
        explorer = FDAExplorer()
        
        # Test device intelligence
        intelligence = await explorer.get_device_intelligence(
            device_name="pacemaker",
            lookback_months=6,
            include_risk_assessment=True
        )
        
        print(f"✅ Device intelligence completed")
        print(f"   Device: {intelligence['device_name']}")
        print(f"   Data sources: {len(intelligence['data'])}")
        print(f"   Risk assessment: {'✅' if intelligence.get('risk_assessment') else '❌'}")
        
        if intelligence.get('risk_assessment'):
            risk = intelligence['risk_assessment']
            print(f"   Risk score: {risk.overall_risk_score}/10")
            print(f"   Severity: {risk.severity_level}")
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ Device intelligence failed: {e}")
        return False

async def test_manufacturer_intelligence():
    """Test manufacturer intelligence"""
    print("\n🏭 Testing Manufacturer Intelligence...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        
        explorer = FDAExplorer()
        
        # Test manufacturer intelligence
        intelligence = await explorer.get_manufacturer_intelligence(
            manufacturer_name="Medtronic",
            lookback_months=6
        )
        
        print(f"✅ Manufacturer intelligence completed")
        print(f"   Manufacturer: {intelligence['manufacturer_name']}")
        print(f"   Search results: {intelligence['search_response'].total_results}")
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ Manufacturer intelligence failed: {e}")
        return False

async def test_trend_analysis():
    """Test trend analysis"""
    print("\n📈 Testing Trend Analysis...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        
        explorer = FDAExplorer()
        
        # Test trend analysis
        trends = await explorer.get_trend_analysis(
            query="cardiac device",
            time_periods=["6months", "1year"]
        )
        
        print(f"✅ Trend analysis completed")
        print(f"   Query: {trends['query']}")
        print(f"   Time periods: {trends['time_periods']}")
        
        for period, data in trends['trend_data'].items():
            total_records = sum(len(df) for df in data.values())
            print(f"   {period}: {total_records} records")
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ Trend analysis failed: {e}")
        return False

async def test_device_comparison():
    """Test device comparison"""
    print("\n⚖️ Testing Device Comparison...")
    
    try:
        from enhanced_fda_explorer.core import FDAExplorer
        
        explorer = FDAExplorer()
        
        # Test device comparison
        comparison = await explorer.compare_devices(
            device_names=["pacemaker", "defibrillator"],
            lookback_months=6
        )
        
        print(f"✅ Device comparison completed")
        print(f"   Devices: {comparison['devices']}")
        
        for device in comparison['devices']:
            device_data = comparison['device_data'][device]
            total_records = sum(len(df) for df in device_data['data'].values())
            print(f"   {device}: {total_records} records")
        
        explorer.close()
        return True
        
    except Exception as e:
        print(f"❌ Device comparison failed: {e}")
        return False

def test_performance():
    """Test performance metrics"""
    print("\n⚡ Testing Performance...")
    
    try:
        import time
        
        async def timed_search():
            from enhanced_fda_explorer.core import FDAExplorer
            
            explorer = FDAExplorer()
            start_time = time.time()
            
            response = await explorer.search(
                query="medical device",
                endpoints=["classification"],
                limit=10,
                include_ai_analysis=False
            )
            
            end_time = time.time()
            explorer.close()
            
            return end_time - start_time, response.total_results
        
        response_time, total_results = asyncio.run(timed_search())
        
        print(f"✅ Performance test completed")
        print(f"   Response time: {response_time:.2f}s")
        print(f"   Results: {total_results}")
        print(f"   Performance: {'✅ Good' if response_time < 10 else '⚠️ Slow'}")
        
        return response_time < 30  # Allow up to 30 seconds
        
    except Exception as e:
        print(f"❌ Performance test failed: {e}")
        return False

async def main():
    """Run all API integration tests"""
    print("🌐 Enhanced FDA Explorer - API Integration Tests")
    print("=" * 60)
    
    # Check API keys first
    has_ai_key = check_api_keys()
    
    if not has_ai_key:
        print("\n⚠️  Warning: AI API key not found. AI-powered tests will be skipped.")
        print("To test AI features, add your AI_API_KEY to the .env file")
    
    # Define tests
    basic_tests = [
        test_simple_search,
    ]
    
    ai_tests = [
        test_search_with_ai,
        test_device_intelligence,
        test_manufacturer_intelligence,
        test_trend_analysis,
        test_device_comparison,
    ]
    
    performance_tests = [
        test_performance,
    ]
    
    # Run basic tests
    print(f"\n🔧 Running Basic Tests ({len(basic_tests)} tests)...")
    basic_results = []
    for test in basic_tests:
        try:
            result = await test()
            basic_results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            basic_results.append(False)
    
    # Run AI tests if API key is available
    ai_results = []
    if has_ai_key:
        print(f"\n🤖 Running AI Tests ({len(ai_tests)} tests)...")
        for test in ai_tests:
            try:
                result = await test()
                ai_results.append(result)
            except Exception as e:
                print(f"❌ Test {test.__name__} crashed: {e}")
                ai_results.append(False)
    else:
        print(f"\n🤖 Skipping AI Tests (no API key)")
    
    # Run performance tests
    print(f"\n⚡ Running Performance Tests ({len(performance_tests)} tests)...")
    perf_results = []
    for test in performance_tests:
        try:
            if asyncio.iscoroutinefunction(test):
                result = await test()
            else:
                result = test()
            perf_results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            perf_results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    basic_passed = sum(basic_results)
    print(f"Basic Tests: {basic_passed}/{len(basic_results)} passed")
    
    if ai_results:
        ai_passed = sum(ai_results)
        print(f"AI Tests: {ai_passed}/{len(ai_results)} passed")
    else:
        print(f"AI Tests: Skipped (no API key)")
    
    perf_passed = sum(perf_results)
    print(f"Performance Tests: {perf_passed}/{len(perf_results)} passed")
    
    all_results = basic_results + ai_results + perf_results
    if all_results and all(all_results):
        print(f"\n🎉 All integration tests passed!")
        print("Your Enhanced FDA Explorer is fully functional!")
    elif basic_results and all(basic_results):
        print(f"\n✅ Basic functionality working!")
        if not has_ai_key:
            print("Add AI API key to test advanced features.")
    else:
        print(f"\n⚠️  Some tests failed. Check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())