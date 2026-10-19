#!/usr/bin/env python3
"""Explicit import path for launchd's independent Python environment."""
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
runpy.run_module("moco", run_name="__main__")
