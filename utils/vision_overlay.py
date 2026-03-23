import cv2


def draw_bounding_box(frame, bbox, label=None):
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    if label:
        cv2.putText(
            frame,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )


def draw_center_lines(frame):
    frame_height, frame_width = frame.shape[:2]
    cv2.line(
        frame,
        (frame_width // 2, 0),
        (frame_width // 2, frame_height),
        (255, 255, 255),
        1,
    )
    cv2.line(
        frame,
        (0, frame_height // 2),
        (frame_width, frame_height // 2),
        (200, 200, 200),
        1,
    )
