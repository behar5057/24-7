import sys
import os

project_dir = '/home/perfctex/chattelo_bot'
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from bot import app as application
print("Chattelo Bot - WSGI loaded!")
