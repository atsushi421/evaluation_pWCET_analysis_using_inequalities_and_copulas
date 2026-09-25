#!/usr/bin/env python3
"""Queue-full stress for cb1 (experiment X2 of the IEEE Access revision).

Republishes every NDT pose on the EKF input topic --copies more times, spaced by --gap-ms,
so that the EKF pose queue (pose_smoothing_steps = 5, max_pose_queue_size = 5) stays full and
every timer_callback runs the pose-update loop at its static bound of 5 iterations. The copies
keep the header stamp of the original, which passes the EKF delay gate; the relay recognizes
its own copies by that stamp and does not copy them again. The EKF subscription keeps only the
last message (depth 1), hence the gap between copies.

    source ~/autoware/install/setup.bash
    python3 tools/pose_burst_relay.py [--copies 6] [--gap-ms 2.5]
"""
import argparse
import collections
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy

TOPIC = "/localization/pose_estimator/pose_with_covariance"


class Relay(Node):
    def __init__(self, copies: int, gap_s: float):
        super().__init__("pose_burst_relay")
        self.copies, self.gap_s = copies, gap_s
        self.seen = collections.deque(maxlen=64)
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)
        self.pub = self.create_publisher(PoseWithCovarianceStamped, TOPIC, qos)
        self.create_subscription(PoseWithCovarianceStamped, TOPIC, self.cb, qos)
        self.n = 0

    def cb(self, msg):
        stamp = (msg.header.stamp.sec, msg.header.stamp.nanosec)
        if stamp in self.seen:
            return
        self.seen.append(stamp)
        for _ in range(self.copies):
            time.sleep(self.gap_s)
            self.pub.publish(msg)
        self.n += 1
        if self.n % 100 == 0:
            self.get_logger().info(f"{self.n} poses relayed")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--copies", type=int, default=6)
    ap.add_argument("--gap-ms", type=float, default=2.5)
    a = ap.parse_args()
    rclpy.init()
    node = Relay(a.copies, a.gap_ms / 1e3)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
