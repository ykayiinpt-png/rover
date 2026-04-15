pip install "av==14.4.0" --only-binary=:all: 


python main_rtc_server.py --host=0.0.0.0 --port=8000


## Central Paltform
- Ui
- RtcProcess for image processing
- SLAMProcess for computation on data

Schema
UI - Qthread(Controller) - Communication Channel - MultiProcessing