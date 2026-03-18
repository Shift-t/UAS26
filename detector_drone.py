import cv2
from ultralytics import YOLO

class PersonTracker:
    def __init__(self, model_path='yolov8n.onnx', camera_index=0):  #cam idx might be different

        print(f"Loading YOLO from: {model_path}...")
        self.model = YOLO(model_path, task='detect')

        self.target_id = None
        
        # self.cap = cv2.VideoCapture(camera_index)   #FOR JETSON NANO
        self.cap = cv2.VideoCapture(1, cv2.CAP_DSHOW) #FOR WINDOWS
        
        if not self.cap.isOpened():
            raise Exception("***Eror: Camera Loading Error***")
        
        # get the camera resolution
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"Camera initialized @ resolution: {self.frame_width}x{self.frame_height}")

    def tracking_loop(self):
        # Main loop to capture video frames and perform detection.
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    print("***Error: Failed to grab frame.***")
                    break

                # classes=[0] to filter out the person class
                results = self.model.track(frame, classes=[0], conf=0.5, persist = True, verbose=False)
                tracking_active = False

                target_center_x = None
                target_center_y = None
                target_area = None

                if results[0].boxes.id is not None:
                    boxes = results[0].boxes.xyxy.cpu().numpy()         #grab bounding boxes 
                    ids = results[0].boxes.id.cpu().numpy().astype(int) #grab ids for detections
                    
                    if self.target_id is None or self.target_id not in ids: #if theres no target currently selected
                        self.target_id = ids[0]                             #select first detection in current frame as target
                        print(f"Target switched to ID: {self.target_id}")

                    
                    if self.target_id in ids:                   #if target in current frame
                        idx = list(ids).index(self.target_id)   #grab index of target
                        x1, y1, x2, y2 = map(int, boxes[idx])   #grab coords for target

                        frame_center_x = self.frame_width // 2
                        frame_center_y = self.frame_height // 2
                        target_center_x = (x1 + x2) // 2
                        target_center_y = (y1 + y2) // 2
                        target_area = (x2 - x1) * (y2 - y1)
                        offset_x = target_center_x - frame_center_x
                        offset_y = target_center_y - frame_center_y

                        # Draw center lines
                        cv2.line(frame, (frame_center_x, 0), (frame_center_x, self.frame_height), (255, 255, 255), 1)
                        cv2.line(frame, (0, frame_center_y), (self.frame_width, frame_center_y), (200, 200, 200), 1)
                        
                        #Draw Bounding Box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                        
                        #Add details to bounding box
                        cv2.putText(frame, f"DX: {offset_x} | DY: {offset_y} | Area: {target_area}", (x1, y1 - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        cv2.circle(frame, (target_center_x, target_center_y), 5, (0, 255, 0), -1)

                        tracking_active = True
                    
                if not tracking_active:     #if no target found
                    self.target_id = None   #reset target
                    cv2.putText(frame, "SEARCHING FOR TARGET...", (20, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        
                # Display cam feed
                cv2.imshow("ONNX Vision Tracker", frame)

                # exit with q (cam feed frame should be in focus)
                if cv2.waitKey(1) == ord('q'):
                    break

        finally:
            self.cap.release()
            cv2.destroyAllWindows()

tracker = PersonTracker(model_path='yolov8n.onnx', camera_index=0)
tracker.tracking_loop()