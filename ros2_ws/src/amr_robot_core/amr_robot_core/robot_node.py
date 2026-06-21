"""
Per-robot node: publishes status, accepts mission goals via action server,
drives a state machine (IDLE → NAVIGATING → DOCKING → CHARGING).
"""
import math
import time
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from std_msgs.msg import Bool
from geometry_msgs.msg import Pose2D
from amr_interfaces.msg import RobotStatus
from amr_interfaces.action import NavigateToGoal


class RobotNode(Node):
    STATE_IDLE = RobotStatus.STATE_IDLE
    STATE_NAVIGATING = RobotStatus.STATE_NAVIGATING
    STATE_DOCKING = RobotStatus.STATE_DOCKING
    STATE_CHARGING = RobotStatus.STATE_CHARGING
    STATE_SAFE_STOP = RobotStatus.STATE_SAFE_STOP
    STATE_ERROR = RobotStatus.STATE_ERROR

    def __init__(self):
        super().__init__("robot_node")

        self.declare_parameter("robot_id", "robot_0")
        self.declare_parameter("battery_drain_rate", 0.05)  # % per second while navigating
        self.declare_parameter("battery_charge_rate", 0.2)

        self._robot_id = self.get_parameter("robot_id").value
        self._battery_drain = self.get_parameter("battery_drain_rate").value
        self._battery_charge = self.get_parameter("battery_charge_rate").value

        self._state = self.STATE_IDLE
        self._battery = 100.0
        self._pose = Pose2D()
        self._mission_id = ""
        self._mission_progress = 0.0
        self._estop = False

        cb = ReentrantCallbackGroup()

        self._status_pub = self.create_publisher(
            RobotStatus, f"/{self._robot_id}/status", 10
        )

        self._estop_sub = self.create_subscription(
            Bool, "/safety/estop", self._on_estop, 10, callback_group=cb
        )

        self._action_server = ActionServer(
            self,
            NavigateToGoal,
            f"/{self._robot_id}/navigate",
            execute_callback=self._execute_navigation,
            goal_callback=self._goal_callback,
            cancel_callback=self._cancel_callback,
            callback_group=cb,
        )

        self._status_timer = self.create_timer(0.5, self._publish_status, callback_group=cb)
        self._sim_timer = self.create_timer(1.0, self._simulate_battery, callback_group=cb)

        self.get_logger().info(f"Robot node started: {self._robot_id}")

    def _goal_callback(self, goal_request):
        if self._estop:
            self.get_logger().warn("Rejecting goal: e-stop active")
            return GoalResponse.REJECT
        if self._state not in (self.STATE_IDLE, self.STATE_NAVIGATING):
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _cancel_callback(self, goal_handle):
        self.get_logger().info("Navigation cancel requested")
        return CancelResponse.ACCEPT

    async def _execute_navigation(self, goal_handle):
        target = goal_handle.request.target_pose
        self._mission_id = goal_handle.request.mission_id
        self._state = self.STATE_NAVIGATING
        self._mission_progress = 0.0

        total_dist = math.hypot(
            target.x - self._pose.x, target.y - self._pose.y
        )
        speed = max(goal_handle.request.max_speed, 0.1)
        steps = max(int(total_dist / speed * 2), 10)

        feedback = NavigateToGoal.Feedback()

        for i in range(steps):
            if goal_handle.is_cancel_requested or self._estop:
                goal_handle.canceled()
                self._state = self.STATE_IDLE if not self._estop else self.STATE_SAFE_STOP
                return NavigateToGoal.Result(success=False, message="Cancelled")

            frac = (i + 1) / steps
            self._pose.x += (target.x - self._pose.x) / (steps - i)
            self._pose.y += (target.y - self._pose.y) / (steps - i)
            self._mission_progress = frac * 100.0

            feedback.current_pose = self._pose
            feedback.distance_remaining_m = total_dist * (1.0 - frac)
            feedback.eta_seconds = feedback.distance_remaining_m / speed
            goal_handle.publish_feedback(feedback)

            time.sleep(0.5)

        self._state = self.STATE_DOCKING
        time.sleep(1.0)
        self._state = self.STATE_IDLE
        self._mission_id = ""
        self._mission_progress = 0.0

        goal_handle.succeed()
        result = NavigateToGoal.Result()
        result.success = True
        result.total_distance_m = total_dist
        result.message = "Goal reached"
        return result

    def _on_estop(self, msg: Bool):
        if msg.data and not self._estop:
            self.get_logger().error("E-STOP received — entering SAFE_STOP")
            self._estop = True
            self._state = self.STATE_SAFE_STOP
        elif not msg.data and self._estop:
            self.get_logger().info("E-STOP cleared")
            self._estop = False
            self._state = self.STATE_IDLE

    def _simulate_battery(self):
        if self._state == self.STATE_NAVIGATING:
            self._battery = max(0.0, self._battery - self._battery_drain)
        elif self._state == self.STATE_CHARGING:
            self._battery = min(100.0, self._battery + self._battery_charge)
        if self._battery < 10.0 and self._state == self.STATE_IDLE:
            self._state = self.STATE_CHARGING

    def _publish_status(self):
        msg = RobotStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.robot_id = self._robot_id
        msg.state = self._state
        msg.battery_percent = self._battery
        msg.pose = self._pose
        msg.mission_id = self._mission_id
        msg.mission_progress = self._mission_progress
        msg.last_heartbeat = self.get_clock().now().to_msg()
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RobotNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
