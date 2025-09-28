import sys
import os

# Add your project directory to the Python path
project_dir = '/home/perfctex/chattelo_bot'
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment variables
os.environ['GIT_COMMIT'] = 'deployed-from-github'

# Import your Flask app
from bot import app as application

print("Chattelo Bot deployed from GitHub - WSGI configuration loaded!")
