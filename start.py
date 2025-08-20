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
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(current_dir, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    # Also add current directory
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    try:
        print(f"Starting NescordBot with Python {sys.version}")
        print(f"Working directory: {os.getcwd()}")
        print(f"Python path: {sys.path[:3]}...")  # Show first 3 entries

        from nescordbot.__main__ import main

        exit_code = main()
        sys.exit(exit_code)
    except ImportError as e:
        print(f"Import error: {e}")
        print("Trying alternative import path...")
        try:
            from src.nescordbot.__main__ import main

            exit_code = main()
            sys.exit(exit_code)
        except ImportError as e2:
            print(f"Alternative import also failed: {e2}")
            sys.exit(1)
    except KeyboardInterrupt:
        print("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
