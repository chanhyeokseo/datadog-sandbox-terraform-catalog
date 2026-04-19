# DogSTAC Benchmark Report

Benchmark of DogSTAC container resource usage during idle and EC2 deployment lifecycle.

## Test Environment

### Host Machine

| Item | Value |
|------|-------|
| Model | MacBook Pro 14-inch, Nov 2023 |
| Chip | Apple M3 Max |
| CPU Cores | 16 |
| Memory | 64 GB |
| OS | macOS 26.2 (Build 25C56) |
| Architecture | arm64 |

### Docker Desktop

| Item | Value |
|------|-------|
| Docker Engine | 29.2.0 |
| Allocated CPUs | 16 |
| Allocated Memory | 7.65 GB |

### DogSTAC Container

| Item | Value |
|------|-------|
| Image | dogstac/dogstac:1.5.2 |
| Image Size | 658 MB |
| Platform | linux/arm64 |
| Terraform | v1.7.0 |
| Python (container) | 3.11.15 |
| Resource Limits | None (unlimited) |
| Ports | 7621 (API), 7622 (MCP) |

### Benchmark Configuration

| Item | Value |
|------|-------|
| Target Resource | ec2_basic (EC2 Linux Basic) |
| Runs per Scenario | 5 |
| IDLE Duration | 30s per run |
| Stats Polling Interval | 1s |
| Cooldown Between Runs | 10s |
| Benchmark Script | Python 3.14.0, httpx + docker SDK |
| Date | 2026-04-19 (UTC) |

## Methodology

- **IDLE**: No API calls. Container stats collected for 30 seconds to establish baseline resource consumption.
- **EC2 Deploy**: Full Terraform lifecycle via API (`init` -> `plan` -> `apply`). Container stats collected during deploy steps. `destroy` is executed after stats collection as cleanup.
- Container CPU/Memory/Network are sampled every 1 second via Docker Stats API.
- Each scenario is repeated 5 times. Results are reported as **median +/- standard deviation**.
- CPU percentage is per-machine (not normalized). 100% = 1 full core. Max possible = 1600% (16 cores).

## Results

### IDLE

| Metric | Value |
|--------|-------|
| CPU Avg | 0.46% (+-0.05) |
| CPU Peak | 0.74% (+-0.80) |
| Memory Avg | 372.18 MB (+-0.13) |
| Memory Peak | 372.22 MB (+-0.11) |
| Network RX | 0.17 KB (+-3.21) |
| Network TX | 0.27 KB (+-8.01) |

#### Per-Run Detail

| Run | CPU Avg | CPU Peak | Mem Avg | Mem Peak |
|-----|---------|----------|---------|----------|
| #1 | 0.46% | 0.63% | 371.97 MB | 372.22 MB |
| #2 | 0.56% | 2.52% | 372.29 MB | 372.45 MB |
| #3 | 0.45% | 0.66% | 372.18 MB | 372.21 MB |
| #4 | 0.47% | 1.03% | 372.04 MB | 372.22 MB |
| #5 | 0.43% | 0.74% | 372.18 MB | 372.21 MB |

### EC2 Deploy (init -> plan -> apply + destroy)

| Metric | Value |
|--------|-------|
| CPU Avg | 44.84% (+-0.79) |
| CPU Peak | 194.30% (+-14.28) |
| Memory Avg | 706.56 MB (+-37.32) |
| Memory Peak | 905.15 MB (+-1.09) |
| Network RX | 210.85 KB (+-11.95) |
| Network TX | 171.74 KB (+-6.84) |

#### Step Timing

| Step | Duration | Output Size |
|------|----------|-------------|
| init | 1.96s (+-0.12) | 0.63 KB |
| plan | 4.23s (+-0.22) | 4.90 KB |
| apply | 17.96s (+-0.14) | 5.31 KB |
| destroy | 36.41s (+-5.18) | 5.87 KB |

**Total deploy time (init + plan + apply)**: 24.23s (+-0.35)

#### Per-Run Detail

| Run | CPU Avg | CPU Peak | Mem Peak | init | plan | apply | destroy |
|-----|---------|----------|----------|------|------|-------|---------|
| #1 | 44.96% | 194.30% | 905.21 MB | 2.13s | 4.23s | 17.96s | 36.87s |
| #2 | 44.79% | 202.16% | 905.15 MB | 1.96s | 4.31s | 17.91s | 27.18s |
| #3 | 44.84% | 185.40% | 903.59 MB | 2.03s | 4.13s | 18.27s | 27.21s |
| #4 | 44.79% | 178.16% | 906.39 MB | 1.91s | 4.28s | 18.04s | 36.64s |
| #5 | 46.60% | 214.70% | 904.09 MB | 1.82s | 3.76s | 17.95s | 36.41s |