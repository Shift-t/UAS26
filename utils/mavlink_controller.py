import time

from pymavlink import mavutil


class MavlinkController:
    def __init__(
        self,
        enabled=True,
        connection_string="tcp:127.0.0.1:5762",
        baud=115200,
        source_system=255,
        heartbeat_timeout_s=30.0,
        command_timeout_s=5.0,
        request_data_stream_hz=10,
        guided_mode_name="GUIDED",
    ):
        self.enabled = enabled
        self.connection_string = connection_string
        self.baud = baud
        self.source_system = source_system
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.command_timeout_s = command_timeout_s
        self.request_data_stream_hz = request_data_stream_hz
        self.guided_mode_name = guided_mode_name
        self.master = None

    def connect(self):
        if not self.enabled:
            print("[MAV] Connection skipped because MAVLink is disabled.")
            return

        print(f"[MAV] Connecting via {self.connection_string}")
        self.master = mavutil.mavlink_connection(
            self.connection_string,
            baud=self.baud,
            source_system=self.source_system,
        )
        self.master.wait_heartbeat(timeout=self.heartbeat_timeout_s)
        print(
            "[MAV] Heartbeat received from "
            f"system {self.master.target_system} component {self.master.target_component}"
        )
        self.master.mav.request_data_stream_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            self.request_data_stream_hz,
            1,
        )

    def close(self):
        if self.master is not None and hasattr(self.master, "close"):
            self.master.close()
        self.master = None

    def set_guided_mode(self):
        self.set_mode(self.guided_mode_name)

    def set_mode(self, mode_name):
        if not self.enabled:
            print(f"[MAV] Skipping mode change to {mode_name} because MAVLink is disabled.")
            return

        self._require_connection()
        mode_mapping = self.master.mode_mapping()
        if mode_name not in mode_mapping:
            raise ValueError(f"Flight mode '{mode_name}' is not supported.")

        mode_id = mode_mapping[mode_name]
        print(f"[MAV] Setting mode to {mode_name}")
        self.master.set_mode(mode_id)

        deadline = time.time() + self.command_timeout_s
        while time.time() < deadline:
            heartbeat = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
            if heartbeat is not None and heartbeat.custom_mode == mode_id:
                print(f"[MAV] Mode confirmed: {mode_name}")
                return

        raise TimeoutError(f"Timed out waiting for mode {mode_name}.")

    def arm(self):
        if not self.enabled:
            print("[MAV] Skipping arming because MAVLink is disabled.")
            return

        self._require_connection()
        print("[MAV] Arming vehicle")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        self._wait_for_command_ack(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM)
        self.master.motors_armed_wait()
        print("[MAV] Vehicle armed")

    def takeoff(self, altitude_m):
        if not self.enabled:
            print(f"[MAV] Skipping takeoff to {altitude_m}m because MAVLink is disabled.")
            return

        self._require_connection()
        print(f"[MAV] Taking off to {altitude_m:.1f}m")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            altitude_m,
        )
        self._wait_for_command_ack(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF)
        self._wait_for_altitude(altitude_m)

    def land(self):
        if not self.enabled:
            print("[MAV] Skipping land because MAVLink is disabled.")
            return

        if self.master is None:
            return

        print("[MAV] Landing vehicle")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )

    def hover(self):
        self.send_body_velocity(vx=0.0, vy=0.0, vz=0.0)

    def send_body_velocity(self, vx, vy, vz):
        if not self.enabled or self.master is None:
            return

        self.master.mav.set_position_target_local_ned_send(
            0,
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            0b0000111111000111,
            0,
            0,
            0,
            vx,
            vy,
            vz,
            0,
            0,
            0,
            0,
            0,
        )

    def send_local_velocity(self, vx, vy, vz):
        if not self.enabled or self.master is None:
            return

        self.master.mav.set_position_target_local_ned_send(
            0,
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111000111,
            0,
            0,
            0,
            vx,
            vy,
            vz,
            0,
            0,
            0,
            0,
            0,
        )

    def set_servo(self, channel, pwm):
        if not self.enabled:
            print(
                f"[MAV] Skipping servo command channel={channel} pwm={pwm} because MAVLink is disabled."
            )
            return

        self._require_connection()
        print(f"[MAV] Setting servo channel {channel} to PWM {pwm}")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            channel,
            pwm,
            0,
            0,
            0,
            0,
            0,
        )
        self._wait_for_command_ack(mavutil.mavlink.MAV_CMD_DO_SET_SERVO)

    # Future OrangeCube helper:
    # def read_rc_channel_pwm(self, channel):
    #     """
    #     Read one RC input channel from the autopilot.
    #
    #     Example:
    #         pwm = flight_controller.read_rc_channel_pwm(channel=7)
    #         if pwm is not None and pwm > 1800:
    #             flight_controller.land()
    #
    #     This is left commented out on purpose because RC channel mapping
    #     depends on your transmitter, receiver, and ArduPilot setup.
    #     """
    #     if not self.enabled or self.master is None:
    #         return None
    #
    #     message = self.master.recv_match(type="RC_CHANNELS", blocking=True, timeout=1)
    #     if message is None:
    #         return None
    #
    #     field_name = f"chan{channel}_raw"
    #     return getattr(message, field_name, None)

    def _wait_for_altitude(self, target_altitude_m):
        while True:
            message = self.master.recv_match(
                type="GLOBAL_POSITION_INT",
                blocking=True,
                timeout=1,
            )
            if message is None:
                print("[MAV] Waiting for altitude update.")
                continue

            current_altitude = message.relative_alt / 1000.0
            print(
                "[MAV] Altitude "
                f"{current_altitude:.1f}m / target {target_altitude_m:.1f}m"
            )
            if current_altitude >= target_altitude_m * 0.95:
                print("[MAV] Target altitude reached")
                return

    def _wait_for_command_ack(self, command_id):
        deadline = time.time() + self.command_timeout_s
        while time.time() < deadline:
            message = self.master.recv_match(type="COMMAND_ACK", blocking=True, timeout=1)
            if message is None:
                continue

            if message.command != command_id:
                continue

            if message.result not in {
                mavutil.mavlink.MAV_RESULT_ACCEPTED,
                mavutil.mavlink.MAV_RESULT_IN_PROGRESS,
            }:
                raise RuntimeError(
                    f"Command {command_id} was rejected with result {message.result}."
                )
            return

        raise TimeoutError(f"Timed out waiting for ACK for command {command_id}.")

    def _require_connection(self):
        if self.master is None:
            raise RuntimeError("MAVLink controller is not connected.")
