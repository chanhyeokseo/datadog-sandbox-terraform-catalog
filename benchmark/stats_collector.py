import json
import logging
import threading
import time
from datetime import datetime, timezone

import docker

from .config import CONTAINER_NAME, STATS_INTERVAL_SEC, RESULTS_DIR

logger = logging.getLogger(__name__)


def _calc_cpu_percent(stats: dict) -> float:
    cpu = stats["cpu_stats"]
    precpu = stats["precpu_stats"]
    cpu_delta = cpu["cpu_usage"]["total_usage"] - precpu["cpu_usage"]["total_usage"]
    system_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    if system_delta <= 0 or cpu_delta < 0:
        return 0.0
    online_cpus = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage", [1]))
    return (cpu_delta / system_delta) * online_cpus * 100.0


def _parse_memory(stats: dict) -> dict:
    mem = stats.get("memory_stats", {})
    usage = mem.get("usage", 0)
    cache = mem.get("stats", {}).get("cache", 0)
    return {
        "usage_mb": round((usage - cache) / (1024 * 1024), 2),
        "limit_mb": round(mem.get("limit", 0) / (1024 * 1024), 2),
    }


def _parse_network(stats: dict) -> dict:
    networks = stats.get("networks", {})
    rx_bytes = sum(v.get("rx_bytes", 0) for v in networks.values())
    tx_bytes = sum(v.get("tx_bytes", 0) for v in networks.values())
    return {"rx_bytes": rx_bytes, "tx_bytes": tx_bytes}


class StatsCollector:
    def __init__(self, label: str):
        self._label = label
        self._client = docker.from_env()
        self._container = self._client.containers.get(CONTAINER_NAME)
        self._samples: list[dict] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._start_time: datetime | None = None
        self._stop_time: datetime | None = None

    def start(self):
        self._running = True
        self._start_time = datetime.now(timezone.utc)
        self._samples.clear()
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        logger.info("Stats collection started (label=%s, container=%s)", self._label, CONTAINER_NAME)

    def stop(self) -> dict:
        self._running = False
        self._stop_time = datetime.now(timezone.utc)
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Stats collection stopped (%d samples)", len(self._samples))
        return self._build_result()

    def _collect_loop(self):
        net_baseline = None
        for stats in self._container.stats(stream=True, decode=True):
            if not self._running:
                break
            cpu_pct = _calc_cpu_percent(stats)
            mem = _parse_memory(stats)
            net = _parse_network(stats)

            if net_baseline is None:
                net_baseline = {"rx_bytes": net["rx_bytes"], "tx_bytes": net["tx_bytes"]}

            self._samples.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "cpu_percent": round(cpu_pct, 2),
                "memory_mb": mem["usage_mb"],
                "memory_limit_mb": mem["limit_mb"],
                "net_rx_bytes": net["rx_bytes"] - net_baseline["rx_bytes"],
                "net_tx_bytes": net["tx_bytes"] - net_baseline["tx_bytes"],
            })
            time.sleep(max(0, STATS_INTERVAL_SEC - 0.05))

    def _build_result(self) -> dict:
        if not self._samples:
            return {"label": self._label, "samples": [], "summary": {}}

        cpus = [s["cpu_percent"] for s in self._samples]
        mems = [s["memory_mb"] for s in self._samples]

        summary = {
            "duration_sec": round((self._stop_time - self._start_time).total_seconds(), 2),
            "sample_count": len(self._samples),
            "cpu_avg_percent": round(sum(cpus) / len(cpus), 2),
            "cpu_peak_percent": round(max(cpus), 2),
            "memory_avg_mb": round(sum(mems) / len(mems), 2),
            "memory_peak_mb": round(max(mems), 2),
            "net_rx_total_kb": round(self._samples[-1]["net_rx_bytes"] / 1024, 2),
            "net_tx_total_kb": round(self._samples[-1]["net_tx_bytes"] / 1024, 2),
        }

        return {
            "label": self._label,
            "start": self._start_time.isoformat(),
            "stop": self._stop_time.isoformat(),
            "summary": summary,
            "samples": self._samples,
        }

    def save(self, result: dict) -> str:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = RESULTS_DIR / f"{self._label}_{ts}.json"
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
        logger.info("Results saved to %s", path)
        return str(path)
