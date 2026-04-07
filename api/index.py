import sys
import os

# Ensure the root directory is on the path so bot.py can be imported correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import app
