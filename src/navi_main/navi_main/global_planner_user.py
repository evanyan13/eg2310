#!/usr/bin/env python3

import rclpy
from geometry_msgs.msg import PoseStamped
from .global_planner_package.global_path_planner import GlobalPathPlanner

def main():
    rclpy.init()
    node = GlobalPathPlanner()

    print("Waiting for map to be loaded...")
    node.wait_for_map()

    while rclpy.ok():
        try:
            pose_x = float(input('Input X coordinate: '))
            pose_y = float(input('Input Y coordinate: '))
            goal = generate_posestamped(node, pose_x, pose_y)

            if node.send_goal(goal):
                node.get_logger().info('main_user: Goal sent successfully')
            else:
                node.get_logger().warn('main_user: Goal sent successfully')
        except Exception as e:
            print(f"Error: {e}")

    rclpy.shutdown()

def generate_posestamped(node, x, y):
    goal = PoseStamped()
    goal.header.stamp = node.get_clock().now().to_msg()
    goal.header.frame_id = "map"
    goal.pose.position.x = x
    goal.pose.position.y = y
    goal.pose.orientation.w = 1.0
    return goal

if __name__ == '__main__':
    main()