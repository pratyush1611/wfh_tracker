# About: WFH tracker

I often forget to mark the days i worked from home, thus presenting an easy/lazy way to keep track of the days worked from home.
The code can be used to build an executable file for widnows which then spawns a widget which stays on the bottom-=most layer on the desktop.
There is a WFH button and a Office button which can be clicked to change the type of work done for the day. The backend uses sqlite database to keep track of the date and type of work.
Additionally the os env variable can be provided with the name of the WiFi SSID of the office wifi, which when detected (scans done every 30 min), sets the value of type of work in database to Office. 

# Setup

* make a venv using the requirements.txt file
* build the exe using:
`pyinstaller --noconfirm --onefile --windowed wfh_tracker.py`
* run the exe file, if you have preexisting sqlite db, place it with the exe or update the value in the empty one created when the exe is first executed.

