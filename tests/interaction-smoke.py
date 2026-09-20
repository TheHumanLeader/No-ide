"""Compatibility entry point for the current frontend interaction suite."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('interaction-v2.py')),run_name='__main__')
