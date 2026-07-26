# Copyright (c) 2026 Cyril Moron — EPL-2.0
"""Thin ROS2 helmsman: gz pose -> Pilot -> vessel_cmd_array. The control brain is
regatta_agents.pilot.Pilot (offline-validated). Seeds a neutral setpoint on start."""

import json
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from lotusim_msgs.msg import VesselCmd, VesselCmdArray
from regatta.pilot import Pilot, opt_sheet

try:
    from gz.transport13 import Node as GzNode
    from gz.msgs10.pose_v_pb2 import Pose_V

    _HAVE_GZ = True
except ImportError:
    _HAVE_GZ = False


class Helmsman(Node):
    def __init__(self):
        super().__init__("regatta_helmsman")
        p = self.declare_parameter
        self.world = p("world", "lotusim").value
        self.vessel = p("vessel", "focus_v2").value
        wind_from = math.radians(p("wind_from_deg", 0.0).value)
        marks = [
            (p("mark_windward_x", 15.0).value, p("mark_windward_y", 0.0).value),
            (p("mark_leeward_x", 0.0).value, p("mark_leeward_y", 0.0).value),
        ]
        self.rate_hz = p("rate_hz", 30.0).value
        self.pilot = Pilot(marks=marks, wind_from=wind_from)
        self.wind_from = wind_from
        self.x = self.y = self.yaw = self.r = 0.0
        self._prev_yaw = None
        self._prev_t = None

        # TRANSIENT_LOCAL: compatible with every subscriber (gz plugin = volatile,
        # ros-tcp-endpoint = transient-local — a volatile publisher is silently
        # rejected by the endpoint: "incompatible QoS ... DURABILITY"), and late
        # joiners (Unity pressing Play mid-run) get the last command immediately.
        qos = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.pub = self.create_publisher(
            VesselCmdArray, f"/{self.world}/vessel_cmd_array", qos
        )
        self._publish(opt_sheet(0.0), 0.0)  # seed neutral so xdyn has a command

        if _HAVE_GZ:
            self.gz = GzNode()
            self.gz.subscribe(
                Pose_V, f"/world/{self.world}/dynamic_pose/info", self._on_pose
            )
        else:
            self.get_logger().error("gz-transport python unavailable; no pose feedback")
        self.create_timer(1.0 / self.rate_hz, self._control)

    def _on_pose(self, msg):
        for e in msg.pose:
            if e.name == self.vessel:
                # gz pose is ENU (x=East, y=North, z=Up); the Pilot works in NED (xdyn frame).
                self.x, self.y = (
                    e.position.y,
                    e.position.x,
                )  # NED North = ENU.y, NED East = ENU.x
                q = e.orientation
                yaw_enu = math.atan2(
                    2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)
                )  # yaw about Z-up, from East CCW
                d = math.pi / 2 - yaw_enu  # NED heading: from North CW
                yaw = math.atan2(math.sin(d), math.cos(d))
                # yaw rate by finite difference on the message header stamp (Pilot damping term)
                t = msg.header.stamp.sec + msg.header.stamp.nsec * 1e-9
                if (
                    self._prev_yaw is not None
                    and self._prev_t is not None
                    and t > self._prev_t
                ):
                    self.r = math.atan2(
                        math.sin(yaw - self._prev_yaw), math.cos(yaw - self._prev_yaw)
                    ) / (t - self._prev_t)
                self.yaw, self._prev_yaw, self._prev_t = yaw, yaw, t

    def _control(self):
        sheet, helm = self.pilot.update(self.x, self.y, self.yaw, self.r)
        self._publish(sheet, helm)

    def _publish(self, sheet, helm):
        cmd = VesselCmd()
        cmd.vessel_name = self.vessel
        cmd.cmd_string = json.dumps({"mainsail(sheet)": sheet, "rudder(helm)": helm})
        arr = VesselCmdArray()
        arr.cmds = [cmd]
        self.pub.publish(arr)


def main():
    rclpy.init()
    try:
        rclpy.spin(Helmsman())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
