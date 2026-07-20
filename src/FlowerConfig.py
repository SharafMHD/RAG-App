import logging
import os


# Flower config
port = int(os.getenv("CELERY_FLOWER_PORT", "5555"))
max_tasks = int(os.getenv("CELERY_FLOWER_MAX_TASKS", "1000"))
auto_refresh = os.getenv("CELERY_FLOWER_AUTO_REFRESH", "True") == "True"

# Authentication: only define basic_auth when a password is configured.
flower_password = os.getenv("CELERY_FLOWER_PASSWORD")
if flower_password:
    logging.info("Flower password is set. Basic auth will be enabled.")
    basic_auth = f"admin:{flower_password}"

# Avoid exposing imported modules as Tornado options.
del logging
del os
