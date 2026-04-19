import json
import logging
import time
from datetime import datetime, timezone

from .api_client import TerraformAPI
from .stats_collector import StatsCollector
from .config import RESOURCE_ID, IDLE_DURATION_SEC, NUM_RUNS, RESULTS_DIR

logger = logging.getLogger(__name__)


def run_idle(run_index: int) -> dict:
    logger.info("=== IDLE run %d/%d ===", run_index, NUM_RUNS)

    collector = StatsCollector(label=f"idle_{run_index}")
    collector.start()
    time.sleep(IDLE_DURATION_SEC)
    stats = collector.stop()

    return {
        "scenario": "idle",
        "run": run_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "container_stats": stats.get("summary", {}),
        "steps": [],
    }


def run_ec2_deploy(run_index: int) -> dict:
    logger.info("=== EC2 DEPLOY run %d/%d ===", run_index, NUM_RUNS)
    api = TerraformAPI()
    steps = []

    collector = StatsCollector(label=f"ec2_{run_index}")
    collector.start()

    for action_fn, name in [
        (api.init, "init"),
        (api.plan, "plan"),
        (api.apply, "apply"),
    ]:
        logger.info("Step: %s", name)
        result = action_fn(RESOURCE_ID)
        steps.append(result)
        if result["exit_code"] != 0:
            logger.error("%s failed (exit=%d), aborting run", name, result["exit_code"])
            break

    stats = collector.stop()

    logger.info("Cleanup: destroy")
    destroy_result = api.destroy(RESOURCE_ID)
    steps.append(destroy_result)

    if destroy_result["exit_code"] != 0:
        logger.warning("Destroy failed (exit=%d), manual cleanup may be needed", destroy_result["exit_code"])

    return {
        "scenario": "ec2_deploy",
        "run": run_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "container_stats": stats.get("summary", {}),
        "steps": steps,
    }


def run_all() -> dict:
    results = {"idle": [], "ec2_deploy": []}

    for i in range(1, NUM_RUNS + 1):
        results["idle"].append(run_idle(i))

    for i in range(1, NUM_RUNS + 1):
        results["ec2_deploy"].append(run_ec2_deploy(i))
        if i < NUM_RUNS:
            logger.info("Cooldown 10s before next run...")
            time.sleep(10)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"benchmark_{ts}.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to %s", path)

    return results
