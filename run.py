#!/usr/bin/env python3
"""
NYC Boulevard Traffic Dashboard
─────────────────────────────────
Run:   python3 run.py
Open:  http://localhost:8765
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from server import run
if __name__ == "__main__":
    run()
