import os

class Config:
    # API
    INTEGRATIONS_BASE_URL = os.getenv("INTEGRATIONS_BASE_URL", "http://localhost:8080")
    INTEGRATIONS_TOKEN = os.getenv("INTEGRATIONS_TOKEN", "changeme")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

    # Tasks
    TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT", "180"))