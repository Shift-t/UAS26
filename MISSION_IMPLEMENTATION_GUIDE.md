# Mission Implementation Guide

This version is intentionally simple.

The mission logic now lives mostly in one file so you can debug it without jumping around the codebase.

## Main Files

- `main.py`
  - Small entry point.
  - This is the file to run.

- `drone_mission.py`
  - This is the main file to read first.
  - It loads the JSON config.
  - It runs the mission loop.
  - It contains the simple mission states:
    - `SEARCH`
    - `ALIGN`
    - `CONFIRM`
    - `DROP`

- `vision/person_tracker.py`
  - Handles camera or video input.
  - Runs YOLO person tracking.
  - Returns target position data such as image offsets and normalized error.

- `utils/mavlink_controller.py`
  - Handles MAVLink only.
  - Connects, arms, takes off, sends movement commands, lands, and triggers the servo.

- `utils/vision_overlay.py`
  - Draws the tracker overlay on the video frame.

- `configs/sitl_mission.json`
  - Default config for SITL-style testing.

- `configs/video_replay_mock.json`
  - Offline config for replaying a recorded video with MAVLink disabled.

## How The Mission Works

The main loop in `drone_mission.py` does this:

1. Start tracker and MAVLink.
2. Arm and take off if MAVLink is enabled.
3. Search for a person.
4. When a person is detected, move into alignment mode.
5. Use the image error to send body-frame velocity commands.
6. Once the person stays centered long enough, trigger payload release.
7. Land or hover depending on config.

## Why This Is Easier To Debug

- The mission behavior is in one place.
- The tracker does not contain flight logic.
- MAVLink does not contain mission decisions.
- The config is flat JSON, so it is easy to scan.

If something goes wrong, you usually only need to inspect:

1. `drone_mission.py`
2. `vision/person_tracker.py`
3. `utils/mavlink_controller.py`

## Config Fields

The config files are flat on purpose.

Important fields:

- `mavlink_enabled`
- `connection_string`
- `takeoff_altitude_m`
- `video_source`
- `confidence_threshold`
- `search_pattern`
- `alignment_gain_x`
- `alignment_gain_y`
- `center_tolerance_x`
- `center_tolerance_y`
- `center_hold_s`
- `payload_mock`
- `payload_servo_channel`

## How To Run

SITL-style run:

```powershell
python main.py --config configs/sitl_mission.json
```

Video replay run:

```powershell
python main.py --config configs/video_replay_mock.json
```

## Suggested Debugging Order

1. Run with `video_replay_mock.json`.
2. Confirm target detection and state changes.
3. Confirm the code prints `MOCK DROP_TRIGGERED` only once.
4. Move to SITL and tune alignment gains.
5. Only after that, tune for real hardware.

## What Still Needs Real Hardware Testing

- Correct MAVLink connection for the OrangeCube.
- Correct camera backend and camera device on Jetson.
- Correct direction signs for centering movement.
- Correct servo channel and PWM values.
- Safety checks before real payload release.
