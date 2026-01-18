#!/usr/bin/env python3
"""
Test script for Global News Aggregator Skill
Verifies that all components are working correctly
"""

import os
import sys
import json

def test_file_structure():
    """Test that all required files exist"""
    print("🔍 Testing file structure...")

    required_files = [
        'SKILL.md',
        'README.md',
        'USAGE.md',
        'requirements.txt',
        'enhanced_news_aggregator.py',
        'claude_news_aggregator.py',
        'news_aggregator.py',
        'demo.py',
        'api-config-example.json'
    ]

    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
            print(f"  ✗ Missing: {file}")
        else:
            print(f"  ✓ Found: {file}")

    if missing_files:
        print(f"\n❌ Test failed: {len(missing_files)} files missing")
        return False

    print("✅ All required files present")
    return True

def test_dependencies():
    """Test that required Python packages are available"""
    print("\n🔍 Testing dependencies...")

    try:
        import requests
        print("  ✓ requests package available")
        return True
    except ImportError:
        print("  ✗ requests package not installed")
        print("  Run: pip install -r requirements.txt")
        return False

def test_config_file():
    """Test configuration file if it exists"""
    print("\n🔍 Testing configuration...")

    if not os.path.exists('api-config.json'):
        print("  ⚠️  No api-config.json found (this is OK for first run)")
        print("  Run setup.py to create configuration")
        return True

    try:
        with open('api-config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Check required keys
        required_keys = ['international_api', 'domestic_api', 'output']
        for key in required_keys:
            if key not in config:
                print(f"  ✗ Missing key in config: {key}")
                return False
            print(f"  ✓ Found config section: {key}")

        # Check API configurations
        for api_type in ['international_api', 'domestic_api']:
            api_config = config[api_type]
            if 'endpoint' not in api_config:
                print(f"  ✗ Missing endpoint in {api_type}")
                return False
            if 'YOUR_API_KEY' in str(api_config) or 'YOUR_TOKEN' in str(api_config):
                print(f"  ⚠️  {api_type} contains placeholder values")
                print(f"  Please update with real API credentials")

        print("✅ Configuration file is valid")
        return True

    except json.JSONDecodeError:
        print("  ✗ Invalid JSON in api-config.json")
        return False
    except Exception as e:
        print(f"  ✗ Error reading config: {str(e)}")
        return False

def test_script_syntax():
    """Test that Python scripts have valid syntax"""
    print("\n🔍 Testing script syntax...")

    scripts = [
        'enhanced_news_aggregator.py',
        'claude_news_aggregator.py',
        'news_aggregator.py',
        'demo.py'
    ]

    for script in scripts:
        try:
            with open(script, 'r', encoding='utf-8') as f:
                compile(f.read(), script, 'exec')
            print(f"  ✓ {script} syntax OK")
        except SyntaxError as e:
            print(f"  ✗ {script} has syntax error: {e}")
            return False

    print("✅ All scripts have valid syntax")
    return True

def test_demo():
    """Test the demo script"""
    print("\n🔍 Testing demo script...")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, 'demo.py'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            print("  ✓ Demo script executed successfully")

            # Check if demo files were created
            if os.path.exists('demo_news_report.html'):
                print("  ✓ Demo HTML report created")
            if os.path.exists('demo-config.json'):
                print("  ✓ Demo config created")

            print("✅ Demo test passed")
            return True
        else:
            print(f"  ✗ Demo script failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("  ✗ Demo script timed out")
        return False
    except Exception as e:
        print(f"  ✗ Error running demo: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Global News Aggregator Skill - Test Suite")
    print("=" * 60)
    print()

    tests = [
        ("File Structure", test_file_structure),
        ("Dependencies", test_dependencies),
        ("Configuration", test_config_file),
        ("Script Syntax", test_script_syntax),
        ("Demo", test_demo)
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} test crashed: {str(e)}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! The skill is ready to use.")
        print("\nNext steps:")
        print("1. Configure your API keys (run setup.py)")
        print("2. Generate a news report: python enhanced_news_aggregator.py api-config.json")
        print("3. Use in Claude Code: 'Generate a global news report'")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
