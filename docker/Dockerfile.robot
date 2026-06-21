FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-nav2-bringup \
    ros-humble-nav2-msgs \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws

COPY ros2_ws/src ./src

RUN . /opt/ros/humble/setup.sh && \
    colcon build \
      --packages-select amr_interfaces amr_robot_core amr_monitoring amr_bringup \
      --cmake-args -DCMAKE_BUILD_TYPE=Release \
    && rm -rf build log

COPY docker/entrypoint.robot.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 9101

ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "amr_bringup", "robot.launch.py"]
