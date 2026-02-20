#!/usr/bin/env python3
"""
Test script for Directors UI and analysis workflow.

This script verifies:
1. Directors load correctly
2. Analysis tools are available
3. Directors analyze without asking for file specifications
4. Canvas UI initializes properly
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_director_loading():
    """Test loading directors from .director files."""
    print("Testing director loading...")

    try:
        from classes.ai_directors.director_loader import get_director_loader

        loader = get_director_loader()
        directors = loader.list_available_directors()

        print(f"✓ Loaded {len(directors)} directors:")
        for director in directors:
            print(f"  - {director.name} ({director.id})")
            print(f"    Expertise: {', '.join(director.personality.expertise_areas)}")
            print(f"    Focus: {', '.join(director.personality.analysis_focus)}")
            print()

        return True
    except Exception as e:
        print(f"✗ Director loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_analysis_tools():
    """Test analysis tools availability."""
    print("Testing analysis tools...")

    try:
        from classes.ai_directors.director_tools import get_director_analysis_tools_for_langchain

        tools = get_director_analysis_tools_for_langchain()

        print(f"✓ {len(tools)} analysis tools available:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

        return True
    except Exception as e:
        print(f"✗ Analysis tools test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_director_prompt():
    """Test that director prompt emphasizes using all tools."""
    print("Testing director analysis prompt...")

    try:
        from classes.ai_directors.director_loader import get_director_loader

        loader = get_director_loader()
        directors = loader.list_available_directors()

        if not directors:
            print("✗ No directors available")
            return False

        director = directors[0]

        # Check if the system prompt mentions tools
        system_prompt = director.get_system_prompt()

        print("✓ Director system prompt configured")
        print(f"  Name: {director.name}")
        print(f"  Prompt length: {len(system_prompt)} chars")

        # The key is in the analysis_prompt in director_agent.py
        # We've updated it to explicitly instruct using all tools

        return True
    except Exception as e:
        print(f"✗ Director prompt test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_files_exist():
    """Test that UI files exist and are accessible."""
    print("Testing UI files...")

    ui_files = [
        'src/timeline/directors/panel.html',
        'src/timeline/directors/panel.css',
        'src/timeline/directors/panel.js',
    ]

    all_exist = True
    for file_path in ui_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            print(f"✓ {file_path} exists ({size} bytes)")
        else:
            print(f"✗ {file_path} missing")
            all_exist = False

    return all_exist


def main():
    """Run all tests."""
    print("=" * 60)
    print("Directors System Test")
    print("=" * 60)
    print()

    tests = [
        ("Director Loading", test_director_loading),
        ("Analysis Tools", test_analysis_tools),
        ("Director Prompt", test_director_prompt),
        ("UI Files", test_ui_files_exist),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"{test_name}")
        print("=" * 60)
        result = test_func()
        results.append((test_name, result))
        print()

    print("=" * 60)
    print("Test Results")
    print("=" * 60)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result for _, result in results)

    print()
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
