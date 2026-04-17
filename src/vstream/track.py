from fractions import Fraction
import logging

from aiortc import VideoStreamTrack
from av import VideoFrame
import cv2


class RtcTrack(VideoStreamTrack):
    """
    Track source for an RTC server
    """
    
    def __init__(self, camera_id=0):
        super().__init__()
        self.cap = cv2.VideoCapture(camera_id)
        self.frame_count = 0
        
        self.target_width = 1400
        self.target_height = 480
        
    async def recv(self):
        try:
            #print(f"Frame: {self.frame_count}")
            
            self.frame_count += 1
            ret, frame = self.cap.read()
            if not ret:
                logging.error("Can't read frame for video capture")
                return None
            
            img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            h, w, _ = img.shape

            # --- Logique de Crop "Cover" (Centré) ---
            target_ratio = self.target_width / self.target_height
            current_ratio = w / h

            if current_ratio > target_ratio:
                # Trop large : on coupe les côtés
                new_w = int(h * target_ratio)
                offset = (w - new_w) // 2
                img = img[:, offset:offset + new_w]
            else:
                # Trop haut : on coupe le haut et le bas
                new_h = int(w / target_ratio)
                offset = (h - new_h) // 2
                img = img[offset:offset + new_h, :]
                
            img = cv2.resize(img, (self.target_width, self.target_height), interpolation=cv2.INTER_AREA)
            

            frame_out = VideoFrame.from_ndarray(img, format="rgb24")
            frame_out.pts = self.frame_count
            frame_out.time_base = Fraction(1, 30)
            
            return frame_out
        except Exception as e:
            logging.error("Error occured while reading frame")
            print(e) # TODO: signal the error to parent
            return None