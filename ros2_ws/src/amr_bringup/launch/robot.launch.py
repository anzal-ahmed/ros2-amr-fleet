"""
Launch file for a single robot node.
Usage: ros2 launch amr_bringup robot.launch.py robot_id:=robot_0
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    robot_id_arg = DeclareLaunchArgument(
        "robot_id",
        default_value="robot_0",
        description="Unique robot identifier",
    )

    cyclone_config = PathJoinSubstitution(
        [FindPackageShare("amr_bringup"), "config", "cyclonedds.xml"]
    )

    return LaunchDescription([
        robot_id_arg,
        SetEnvironmentVariable("CYCLONEDDS_URI", ["file://", cyclone_config]),
        SetEnvironmentVariable("RMW_IMPLEMENTATION", "rmw_cyclonedds_cpp"),
        Node(
            package="amr_robot_core",
            executable="robot_node",
            name=LaunchConfiguration("robot_id"),
            namespace=LaunchConfiguration("robot_id"),
            parameters=[{
                "robot_id": LaunchConfiguration("robot_id"),
                "battery_drain_rate": 0.05,
                "battery_charge_rate": 0.2,
            }],
            remappings=[
                ("/tf", "tf"),
                ("/tf_static", "tf_static"),
            ],
            output="screen",
        ),
        Node(
            package="amr_monitoring",
            executable="metrics_exporter",
            name="metrics_exporter",
            parameters=[{
                "metrics_port": 9101,
                "robot_ids": [LaunchConfiguration("robot_id")],
            }],
            output="screen",
        ),
    ])
