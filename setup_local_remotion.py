#!/usr/bin/env python3
"""
Configure Zenvi to use local Remotion server.
This script updates the settings to point to the local Remotion instance.
"""

import sys
import os
import json

def setup_local_remotion():
    """Configure Zenvi settings for local Remotion"""

    print("\n" + "="*60)
    print("⚙️  CONFIGURING ZENVI FOR LOCAL REMOTION")
    print("="*60)

    # Configuration
    config = {
        "api_key": "dev-key-change-me",
        "base_url": "http://127.0.0.1:4500/api/v1",
        "service": "remotion"
    }

    print(f"\n📋 Configuration to apply:")
    print(f"   Video Generation Service: {config['service']}")
    print(f"   Remotion API Key: {config['api_key']}")
    print(f"   Remotion Base URL: {config['base_url']}")

    # Update .env file
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    print(f"\n📝 Updating .env file...")

    try:
        # Check if already configured
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()

            if 'REMOTION_API_KEY' in env_content:
                print("   ✅ .env already has Remotion configuration")
            else:
                print("   ⚠️  .env exists but missing Remotion config")
                print("   Please add these lines to .env:")
                print(f"      REMOTION_API_KEY={config['api_key']}")
                print(f"      REMOTION_BASE_URL={config['base_url']}")
        else:
            print("   ℹ️  No .env file found (this is OK)")
    except Exception as e:
        print(f"   ⚠️  Could not check .env: {e}")

    # Instructions for Zenvi Preferences
    print("\n" + "="*60)
    print("📱 MANUAL SETUP REQUIRED IN ZENVI")
    print("="*60)

    print("\n1️⃣  Launch Zenvi")
    print("   python src/launch.py")
    print("   (or your normal launch method)")

    print("\n2️⃣  Open Preferences")
    print("   Menu: Edit > Preferences")
    print("   (or Zenvi > Preferences on macOS)")

    print("\n3️⃣  Navigate to AI Settings")
    print("   Click: AI (in left sidebar)")

    print("\n4️⃣  Configure Video Generation")
    print(f"   Video Generation Service: Select 'Remotion'")
    print(f"   Remotion API Key: {config['api_key']}")
    print(f"   Remotion Base URL: {config['base_url']}")

    print("\n5️⃣  Save Settings")
    print("   Click: OK")

    print("\n6️⃣  Test It Out!")
    print("   Open AI Chat panel")
    print("   Type: 'Generate a video showing a modern tech office'")
    print("   Watch: Video generates and adds to timeline!")

    # Verification
    print("\n" + "="*60)
    print("✅ VERIFICATION")
    print("="*60)

    print("\n🔍 Check Remotion server is running:")
    print("   curl http://127.0.0.1:4500/api/v1/health")

    print("\n🔍 Check available templates:")
    print("   Available: product-launch, globe-travel, code-showcase, desktop-app-demo")

    print("\n🔍 Test video generation:")
    print("   python test_local_remotion.py")

    print("\n" + "="*60)
    print("📚 For more information, see:")
    print("   REMOTION_GUIDE.md")
    print("="*60 + "\n")


if __name__ == "__main__":
    setup_local_remotion()
