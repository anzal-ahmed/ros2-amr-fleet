"""
Fleet coordinator: aggregates robot statuses, allocates missions to robots
using a greedy least-loaded assignment strategy, exposes /fleet/assign_mission.
"""
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from amr_interfaces.msg import RobotStatus, FleetState
from amr_interfaces.srv import AssignMission


class FleetCoordinatorNode(Node):
    def __init__(self):
        super().__init__("fleet_coordinator")

        self.declare_parameter("robot_ids", ["robot_0", "robot_1", "robot_2"])
        self.declare_parameter("status_timeout_sec", 2.0)

        self._robot_ids: list[str] = self.get_parameter("robot_ids").value
        self._timeout: float = self.get_parameter("status_timeout_sec").value

        self._robot_statuses: dict[str, RobotStatus] = {}

        cb = ReentrantCallbackGroup()

        for rid in self._robot_ids:
            self.create_subscription(
                RobotStatus,
                f"/{rid}/status",
                lambda msg, r=rid: self._on_robot_status(msg, r),
                10,
                callback_group=cb,
            )

        self._fleet_pub = self.create_publisher(FleetState, "/fleet/state", 10)

        self._assign_srv = self.create_service(
            AssignMission,
            "/fleet/assign_mission",
            self._handle_assign_mission,
            callback_group=cb,
        )

        self.create_timer(1.0, self._publish_fleet_state, callback_group=cb)

        self.get_logger().info(
            f"Fleet coordinator started, managing: {self._robot_ids}"
        )

    def _on_robot_status(self, msg: RobotStatus, robot_id: str):
        self._robot_statuses[robot_id] = msg

    def _pick_best_robot(self, preferred_id: str = "") -> str | None:
        """Greedy: prefer explicitly requested robot, else pick IDLE robot with highest battery."""
        if preferred_id and preferred_id in self._robot_statuses:
            s = self._robot_statuses[preferred_id]
            if s.state == RobotStatus.STATE_IDLE:
                return preferred_id

        candidates = [
            (rid, s)
            for rid, s in self._robot_statuses.items()
            if s.state == RobotStatus.STATE_IDLE and s.battery_percent > 15.0
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[1].battery_percent)[0]

    def _handle_assign_mission(
        self, request: AssignMission.Request, response: AssignMission.Response
    ):
        robot_id = self._pick_best_robot(request.robot_id)
        if robot_id is None:
            response.success = False
            response.message = "No available robot with sufficient battery"
            return response

        response.success = True
        response.assigned_robot_id = robot_id
        response.message = f"Mission {request.mission_id} assigned to {robot_id}"
        self.get_logger().info(response.message)
        return response

    def _publish_fleet_state(self):
        msg = FleetState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.robots = list(self._robot_statuses.values())
        msg.active_missions = sum(
            1 for s in self._robot_statuses.values()
            if s.state == RobotStatus.STATE_NAVIGATING
        )
        msg.robots_available = sum(
            1 for s in self._robot_statuses.values()
            if s.state == RobotStatus.STATE_IDLE
        )
        msg.estop_active = any(
            s.state == RobotStatus.STATE_SAFE_STOP
            for s in self._robot_statuses.values()
        )
        self._fleet_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = FleetCoordinatorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
