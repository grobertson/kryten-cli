#!/usr/bin/env python3
"""Test script to verify kryten-cli installation and basic functionality."""

import sys


def test_imports():
    """Test that all required imports work."""
    print("Testing imports...")
    try:
        from kryten import KrytenClient
        print("✓ Successfully imported KrytenClient from kryten")
        return True
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        print("\nPlease install kryten-py:")
        print("  cd ../kryten-py && pip install -e .")
        return False


def test_cli_module():
    """Test that the CLI module loads."""
    print("\nTesting CLI module...")
    try:
        import kryten_cli
        print("✓ Successfully loaded kryten_cli module")
        return True
    except Exception as e:
        print(f"✗ Failed to load CLI: {e}")
        return False


def test_config_example():
    """Test that config example exists."""
    print("\nChecking config example...")
    from pathlib import Path
    
    config_file = Path("config.example.json")
    if config_file.exists():
        print(f"✓ Found {config_file}")
        return True
    else:
        print(f"✗ Missing {config_file}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("kryten-cli Installation Test")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("CLI Module", test_cli_module()))
    results.append(("Config Example", test_config_example()))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All tests passed! kryten-cli is ready to use.")
        print("\nNext steps:")
        print("  1. Copy config.example.json to config.json")
        print("  2. Edit config.json with your settings")
        print("  3. Run: kryten say 'Hello from kryten-cli!'")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
