# ROS2 AMR Fleet System

Production-grade distributed Autonomous Mobile Robot (AMR) fleet running on AWS, built as a portfolio project targeting German robotics and automation engineering roles.

## Architecture

```
                        AWS eu-central-1 (Frankfurt)
                        VPC 10.0.0.0/16
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   robot-0    │  │   robot-1    │  │   robot-2    │     │
│  │  t3.small    │  │  t3.small    │  │  t3.small    │     │
│  │  10.0.1.68   │  │  10.0.2.111  │  │  10.0.1.94   │     │
│  │              │  │              │  │              │     │
│  │ amr_robot_   │  │ amr_robot_   │  │ amr_robot_   │     │
│  │ core         │  │ core         │  │ core         │     │
│  │ node_export  │  │ node_export  │  │ node_export  │     │
│  │ :9100        │  │ :9100        │  │ :9100        │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │  CycloneDDS UDP 7400-7500 (unicast)│             │
│         └─────────────────┴──────────────────┘             │
│                            │                               │
│                   ┌────────▼────────┐                      │
│                   │   monitoring    │                      │
│                   │   t3.small      │                      │
│                   │   10.0.1.175    │                      │
│                   │                 │                      │
│                   │ fleet_coord     │                      │
│                   │ watchdog        │                      │
│                   │ Prometheus :9090│                      │
│                   │ Grafana    :3000│                      │
│                   └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
         │
         │  GitHub Actions (OIDC — no long-lived keys)
         ▼
  Terraform plan on PR → apply on merge to main
```

## Tech Stack

| Layer | Technology |
|---|---|
| Robotics middleware | ROS2 Humble Hawksbill |
| DDS transport | CycloneDDS (unicast, multicast disabled for AWS VPC) |
| Cloud infra | AWS eu-central-1 — EC2, VPC, IAM, S3, SSM Fleet Manager |
| IaC | Terraform v1.5+ with S3 remote state + native locking |
| CI/CD | GitHub Actions + AWS OIDC (no stored credentials) |
| Config management | Ansible 2.14 |
| Monitoring | Prometheus v2.51.2 + Grafana v10.4.2 |
| OS | Ubuntu 22.04 (Jammy) on all nodes |
| Container runtime | Docker + docker-compose (for local simulation) |

## Repository Structure

```
ros2-amr-fleet/
├── terraform/                  # AWS infrastructure
│   ├── main.tf                 # EC2, IAM, OIDC, security groups
│   ├── modules/
│   │   ├── vpc/                # VPC, subnets, IGW, route tables
│   │   ├── robot-node/         # Robot EC2 instances (count-based)
│   │   └── monitoring-node/    # Monitoring EC2 instance
│   └── backend.tf              # S3 remote state, native locking
│
├── ros2_ws/src/                # ROS2 workspace
│   ├── amr_interfaces/         # Custom msg/srv/action definitions
│   ├── amr_robot_core/         # Per-robot state machine + action server
│   ├── amr_fleet_coordinator/  # Mission allocator + fleet state
│   ├── amr_safety/             # Watchdog + e-stop manager
│   ├── amr_monitoring/         # ROS2 → Prometheus metrics bridge
│   └── amr_bringup/            # Launch files + CycloneDDS config + Nav2 params
│
├── ansible/                    # Monitoring stack deployment
│   ├── site.yml                # Top-level playbook
│   ├── inventory/hosts.ini     # EC2 IPs (public SSH, private scrape)
│   └── roles/
│       ├── node_exporter/      # System metrics on robot nodes
│       ├── prometheus/         # Scrapes node_exporter + ROS2 metrics
│       └── grafana/            # Dashboard + provisioned datasource
│
├── docker/                     # Container deployment
│   ├── Dockerfile.robot        # Robot node image (ros:humble-base)
│   ├── Dockerfile.coordinator  # Fleet coordinator image
│   └── docker-compose.yml      # Local full-fleet simulation
│
└── .github/workflows/
    ├── terraform-plan.yml      # Runs on PR — posts plan as comment
    └── terraform-apply.yml     # Runs on merge to main — applies infra
```

## ROS2 Packages

### `amr_interfaces`
Custom ROS2 interface definitions. All other packages depend on this.

| Type | Name | Purpose |
|---|---|---|
| msg | `RobotStatus` | Per-robot state, battery, pose, mission progress |
| msg | `FleetState` | Aggregated view of all robots |
| srv | `AssignMission` | Request mission allocation from coordinator |
| action | `NavigateToGoal` | Goal + feedback + result for navigation |

### `amr_robot_core`
Runs on each robot node. State machine driven by action server calls.

```
IDLE ──► NAVIGATING ──► DOCKING ──► IDLE
           │                          ▲
           ▼                          │
        SAFE_STOP ──── (estop clear) ─┘
```
- Publishes `/{robot_id}/status` at 2 Hz with heartbeat timestamp
- Accepts `/{robot_id}/navigate` action goals
- Simulates battery drain (navigating) and charge (docked)
- Immediately transitions to `SAFE_STOP` on `/safety/estop`

### `amr_fleet_coordinator`
Runs on the monitoring node.
- Subscribes to all robot status topics
- Assigns missions to the highest-battery available robot (greedy allocator)
- Publishes `/fleet/state` at 1 Hz

