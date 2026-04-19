import json
import logging
import statistics

from .config import RESULTS_DIR

logger = logging.getLogger(__name__)

CONTAINER_METRICS = [
    ("CPU Avg", "cpu_avg_percent", "%"),
    ("CPU Peak", "cpu_peak_percent", "%"),
    ("Memory Avg", "memory_avg_mb", " MB"),
    ("Memory Peak", "memory_peak_mb", " MB"),
    ("Network RX", "net_rx_total_kb", " KB"),
    ("Network TX", "net_tx_total_kb", " KB"),
]

STEP_NAMES = ["init", "plan", "apply", "destroy"]


def _fmt_row(cells: list[str], widths: list[int]) -> str:
    return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"


def _render_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    col_widths = [max(len(r[i]) for r in [headers] + rows) for i in range(len(headers))]
    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    lines = [_fmt_row(headers, col_widths), sep]
    for row in rows:
        lines.append(_fmt_row(row, col_widths))
    return lines


def _agg_stat(values: list[float]) -> str:
    if not values:
        return "N/A"
    med = statistics.median(values)
    std = statistics.stdev(values) if len(values) >= 2 else 0.0
    return f"{med:.2f} (±{std:.2f})"


def generate_report(results: dict) -> str:
    lines = ["# DogSTAC Benchmark Report", ""]

    for scenario in ["idle", "ec2_deploy"]:
        runs = results.get(scenario, [])
        if not runs:
            continue

        title = "IDLE" if scenario == "idle" else "EC2 Deploy (init → plan → apply + destroy)"
        lines += [f"## {title}", f"", f"Runs: {len(runs)}", ""]

        lines.append("### Container Stats (median ± stdev)")
        lines.append("")
        headers = ["Metric", "Value"]
        rows = []
        for display, key, unit in CONTAINER_METRICS:
            values = [r["container_stats"].get(key, 0) for r in runs]
            rows.append([display, _agg_stat(values) + unit])
        lines += _render_table(headers, rows)
        lines.append("")

        if scenario == "ec2_deploy":
            lines.append("### Step Timing (median ± stdev)")
            lines.append("")
            headers = ["Step", "Duration", "Output Size"]
            rows = []
            for step_name in STEP_NAMES:
                durations = []
                sizes = []
                for r in runs:
                    for s in r.get("steps", []):
                        if s.get("action") == step_name:
                            durations.append(s.get("elapsed_sec", 0))
                            sizes.append(s.get("output_bytes", 0))
                rows.append([
                    step_name,
                    _agg_stat(durations) + "s",
                    _agg_stat([b / 1024 for b in sizes]) + " KB" if sizes else "N/A",
                ])
            lines += _render_table(headers, rows)
            lines.append("")

            total_durations = []
            for r in runs:
                deploy_steps = [s for s in r.get("steps", []) if s.get("action") in ("init", "plan", "apply")]
                total_durations.append(sum(s.get("elapsed_sec", 0) for s in deploy_steps))
            lines.append(f"**Total deploy time (init+plan+apply)**: {_agg_stat(total_durations)}s")
            lines.append("")

        lines.append("### Per-Run Detail")
        lines.append("")
        if scenario == "idle":
            headers = ["Run", "CPU Avg", "CPU Peak", "Mem Avg", "Mem Peak"]
            rows = []
            for r in runs:
                s = r["container_stats"]
                rows.append([
                    f"#{r['run']}",
                    f"{s.get('cpu_avg_percent', 0)}%",
                    f"{s.get('cpu_peak_percent', 0)}%",
                    f"{s.get('memory_avg_mb', 0)} MB",
                    f"{s.get('memory_peak_mb', 0)} MB",
                ])
        else:
            headers = ["Run", "CPU Avg", "CPU Peak", "Mem Peak", "init", "plan", "apply", "destroy"]
            rows = []
            for r in runs:
                s = r["container_stats"]
                step_times = {st["action"]: f"{st['elapsed_sec']}s" for st in r.get("steps", [])}
                rows.append([
                    f"#{r['run']}",
                    f"{s.get('cpu_avg_percent', 0)}%",
                    f"{s.get('cpu_peak_percent', 0)}%",
                    f"{s.get('memory_peak_mb', 0)} MB",
                    step_times.get("init", "N/A"),
                    step_times.get("plan", "N/A"),
                    step_times.get("apply", "N/A"),
                    step_times.get("destroy", "N/A"),
                ])
        lines += _render_table(headers, rows)
        lines.append("")

    report = "\n".join(lines)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = RESULTS_DIR / "report.md"
    with open(report_path, "w") as f:
        f.write(report)
    logger.info("Report saved to %s", report_path)

    return report


def generate_from_latest() -> str:
    files = sorted(RESULTS_DIR.glob("benchmark_*.json"), reverse=True)
    if not files:
        return "No benchmark results found."
    with open(files[0]) as f:
        return generate_report(json.load(f))
