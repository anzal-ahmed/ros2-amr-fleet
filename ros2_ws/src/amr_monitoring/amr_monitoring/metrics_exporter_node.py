"""
Prometheus metrics exporter: subscribes to /fleet/state and per-robot /status topics,
exposes metrics on HTTP :9101 in Prometheus text format.
Port 9100 is reserved for node_exporter; this node uses 9101.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from amr_interfaces.msg import RobotStatus, FleetState


_METRICS: dict[str, float] = {}
_METRICS_LOCK = threading.Lock()


def _fmt_label(robot_id: str) -> str:
    return f'{{robot_id="{robot_id}"}}'


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path not in ("/metrics", "/"):
            self.send_response(404)
            self.end_headers()
            return
        with _METRICS_LOCK:
            lines = list(_METRICS.items())

        body = ""
        for key, val in lines:
            body += f"{key} {val}\n"

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *args):  # silence access logs
        pass


class MetricsExporterNode(Node):
    STATE_NAMES = {
        RobotStatus.STATE_IDLE: 0,
        RobotStatus.STATE_NAVIGATING: 1,
        RobotStatus.STATE_DOCKING: 2,
        RobotStatus.STATE_CHARGING: 3,
        RobotStatus.STATE_SAFE_STOP: 4,
        RobotStatus.STATE_ERROR: 5,
    }

    def __init__(self):
        super().__init__("metrics_exporter")

        self.declare_parameter("metrics_port", 9101)
        self.declare_parameter("robot_ids", ["robot_0", "robot_1", "robot_2"])
        # robot_id (singular) used when launched per-robot from robot.launch.py
        self.declare_parameter("robot_id", "")

        port = self.get_parameter("metrics_port").value
        single_id = self.get_parameter("robot_id").value
        robot_ids: list[str] = (
            [single_id] if single_id else self.get_parameter("robot_ids").value
        )

        cb = ReentrantCallbackGroup()

        for rid in robot_ids:
            self.create_subscription(
                RobotStatus,
                f"/{rid}/status",
                self._on_robot_status,
                10,
                callback_group=cb,
            )

        self.create_subscription(
            FleetState, "/fleet/state", self._on_fleet_state, 10, callback_group=cb
        )

        server = HTTPServer(("0.0.0.0", port), MetricsHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        self.get_logger().info(f"Metrics exporter running on :{port}/metrics")

    def _on_robot_status(self, msg: RobotStatus):
        lbl = _fmt_label(msg.robot_id)
        with _METRICS_LOCK:
            _METRICS[f"amr_robot_battery_percent{lbl}"] = msg.battery_percent
            _METRICS[f"amr_robot_state{lbl}"] = float(msg.state)
            _METRICS[f"amr_robot_mission_progress{lbl}"] = msg.mission_progress
            _METRICS[f"amr_robot_pose_x{lbl}"] = msg.pose.x
            _METRICS[f"amr_robot_pose_y{lbl}"] = msg.pose.y

    def _on_fleet_state(self, msg: FleetState):
        with _METRICS_LOCK:
            _METRICS["amr_fleet_active_missions"] = float(msg.active_missions)
            _METRICS["amr_fleet_robots_available"] = float(msg.robots_available)
            _METRICS["amr_fleet_estop_active"] = float(msg.estop_active)


def main(args=None):
    rclpy.init(args=args)
    node = MetricsExporterNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
