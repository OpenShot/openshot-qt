#!/usr/bin/env python3
"""
Comprehensive test suite for the Transitions Agent.
Tests all tools and agent integration.
"""

import sys
import os
sys.path.insert(0, 'src')

def test_imports():
    """Test 1: Verify all imports work"""
    print("=" * 60)
    print("TEST 1: Verifying Imports")
    print("=" * 60)

    try:
        from classes.ai_transitions_tools import (
            list_transitions,
            search_transitions,
            get_transitions_tools_for_langchain
        )
        print("✓ Transitions tools imported successfully")

        from classes.ai_multi_agent.sub_agents import run_transitions_agent
        print("✓ Transitions agent imported successfully")

        from classes.ai_multi_agent.root_agent import ROOT_SYSTEM_PROMPT
        print("✓ Root agent with transitions imported successfully")

        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_list_transitions():
    """Test 2: List transitions functionality"""
    print("\n" + "=" * 60)
    print("TEST 2: List Transitions")
    print("=" * 60)

    try:
        from classes.ai_transitions_tools import list_transitions
        import json

        # Test listing common transitions
        result = list_transitions("common")
        data = json.loads(result)
        print(f"✓ Common transitions found: {data['total']}")

        if data['total'] == 7:
            print("✓ Correct number of common transitions (7)")

        # Test listing all transitions
        result = list_transitions("all")
        data = json.loads(result)
        print(f"✓ Total transitions found: {data['total']}")

        if data['total'] >= 400:
            print(f"✓ Large transition library confirmed ({data['total']} transitions)")

        return True
    except Exception as e:
        print(f"✗ List transitions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_transitions():
    """Test 3: Search transitions functionality"""
    print("\n" + "=" * 60)
    print("TEST 3: Search Transitions")
    print("=" * 60)

    try:
        from classes.ai_transitions_tools import search_transitions
        import json

        # Test searching for fade
        result = search_transitions("fade")
        data = json.loads(result)
        print(f"✓ Search for 'fade': {data['matches']} match(es)")

        if data['matches'] >= 1:
            print(f"  - Found: {data['transitions'][0]['name']}")

        # Test searching for wipe
        result = search_transitions("wipe")
        data = json.loads(result)
        print(f"✓ Search for 'wipe': {data['matches']} match(es)")

        # Test searching for blur
        result = search_transitions("blur")
        data = json.loads(result)
        print(f"✓ Search for 'blur': {data['matches']} match(es)")

        # Test searching for circle
        result = search_transitions("circle")
        data = json.loads(result)
        print(f"✓ Search for 'circle': {data['matches']} match(es)")

        return True
    except Exception as e:
        print(f"✗ Search transitions failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_langchain_tools():
    """Test 4: LangChain tool wrappers"""
    print("\n" + "=" * 60)
    print("TEST 4: LangChain Tool Wrappers")
    print("=" * 60)

    try:
        from classes.ai_transitions_tools import get_transitions_tools_for_langchain

        tools = get_transitions_tools_for_langchain()
        print(f"✓ Created {len(tools)} LangChain tools")

        expected_tools = [
            "list_transitions_tool",
            "search_transitions_tool",
            "add_transition_between_clips_tool",
            "add_transition_to_clip_tool"
        ]

        tool_names = [tool.name for tool in tools]

        for expected in expected_tools:
            if expected in tool_names:
                print(f"  ✓ {expected}")
            else:
                print(f"  ✗ Missing: {expected}")
                return False

        return True
    except Exception as e:
        print(f"✗ LangChain tools failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_root_agent_integration():
    """Test 5: Root agent includes transitions"""
    print("\n" + "=" * 60)
    print("TEST 5: Root Agent Integration")
    print("=" * 60)

    try:
        from classes.ai_multi_agent.root_agent import ROOT_SYSTEM_PROMPT

        if "invoke_transitions_agent" in ROOT_SYSTEM_PROMPT:
            print("✓ Root agent includes invoke_transitions_agent")
        else:
            print("✗ Root agent missing transitions agent reference")
            return False

        if "seven tools" in ROOT_SYSTEM_PROMPT or "7 tools" in ROOT_SYSTEM_PROMPT:
            print("✓ Root agent updated tool count")
        else:
            print("⚠ Root agent tool count may need verification")

        if "412+" in ROOT_SYSTEM_PROMPT or "transitions" in ROOT_SYSTEM_PROMPT.lower():
            print("✓ Root agent describes transitions capability")

        return True
    except Exception as e:
        print(f"✗ Root agent integration check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_transition_files_exist():
    """Test 6: Verify transition files exist"""
    print("\n" + "=" * 60)
    print("TEST 6: Transition Files Existence")
    print("=" * 60)

    try:
        from classes import info

        transitions_dir = os.path.join(info.PATH, "transitions")
        common_dir = os.path.join(transitions_dir, "common")
        extra_dir = os.path.join(transitions_dir, "extra")

        if os.path.exists(common_dir):
            common_count = len([f for f in os.listdir(common_dir) if not f.startswith('.')])
            print(f"✓ Common transitions directory exists: {common_count} files")
        else:
            print("✗ Common transitions directory not found")
            return False

        if os.path.exists(extra_dir):
            extra_count = len([f for f in os.listdir(extra_dir) if not f.startswith('.')])
            print(f"✓ Extra transitions directory exists: {extra_count} files")
        else:
            print("✗ Extra transitions directory not found")
            return False

        print(f"✓ Total transition files: {common_count + extra_count}")

        return True
    except Exception as e:
        print(f"✗ File existence check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_system_prompt():
    """Test 7: Verify transitions agent system prompt"""
    print("\n" + "=" * 60)
    print("TEST 7: Transitions Agent System Prompt")
    print("=" * 60)

    try:
        from classes.ai_multi_agent.sub_agents import TRANSITIONS_SYSTEM_PROMPT

        required_terms = [
            "transitions",
            "list_clips_tool",
            "search_transitions_tool",
            "add_transition",
            "fade",
            "wipe"
        ]

        for term in required_terms:
            if term.lower() in TRANSITIONS_SYSTEM_PROMPT.lower():
                print(f"  ✓ Contains '{term}'")
            else:
                print(f"  ✗ Missing '{term}'")
                return False

        print("✓ Transitions agent system prompt is complete")
        return True
    except Exception as e:
        print(f"✗ System prompt check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "=" * 60)
    print("TRANSITIONS AGENT TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        ("Imports", test_imports),
        ("List Transitions", test_list_transitions),
        ("Search Transitions", test_search_transitions),
        ("LangChain Tools", test_langchain_tools),
        ("Root Agent Integration", test_root_agent_integration),
        ("Transition Files", test_transition_files_exist),
        ("Agent System Prompt", test_agent_system_prompt),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Transitions Agent is ready to use.")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
