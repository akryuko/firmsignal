import pytest
from dotenv import load_dotenv

# Load .env so tests can access environment variables
# Use a test-specific .env.test if you want isolated test config
load_dotenv()