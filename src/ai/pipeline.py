import time
import numpy as np
import cv2
from ultralytics import YOLO

import math
import time


class TrackedObject:
    def __init__(self, track_id, class_name, bbox, confidence, bbox_image=None):
        self.id = track_id
        self.class_name = class_name
        self.bbox = bbox
        self.bbox_image = bbox_image
        self.confidence = confidence

        self.centroid = self._compute_centroid(bbox)

        self.first_seen = time.time()
        self.last_seen = time.time()

        self.missed_frames = 0
        self.reported = False

    @staticmethod
    def _compute_centroid(bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def update(self, bbox, bbox_image=None):
        self.bbox = bbox
        self.bbox_image = bbox_image
        self.centroid = self._compute_centroid(bbox)
        self.last_seen = time.time()
        self.missed_frames = 0

# class ObjectTracker:
#     def __init__(
#         self,
#         max_distance=50,
#         max_missed_frames=15
#     ):
#         """
#         Args:
#             max_distance (int):
#                 Maximum centroid distance to match object

#             max_missed_frames (int):
#                 Remove object after N missed frames
#         """

#         self.max_distance = max_distance
#         self.max_missed_frames = max_missed_frames

#         self.next_track_id = 0
#         self.tracks = {}

#     @staticmethod
#     def _distance(c1, c2):
#         return math.sqrt(
#             (c1[0] - c2[0]) ** 2 +
#             (c1[1] - c2[1]) ** 2
#         )

#     @staticmethod
#     def _centroid(bbox):
#         x1, y1, x2, y2 = bbox
#         return ((x1 + x2) // 2, (y1 + y2) // 2)

#     def update(self, detections):
#         """
#         Args:
#             detections (list):
#                 [
#                     {
#                         "class": str,
#                         "bbox": [x1, y1, x2, y2],
#                         ...
#                     }
#                 ]

#         Returns:
#             tracks (list):
#                 list of matched tracked objects
#         """

#         updated_tracks = []

#         matched_track_ids = set()

#         # Match detections to existing tracks
#         for detection in detections:
#             bbox = detection["bbox"]
#             class_name = detection["class"]
#             confidence = detection["bbox"]

#             centroid = self._centroid(bbox)

#             best_track = None
#             best_distance = float("inf")

#             for track_id, track in self.tracks.items():

#                 # match only same class
#                 if track.class_name != class_name:
#                     continue

#                 distance = self._distance(
#                     centroid,
#                     track.centroid
#                 )

#                 if distance < best_distance and distance < self.max_distance:
#                     best_distance = distance
#                     best_track = track

#             if best_track is not None:
#                 best_track.update(bbox)
#                 matched_track_ids.add(best_track.id)
#                 updated_tracks.append(best_track)

#             else:
#                 # Create new track
#                 track = TrackedObject(
#                     track_id=self.next_track_id,
#                     class_name=class_name,
#                     bbox=bbox, confidence=confidence
#                 )

#                 self.tracks[self.next_track_id] = track

#                 matched_track_ids.add(track.id)
#                 updated_tracks.append(track)

#                 self.next_track_id += 1

#         # Increment missed frames
#         to_delete = []

#         for track_id, track in self.tracks.items():

#             if track_id not in matched_track_ids:
#                 track.missed_frames += 1

#             if track.missed_frames > self.max_missed_frames:
#                 to_delete.append(track_id)

#         for track_id in to_delete:
#             del self.tracks[track_id]

#         return updated_tracks



class ObjectTracker:

    def __init__(
        self,
        max_distance=50,
        max_missed_frames=15
    ):

        self.max_distance = max_distance
        self.max_missed_frames = max_missed_frames

        self.next_track_id = 0
        self.tracks = {}

    @staticmethod
    def _distance(c1, c2):
        return math.sqrt(
            (c1[0] - c2[0]) ** 2 +
            (c1[1] - c2[1]) ** 2
        )

    @staticmethod
    def _centroid(bbox):
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def update(self, detections):

        updated_tracks = []
        new_tracks = []

        matched_track_ids = set()

        for detection in detections:
            bbox = detection["bbox"]
            class_name = detection["class"]
            confidence = detection["confidence"]
            bbox_image = detection["bbox_image"]

            centroid = self._centroid(bbox)

            best_track: TrackedObject = None
            best_distance = float("inf")

            for track_id, track in self.tracks.items():

                if track.class_name != class_name:
                    continue

                distance = self._distance(
                    centroid,
                    track.centroid
                )

                if (
                    distance < best_distance
                    and distance < self.max_distance
                ):
                    best_distance = distance
                    best_track = track

            # Existing object
            if best_track is not None:
                best_track.update(bbox, bbox_image)

                matched_track_ids.add(best_track.id)
                updated_tracks.append(best_track)

            # New object
            else:
                track = TrackedObject(
                    track_id=self.next_track_id,
                    class_name=class_name,
                    bbox=bbox, confidence=confidence,
                    bbox_image=bbox_image
                )

                self.tracks[self.next_track_id] = track

                matched_track_ids.add(track.id)

                updated_tracks.append(track)
                new_tracks.append(track)

                self.next_track_id += 1

        # cleanup
        to_delete = []

        for track_id, track in self.tracks.items():

            if track_id not in matched_track_ids:
                track.missed_frames += 1

            if track.missed_frames > self.max_missed_frames:
                to_delete.append(track_id)

        for track_id in to_delete:
            del self.tracks[track_id]

        return updated_tracks, new_tracks

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

        # NEW
        self.tracker = ObjectTracker(
            max_distance=60,
            max_missed_frames=20
        )

    def process(self, frame: np.ndarray):
        """
        Args:
            frame (np.ndarray): RGB image

        Returns:
            processed_frame (np.ndarray)
            detections (list)
        """

        h, w = frame.shape[:2]

        detections = []

        # Default output = input frame copy
        output_frame = frame.copy()

        self.frame_counter += 1

        # Run detection only every N frames
        if self.frame_counter % self.frame_rate != 0:
            return output_frame, self.last_results

        # Run YOLO inference
        results = self.model(frame, verbose=False)[0]


        raw_detections = []

        for box in results.boxes:
            confidence = float(box.conf[0])
            # print("Confidence: ", confidence, self.conf_threshold)
            if confidence < self.conf_threshold:
                continue

            class_id = int(box.cls[0])

            # safety check
            # print("class_id", class_id, len(self.classes))

            if class_id >= len(self.classes):
                class_name = str(class_id)
            else:
                class_name = self.classes[class_id]

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            x1 = max(0, x1)
            y1 = max(0, y1)

            x2 = min(w, x2)
            y2 = min(h, y2)

            bbox_crop = frame[y1:y2, x1:x2].copy()

            detection = {
                "msg_type": "ANNOTATION",
                "class": class_name,
                "confidence": confidence,
                "bbox": [x1, y1, x2, y2],
                "timestamp": time.time(),
                "bbox_image": bbox_crop
            }

            raw_detections.append(detection)


        # Track objects
        updated_tracks, new_tracks = self.tracker.update(raw_detections)

        for track in new_tracks:
            x1, y1, x2, y2 = track.bbox

            # Emit only ONCE
            if not track.reported:
                detection = {
                    "msg_type": "ANNOTATION",
                    "track_id": track.id,
                    "class": track.class_name,
                    "bbox": [x1, y1, x2, y2],
                    "timestamp": time.time()
                }
                detections.append(detection)

                track.reported = True

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
