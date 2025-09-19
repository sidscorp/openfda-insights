#!/usr/bin/env python3
"""Test script for openFDA Explorer API"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, 'src')

from enhanced_fda_explorer import FDAExplorer

async def test_basic_search():
    """Test basic FDA search without AI"""
    print("\n=== Testing Basic FDA Search ===")
    explorer = FDAExplorer()
    
    try:
        # Search for pacemaker devices
        result = await explorer.search(
            query="pacemaker",
            query_type="device",
            limit=5,
            include_ai_analysis=False
        )
        
        print(f"✅ Search successful!")
        print(f"   Query: {result['query']}")
        print(f"   Total results: {result['total_results']}")
        print(f"   Results returned: {result['results_count']}")
        
        if result['results_count'] > 0:
            print(f"   Sample result: {result['results'][0].get('report_number', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"❌ Basic search failed: {e}")
        return False
    finally:
        await explorer.close()

async def test_ai_analysis():
    """Test AI-powered analysis"""
    print("\n=== Testing AI Analysis ===")
    
    # Check if AI key is set
    ai_key = os.getenv('AI_API_KEY', '')
    if not ai_key:
        print("⚠️  AI_API_KEY not set, skipping AI test")
        return None
        
    explorer = FDAExplorer()
    
    try:
        # Search with AI analysis
        result = await explorer.search(
            query="insulin pump",
            query_type="device", 
            limit=10,
            include_ai_analysis=True
        )
        
        print(f"✅ AI search successful!")
        
        if 'ai_analysis' in result:
            ai = result['ai_analysis']
            print(f"   AI Summary: {ai.get('summary', 'N/A')[:100]}...")
            
            if 'key_insights' in ai:
                print(f"   Insights found: {len(ai['key_insights'])}")
                
            if 'risk_assessment' in ai:
                risk = ai['risk_assessment']
                print(f"   Risk Level: {risk.get('level', 'N/A')}")
                print(f"   Risk Score: {risk.get('score', 'N/A')}")
        else:
            print("   No AI analysis in response")
            
        return True
    except Exception as e:
        print(f"❌ AI analysis failed: {e}")
        return False
    finally:
        await explorer.close()

async def test_device_intelligence():
    """Test device intelligence feature"""
    print("\n=== Testing Device Intelligence ===")
    
    explorer = FDAExplorer()
    
    try:
        # Get device intelligence
        result = await explorer.get_device_intelligence(
            device_name="defibrillator",
            lookback_months=6,
            include_risk_assessment=True
        )
        
        print(f"✅ Device intelligence successful!")
        print(f"   Device: {result.get('device_name', 'N/A')}")
        print(f"   Total events: {result.get('total_events', 0)}")
        
        if 'temporal_trends' in result:
            print(f"   Trend data points: {len(result['temporal_trends'])}")
            
        if 'risk_assessment' in result:
            risk = result['risk_assessment']
            print(f"   Risk assessment included: Yes")
            print(f"   Risk level: {risk.get('level', 'N/A')}")
            
        return True
    except Exception as e:
        print(f"❌ Device intelligence failed: {e}")
        return False
    finally:
        await explorer.close()

async def main():
    """Run all tests"""
    print("=" * 50)
    print("OpenFDA Explorer Test Suite")
    print("=" * 50)
    
    # Show configuration
    print("\n📋 Configuration:")
    print(f"   FDA API Key: {'✅ Set' if os.getenv('FDA_API_KEY') else '❌ Not set'}")
    print(f"   AI Provider: {os.getenv('AI_PROVIDER', 'Not set')}")
    print(f"   AI API Key: {'✅ Set' if os.getenv('AI_API_KEY') else '❌ Not set'}")
    
    # Run tests
    results = []
    
    # Test 1: Basic search
    results.append(("Basic FDA Search", await test_basic_search()))
    
    # Test 2: AI analysis
    results.append(("AI Analysis", await test_ai_analysis()))
    
    # Test 3: Device intelligence  
    results.append(("Device Intelligence", await test_device_intelligence()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    print("=" * 50)
    
    for test_name, result in results:
        if result is None:
            status = "⚠️  SKIPPED"
        elif result:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"{test_name:.<30} {status}")
    
    # Overall result
    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)