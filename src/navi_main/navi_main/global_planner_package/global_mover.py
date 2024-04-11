import rclpy
import math
import threading
import numpy as np
from math import atan2, pi
from rclpy.node import Node
from rclpy.duration import Duration
from rclpy.qos import qos_profile_sensor_data
import rclpy.logging as log
from geometry_msgs.msg import Twist
from nav_msgs.msg import Path
from sensor_msgs.msg import LaserScan

MOVE_TOL = 0.1
LINEAR_VEL = 0.1
ANGULAR_VEL = 0.05
OBSTACLE_THRESHOLD = 0.20 # metres
PATH_REFRESH = 5  # seconds
LOOKAHEAD_DIST = 1.0
logger = log.get_logger("global_mover")

class GlobalMover(Node):
    def __init__(self, planner):
        super().__init__('global_mover')
        self.planner = planner
        self.robot_pos = None
        self.current_path = []
        self.current_goal_index = 0
        self.obstacle_detected = False

        self.path_subscriber = self.create_subscription(Path, 'path', self.path_callback, qos_profile_sensor_data)
        self.scan_subscriber = self.create_subscription(LaserScan, 'scan', self.scan_callback, qos_profile_sensor_data)

        self.velocity_publisher = self.create_publisher(Twist, 'cmd_vel', 10)

        # Timer for following the path
        self.follow_path_timer = self.create_timer(1, self.follow_path)

    def path_callback(self, path_msg: Path):
        """
        Processing the incoming path and initiating navigation.
        """
        self.current_path = [(pose.pose.position.x, pose.pose.position.y) for pose in path_msg.poses]
        self.current_goal_index = 0
        # logger.info(f"path_callback: Received path with {len(self.current_path)} points.")

    def scan_callback(self, scan_msg: LaserScan):
        """ 
        Processes laser scan data to detect obstacles
        """
        if np.nanmin(scan_msg.ranges) < OBSTACLE_THRESHOLD:
            self.obstacle_detected = True
        else:
            self.obstacle_detected = False

    def follow_path(self):
        """
        Follows the given path by moving to each point sequentially.
        """
        if not self.current_path:
            return
        
        if self.obstacle_detected:
            logger.info(f"Obstacle detected, adjusting position")
            self.adjust_obstacle()
            return

        if self.current_goal_index >= len(self.current_path):
            logger.info("End of path reached")
            self.stop_moving()
            self.reset_path()
            return
        else:
            current_goal = self.current_path[self.current_goal_index]
            self.move_to_point(current_goal)
        
    def move_to_point(self, goal):
        # if self.current_goal_index >= len(self.current_path):
        #     self.stop_moving()  # Stop if path is complete
        #     return
        
        # lookahead_point = self.get_lookahead_point(LOOKAHEAD_DIST)

        # if lookahead_point is None:
        #     logger.info("No valid lookahead point found, stopping")
        #     self.stop_moving()
        #     return
    
        # istance_to_lookahead = math.hypot(lookahead_point[0] - self.robot_pos.x, lookahead_point[1] - self.robot_pos.y)
        # target_heading = math.atan2(lookahead_point[1] - self.robot_pos.y, lookahead_point[0] - self.robot_pos.x)
        # heading_error = self.normalise_angle(target_heading - self.robot_pos.theta)

        # linear = LINEAR_VEL
        # angular = ANGULAR_VEL * heading_error

        # logger.info(f"Moving to lookahead point {lookahead_point}")
        # self.send_velocity(linear, angular)
        # Control the robot to move to the next point in the path
        distance_to_goal = math.hypot(goal[0] - self.robot_pos.x, goal[1] - self.robot_pos.y)
        target_heading = math.atan2(goal[1] - self.robot_pos.y, goal[0] - self.robot_pos.x)
        heading_error = self.normalise_angle(target_heading - self.robot_pos.theta)

        if distance_to_goal < MOVE_TOL:
            self.current_goal_index += 1
            if self.current_goal_index >= len(self.current_path):
                self.stop_moving()  # Stop if path is complete
                return

        linear = LINEAR_VEL
        angular = ANGULAR_VEL * heading_error

        # Moderate linear velocity based on how aligned we are to the goal direction
        # This ensures the robot slows down if it needs to turn sharply
        linear = LINEAR_VEL * max(0, 1 - 2 * abs(heading_error) / pi)

        logger.info(f"Moving to point {goal}")
        self.send_velocity(linear, angular)

    def adjust_obstacle(self):
        self.stop_moving()
        # Rotate towards the next point or away from obstacle
        if self.current_goal_index < len(self.current_path):
            current_goal = self.current_path[self.current_goal_index]
            target_heading = math.atan2(current_goal[1] - self.robot_pos.y, current_goal[0] - self.robot_pos.x)
            heading_error = self.normalise_angle(target_heading - self.robot_pos.theta)
            
            # Rotate in the direction of heading error
            angular_speed = -ANGULAR_VEL * 2 if heading_error > 0 else ANGULAR_VEL * 2
            self.send_velocity(0.0, angular_speed)
            logger.info(f"Published rotation: {angular_speed}")
            # Allow some time for rotation, then recheck or resume movement
            threading.Timer(10.0, self.check_obstacle_clear).start() # seconds
    
    def check_obstacle_clear(self):
        self.stop_moving()
        # Check if the obstacle is still detected
        if not self.obstacle_detected:
            logger.info("Obstacle cleared, resuming path")
            threading.Timer(5.0, self.follow_path).start()
        else:
            logger.info("Obstacle still detected, checking further")
            self.send_velocity(LINEAR_VEL, 0.0)
            threading.Timer(5.0, self.adjust_obstacle).start()
    
    def send_velocity(self, linear, angular):
        twist = Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        self.velocity_publisher.publish(twist)
    
    def reset_path(self):
        self.planner.plan_path() 
        # rclpy.spin_once(self.planner, timeout_sec=3.0)

    def stop_moving(self):
        self.send_velocity(0.0, 0.0)
        self.planner.fail()
    
    def normalise_angle(self, angle):
        # Normalize the angle to be between -pi and pi
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle
    
