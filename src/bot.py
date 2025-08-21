#!/usr/bin/env python3
"""
Railway compatibility wrapper for bot.py

This file exists for backward compatibility with Railway deployments
that may be looking for src/bot.py instead of the new module structure.
"""

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))

    # Import and run the actual bot
    from nescordbot.__main__ import main

    exit_code = main()
    sys.exit(exit_code)
