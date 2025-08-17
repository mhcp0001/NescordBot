#!/usr/bin/env python3
"""
NescordBot entry point for direct module execution.

This module allows running NescordBot via 'python -m nescordbot'.
"""

import sys

from .main import main

if __name__ == "__main__":
    exit_code = main()
    if exit_code != 0:
        print(f"\n❌ Bot exited with code {exit_code}")
    else:
        print("\n✅ Bot shutdown complete")
    sys.exit(exit_code)
