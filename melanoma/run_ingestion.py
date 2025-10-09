#!/usr/bin/env python3
"""Startup script for the Bionocular ingestion system."""

import os
import sys
from pathlib import Path

import uvicorn

# Add the src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def main():
    """Main startup function."""
    print("🚀 Starting Bionocular Ingestion System...")

    # Check if we're in the right directory
    if not (Path.cwd() / "src").exists():
        print("❌ Error: Please run this script from the project root directory")
        print("   Current directory:", Path.cwd())
        print("   Expected to find 'src' directory here")
        sys.exit(1)

    # Load environment variables
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        print("📋 Loading environment from .env file...")
        from dotenv import load_dotenv

        load_dotenv()
    else:
        print("⚠️  No .env file found, using default configuration")

    # Configuration
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    print(f"🌐 Starting server on {host}:{port}")
    print(f"📚 API Documentation: http://{host}:{port}/docs")
    print(f"📊 Health Check: http://{host}:{port}/health")
    print("⏹️  Press Ctrl+C to stop the server")
    print()

    try:
        # Start the FastAPI server
        uvicorn.run(
            "main.binocular.python.app.api:app",
            host=host,
            port=port,
            reload=True,  # Enable auto-reload for development
            log_level="info",
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
