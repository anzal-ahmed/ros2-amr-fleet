"""
Watchdog node: monitors heartbeats from all robot nodes.
If any robot misses its heartbeat deadline, broadcasts an e-stop.
Clears e-stop once all robots resume reporting.
"""
import rclpy
from rclpy.node import Node
from rclpy.time import Duration
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import Bool
from amr_interfaces.msg import RobotStatus


class WatchdogNode(Node):
    def __init__(self):
        super().__init__("watchdog")

        self.declare_parameter("robot_ids", ["robot_0", "robot_1", "robot_2"])
        self.declare_parameter("heartbeat_timeout_sec", 2.0)

        self._robot_ids: list[str] = self.get_parameter("robot_ids").value
        self._timeout = Duration(
            seconds=self.get_parameter("heartbeat_timeout_sec").value
        )

        self._last_seen: dict[str, rclpy.time.Time] = {}
        self._estop_active = False

        cb = ReentrantCallbackGroup()

        for rid in self._robot_ids:
            self.create_subscription(
                RobotStatus,
                f"/{rid}/status",
                lambda msg, r=rid: self._on_heartbeat(msg, r),
                10,
                callback_group=cb,
            )

        self._estop_pub = self.create_publisher(Bool, "/safety/estop", qos_profile=10)

        # Publish retained e-stop state at 2 Hz so late-joining nodes get it
        self.create_timer(0.5, self._check_heartbeats, callback_group=cb)

        self.get_logger().info(
            f"Watchdog started, monitoring: {self._robot_ids}, "
            f"timeout: {self.get_parameter('heartbeat_timeout_sec').value}s"
        )

    def _on_heartbeat(self, msg: RobotStatus, robot_id: str):
        self._last_seen[robot_id] = self.get_clock().now()

    def _check_heartbeats(self):
        now = self.get_clock().now()
        stale = []

        for rid in self._robot_ids:
            if rid not in self._last_seen:
                stale.append(rid)
                continue
            if now - self._last_seen[rid] > self._timeout:
                stale.append(rid)

        should_estop = len(stale) > 0

        if should_estop and not self._estop_active:
            self.get_logger().error(
                f"HEARTBEAT LOST for {stale} — broadcasting E-STOP"
            )
            self._estop_active = True

        elif not should_estop and self._estop_active:
            self.get_logger().info("All heartbeats restored — clearing E-STOP")
            self._estop_active = False

        msg = Bool()
        msg.data = self._estop_active
        self._estop_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = WatchdogNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
