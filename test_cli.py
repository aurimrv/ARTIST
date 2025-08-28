#!/usr/bin/env python3
"""
Simple test script for the CLI interface.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"\n🧪 Testing: {description}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Success")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ Failed (exit code: {result.returncode})")
            if result.stderr.strip():
                print(f"Error: {result.stderr.strip()}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def main():
    """Test the CLI interface."""
    print("🚀 API Test Generator CLI Test Suite")
    print("=" * 50)
    
    # Change to project directory
    project_dir = Path(__file__).parent
    
    tests = [
        # Test help output
        (["python", "main.py", "--help"], "Help output"),
        
        # Test version command
        (["python", "main.py", "version"], "Version command"),
        
        # Test validate command (should work even without API key)
        (["python", "main.py", "validate"], "System validation"),
        
        # Test generate command with invalid inputs (should fail gracefully)
        (["python", "main.py", "generate", "--api-spec", "nonexistent.yaml", "--api-src", "nonexistent", "--output", "/tmp/test"], "Generate with invalid inputs"),
    ]
    
    passed = 0
    total = len(tests)
    
    for cmd, description in tests:
        if run_command(cmd, description):
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All CLI tests passed!")
        return 0
    else:
        print("⚠️  Some CLI tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

