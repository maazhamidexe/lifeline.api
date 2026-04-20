import sys
from pathlib import Path

# Ensure tests can import main.py and app/* regardless of runner cwd.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
