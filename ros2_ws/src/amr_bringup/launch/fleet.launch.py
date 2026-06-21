"""
Fleet-level launch: coordinator + watchdog + safety nodes.
Run on the monitoring node after all robot nodes are up.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

ROBOT_IDS = ["robot_0", "robot_1", "robot_2"]


def generate_launch_description():
    cyclone_config = PathJoinSubstitution(
        [FindPackageShare("amr_bringup"), "config", "cyclonedds.xml"]
    )

    return LaunchDescription([
        SetEnvironmentVariable("CYCLONEDDS_URI", ["file://", cyclone_config]),
        SetEnvironmentVariable("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp"),

        Node(
            package="amr_fleet_coordinator",
            executable="fleet_coordinator",
            name="fleet_coordinator",
            parameters=[{
                "robot_ids": ROBOT_IDS,
                "status_timeout_sec": 2.0,
            }],
            output="screen",
        ),

        Node(
            package="amr_safety",
            executable="watchdog",
            name="watchdog",
            parameters=[{
                "robot_ids": ROBOT_IDS,
                "heartbeat_timeout_sec": 2.0,
            }],
            output="screen",
        ),

        Node(
            package="amr_monitoring",
            executable="metrics_exporter",
            name="fleet_metrics_exporter",
            parameters=[{
                "metrics_port": 9101,
                "robot_ids": ROBOT_IDS,
            }],
            output="screen",
        ),
    ])
