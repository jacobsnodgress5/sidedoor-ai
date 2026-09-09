import os
import sys

# Ensure src in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.web.server import start_server
#starts the application server on a local port
if __name__ == "__main__":
    start_server(port=8080)
#will need to have a cloud server setup if I was to run this concurrently / expand it into a larger project
