# Autonomous Person-Tracking Drone Mission

This project is a simple onboard mission script for a drone that:

1. flies a search path,
2. looks for a person using computer vision,
3. moves to center the person in the camera view,
4. drops a payload once,
5. then resumes the search path until the pilot lands the vehicle.

## Quick Links

- [Setup](#setup)
- [What This Project Is For](#what-this-project-is-for)
- [Mission Overview](#mission-overview)
- [Project Layout](#project-layout)
- [How The Code Thinks](#how-the-code-thinks)
- [How Person Tracking Works](#how-person-tracking-works)
- [How MAVLink Is Used](#how-mavlink-is-used)
- [Running The Project](#running-the-project)
- [Config Files](#config-files)
- [Current Behavior After Payload Drop](#current-behavior-after-payload-drop)
- [Recommended Way To Learn The Code](#recommended-way-to-learn-the-code)
- [Important Limitations](#important-limitations)
- [Safety Notes](#safety-notes)
- [Jetson + OrangeCube + Mission Planner Connection Guide](#jetson--orangecube--mission-planner-connection-guide)
- [OrangeCube / ArduPilot / Motor Setup For This Code](#orangecube--ardupilot--motor-setup-for-this-code)

## Setup

Install the Python dependencies first:

```powershell
pip install -r requirements.txt
```

Main runtime packages used by this project:

- `ultralytics` for person detection / tracking
- `opencv-python` for camera input and video display
- `pymavlink` for communication with ArduPilot / OrangeCube
- `onnxruntime` for running the exported YOLO ONNX model

## What This Project Is For

The intended hardware setup is:

- an onboard computer such as a Jetson
- an OrangeCube flight controller
- a camera for person detection
- a payload release mechanism controlled through MAVLink / servo output

The current codebase is designed so the same mission logic can be tested in three ways:

- with only a recorded video
- with only a simulated drone
- with both vision and simulated flight together

That makes it possible to keep developing even when the real drone is not available.

## Mission Overview

At a high level, the mission works like this:

1. Start the program.
2. Load the selected config file.
3. Start the person tracker.
4. Connect to the drone if MAVLink is enabled.
5. Arm and take off.
6. Follow a search path.
7. If a person is detected, try to center them in the camera frame.
8. If the person stays centered for long enough, drop the payload.
9. Resume the search path.
10. Let the pilot land the drone manually later.

## Project Layout

- `main.py`
  - Small entry point used to launch the program.

- `drone_mission.py`
  - Main mission logic.
  - This is the best file to read first if you want to understand the program flow.

- `vision/person_tracker.py`
  - Handles camera or video input.
  - Runs YOLO person tracking.
  - Returns target location information to the mission logic.

- `utils/mavlink_controller.py`
  - Handles MAVLink communication with the autopilot.
  - Sends commands such as arm, takeoff, velocity movement, servo actuation, and land.

- `utils/vision_overlay.py`
  - Draws center lines and bounding boxes on the video feed for debugging.

- `configs/sitl_mission.json`
  - Example config for simulated flight.

- `configs/video_replay_mock.json`
  - Example config for testing with a recorded video and no drone connection.

## How The Code Thinks

The mission uses a few simple states:

- `SEARCH`
  - No target is currently being acted on.
  - The drone follows its search path.

- `ALIGN`
  - A person has been found.
  - The drone tries to move until the person is centered in the image.

- `CONFIRM`
  - The drone checks that the person stays centered for a short time.
  - This helps avoid dropping due to one bad or lucky frame.

- `DROP`
  - The payload is released once.
  - After that, the drone returns to `SEARCH`.

## How Person Tracking Works

The tracker reads a frame from the camera or video file and runs YOLO person detection/tracking on it.

For the selected person, it computes:

- the bounding box
- the target center in the image
- how far the target is from the image center
- a normalized error value used by the mission logic

The mission code then converts that error into movement commands for the drone.

In simple terms:

- if the person is left in the image, move left
- if the person is right in the image, move right
- if the person is high or low in the image, move accordingly

## How MAVLink Is Used

If MAVLink is enabled in the config, the code will:

- connect to the vehicle
- switch to guided mode
- arm the motors
- take off to the configured altitude
- send velocity commands during search and alignment
- trigger a servo command for payload release

If MAVLink is disabled, the same mission logic can still run with a video file, which is useful for offline testing.

## Running The Project

### 1. Video-only test

This is the easiest place to start.

Edit `configs/video_replay_mock.json` and replace:

```json
"video_source": "replace_with_test_video.mp4"
```

with the path to a real test video.

Then run:

```powershell
python main.py --config configs/video_replay_mock.json
```

This mode tests:

- video input
- person tracking
- mission state changes
- mock payload release

### 2. SITL / simulated flight test

If you have ArduPilot SITL running and available on the configured MAVLink port:

```powershell
python main.py --config configs/sitl_mission.json
```

This mode tests:

- MAVLink connection
- guided mode
- arming
- takeoff
- search motion

### 3. Combined test

You can also create your own config that uses:

- a video file for vision
- SITL for flight
- mock payload release

That is the closest digital test to the real mission.

## Config Files

The config files are plain JSON so they are easy to edit without touching Python code.

Important fields include:

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

## Current Behavior After Payload Drop

Right now the drone:

- drops the payload once
- returns to the search path
- keeps flying until the pilot lands manually

There is also commented code showing where future OrangeCube RC-channel based landing logic could be added.

## Recommended Way To Learn The Code

If you are new to this kind of system, read the files in this order:

1. `main.py`
2. `drone_mission.py`
3. `vision/person_tracker.py`
4. `utils/mavlink_controller.py`

That order matches the real execution flow of the program.

## Important Limitations

This project is still a development prototype. It should not be treated as flight-ready for a real mission yet.

Things that still need careful real-world validation:

- camera placement and orientation
- correct sign of movement commands
- payload servo channel and PWM values
- real autopilot connection settings
- flight safety checks and pilot override behavior
- tuning for stable centering

## Safety Notes

- Test vision first without MAVLink.
- Test MAVLink in SITL before any real hardware.
- Keep payload release in mock mode until the rest of the system is stable.
- Do not test new mission logic for the first time on a real aircraft.

## In One Sentence

This repository contains a simple, simulation-friendly drone mission that detects a person, centers the drone on them, drops a payload once, and then resumes its search path.

## Jetson + OrangeCube + Mission Planner Connection Guide

This is the recommended way to connect the system in practice.

### Recommended Physical Topology

Use separate links for the onboard computer and the ground station:

- Jetson <-> OrangeCube `TELEM2`
- Mission Planner <-> OrangeCube `TELEM1` or USB / telemetry radio

This is the cleanest setup because:

- the Jetson gets a dedicated MAVLink link to the flight controller
- Mission Planner gets its own link for setup, monitoring, and tuning
- you avoid both systems fighting over one cable or one serial port

### Recommended Wiring: Jetson to OrangeCube

Connect the Jetson UART to one telemetry port on the OrangeCube, preferably `TELEM2`.

Minimum required connections:

- OrangeCube `TX` -> Jetson `RX`
- OrangeCube `RX` -> Jetson `TX`
- OrangeCube `GND` -> Jetson `GND`

Optional if you want hardware flow control:

- OrangeCube `CTS` -> Jetson `RTS`
- OrangeCube `RTS` -> Jetson `CTS`

Important:

- The TELEM ports on The Cube are TTL serial ports, not USB.
- Do not connect the Jetson to the flight controller over the USB port for flight use.
- Power the Jetson from its own proper power supply, not from the TELEM port.

### OrangeCube Port Notes

According to CubePilot, The Cube exposes `TELEM1` and `TELEM2` as UART telemetry ports, and the generic TELEM connector provides:

- 5V
- TX
- RX
- CTS
- RTS
- GND

### Recommended ArduPilot Parameters

If Jetson is connected to `TELEM2`, then `TELEM2` is usually `SERIAL2`.

Recommended starting point:

- `SERIAL2_PROTOCOL = 2`
- `SERIAL2_BAUD = 115`
- `BRD_SER2_RTSCTS = 0` if you are only wiring TX/RX/GND
- `BRD_SER2_RTSCTS = 1` if you also wired RTS/CTS correctly

Explanation:

- `SERIALx_PROTOCOL = 2` means MAVLink2
- `SERIALx_BAUD = 115` means 115200 baud in ArduPilot parameter format

For the Mission Planner link on `TELEM1`, the same idea applies:

- `SERIAL1_PROTOCOL = 2` is preferred if your telemetry hardware supports MAVLink2
- `SERIAL1_BAUD` must match the radio / telemetry link baud rate you are actually using

### How Mission Planner Should Connect

You have three normal options:

- Bench setup: Mission Planner <-> OrangeCube USB
- Field telemetry: Mission Planner <-> radio / telemetry modem on `TELEM1`
- Network telemetry: Mission Planner <-> UDP/TCP endpoint if you build a network bridge

For bench setup, USB is fine.

For flight use, it is better to let Mission Planner use a separate telemetry link and let the Jetson stay on its own TELEM port.

### Why Separate Links Are Better

ArduPilot supports MAVLink routing between links, so a companion computer and a ground station can coexist. But the easiest and least confusing setup is still:

- one MAVLink port for the Jetson
- one MAVLink port for Mission Planner

That reduces debugging time and avoids command-routing confusion early in development.

### If You Only Have One Ground Link

If later you want one computer to receive telemetry and forward it elsewhere, MAVProxy can forward MAVLink data to other local or remote software.

That is useful for cases like:

- Jetson connected to the vehicle
- Jetson forwarding telemetry over UDP
- Mission Planner listening on that UDP port

This is valid, but it is more complex than using separate physical links.

### What To Set In This Repository

In your config file, set the connection string to match the Jetson-to-OrangeCube serial port.

Example on Jetson:

```json
"connection_string": "/dev/ttyTHS1",
"baud": 115200
```

The exact Linux device name depends on your Jetson carrier board and UART mapping.

### Recommended First Real-Hardware Bring-Up

1. Verify Mission Planner can connect to the OrangeCube by itself.
2. Set the TELEM port parameters for the Jetson in Mission Planner.
3. Reboot the OrangeCube.
4. Connect the Jetson UART to the chosen TELEM port.
5. Run this code on the Jetson with movement logic disabled or in a safe test condition first.
6. Confirm heartbeat and telemetry are visible.
7. Confirm guided mode, arm, and takeoff only after basic MAVLink communication is stable.

### Common Mistakes To Avoid

- Using USB as the in-flight companion-computer link
- Forgetting to cross TX and RX
- Mismatched baud rate between Jetson and OrangeCube
- Enabling RTS/CTS in parameters without wiring RTS/CTS physically
- Trying to power the Jetson from a TELEM connector
- Letting Mission Planner and the Jetson both control the vehicle without understanding which link is issuing commands

### Sources

- ArduPilot Companion Computers:
  - https://ardupilot.org/dev/docs/companion-computers.html
- ArduPilot MAVLink Routing:
  - https://ardupilot.org/dev/docs/mavlink-routing-in-ardupilot.html
- ArduPilot Telemetry / Serial Port Setup:
  - https://ardupilot.org/sub/docs/common-telemetry-port-setup.html
- ArduPilot Serial Port Configuration:
  - https://ardupilot.org/sub/docs/common-serial-options.html
- MAVProxy Telemetry Forwarding:
  - https://ardupilot.org/mavproxy/docs/getting_started/forwarding.html
- CubePilot Interface Specifications:
  - https://docs.cubepilot.org/user-guides/autopilot/the-cube/introduction/interface-specifications
- CubePilot Mission Planner setup:
  - https://docs.cubepilot.org/user-guides/autopilot/the-cube/setup/mission-planner

## OrangeCube / ArduPilot / Motor Setup For This Code

This section is the practical setup checklist for the team that is wiring and configuring the aircraft.

The code in this repository assumes:

- the OrangeCube is already running the correct ArduPilot firmware
- the receiver is already working
- the motors and ESCs are already configured correctly
- the Jetson only needs to send mission-level commands over MAVLink

In other words, this code is not doing low-level motor control. ArduPilot does that.

### 1. Load The Correct Firmware

For a multirotor drone, load `ArduCopter` onto the OrangeCube using Mission Planner.

Then make sure the vehicle frame type in ArduPilot matches the real airframe:

- quad X
- quad plus
- hex
- etc.

This matters because ArduPilot uses the chosen frame type to assign motor outputs correctly.

### 2. Connect ESCs And Motors Correctly

Each ESC signal wire must go to the correct motor output on the OrangeCube/carrier board.

Do not guess motor order. Use the ArduPilot motor-order diagram for your chosen frame type and then confirm it in Mission Planner using Motor Test.

Good workflow:

1. Set the frame class and frame type in ArduPilot.
2. Wire ESC signal outputs to the expected motor outputs.
3. Remove all propellers.
4. Use Mission Planner Motor Test to confirm the right motor spins when expected.
5. Confirm each motor spins in the correct direction.
6. Reverse any motor that spins the wrong way.

### 3. Calibrate The Radio Receiver

Your FlySky receiver must be fully working in Mission Planner before trying autonomous control.

At minimum:

- transmitter bound to receiver
- receiver connected correctly to the OrangeCube
- sticks move correctly in Mission Planner Radio Calibration
- flight mode switch works
- manual pilot takeover is available

This matters because the receiver is your backup and manual-control path.

### 4. Run Mandatory Sensor Setup In Mission Planner

Before trusting any companion-computer commands, complete the normal ArduPilot setup:

- accelerometer calibration
- compass calibration if used
- radio calibration
- flight mode setup
- failsafe setup

The Jetson code assumes the flight controller is already healthy and flyable on its own.

### 5. Configure The Jetson MAVLink Port

If the Jetson is connected to `TELEM2`, use:

- `SERIAL2_PROTOCOL = 2`
- `SERIAL2_BAUD = 115`

If only TX/RX/GND are wired:

- `BRD_SER2_RTSCTS = 0`

If RTS/CTS are also wired correctly:

- `BRD_SER2_RTSCTS = 1`

These settings allow the Jetson to communicate with the OrangeCube over MAVLink2.

### 6. Give Mission Planner Its Own Link

Recommended:

- Jetson on `TELEM2`
- Mission Planner on `TELEM1`, USB, or telemetry radio

This keeps setup and debugging much simpler.

### 7. Configure The Payload Output Correctly

Your code uses `MAV_CMD_DO_SET_SERVO` to move the payload release servo.

That means the output used for payload release must:

- be a free output
- not be assigned to a motor
- not already be assigned to another flight function

Recommended starting approach for Copter:

- put the payload servo on an unused `AUX OUT`
- set the matching `SERVOx_FUNCTION = 0`
- match `x` to the channel number used in your config file

Example:

If your config says:

```json
"payload_servo_channel": 9
```

then the matching ArduPilot output must allow direct servo control on channel 9.

If that output is already assigned to another function, `DO_SET_SERVO` will not work correctly.

### 8. Match The Config File To The Aircraft

The following values in this repository must match the real aircraft setup:

- `connection_string`
- `baud`
- `guided_mode_name`
- `payload_servo_channel`
- `payload_hold_pwm`
- `payload_drop_pwm`

And these values usually need tuning:

- `alignment_gain_x`
- `alignment_gain_y`
- `alignment_max_speed_mps`
- `center_tolerance_x`
- `center_tolerance_y`
- `center_hold_s`

### 9. First Integration Test Order

Do not jump straight to full autonomy.

Use this order:

1. Mission Planner only
   - verify sensors, receiver, modes, and motor outputs
2. Mission Planner Motor Test
   - verify motor numbering and spin direction
3. ESC calibration if your ESC type requires it
4. Jetson heartbeat only
   - verify the Jetson can talk MAVLink to the OrangeCube
5. Jetson-guided takeoff in a safe test setup
6. Vision-only replay testing
7. Combined testing

### 10. What “Seamless Communication” Means Here

If setup is correct, the system should behave like this:

- receiver gives pilot commands to OrangeCube
- Mission Planner monitors and configures OrangeCube
- Jetson sends mission commands to OrangeCube over MAVLink
- OrangeCube mixes all of this with its own stabilization and sensor logic
- motors and ESCs are still controlled by ArduPilot, not by Python

That is the correct architecture for this project.

### Extra References For The Team

- ESC calibration:
  - https://ardupilot.org/copter/docs/esc-calibration.html
- Connect ESCs and motors:
  - https://ardupilot.org/copter/docs/connect-escs-and-motors.html
- Radio calibration:
  - https://ardupilot.org/planner/docs/common-radio-control-calibration.html
- Autopilot output functions:
  - https://ardupilot.org/rover/docs/common-rcoutput-mapping.html
- Servo control / payload outputs:
  - https://ardupilot.org/copter/docs/common-servo.html
- MAVLink servo command behavior:
  - https://ardupilot.org/dev/docs/mavlink-move-servo.html
