import time
import numpy as np
import cv2
from ultralytics import YOLO
import ncnn

ncnn.set_omp_num_threads(1)

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
        results = self.model(frame, verbose=True)[0]
        print(results)

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



class ObjectDetectionPipelineNcnnTwo:
    def __init__(
        self,
        object_detector,
        classes,
        frame_rate: int = 5,
        draw_boxes: bool = True
    ):
        """
        Args:
            object_detector: instance of repo ObjectDetector
            classes: list of class names
            frame_rate: run inference every N frames
            draw_boxes: draw bounding boxes
        """

        self.detector = object_detector
        self.classes = classes
        self.frame_rate = frame_rate
        self.draw_boxes = draw_boxes

        self.counter = 0
        self.last_results = []

    def process(self, frame: np.ndarray):
        """
        Args:
            frame: BGR image (OpenCV)

        Returns:
            annotated_frame, detections_list
        """

        self.counter += 1

        # -----------------------------------
        # SKIP FRAMES (speed optimization)
        # -----------------------------------
        if self.counter % self.frame_rate != 0:
            return frame, self.last_results
        
        output_frame = frame.copy()

        # -----------------------------------
        # INFERENCE (NCNN via ObjectDetector)
        # -----------------------------------
        print("Inferencing...")
        detections = self.detector.detect(frame)
        print("Detections", detections)

        results = []
        print("Hiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiiii")

        for det in detections:
            # repo format:
            # det.label, det.score, det.x, det.y, det.w, det.h

            class_id = det.label
            confidence = float(det.score)

            class_name = (
                self.classes[class_id]
                if class_id < len(self.classes)
                else str(class_id)
            )

            x1 = int(det.x)
            y1 = int(det.y)
            x2 = int(det.x + det.w)
            y2 = int(det.y + det.h)

            results.append({
                "msg_type": "ANNOTATION",
                "class": class_name,
                "confidence": confidence,
                "timestamp": time.time()
            })

            # -----------------------------------
            # DRAW BOXES (optional)
            # -----------------------------------
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
                    (x1, max(20, y1 - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )

        self.last_results = results
        return output_frame, results


class ObjectDetectionPipelineNcnn(IaVisionPipeline):
    def __init__(
        self,
        param_path: str,
        bin_path: str,
        input_name: str,
        output_name: str,
        classes: list,
        frame_rate: int = 5,
        draw_boxes: bool = True,
        conf_threshold: float = 0.4,
        img_size: int = 640
    ):
        """
        NCNN YOLOv8 pipeline (Python API)

        Args:
            param_path: .param file
            bin_path: .bin file
            input_name: input blob name (e.g. "in0")
            output_name: output blob name (e.g. "out0")
            classes: class names
        """
        super().__init__(name="ObjectDetectionPipelineNcnn", key="object_detection_ncnn")

        self.param_path = param_path
        self.bin_path = bin_path
        self.input_name = input_name
        self.output_name = output_name

        self.classes = classes
        self.frame_rate = frame_rate
        self.draw_boxes = draw_boxes
        self.conf_threshold = conf_threshold
        self.img_size = img_size

        self.counter = 0
        self.last_results = []

        # Load NCNN model once
        self.net = ncnn.Net()
        self.net.load_param(param_path)
        self.net.load_model(bin_path)

    # -----------------------------
    # PREPROCESS
    # -----------------------------
    def _preprocess(self, frame):
        img = cv2.resize(frame, (self.img_size, self.img_size))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # NCNN expects CHW float32
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))

        return img

    # -----------------------------
    # MAIN PROCESS
    # -----------------------------
    def process(self, frame: np.ndarray):
        self.counter += 1

        output_frame = frame.copy()

        # frame skipping
        if self.counter % self.frame_rate != 0:
            return output_frame, self.last_results

        h, w = frame.shape[:2]

        detections = []

        img = self._preprocess(frame)
        print("Processed ....")

        with self.net.create_extractor() as ex:

            # INPUT
            ex.input(self.input_name, ncnn.Mat(img).clone())

            # OUTPUT
            _, out = ex.extract(self.output_name)

            out = np.array(out)

            # YOLOv8 NCNN format usually:
            # [x, y, w, h, conf, cls]

            for det in out:
                x, y, bw, bh, conf, cls_id = det[:6]

                if conf < self.conf_threshold:
                    continue

                cls_id = int(cls_id)
                class_name = (
                    self.classes[cls_id]
                    if cls_id < len(self.classes)
                    else str(cls_id)
                )

                # scale back to original image
                x1 = int(x * w / self.img_size)
                y1 = int(y * h / self.img_size)
                x2 = int((x + bw) * w / self.img_size)
                y2 = int((y + bh) * h / self.img_size)

                detection = {
                    "msg_type": "ANNOTATION",
                    "class": class_name,
                    "confidence": float(conf),
                    "timestamp": time.time()
                }

                detections.append(detection)

                # DRAW
                if self.draw_boxes:
                    cv2.rectangle(output_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    label = f"{class_name} {conf:.2f}"
                    cv2.putText(
                        output_frame,
                        label,
                        (x1, max(20, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2
                    )

        self.last_results = detections
        return output_frame, detections