### `amr_safety`
- **Watchdog**: monitors heartbeats from all robots with 2 s timeout. Broadcasts `True` on `/safety/estop` if any robot goes silent — matching ISO 10218 safe-state requirements.
- Clears e-stop automatically when all robots resume reporting.

### `amr_monitoring`
- Subscribes to all fleet and robot topics
- Exposes Prometheus metrics at `:9101/metrics`
- Metrics: `amr_robot_battery_percent`, `amr_robot_state`, `amr_robot_mission_progress`, `amr_fleet_active_missions`, `amr_fleet_estop_active`

### `amr_bringup`
- `robot.launch.py` — launches `robot_node` + `metrics_exporter` for one robot
- `fleet.launch.py` — launches coordinator, watchdog, fleet metrics exporter
- `config/cyclonedds.xml` — unicast peer list for AWS VPC (multicast not routable)
- `config/nav2_params.yaml` — Nav2 tuned for t3.small (2 GB RAM)

## Infrastructure

### Prerequisites

```bash
# AWS CLI configured, SSH key generated
aws configure
ssh-keygen -t ed25519 -f ~/.ssh/ros2_fleet_key

# Bootstrap S3 state bucket (run once)
bash terraform/bootstrap.sh
```

### Deploy

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Resources created: VPC, 2 public subnets (eu-central-1a/b), internet gateway, 3 robot EC2 nodes, 1 monitoring EC2 node, IAM OIDC provider for GitHub Actions, SSM instance profile for Fleet Manager.

### Tear down

```bash
terraform destroy
```

## Monitoring Deployment

```bash
cd ansible

# Deploy node_exporter on robots + Prometheus + Grafana on monitoring node
ansible-playbook site.yml

# Re-run safely at any time (idempotent)
ansible-playbook site.yml
```

**Grafana:** http://52.57.14.33:3000 — login `admin`  
**Prometheus:** http://52.57.14.33:9090

The "ROS2 AMR Fleet" dashboard loads automatically. Panels:
- Fleet overview: active missions, robots available, e-stop status
- Per-robot: battery %, state (IDLE/NAVIGATING/DOCKING/CHARGING/SAFE_STOP)
- System (node_exporter): CPU, memory, disk, network RX/TX per node

## CI/CD

GitHub Actions uses AWS OIDC — no `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` stored anywhere.

| Trigger | Workflow | Action |
|---|---|---|
| Pull request to `main` | `terraform-plan.yml` | Runs `terraform plan`, posts output as PR comment |
| Merge to `main` | `terraform-apply.yml` | Runs `terraform apply -auto-approve` in `production` environment |

All third-party actions are pinned to commit SHAs (not version tags) to prevent supply chain attacks.

## Local Simulation

Run the full fleet on a single machine without AWS:

```bash
# Build and start all containers
docker compose -f docker/docker-compose.yml up --build

# Check robot statuses
ros2 topic echo /robot_0/status

# Assign a mission manually
ros2 service call /fleet/assign_mission amr_interfaces/srv/AssignMission \
  "{robot_id: '', goal_pose: {x: 5.0, y: 3.0, theta: 0.0}, mission_id: 'test-01', priority: 1.0}"

# View fleet state
ros2 topic echo /fleet/state

# Trigger e-stop
ros2 topic pub /safety/estop std_msgs/msg/Bool "{data: true}" --once
```

## SSH Access

```bash
# Robot nodes
ssh -i ~/.ssh/ros2_fleet_key ubuntu@52.58.250.240   # robot-0
ssh -i ~/.ssh/ros2_fleet_key ubuntu@51.102.250.20   # robot-1
ssh -i ~/.ssh/ros2_fleet_key ubuntu@54.93.81.91     # robot-2

# Monitoring node
ssh -i ~/.ssh/ros2_fleet_key ubuntu@52.57.14.33
```

All nodes are also accessible via AWS SSM Fleet Manager (no SSH port required).

## Key Design Decisions

**CycloneDDS unicast over VPC** — AWS VPC does not route multicast traffic. The `cyclonedds.xml` config lists all node private IPs explicitly as peers, enabling DDS discovery across subnets without a multicast workaround.

**OIDC over long-lived AWS keys** — GitHub Actions assumes an IAM role via OIDC web identity federation. The trust policy is scoped to `repo:anzal-ahmed/ros2-amr-fleet:*`, so no other repo can assume it even with the same OIDC provider.

**Watchdog triggers soft stop, not hard kill** — On heartbeat timeout, the watchdog publishes on `/safety/estop` and each robot transitions to `STATE_SAFE_STOP` (stops accepting new goals, decelerates). This matches ISO 10218-1 Category 1 stop behaviour rather than a Category 0 power cut.

**Prometheus scrapes two job types per robot** — `robot_node_exporter` (OS metrics on :9100) and `ros2_fleet_metrics` (application metrics on :9101). This separates infrastructure observability from application observability in Grafana.

**S3 native locking** — Uses `use_lockfile = true` (Terraform 1.5+) instead of the deprecated `dynamodb_table` parameter. No DynamoDB table required for state locking.

## Author

Anzal Ahmed — [github.com/anzal-ahmed](https://github.com/anzal-ahmed)
