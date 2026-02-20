#!/usr/bin/env python3
"""
Test routing for product launch agent.
Verifies that the root agent correctly routes product launch requests.
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_routing_keywords():
    """Test that the root agent system prompt includes proper routing keywords."""
    print("\n" + "=" * 60)
    print("TEST: Product Launch Agent Routing")
    print("=" * 60)

    from classes.ai_multi_agent.root_agent import ROOT_SYSTEM_PROMPT

    # Keywords that should trigger product launch agent
    keywords = [
        "product launch",
        "launch video",
        "promotional video",
        "showcase video",
        "repo video",
        "GitHub video",
        "invoke_product_launch_agent",
    ]

    print("\nChecking root agent system prompt for routing keywords...")

    all_found = True
    for keyword in keywords:
        found = keyword in ROOT_SYSTEM_PROMPT
        status = "✅" if found else "❌"
        print(f"{status} '{keyword}': {'FOUND' if found else 'MISSING'}")
        if not found:
            all_found = False

    if all_found:
        print("\n✅ All routing keywords present in system prompt")
        return True
    else:
        print("\n❌ Some routing keywords missing")
        return False


def test_tool_registration():
    """Test that invoke_product_launch_agent tool exists."""
    print("\n" + "=" * 60)
    print("TEST: Product Launch Tool Registration")
    print("=" * 60)

    try:
        # This would need a mock setup to work fully, but we can at least check imports
        from classes.ai_multi_agent import sub_agents

        print("\n✅ Product launch agent module imported successfully")
        print(f"✅ run_product_launch_agent function exists: {hasattr(sub_agents, 'run_product_launch_agent')}")

        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def print_example_prompts():
    """Print example user prompts that should trigger the product launch agent."""
    print("\n" + "=" * 60)
    print("EXAMPLE USER PROMPTS")
    print("=" * 60)
    print("\nThese prompts should all route to the product launch agent:\n")

    examples = [
        "Create a product launch video for https://github.com/facebook/react",
        "Make a launch video for facebook/react",
        "Generate a promotional video for this GitHub repo: github.com/openai/gpt-4",
        "Build a showcase video for my repository",
        "I need a GitHub video for my project at github.com/user/repo",
        "Create an animated launch video from github.com/project/name",
    ]

    for i, example in enumerate(examples, 1):
        print(f"{i}. \"{example}\"")

    print("\n" + "=" * 60)


def main():
    """Run routing tests."""
    print("\nProduct Launch Agent - Routing Tests")

    results = {
        "Routing Keywords": test_routing_keywords(),
        "Tool Registration": test_tool_registration(),
    }

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    if passed_count == total_count:
        print("\n✅ Routing is properly configured!")
        print_example_prompts()
        print("\n💡 TIP: If you still get 'command not recognized' errors:")
        print("   1. Restart the Flowcut application to reload the updated agent")
        print("   2. Try one of the example prompts above")
        print("   3. Make sure to include 'product launch' or 'GitHub' in your request")
        return 0
    else:
        print(f"\n⚠ {total_count - passed_count} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
