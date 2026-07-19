import logging
from dotenv import dotenv_values

config = dotenv_values(".env")

# flower config
port = int(config.get("CELERY_FLOWER_PORT", 5555))
max_tasks = int(config.get("CELERY_FLOWER_MAX_TASKS", 1000)) 
auto_refresh = config.get("CELERY_FLOWER_AUTO_REFRESH", "True") == "True"

# authentication
flower_password = config.get("CELERY_FLOWER_PASSWORD")

if flower_password:
    # Use standard logging directly
    logging.info("Flower password is set. Basic auth will be enabled.")
    basic_auth = f"admin:{flower_password}"
else:
    basic_auth = None

# CLEANUP: Remove imported references so Tornado does not scan them as configuration options
del dotenv_values
del config
del logging
