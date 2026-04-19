# DogSTAC Benchmark Report

## IDLE

Runs: 5

### Container Stats (median ± stdev)

| Metric      | Value             |
| ----------- | ----------------- |
| CPU Avg     | 0.46 (±0.05)%     |
| CPU Peak    | 0.74 (±0.80)%     |
| Memory Avg  | 372.18 (±0.13) MB |
| Memory Peak | 372.22 (±0.11) MB |
| Network RX  | 0.17 (±3.21) KB   |
| Network TX  | 0.27 (±8.01) KB   |

### Per-Run Detail

| Run | CPU Avg | CPU Peak | Mem Avg   | Mem Peak  |
| --- | ------- | -------- | --------- | --------- |
| #1  | 0.46%   | 0.63%    | 371.97 MB | 372.22 MB |
| #2  | 0.56%   | 2.52%    | 372.29 MB | 372.45 MB |
| #3  | 0.45%   | 0.66%    | 372.18 MB | 372.21 MB |
| #4  | 0.47%   | 1.03%    | 372.04 MB | 372.22 MB |
| #5  | 0.43%   | 0.74%    | 372.18 MB | 372.21 MB |

## EC2 Deploy (init → plan → apply + destroy)

Runs: 5

### Container Stats (median ± stdev)

| Metric      | Value              |
| ----------- | ------------------ |
| CPU Avg     | 44.84 (±0.79)%     |
| CPU Peak    | 194.30 (±14.28)%   |
| Memory Avg  | 706.56 (±37.32) MB |
| Memory Peak | 905.15 (±1.09) MB  |
| Network RX  | 210.85 (±11.95) KB |
| Network TX  | 171.74 (±6.84) KB  |

### Step Timing (median ± stdev)

| Step    | Duration       | Output Size     |
| ------- | -------------- | --------------- |
| init    | 1.96 (±0.12)s  | 0.63 (±0.00) KB |
| plan    | 4.23 (±0.22)s  | 4.90 (±0.00) KB |
| apply   | 17.96 (±0.14)s | 5.31 (±0.00) KB |
| destroy | 36.41 (±5.18)s | 5.87 (±0.08) KB |

**Total deploy time (init+plan+apply)**: 24.23 (±0.35)s

### Per-Run Detail

| Run | CPU Avg | CPU Peak | Mem Peak  | init  | plan  | apply  | destroy |
| --- | ------- | -------- | --------- | ----- | ----- | ------ | ------- |
| #1  | 44.96%  | 194.3%   | 905.21 MB | 2.13s | 4.23s | 17.96s | 36.87s  |
| #2  | 44.79%  | 202.16%  | 905.15 MB | 1.96s | 4.31s | 17.91s | 27.18s  |
| #3  | 44.84%  | 185.4%   | 903.59 MB | 2.03s | 4.13s | 18.27s | 27.21s  |
| #4  | 44.79%  | 178.16%  | 906.39 MB | 1.91s | 4.28s | 18.04s | 36.64s  |
| #5  | 46.6%   | 214.7%   | 904.09 MB | 1.82s | 3.76s | 17.95s | 36.41s  |
