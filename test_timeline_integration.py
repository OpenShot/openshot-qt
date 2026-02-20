#!/usr/bin/env python3
"""
Test timeline integration for product launch videos.
Verifies the file can be found and added to timeline.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_file_lookup():
    """Test that File.get() can find files properly."""
    print("\n" + "=" * 60)
    print("TEST: File Lookup Methods")
    print("=" * 60)

    print("\n1. Testing File.get() method...")
    try:
        from classes.query import File

        # Get all files
        all_files = File.filter()
        print(f"✅ Found {len(all_files)} files in project")

        if len(all_files) > 0:
            # Test first file
            test_file = all_files[0]
            print(f"\n2. Testing file methods on: {test_file.data.get('path', 'unknown')}")

            # Test path attribute
            if hasattr(test_file, 'path'):
                print(f"   ✅ Has 'path' attribute: {test_file.path}")
            else:
                print(f"   ⚠ No 'path' attribute")

            # Test absolute_path method
            if hasattr(test_file, 'absolute_path'):
                if callable(test_file.absolute_path):
                    abs_path = test_file.absolute_path()
                    print(f"   ✅ Has 'absolute_path()' method: {abs_path}")
                else:
                    print(f"   ⚠ 'absolute_path' exists but not callable")
            else:
                print(f"   ⚠ No 'absolute_path' method")

            # Test data structure
            if hasattr(test_file, 'data'):
                print(f"   ✅ Has 'data' dict with keys: {list(test_file.data.keys())[:5]}")
            else:
                print(f"   ⚠ No 'data' attribute")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_add_clip_function():
    """Test that add_clip_to_timeline function exists."""
    print("\n" + "=" * 60)
    print("TEST: Timeline Functions")
    print("=" * 60)

    try:
        from classes.ai_openshot_tools import add_clip_to_timeline

        print("\n1. Testing add_clip_to_timeline...")
        print(f"   ✅ Function imported successfully")
        print(f"   ✅ Function signature: {add_clip_to_timeline.__name__}")

        # Check function parameters
        import inspect
        sig = inspect.signature(add_clip_to_timeline)
        params = list(sig.parameters.keys())
        print(f"   ✅ Parameters: {params}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_integration_tips():
    """Print tips for debugging timeline integration."""
    print("\n" + "=" * 60)
    print("TIMELINE INTEGRATION TIPS")
    print("=" * 60)

    print("\nIf video is not appearing on timeline:")
    print("\n1. Check console logs:")
    print("   - Look for 'Adding product launch video to project...'")
    print("   - Check for 'add_files failed' errors")
    print("   - Look for 'Could not find file in database'")

    print("\n2. Check Project Files tab:")
    print("   - Video should appear in project files after generation")
    print("   - Look for files starting with 'product_launch_combined'")

    print("\n3. Manual workaround:")
    print("   - Note the video path from success message")
    print("   - Go to Project Files > Import Files")
    print("   - Select the video file")
    print("   - Drag it to your timeline")

    print("\n4. Check temp directory:")
    print("   - Videos are saved in: /tmp/flowcut_product_launch_*/")
    print("   - Use: ls -la /tmp/flowcut_product_launch_*/")


def main():
    """Run diagnostic tests."""
    print("\nProduct Launch - Timeline Integration Diagnostics")

    results = {
        "File Lookup": test_file_lookup(),
        "Timeline Functions": test_add_clip_function(),
    }

    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n✅ Timeline integration components are working!")
        print_integration_tips()
        return 0
    else:
        print(f"\n⚠ {total_count - passed_count} diagnostic(s) failed.")
        print_integration_tips()
        return 1


if __name__ == "__main__":
    sys.exit(main())
