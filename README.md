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


## Central Paltform
- Ui
- RtcProcess for image processing
- SLAMProcess for computation on data

Schema
UI - Qthread(Controller) - Communication Channel - MultiProcessing