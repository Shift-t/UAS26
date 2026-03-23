import argparse
import json
import math
import time
from pathlib import Path

from utils.mavlink_controller import MavlinkController
from vision.person_tracker import PersonTracker


DEFAULT_CONFIG_PATH = Path("configs/sitl_mission.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the drone mission with a JSON config file."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the JSON config file.",
    )
    return parser.parse_args()


def load_config(path):
    with open(path, "r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    video_source = config.get("video_source", 0)
    if isinstance(video_source, str) and video_source.isdigit():
        config["video_source"] = int(video_source)

    return config


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def log_state_change(current_state, next_state, reason):
    if current_state != next_state:
        print(f"[MISSION] {current_state} -> {next_state}: {reason}")


def is_target_centered(target, config):
    return (
        abs(target.normalized_error_x) <= config["center_tolerance_x"]
        and abs(target.normalized_error_y) <= config["center_tolerance_y"]
    )


def build_alignment_velocity(target, config):
    forward = target.normalized_error_y * config["alignment_gain_y"]
    right = target.normalized_error_x * config["alignment_gain_x"]

    if config.get("invert_vertical", False):
        forward *= -1.0

    if config.get("invert_horizontal", False):
        right *= -1.0

    max_speed = config["alignment_max_speed_mps"]
    forward = clamp(forward, -max_speed, max_speed)
    right = clamp(right, -max_speed, max_speed)
    return forward, right


def target_is_lost(last_target_seen_at, now, config):
    if last_target_seen_at is None:
        return True

    return (now - last_target_seen_at) > config["lost_target_timeout_s"]


def run_search_pattern(flight_controller, config, search_started_at, now):
    pattern = config.get("search_pattern", "hover").lower()

    if pattern == "circle":
        radius = max(config["search_radius_m"], 0.1)
        speed = config["search_speed_mps"]
        omega = speed / radius
        elapsed = now - search_started_at
        vx = -radius * omega * math.sin(omega * elapsed)
        vy = radius * omega * math.cos(omega * elapsed)
        flight_controller.send_local_velocity(vx=vx, vy=vy, vz=0.0)
        return

    flight_controller.hover()


def release_payload(flight_controller, config):
    if not config.get("payload_enabled", True):
        print("[PAYLOAD] Payload release is disabled in config.")
        return False

    if config.get("payload_mock", True):
        print("[PAYLOAD] MOCK DROP_TRIGGERED")
        return True

    channel = config["payload_servo_channel"]
    hold_pwm = config["payload_hold_pwm"]
    drop_pwm = config["payload_drop_pwm"]
    release_hold_s = config["payload_release_hold_s"]

    print(f"[PAYLOAD] Releasing payload on servo channel {channel}")
    flight_controller.set_servo(channel=channel, pwm=drop_pwm)
    time.sleep(release_hold_s)
    flight_controller.set_servo(channel=channel, pwm=hold_pwm)
    return True


def should_land_from_controller(flight_controller):
    # OrangeCube / ArduPilot note:
    # A clean real-world approach is usually to let the pilot land by changing
    # flight mode from the RC transmitter, for example to LAND or RTL.
    #
    # If later you want the companion computer to watch an RC switch directly,
    # add a method in MavlinkController that reads RC_CHANNELS and then check a
    # chosen channel threshold here.
    #
    # Example future usage:
    # rc_value = flight_controller.read_rc_channel_pwm(channel=7)
    # return rc_value is not None and rc_value > 1800
    #
    # For now this stays disabled so landing remains pilot-controlled.
    return False


def run_mission(config):
    tracker = PersonTracker(
        model_path=config["model_path"],
        source=config["video_source"],
        confidence_threshold=config["confidence_threshold"],
        display=config["display"],
        capture_backend=config["capture_backend"],
        tracker_persist=config["tracker_persist"],
    )

    flight_controller = MavlinkController(
        enabled=config["mavlink_enabled"],
        connection_string=config["connection_string"],
        baud=config["baud"],
        source_system=config["source_system"],
        heartbeat_timeout_s=config["heartbeat_timeout_s"],
        command_timeout_s=config["command_timeout_s"],
        request_data_stream_hz=config["request_data_stream_hz"],
        guided_mode_name=config["guided_mode_name"],
    )

    state = "SEARCH"
    search_started_at = None
    centered_since = None
    last_target_seen_at = None
    payload_released = False

    try:
        print("[MISSION] Starting mission.")
        if flight_controller.enabled:
            flight_controller.connect()
            flight_controller.set_guided_mode()
            flight_controller.arm()
            flight_controller.takeoff(config["takeoff_altitude_m"])
        else:
            print("[MISSION] MAVLink is disabled. Running in vision-only mode.")

        while state not in {"COMPLETE", "ABORTED"}:
            result = tracker.read_result()
            now = time.time()

            if result.stream_ended:
                print("[MISSION] Video stream ended.")
                state = "ABORTED"
                break

            if result.quit_requested:
                print("[MISSION] Quit requested from video window.")
                state = "ABORTED"
                break

            target = result.target
            if target is not None:
                last_target_seen_at = now

            if state == "SEARCH":
                if payload_released:
                    if should_land_from_controller(flight_controller):
                        print("[MISSION] Landing requested from controller input.")
                        state = "ABORTED"
                        break

                    if search_started_at is None:
                        search_started_at = now
                    run_search_pattern(flight_controller, config, search_started_at, now)
                    time.sleep(config["loop_delay_s"])
                    continue

                if target is not None:
                    log_state_change(state, "ALIGN", "Target detected.")
                    state = "ALIGN"
                    centered_since = None
                    continue

                if search_started_at is None:
                    search_started_at = now
                run_search_pattern(flight_controller, config, search_started_at, now)

            elif state == "ALIGN":
                if target is None:
                    if target_is_lost(last_target_seen_at, now, config):
                        log_state_change(state, "SEARCH", "Target lost.")
                        state = "SEARCH"
                        search_started_at = None
                    else:
                        flight_controller.hover()
                    time.sleep(config["loop_delay_s"])
                    continue

                forward, right = build_alignment_velocity(target, config)
                flight_controller.send_body_velocity(
                    vx=forward,
                    vy=right,
                    vz=0.0,
                )

                if is_target_centered(target, config):
                    flight_controller.hover()
                    centered_since = now
                    log_state_change(state, "CONFIRM", "Target is inside center tolerance.")
                    state = "CONFIRM"

            elif state == "CONFIRM":
                if target is None:
                    centered_since = None
                    if target_is_lost(last_target_seen_at, now, config):
                        log_state_change(state, "SEARCH", "Target lost during confirm.")
                        state = "SEARCH"
                        search_started_at = None
                    else:
                        log_state_change(state, "ALIGN", "Waiting for target to stabilize again.")
                        state = "ALIGN"
                    time.sleep(config["loop_delay_s"])
                    continue

                if not is_target_centered(target, config):
                    centered_since = None
                    log_state_change(state, "ALIGN", "Target drifted outside tolerance.")
                    state = "ALIGN"
                    time.sleep(config["loop_delay_s"])
                    continue

                flight_controller.hover()
                if centered_since is None:
                    centered_since = now

                if (now - centered_since) >= config["center_hold_s"]:
                    log_state_change(state, "DROP", "Target remained centered long enough.")
                    state = "DROP"

            elif state == "DROP":
                if not payload_released:
                    payload_released = release_payload(flight_controller, config)

                search_started_at = now
                centered_since = None
                flight_controller.hover()
                log_state_change(
                    state,
                    "SEARCH",
                    "Payload dropped. Resuming search path until pilot lands the vehicle.",
                )
                state = "SEARCH"

            time.sleep(config["loop_delay_s"])

    except KeyboardInterrupt:
        print("[MISSION] Keyboard interrupt received.")
        state = "ABORTED"
    finally:
        tracker.close()
        if state == "ABORTED":
            print("[MISSION] Mission aborted. Landing if possible.")
            flight_controller.land()
        elif state != "COMPLETE":
            print("[MISSION] Mission ended without completion. Hovering if possible.")
            flight_controller.hover()
        flight_controller.close()


def main():
    args = parse_args()
    config = load_config(args.config)
    run_mission(config)


if __name__ == "__main__":
    main()
