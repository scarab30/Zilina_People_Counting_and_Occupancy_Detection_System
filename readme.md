
# Žilinská univerzita v Žiline | People Counting and Occupancy Detection System Using the VL53L5CX ToF Sensor  | Internship | 

author : 
- Noah GALLOIS (FR)
- César CONSTANT (FR)

referee : 
- Lukáš Formanek
- Peter Šarafín

## Description of the project 

The aim of this project is to design and implement a privacy-preserving system for people counting and occupancy detection in indoor spaces. The system will be based on the ESP32 microcontroller and the VL53L5CX time-of-flight sensor, which provides an 8×8 distance matrix for spatial depth measurement.
The system will monitor a selected area, such as a doorway, corridor, or room entrance, and analyze changes in the distance map to detect the presence and movement of people. By evaluating movement direction and object position over time, the system will estimate entries and exits and determine the current occupancy of the monitored space.
Measured and processed data can be displayed through a web interface, where users will be able to view real-time occupancy status, people count statistics, and historical records. The system may also support configuration of detection parameters, such as distance threshold, monitoring zone, and counting sensitivity. This system can be used in smart buildings, classrooms, offices, laboratories, meeting rooms, or public spaces where it is useful to monitor occupancy without using cameras.

## Components & technologies used 

- Visual Studio Code / Pycharm
- Python 3.7+
- Node.js 14+
- npm 
- MicroPython (last version from 06/07/2026)
- ESP32-S3 XIAO
- VL53L5CX Sensor module (Satel)

## draft 

pour la librairie sensor module

``git pull https://github.com/mp-extras/vl53l5cx.git``

// ce mettre dans le folder du repo

``mpremote connect COM6 mkdir :lib``
``mpremote connect COM6 mkdir :lib/vl53l5cx``
``mpremote connect COM6 cp vl53l5cx/__init__.py :lib/vl53l5cx/__init__.py``
``mpremote connect COM6 cp vl53l5cx/_config_file.py :lib/vl53l5cx/_config_file.py``
``mpremote connect COM6 cp vl53l5cx/mp.py :lib/vl53l5cx/mp.py``
``mpremote connect COM6 cp vl53l5cx/vl_fw_config.bin :lib/vl53l5cx/vl_fw_config.bin``

COM6 = le port que l'on utilise (cf : ``mpremote connect list``)

