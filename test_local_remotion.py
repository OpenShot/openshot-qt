#!/usr/bin/env python3
"""
Test local Remotion server with the configured API key
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_local_remotion():
    """Test that local Remotion works with dev API key"""
    print("\n" + "="*60)
    print("🧪 TESTING LOCAL REMOTION SERVER")
    print("="*60)

    try:
        from classes.video_generation.remotion_client import (
            render_from_repo,
            RemotionError,
        )

        # Local server configuration
        api_key = "dev-key-change-me"
        base_url = "http://127.0.0.1:4500/api/v1"

        print(f"\n📋 Configuration:")
        print(f"   API Key: {api_key}")
        print(f"   Base URL: {base_url}")
        print(f"   Test: Simple text video")

        print("\n🚀 Submitting render job...")
        print("   (This may take 30-60 seconds)")

        # Progress tracker
        last_progress = [-1]

        def progress_callback(progress, status):
            if progress != last_progress[0]:
                print(f"   📊 Progress: {progress}% - {status}")
                last_progress[0] = progress

        # Start render with product-launch template
        result = render_from_repo(
            api_key=api_key,
            repo_url="https://github.com/remotion-dev/template-still",
            template="product-launch",  # Using available template from local server
            user_input="Test from Flowcut - Local Remotion Working!",
            codec="h264",
            base_url=base_url,
            timeout_seconds=120,
            poll_callback=progress_callback,
        )

        print("\n✅ SUCCESS! Video generated!")
        print(f"\n📦 Result:")
        print(f"   Job ID: {result.get('jobId')}")
        print(f"   Video URL: {result.get('videoUrl')}")
        print(f"   Download URL: {result.get('downloadUrl')}")

        metadata = result.get('metadata', {})
        if metadata:
            print(f"\n📊 Metadata:")
            print(f"   Duration: {metadata.get('duration', 'N/A')}s")
            print(f"   Width: {metadata.get('width', 'N/A')}")
            print(f"   Height: {metadata.get('height', 'N/A')}")
            print(f"   FPS: {metadata.get('fps', 'N/A')}")

        print("\n🎉 Local Remotion is working perfectly!")
        print("\n💡 This means:")
        print("   ✅ Remotion server is running")
        print("   ✅ Authentication is working")
        print("   ✅ Video rendering is functional")
        print("   ✅ Ready to use in Flowcut!")

        return True

    except RemotionError as e:
        print(f"\n❌ Remotion Error: {e}")
        if "Authentication failed" in str(e):
            print("\n🔍 Troubleshooting:")
            print("   1. Check that Remotion server is running:")
            print("      ps aux | grep remotion")
            print("   2. Check the API key in remotion/api/.env")
            print("   3. Restart the Remotion server if needed")
        return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_local_remotion()
    sys.exit(0 if success else 1)
