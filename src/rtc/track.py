import logging

from aiortc import VideoStreamTrack
import cv2


class RtcTrack(VideoStreamTrack):
    """
    Track source for an RTC server
    """
    
    def __init__(self, camera_id=0):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_id)
        
    def recv(self):
        try:
            ret, frame = self.cap.read()
            if not ret:
                logging.error("Can't read frame for video capture")
                return None
            
            return frame
        except Exception as e:
            logging.error("Error occured while reading frame")
            print(e) # TODO: signal the error to parent
            return None