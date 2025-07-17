#!/usr/bin/env python3
"""
Nescordbot launcher script
"""

import sys
import os

# srcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# bot.pyのmain関数を実行
from bot import main

if __name__ == '__main__':
    print("🚀 Nescordbot を起動しています...")
    main()
