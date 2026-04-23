import subprocess
import numpy as np
import cv2

cmd = [
    "libcamera-vid",
    "-t", "0",
    "--codec", "mjpeg",
    "--width", "320",
    "--height", "240",
    "-o", "-"
]

cmd = [
    "libcamera-vid",
    "-t", "0",
    "--codec", "mjpeg",
    "--width", "320",
    "--height", "240",
    "--nopreview",
    "-o", "-"
]

#proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)

proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    start_new_session=True
)

stream = b""

while True:
    stream += proc.stdout.read(1024)

    a = stream.find(b'\xff\xd8')  # JPEG start
    b = stream.find(b'\xff\xd9')  # JPEG end

    if a != -1 and b != -1:
        jpg = stream[a:b+2]
        stream = stream[b+2:]

        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)

        cv2.imshow("Stream", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

proc.kill()
cv2.destroyAllWindows()