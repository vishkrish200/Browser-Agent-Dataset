import sys
import os

# Add the 'src' directory to the Python path for pytest discovery
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# You can also define root-level fixtures here if needed in the future 