"""Double-click entry point (pythonw: no console window). Also what the .exe is built from."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tamp.app import main  # noqa: E402

sys.exit(main())
