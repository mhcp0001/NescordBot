#!/usr/bin/env python3
"""
Railway compatibility startup script

This script provides backward compatibility for Railway deployment
while maintaining the new module structure.
"""

if __name__ == "__main__":
    # Import and run the main module
    import os
    import sys

    # Add src directory to Python path for Railway compatibility
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

    from src.nescordbot.__main__ import main

    try:
        print(f"Starting NescordBot with Python {sys.version}")
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
