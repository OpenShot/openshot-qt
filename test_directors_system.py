#!/usr/bin/env python3
"""
Test script for Directors System

This script tests the directors system end-to-end without requiring a full GUI.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def test_director_loading():
    """Test 1: Load built-in directors"""
    print("\n=== Test 1: Director Loading ===")
    try:
        from classes.ai_directors.director_loader import get_director_loader

        loader = get_director_loader()

        # Load individual directors
        youtube = loader.load_director("youtube_director")
        genz = loader.load_director("genz_director")
        cinematic = loader.load_director("cinematic_director")

        assert youtube is not None, "YouTube director not loaded"
        assert genz is not None, "GenZ director not loaded"
        assert cinematic is not None, "Cinematic director not loaded"

        print(f"✓ Loaded YouTube Director: {youtube.name}")
        print(f"✓ Loaded GenZ Director: {genz.name}")
        print(f"✓ Loaded Cinematic Director: {cinematic.name}")

        # List all directors
        all_directors = loader.list_available_directors()
        print(f"✓ Total directors available: {len(all_directors)}")

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_director_tools():
    """Test 2: Analysis tools"""
    print("\n=== Test 2: Analysis Tools ===")
    try:
        from classes.ai_directors.director_tools import (
            get_director_analysis_tools_for_langchain
        )

        tools = get_director_analysis_tools_for_langchain()

        print(f"✓ Loaded {len(tools)} analysis tools:")
        for tool in tools:
            print(f"  - {tool.name}")

        assert len(tools) == 7, f"Expected 7 tools, got {len(tools)}"

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plan_structures():
    """Test 3: Plan data structures"""
    print("\n=== Test 3: Plan Data Structures ===")
    try:
        from classes.ai_directors.director_plan import (
            DirectorPlan, PlanStep, PlanStepType, DebateMessage
        )
        import uuid

        # Create a plan
        plan = DirectorPlan(
            title="Test Plan",
            summary="This is a test plan",
            created_by=["youtube_director", "cinematic_director"]
        )

        # Add steps
        step1 = PlanStep(
            step_id=str(uuid.uuid4()),
            type=PlanStepType.EDIT_TIMELINE,
            description="Improve pacing",
            agent="video",
            tool_name="test_tool",
            tool_args={},
            rationale="For better retention",
            confidence=0.8,
        )

        step2 = PlanStep(
            step_id=str(uuid.uuid4()),
            type=PlanStepType.ADD_TRANSITION,
            description="Add smooth transitions",
            agent="video",
            tool_name="test_tool",
            tool_args={},
            rationale="For cinematic quality",
            confidence=0.7,
            dependencies=[step1.step_id],
        )

        plan.add_step(step1)
        plan.add_step(step2)

        # Add debate message
        message = DebateMessage(
            director_id="youtube_director",
            director_name="YouTube Director",
            round_number=0,
            message_type="analysis",
            content="Pacing is too slow",
        )
        plan.add_debate_message(message)

        # Validate plan
        is_valid, error = plan.validate()
        assert is_valid, f"Plan validation failed: {error}"

        # Serialize
        plan_dict = plan.to_dict()
        assert "plan_id" in plan_dict
        assert len(plan_dict["steps"]) == 2
        assert len(plan_dict["debate_transcript"]) == 1

        print(f"✓ Created plan with {len(plan.steps)} steps")
        print(f"✓ Plan validation: passed")
        print(f"✓ Serialization: passed")

        # Test deserialization
        plan2 = DirectorPlan.from_dict(plan_dict)
        assert plan2.plan_id == plan.plan_id
        assert len(plan2.steps) == len(plan.steps)

        print(f"✓ Deserialization: passed")

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_marketplace():
    """Test 4: Marketplace functions"""
    print("\n=== Test 4: Marketplace ===")
    try:
        from classes.ai_directors.director_marketplace import get_marketplace

        marketplace = get_marketplace()

        # List directors
        directors = marketplace.list_available_directors()
        print(f"✓ Marketplace has {len(directors)} directors")

        # Test export (to temp file)
        import tempfile
        if directors:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.director', delete=False) as f:
                temp_path = f.name

            success = marketplace.export_director(directors[0].id, temp_path)
            assert success, "Export failed"
            print(f"✓ Exported director to {temp_path}")

            # Test import
            success = marketplace.install_director_from_file(temp_path)
            assert success, "Import failed"
            print(f"✓ Imported director from {temp_path}")

            # Clean up
            os.remove(temp_path)

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plan_executor():
    """Test 5: Plan executor (without actual execution)"""
    print("\n=== Test 5: Plan Executor ===")
    try:
        from classes.ai_plan_executor import PlanExecutor
        from classes.ai_directors.director_plan import DirectorPlan, PlanStep, PlanStepType
        import uuid

        # Create mock plan
        plan = DirectorPlan(title="Test Execution Plan")

        step1 = PlanStep(
            step_id=str(uuid.uuid4()),
            type=PlanStepType.EDIT_TIMELINE,
            description="Step 1",
            agent="video",
            tool_name="test",
            tool_args={},
            rationale="Test",
            confidence=0.8,
        )

        step2 = PlanStep(
            step_id=str(uuid.uuid4()),
            type=PlanStepType.EDIT_TIMELINE,
            description="Step 2",
            agent="video",
            tool_name="test",
            tool_args={},
            rationale="Test",
            confidence=0.8,
            dependencies=[step1.step_id],
        )

        plan.add_step(step1)
        plan.add_step(step2)

        # Validate
        is_valid, error = plan.validate()
        assert is_valid, f"Plan validation failed: {error}"
        print(f"✓ Plan created with 2 dependent steps")

        # Note: We can't actually execute without a Qt app and main thread runner
        print(f"✓ PlanExecutor class available")
        print(f"  (Actual execution requires Qt application)")

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_settings():
    """Test 6: Settings integration"""
    print("\n=== Test 6: Settings Integration ===")
    try:
        # Check if settings file has Directors category
        settings_path = os.path.join(
            os.path.dirname(__file__),
            'src', 'settings', '_default.settings'
        )

        with open(settings_path, 'r') as f:
            import json
            settings = json.load(f)

        directors_settings = [s for s in settings if s.get('category') == 'Directors']

        assert len(directors_settings) >= 4, f"Expected at least 4 Directors settings, found {len(directors_settings)}"

        print(f"✓ Found {len(directors_settings)} Directors settings:")
        for setting in directors_settings:
            print(f"  - {setting.get('setting')}: {setting.get('title')}")

        return True

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("DIRECTORS SYSTEM TEST SUITE")
    print("=" * 60)

    tests = [
        ("Director Loading", test_director_loading),
        ("Analysis Tools", test_director_tools),
        ("Plan Structures", test_plan_structures),
        ("Marketplace", test_marketplace),
        ("Plan Executor", test_plan_executor),
        ("Settings", test_settings),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
