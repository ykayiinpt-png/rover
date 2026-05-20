import logging
import multiprocessing
import subprocess
import time

import cv2
import numpy as np

from libs.tencent_ncnn.src.inference.detector import ObjectDetector
from src.raspberry.config import Config
from src.raspberry.video.pipeline import ObjectDetectionPipeline, ObjectDetectionPipelineNcnn, ObjectDetectionPipelineNcnnTwo


class CameraProcess(multiprocessing.Process):
    """
    A multiprocessing-based camera pipeline for real-time video processing
    and RTP streaming.

    This process launches and manages two external subprocesses:

    1. `libcamera-vid`
       Captures MJPEG video frames from the camera and streams them
       through stdout.

    2. `ffmpeg`
       Receives processed raw video frames through stdin and publishes
       them as an RTP video stream for remote clients.

    Between these two subprocesses, frames are decoded and processed
    using OpenCV. This processing stage can be extended to include
    computer vision or AI-based inference tasks such as object detection,
    tracking, or image enhancement.

    Workflow:
        Camera -> libcamera-vid -> OpenCV processing -> ffmpeg -> RTP stream

    Attributes:

        stop_event (multiprocessing.Event):
            Synchronization event used to gracefully stop the process.
    """
    
    def __init__(self, cam_cmd: str, ffmpeg_cmd: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.stop_event = multiprocessing.Event()
        
        self.cam_cmd = cam_cmd
        self.ffmpeg_cmd = ffmpeg_cmd
        self.cam_subprocess = None
        self.ffmpeg_subprocess = None 

        # self.cam_cmd = [
        #     "libcamera-vid",
        #     "-t", "0",
        #     "--codec", "mjpeg",
        #     "--width", "320",
        #     "--height", "240",
        #     "--framerate", "30",
        #     "--nopreview",
        #     "-o", "-"
        # ]
        
        # self.ffmpeg_cmd = [
        #     "ffmpeg",

        #     "-f", "rawvideo",
        #     "-pix_fmt", "bgr24",
        #     "-s", "3200x240",
        #     "-r", "30",
        #     "-i", "-",

        #     "-an",
        #     "-c:v", "libx264",
        #     "-preset", "ultrafast",
        #     "-tune", "zerolatency",

        #     "-f", "rtp",
        #     f"rtp://{self.rtp_ip}:{self.rtp_port}"
        # ]
        
        # Config
        self.cfg = Config()
        
        # Pipelines
        self.pipeline_object_detection = ObjectDetectionPipeline(
            classes=self.cfg.video.pipelines.object_detection.classes,
            conf_threshold=self.cfg.video.pipelines.object_detection.confidence.threshold,
            draw_boxes=self.cfg.video.pipelines.object_detection.draw_boxes,
            frame_rate=self.cfg.video.pipelines.object_detection.frame.rate,
            model_name=self.cfg.video.pipelines.object_detection.model.name,
        )
        
        # self.pipeline_object_detection_ncnn = ObjectDetectionPipelineNcnn(
        #     bin_path=self.cfg.video.pipelines.object_detection_ncnn.bin_path,
        #     input_name=self.cfg.video.pipelines.object_detection_ncnn.input_name,
        #     output_name=self.cfg.video.pipelines.object_detection_ncnn.output_name,
        #     param_path=self.cfg.video.pipelines.object_detection_ncnn.param_path,
        #     classes=self.cfg.video.pipelines.object_detection_ncnn.classes,
        #     conf_threshold=self.cfg.video.pipelines.object_detection_ncnn.confidence.threshold,
        #     draw_boxes=self.cfg.video.pipelines.object_detection_ncnn.draw_boxes,
        #     frame_rate=self.cfg.video.pipelines.object_detection_ncnn.frame.rate
        # )
        
        
        # detector = ObjectDetector(
        #     bin_path=self.cfg.video.pipelines.object_detection_ncnn.bin_path,
        #     param_path=self.cfg.video.pipelines.object_detection_ncnn.param_path,
        #     architecture="yolov8",
        #     target_size=320,
        #     num_threads=4,
        #     use_vulkan=False
        # )
            
        # self.pipeline_object_detection_ncnn = ObjectDetectionPipelineNcnnTwo(
        #     object_detector=detector,
        #     classes=self.cfg.video.pipelines.object_detection_ncnn.classes,
        #     frame_rate=5,
        #     draw_boxes=True
        # )
        
    def main(self):
        self.cam_subprocess = subprocess.Popen(
            self.cam_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0
        )
        logging.info("[CameraProcess] Camera subprocess started")
        
        self.ffmpeg_subprocess = subprocess.Popen(self.ffmpeg_cmd, stdin=subprocess.PIPE)
        logging.info("[CameraProcess] FFmpeg subprocess started")
        
        buffer = b""
        prev_time = time.time()
        fps = 0.0
        frame_count = 0

        while not self.stop_event.is_set():
            buffer += self.cam_subprocess.stdout.read(4096)

            a = buffer.find(b'\xff\xd8')
            b = buffer.find(b'\xff\xd9')

            if a == -1 or b == -1:
                continue

            jpg = buffer[a:b+2]
            buffer = buffer[b+2:]

            frame = cv2.imdecode(
                np.frombuffer(jpg, np.uint8),
                cv2.IMREAD_COLOR
            )

            if frame is None:
                continue
            
            frame_count += 1
            current_time = time.time()

            if current_time - prev_time >= 1.0:
                fps = frame_count / (current_time - prev_time)
                prev_time = current_time
                frame_count = 0

            # TODO: Run IA here to detect object
            #gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            #edges = cv2.Canny(gray, 100, 200)
            #processed = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            
            #result_frame = frame
            
            
            #if self.cfg.video.pipelines.object_detection.enabled:
            #    result_frame, objects = self.pipeline_object_detection.process(result_frame)
            #    print("Objects Yolo: ", objects)
            
            #if self.cfg.video.pipelines.object_detection_ncnn.enabled:
            #    print("I?")
            #    result_frame, objects = self.pipeline_object_detection_ncnn.process(result_frame)
            #    print("Objects Ncnn: ", objects)
            #    pass  
                
            
            
            #################""
            # Write FPS
            # text = f"FPS: {fps:.1f}"

            # font = cv2.FONT_HERSHEY_SIMPLEX
            # font_scale = 0.3
            # thickness = 1

            # (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)

            # x = frame.shape[1] - text_w - 10   # top-right padding
            # y = 30

            # cv2.putText(
            #     frame,
            #     text,
            #     (x, y),
            #     font,
            #     font_scale,
            #     (0, 255, 0),
            #     thickness,
            #     cv2.LINE_AA
            # )

            self.ffmpeg_subprocess.stdin.write(frame.tobytes())
        
        logging.info("[CameraProcess] Process ended")
        
    def run(self):
        try:
            self.main()
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            raise e
        
        
    
    def stop(self):
        logging.info("[CameraProcess] Stopping Camera Process")
        if self.stop_event.is_set():
            return
        
        self.stop_event.set()
        time.sleep(1)
        
        try:
            self.cam_subprocess.terminate()
            self.ffmpeg_subprocess.terminate()
            
            self.cam_subprocess.wait(3)
            self.ffmpeg_subprocess.wait(5)
            
            self.cam_subprocess.kill()
            self.ffmpeg_subprocess.kill()
        except:
            logging.exception("[CameraProcess] Exception While stopping")
            pass