# ***pip install pymavlink
import time
from pymavlink import mavutil

class DroneController:
    def __init__(self, connection_string, baud_rate):
        self.vehicle = mavutil.mavlink_connection(connection_string, baud = baud_rate)
        self.vehicle.wait_heartbeat()
    
    def set_mode(self, mode_name):
        mode_id = self.vehicle.mode_mapping()[mode_name]
        self.vehicle.mav.set_mode_send(
            self.vehicle.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
    
    def send_velocity_cmd(self, x, y, z, yaw):  #x = forward/backward, y = left/right, z = up/down
        self.vehicle.mav.set_position_target_local_ned_send(
            0,
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b010111000111, # mask to ignore position/accel, enable velocity and yaw
            0, 0, 0,        # ignore position
            x, y, z,        # velocity
            0, 0, 0,        # ignore acceleration
            0, yaw          # yaw, yaw rate
        )