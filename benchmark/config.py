import os
from pathlib import Path

BACKEND_URL = os.environ.get("DOGSTAC_URL", "http://localhost:7621")
CONTAINER_NAME = os.environ.get("DOGSTAC_CONTAINER", "dogstac")
RESOURCE_ID = os.environ.get("DOGSTAC_RESOURCE", "ec2_basic")
STATS_INTERVAL_SEC = 1.0
IDLE_DURATION_SEC = 30
NUM_RUNS = 5
RESULTS_DIR = Path(__file__).parent / "results"
