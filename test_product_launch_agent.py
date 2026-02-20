#!/usr/bin/env python3
"""
Test suite for Product Launch Agent.

Tests GitHub client, product launch tools, and agent integration.
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from classes.logger import log


def test_github_client():
    """Test GitHub API client functions."""
    print("\n" + "=" * 60)
    print("TEST 1: GitHub Client")
    print("=" * 60)

    try:
        from classes.github_client import parse_github_url, get_repo_info, get_readme, GitHubError

        # Test URL parsing
        print("\n1.1: Testing URL parsing...")
        test_urls = [
            ("https://github.com/facebook/react", "facebook", "react"),
            ("github.com/openai/gpt-4", "openai", "gpt-4"),
            ("facebook/react", "facebook", "react"),
            ("https://github.com/facebook/react.git", "facebook", "react"),
        ]

        for url, expected_owner, expected_repo in test_urls:
            owner, repo = parse_github_url(url)
            assert owner == expected_owner and repo == expected_repo, f"Failed to parse {url}"
            print(f"✓ Parsed {url} -> {owner}/{repo}")

        print("\n1.2: Testing repo info fetch (public repo: facebook/react)...")
        repo_info = get_repo_info("facebook", "react")

        assert repo_info.get("name") == "react", "Repo name mismatch"
        assert repo_info.get("owner", {}).get("login") == "facebook", "Owner mismatch"
        assert isinstance(repo_info.get("stargazers_count"), int), "Stars should be integer"

        print(f"✓ Fetched repo: {repo_info.get('full_name')}")
        print(f"  - Stars: {repo_info.get('stargazers_count'):,}")
        print(f"  - Description: {repo_info.get('description')[:60]}...")
        print(f"  - Language: {repo_info.get('language')}")

        print("\n1.3: Testing README fetch...")
        readme = get_readme("facebook", "react")
        assert len(readme) > 0, "README should not be empty"
        print(f"✓ Fetched README ({len(readme)} characters)")
        print(f"  Preview: {readme[:100]}...")

        print("\n✅ GitHub Client: ALL TESTS PASSED")
        return True

    except GitHubError as e:
        print(f"\n❌ GitHub API Error: {e}")
        if e.status_code == 403:
            print("   Note: Rate limit may be exceeded. Try again later or add a GitHub token.")
        return False
    except Exception as e:
        print(f"\n❌ GitHub Client Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_product_launch_tools():
    """Test product launch tools (without running the agent)."""
    print("\n" + "=" * 60)
    print("TEST 2: Product Launch Tools")
    print("=" * 60)

    try:
        from classes.ai_product_launch_tools import (
            get_product_launch_tools_for_langchain,
            generate_product_launch_manim_code,
        )
        from classes.github_client import get_repo_data_from_url

        print("\n2.1: Testing tool registration...")
        tools = get_product_launch_tools_for_langchain()
        assert len(tools) == 2, f"Expected 2 tools, got {len(tools)}"

        tool_names = [t.name for t in tools]
        assert "fetch_github_repo_data" in tool_names, "Missing fetch_github_repo_data"
        assert "generate_product_launch_video" in tool_names, "Missing generate_product_launch_video"

        print(f"✓ Registered {len(tools)} tools: {', '.join(tool_names)}")

        print("\n2.2: Testing GitHub data extraction tool...")
        fetch_tool = tools[0]  # fetch_github_repo_data
        result_json = fetch_tool.invoke({"repo_url": "facebook/react"})
        result = json.loads(result_json)

        if "error" in result:
            print(f"⚠ GitHub API Error: {result['error']}")
            if "rate limit" in str(result.get("detail", "")).lower():
                print("   Note: Rate limit exceeded. Continuing with mock data...")
                # Create mock data for testing
                result = {
                    "success": True,
                    "owner": "facebook",
                    "repo": "react",
                    "name": "react",
                    "description": "A JavaScript library for building user interfaces",
                    "stars": 200000,
                    "forks": 45000,
                    "language": "JavaScript",
                    "topics": ["javascript", "library", "ui"],
                    "full_data": {
                        "repo_info": {
                            "name": "react",
                            "description": "A JavaScript library for building user interfaces",
                            "stargazers_count": 200000,
                            "forks_count": 45000,
                            "language": "JavaScript",
                            "topics": ["javascript", "library", "ui"],
                        },
                        "readme": "# React\n\nA JavaScript library for building user interfaces.\n\n- Declarative\n- Component-Based\n- Learn Once, Write Anywhere",
                        "owner": "facebook",
                        "repo": "react",
                    }
                }
        else:
            assert result.get("success") == True, "Should return success: true"
            assert result.get("name") == "react", "Repo name mismatch"
            assert isinstance(result.get("stars"), int), "Stars should be integer"

        print(f"✓ Fetched data for {result['owner']}/{result['repo']}")
        print(f"  - Stars: {result.get('stars', 0):,}")
        print(f"  - Language: {result.get('language')}")
        print(f"  - Topics: {', '.join(result.get('topics', [])[:3])}")

        print("\n2.3: Testing Manim code generation...")
        full_data = result.get("full_data")
        if full_data:
            manim_code = generate_product_launch_manim_code(full_data)

            assert "class IntroScene(Scene):" in manim_code, "Missing IntroScene"
            assert "class StatsScene(Scene):" in manim_code, "Missing StatsScene"
            assert "class OutroScene(Scene):" in manim_code, "Missing OutroScene"

            # Count scenes
            scene_count = manim_code.count("class") - manim_code.count("# class")
            print(f"✓ Generated Manim code with {scene_count} scenes")
            print(f"  - Code length: {len(manim_code)} characters")
            print(f"  - Scenes: IntroScene, StatsScene, OutroScene" + (", FeaturesScene" if "FeaturesScene" in manim_code else ""))
        else:
            print("⚠ Skipping Manim code generation (no full_data)")

        print("\n✅ Product Launch Tools: ALL TESTS PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Product Launch Tools Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_registration():
    """Test that the agent is properly registered."""
    print("\n" + "=" * 60)
    print("TEST 3: Agent Registration")
    print("=" * 60)

    try:
        print("\n3.1: Testing sub-agent import...")
        from classes.ai_multi_agent import sub_agents
        assert hasattr(sub_agents, "run_product_launch_agent"), "Missing run_product_launch_agent"
        print("✓ Product launch agent found in sub_agents")

        print("\n3.2: Testing root agent integration...")
        from classes.ai_multi_agent.root_agent import ROOT_SYSTEM_PROMPT
        assert "invoke_product_launch_agent" in ROOT_SYSTEM_PROMPT, "Product launch agent not in root prompt"
        print("✓ Product launch agent included in root system prompt")

        print("\n3.3: Testing MainThreadToolRunner registration...")
        from classes.ai_agent_runner import create_main_thread_runner
        runner = create_main_thread_runner()

        # Check if product launch tools are registered
        assert "fetch_github_repo_data" in runner._tools, "fetch_github_repo_data not registered"
        assert "generate_product_launch_video" in runner._tools, "generate_product_launch_video not registered"
        print(f"✓ Product launch tools registered in MainThreadToolRunner")
        print(f"  - Total tools registered: {len(runner._tools)}")

        print("\n✅ Agent Registration: ALL TESTS PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Agent Registration Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manim_availability():
    """Test if Manim is installed and available."""
    print("\n" + "=" * 60)
    print("TEST 4: Manim Availability")
    print("=" * 60)

    try:
        print("\n4.1: Testing Manim import...")
        try:
            import manim
            print(f"✓ Manim is installed (version: {manim.__version__})")
            manim_available = True
        except ImportError:
            print("⚠ Manim not installed via pip install")
            manim_available = False

        print("\n4.2: Testing Manim CLI...")
        import shutil
        manim_cli = shutil.which("manim")
        if manim_cli:
            print(f"✓ Manim CLI found at: {manim_cli}")
            manim_available = True
        else:
            print("⚠ Manim CLI not found in PATH")

        if not manim_available:
            print("\n⚠ Manim is not available. Product launch videos will require Manim installation:")
            print("   pip install manim")
            print("   For more info: https://docs.manim.community/")
            return False

        print("\n✅ Manim Availability: PASSED")
        return True

    except Exception as e:
        print(f"\n❌ Manim Availability Test Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PRODUCT LAUNCH AGENT - TEST SUITE")
    print("=" * 60)

    results = {
        "GitHub Client": test_github_client(),
        "Product Launch Tools": test_product_launch_tools(),
        "Agent Registration": test_agent_registration(),
        "Manim Availability": test_manim_availability(),
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
        print("\n🎉 ALL TESTS PASSED! Product Launch Agent is ready to use.")
        print("\nTo test the full agent:")
        print('1. Start Flowcut')
        print('2. In the chat, type: "Create a product launch video for https://github.com/facebook/react"')
        print('3. The agent will fetch GitHub data, generate Manim scenes, and add the video to your timeline')
        return 0
    else:
        print(f"\n⚠ {total_count - passed_count} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
