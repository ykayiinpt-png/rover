import time
import numpy as np
import cv2
from ultralytics import YOLO

class IaVisionPipeline(object):
    def __init__(self, name, key):
        self.name = name
        self.key = key
    def process(self, frame: np.ndarray):
        pass 


class ObjectDetectionPipeline(IaVisionPipeline):
    def __init__(
        self,
        model_name: str,
        classes: list,
        frame_rate: int = 1,
        draw_boxes: bool = True,
        conf_threshold: float = 0.4
    ):
        """
        Args:
            model_name (str): path or name of YOLO model (e.g. yolov8n.pt)
            classes (list): list of class names
            frame_rate (int): run detection every N frames
            draw_boxes (bool): whether to draw bounding boxes
            conf_threshold (float): confidence threshold
        """
        super().__init__(name="ObjectDetectionPipeline", key="object_detection")
        
        self.model = YOLO(model_name)
        self.classes = classes
        self.frame_rate = frame_rate
        self.draw_boxes = draw_boxes
        self.conf_threshold = conf_threshold

        self.frame_counter = 0
        self.last_results = []

    def process(self, frame: np.ndarray):
        """
        Args:
            frame (np.ndarray): RGB image

        Returns:
            processed_frame (np.ndarray)
            detections (list)
        """

        detections = []

        # Default output = input frame copy
        output_frame = frame.copy()

        self.frame_counter += 1

        # Run detection only every N frames
        if self.frame_counter % self.frame_rate != 0:
            return output_frame, self.last_results

        # Run YOLO inference
        results = self.model(frame, verbose=False)[0]

        for box in results.boxes:
            confidence = float(box.conf[0])
            if confidence < self.conf_threshold:
                continue

            class_id = int(box.cls[0])

            # safety check
            if class_id >= len(self.classes):
                class_name = str(class_id)
            else:
                class_name = self.classes[class_id]

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            detection = {
                "msg_type": "ANNOTATION",
                "class": class_name,
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2],
                "timestamp": time.time()
            }

            detections.append(detection)

            # Draw if enabled
            if self.draw_boxes:
                cv2.rectangle(
                    output_frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                label = f"{class_name} {confidence:.2f}"
                cv2.putText(
                    output_frame,
                    label,
                    (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        # Save last results for skipped frames
        self.last_results = detections

        return output_frame, detections
