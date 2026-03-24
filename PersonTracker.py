import cv2
import numpy as np
from ultralytics import YOLO

class PersonTracker:
    def __init__(self, drone, model_path, camera_index):  #cam idx might be different

        print(f"[PersonTracker] Loading YOLO from: {model_path}...")
        self.model = YOLO(model_path)
        self.target_id = None
        self.drone = drone

        # self.cap = cv2.VideoCapture(camera_index)   #FOR JETSON NANO
        self.cap = cv2.VideoCapture(2, cv2.CAP_DSHOW) #FOR WINDOWS
        if not self.cap.isOpened():
            raise Exception("[PersonTracker] ***Error: Camera Loading Error***")
        
        # get the camera resolution
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[PersonTracker] Camera initialized @ resolution: {self.frame_width}x{self.frame_height}")

        #***Adjust Parameters***
        self.target_ideal_area = 50000           # Smaller value = higher drone altitude, larger value = lower
        self.vertical_deadzone = 5000            # Tolerance
        self.horizontal_deadzone_radius = 25     # deadzone in pixels for horizontal movements

    def tracking_loop(self):
        # Main loop to capture video frames and perform detection.
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("[PersonTracker] **Error: Failed to grab frame.***")
                    break

                # classes=[0] to filter out the person class
                results = self.model.track(frame, classes=[0], conf=0.5, persist = True, verbose=False)
                # ***[YOLO VisDrone]*** results = self.model.track(frame, classes=[0, 1], conf=0.15, persist = True, verbose=False)
                
                tracking_active = False

                if len(results[0].boxes) > 0 and results[0].boxes.id is not None:
                    boxes = results[0].boxes.xyxy.cpu().numpy()         #grab bounding boxes 
                    ids = results[0].boxes.id.cpu().numpy().astype(int) #grab ids for detections
                    if self.target_id is None or self.target_id not in ids: #if theres no target currently selected
                        self.target_id = ids[0]                             #select first detection in current frame as target
                        print(f"Target switched to ID: {self.target_id}")

                    if self.target_id in ids:                   #if target in current frame
                        idx = list(ids).index(self.target_id)   #grab index of target
                        x1, y1, x2, y2 = map(int, boxes[idx])   #grab coords for target

                        speeds, measurements = self._calculate_velocities(x1, y1, x2, y2)
                        self.drone.send_velocity_cmd(*speeds)
                        self._draw_hud(frame, x1, y1, x2, y2, measurements)

                        tracking_active = True
                    
                if not tracking_active:     #if no target found
                    self.target_id = None   #reset target
                    cv2.putText(frame, "SEARCHING FOR TARGET...", (20, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    self.drone.send_velocity_cmd(0,0,0,0)   #No target, maintain position
                        
                # Display cam feed
                cv2.imshow("ONNX Vision Tracker", frame)

                # exit with q (cam feed frame should be in focus)
                if cv2.waitKey(1) == ord('q'):
                    break
        finally:
            self.cap.release()
            cv2.destroyAllWindows()

    # Helper Functions
    def _calculate_velocities(self, x1, y1, x2, y2):
        frame_center_x = self.frame_width // 2
        frame_center_y = self.frame_height // 2
        target_center_x = (x1 + x2) // 2
        target_center_y = (y1 + y2) // 2
        target_area = (x2 - x1) * (y2 - y1)
        offset_x = target_center_x - frame_center_x
        offset_y = target_center_y - frame_center_y
        distance_from_center = np.sqrt(offset_x**2 + offset_y**2)

        if distance_from_center > self.horizontal_deadzone_radius:
            # forward/backward velocity (x) of drone maps to vertical screen offset
            forward_speed = -0.002 * offset_y   #Down on screen is +ve
            # left/right velocity (y) maps to horizontal screen offset
            right_speed = 0.002 * offset_x      #Right on screen is +ve
        else:
            #dont move
            forward_speed = 0
            right_speed = 0

        area_diff = self.target_ideal_area - target_area
        if abs(area_diff) > self.vertical_deadzone:
            vertical_speed = 0.00002 * area_diff
        else:
            vertical_speed = 0

        yaw_rate = 0

        # forward_speed = np.clip(forward_speed, -1, 1)         #clip the speed to 1m/s max for safety
        # right_speed = np.clip(right_speed, -1, 1)             #clip the speed to 1m/s max for safety
        # vertical_speed = np.clip(vertical_speed, -0.5, 0.5)   #clip the speed to 0.5m/s max for safety

        speeds = (forward_speed, right_speed, vertical_speed, yaw_rate)
        measurements = (offset_x, offset_y, target_area, target_center_x, target_center_y)

        return speeds, measurements

    def _draw_hud(self, frame, x1, y1, x2, y2, measurements):
        offset_x, offset_y, target_area, target_center_x, target_center_y = measurements
        frame_center_x = self.frame_width //2
        frame_center_y = self.frame_height //2

        # Draw center lines
        cv2.line(frame, (frame_center_x, 0), (frame_center_x, self.frame_height), (255, 255, 255), 1)
        cv2.line(frame, (0, frame_center_y), (self.frame_width, frame_center_y), (200, 200, 200), 1)

        # Draw Horizontal Deadzone circle
        cv2.circle(frame, (frame_center_x, frame_center_y), self.horizontal_deadzone_radius, (255, 255, 0), 2)
        
        #Draw Bounding Box
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
        
        #Add details to bounding box
        cv2.putText(frame, f"DX: {offset_x} | DY: {offset_y} | Area: {target_area}", (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.circle(frame, (target_center_x, target_center_y), 5, (0, 255, 0), -1)

# tracker = PersonTracker(model_path='yolov8n.onnx', camera_index=0)
# tracker.tracking_loop()