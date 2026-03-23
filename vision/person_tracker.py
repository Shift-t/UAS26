from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
from ultralytics import YOLO

from utils.vision_overlay import draw_bounding_box, draw_center_lines


@dataclass
class DetectedTarget:
    track_id: int
    confidence: float
    bbox: Tuple[int, int, int, int]
    frame_width: int
    frame_height: int
    target_center_x: int
    target_center_y: int
    area: int
    offset_x: int
    offset_y: int
    normalized_error_x: float
    normalized_error_y: float


@dataclass
class TrackerFrameResult:
    target: Optional[DetectedTarget]
    quit_requested: bool = False
    stream_ended: bool = False


class PersonTracker:
    def __init__(
        self,
        model_path="yolov8n.onnx",
        source=0,
        confidence_threshold=0.5,
        display=True,
        capture_backend="default",
        tracker_persist=True,
    ):
        print(f"[TRACKER] Loading YOLO model from: {model_path}")
        self.model = YOLO(model_path, task="detect")
        self.target_id = None
        self.confidence_threshold = confidence_threshold
        self.display = display
        self.tracker_persist = tracker_persist

        self.cap = self._open_capture(source, capture_backend)
        if not self.cap.isOpened():
            raise RuntimeError("Camera or video source failed to open.")

        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(
            "[TRACKER] Video source initialized at "
            f"{self.frame_width}x{self.frame_height}."
        )

    def read_result(self):
        ret, frame = self.cap.read()
        if not ret:
            print("[TRACKER] Video stream ended or frame grab failed.")
            return TrackerFrameResult(target=None, stream_ended=True)

        results = self.model.track(
            frame,
            classes=[0],
            conf=self.confidence_threshold,
            persist=self.tracker_persist,
            verbose=False,
        )

        target = self._extract_target(frame, results)
        if target is None:
            self.target_id = None
            cv2.putText(
                frame,
                "SEARCHING FOR TARGET...",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2,
            )

        quit_requested = self._show_frame(frame)
        return TrackerFrameResult(target=target, quit_requested=quit_requested)

    def tracking_loop(self):
        try:
            while True:
                result = self.read_result()
                if result.quit_requested or result.stream_ended:
                    break
        finally:
            self.close()

    def close(self):
        if self.cap is not None:
            self.cap.release()
        if self.display:
            cv2.destroyAllWindows()

    def _extract_target(self, frame, results):
        if not results or results[0].boxes is None or results[0].boxes.id is None:
            return None

        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.cpu().numpy().astype(int)
        confidences = results[0].boxes.conf.cpu().numpy()

        selected_index = self._select_target_index(boxes, ids)
        if selected_index is None:
            return None

        x1, y1, x2, y2 = [int(value) for value in boxes[selected_index]]
        self.target_id = int(ids[selected_index])

        frame_center_x = self.frame_width // 2
        frame_center_y = self.frame_height // 2
        target_center_x = (x1 + x2) // 2
        target_center_y = (y1 + y2) // 2
        area = (x2 - x1) * (y2 - y1)
        offset_x = target_center_x - frame_center_x
        offset_y = target_center_y - frame_center_y
        normalized_error_x = offset_x / max(frame_center_x, 1)
        normalized_error_y = offset_y / max(frame_center_y, 1)

        draw_center_lines(frame)
        draw_bounding_box(
            frame,
            (x1, y1, x2, y2),
            (
                f"ID: {self.target_id} "
                f"Conf: {confidences[selected_index]:.2f} "
                f"DX: {offset_x} DY: {offset_y}"
            ),
        )
        cv2.circle(frame, (target_center_x, target_center_y), 5, (0, 255, 0), -1)

        return DetectedTarget(
            track_id=self.target_id,
            confidence=float(confidences[selected_index]),
            bbox=(x1, y1, x2, y2),
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            target_center_x=target_center_x,
            target_center_y=target_center_y,
            area=area,
            offset_x=offset_x,
            offset_y=offset_y,
            normalized_error_x=normalized_error_x,
            normalized_error_y=normalized_error_y,
        )

    def _select_target_index(self, boxes, ids):
        if len(ids) == 0:
            return None

        if self.target_id is not None:
            for index, detected_id in enumerate(ids):
                if int(detected_id) == int(self.target_id):
                    return index

        largest_index = 0
        largest_area = -1
        for index, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            area = int((x2 - x1) * (y2 - y1))
            if area > largest_area:
                largest_area = area
                largest_index = index

        print(f"[TRACKER] Target switched to ID: {int(ids[largest_index])}")
        return largest_index

    def _show_frame(self, frame):
        if not self.display:
            return False

        cv2.imshow("ONNX Vision Tracker", frame)
        return cv2.waitKey(1) == ord("q")

    @staticmethod
    def _open_capture(source, capture_backend):
        backend_name = (capture_backend or "default").upper()
        backend_map = {
            "DEFAULT": None,
            "DSHOW": getattr(cv2, "CAP_DSHOW", None),
            "GSTREAMER": getattr(cv2, "CAP_GSTREAMER", None),
            "FFMPEG": getattr(cv2, "CAP_FFMPEG", None),
            "V4L2": getattr(cv2, "CAP_V4L2", None),
        }

        backend = backend_map.get(backend_name)
        if backend is None:
            return cv2.VideoCapture(source)

        return cv2.VideoCapture(source, backend)
