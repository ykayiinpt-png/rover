# Windows
pip install "av==14.4.0" --only-binary=:all: 


@deprecated
python main_rtc_server.py --host=0.0.0.0 --port=8000

Starts the video stream server
```
python main_vstream_ws_server.py --host=0.0.0.0 --port=8000
```

On the raspberry PI we have to run the main application
```bash
python main_raspberry.py --mqtt_host=0.0.0.0 --mqtt_port=8000
```

Start the ui application
```
python main_ui.py
```
We can obtain help by typing the command help
```bash
python main_ui.py --help
Setting event policy...
usage: main_ui.py [-h] [--ws_uri WS_URI] [--mqtt_host MQTT_HOST] [--mqtt_port MQTT_PORT]
                  [--feature {video,data,commands} [{video,data,commands} ...]]

optional arguments:
  -h, --help            show this help message and exit
  --ws_uri WS_URI       Host (e.g. http://127.0.0.1:8000)
  --mqtt_host MQTT_HOST
                        MQTT Host (e.g. 127.0.0.1)
  --mqtt_port MQTT_PORT
                        MQTT Port number (default: 1883)
  --feature {video,data,commands} [{video,data,commands} ...]
                        MQTT Port number (default: 1883)

```

Install package and ignore not compatible
```bash
python -c "import subprocess; [subprocess.run(['pip', 'install', line.strip()]) for line in open('requirements.txt') if line.strip() and not line.startswith('#')]"

```

Test remote connection ofrom raspberry pi to a remote
```
timeout 3 bash -c '</dev/tcp/192.168.1.100/80' && echo "Open" || echo "Closed"

```


## Central Paltform
- Ui
- RtcProcess for image processing
- SLAMProcess for computation on data

Schema
UI - Qthread(Controller) - Communication Channel - MultiProcessing

# Raspberry video stream 

uing RTSP
sudo apt install ffmpeg libcamera-apps v4l2loopback-dkms


Start the RSTP 
ffmpeg -rtsp_flags listen -i rtsp://0.0.0.0:8554/live -f null -


# Video Strealing

On raspberry 
```bash
python main_vstream_ws_server.py --io_host=192.168.137.1 --io_port=8000 --ws_uri=http://192.168.137.1:8000 --os=raspberry_pi --feature=video
```

On Windows
```bash
python main_vstream_ws_server.py --io_host=192.168.137.1 --io_port=8000 --ws_uri=http://192.168.137.1:8000 --feature=server
```