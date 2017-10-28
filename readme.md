# PyGrid
PyGrid allows to control fan speeds using [NZXT Grid+ V2](https://www.nzxt.com/products/grid-plus-v2) device. PyGrid is a simple and stable alternative to NZXT CAM software when it comes to fan control.

<img src="https://github.com/andyatgh/pygrid/blob/master/screenshots/pygrid1.png">
<img src="https://github.com/andyatgh/pygrid/blob/master/screenshots/pygrid2.png" width="320">

## PyGrid key features
* Very simple interface, all settings are edited as text.
* The settings are saved to a file in the same folder as the app - easy to backup, so no need to edit fan curves from scratch if Windows is reinstalled or if a new system is built.
* Starts with Windows, acts as a tray icon application, minimal CPU footprint.
* Rich customization of temperature signals and fan curves allows lots of flexibility in fan control.

## Installation
1. Download and launch [Open Hardware Monitor](http://openhardwaremonitor.org/downloads/). Make sure it starts with Windows. PyGrid uses temperature data from OHM.
2. Download [PyGrid executable](https://github.com/andyatgh/pygrid/tree/master/dist) and launch it from any folder. The app will open and register itself for startup with Windows.
3. PyGrid will initialize the settings and create default fan curves for all fans - edit them in the Settings panel, setup other parameters the way you think is best for your system, hit Ctrl+Enter, settings will be saved and applied immediately.

<img src="https://github.com/andyatgh/pygrid/blob/master/screenshots/hamon1.png" width="320">
<img src="https://github.com/andyatgh/pygrid/blob/master/screenshots/pygrid3.png" width="320">


## PyGrid settings
The file format of the settings is JSON. The file contains the settings global to the app as well as individual parameters for each fan. Below is an example of settings with field descriptions in the comments.

    {
      "grid": {"port": "COM5"},      // COM port where Grid sits.
      "policy": {
        "movingaverage": 5,          // Use average temperature readings of the last N seconds
        "hysteresis": 5,             // React only when temperature moves opposite direction by at least N degrees
        "fan1": {
          "name": "CPU",             // The name of the fan that appears in the status panel
          "signal": "cpu",           // Temperature signal used to control this fan (see below)
          "mode": "auto",            // "auto" ("a"), "manual" ("m"), "off" ("")
          "speed": 100,              // fan speed [0..100] for manual mode
          "curve": [[0, 75], [65, 75], [75, 100]]    // fan curve for auto mode, value pairs: [temperature, speed]
        },
        ...
        "fan4": {
          "name": "",                // Use empty name to hide the fan from the status panel
          ... },
        "fan5": { ... },
        "fan6": { ... }
      },
      "signals": {                   // Signals combine temperature from sensors taking max or average of them
        "cpu": {                     // Signal name. Use those in fan.signal field.
          "fn": "max",               // "max" or "avg"
          "sensors": [
            "/intelcpu/0, CPU Core #1",   // Individual sensors, in this case one for each CPU core
            "/intelcpu/0, CPU Core #2",   // Writing simply "/intelcpu/0" will include all cores.
            "/intelcpu/0, CPU Core #3",
            "/intelcpu/0, CPU Core #4"
          ]
        },
        "gpu": {
          "fn": "max", "sensors": ["/nvidiagpu/0"]
        },
        "sys": {                     // An example of a signal that combines sensors from multiple devices
          "fn": "max",
          "sensors": ["/intelcpu/0", "/nvidiagpu/0"]   // all CPU cores of CPU0 and all GPU cores of GPU0
        }
      },
      "app": {
        "startwithwindows": true,    // Startup with Windows - can be switched on or off
        "startminimized": true,      // false by default, can be changed any time
        "closetotray": true          // Window 'Close' button acts as minimize
      }
    }

## Fan control modes
The fan can either be turned off (mode = "off"), set to manual (mode = "manual") or set to automatic control (mode = "auto"). When automatic control is enabled the app utilizes the fan curves to determine the fan speed for a given temperature.

A few examples of fan curves:

`[60, 75], [75, 100]]` - at 60 degrees spin-up the fan to 75% speed, between 60 and 75 degrees accelerate linearly to 100%, stay at 100% beyond 75 degrees.

`[[0, 75], [60, 75], [75, 100]]` - from 0 to 60 degrees keep 75% speed, then between 60 and 75 degrees accelerate linearly to 100%.

`[[0, 50], [60, 50], [60, 70], [75, 100]]` - from 0 to 60 degrees keep speed flat at 50%, at 60 deg. step change to 70%, and from 60 to 75 degrees keep accelerating linearly to 100%.

Note that all temperatures are in degrees Celsius.


## Design details
Every effort has been taken to make the app consume as few CPU cycles as possible:
* PyGrid minimizes the communication with the Grid controller and only sends new RPM settings when the fan speed actually needs to change.
* When PyGrid is minimized to tray, no RPM or voltage data is polled from Grid as those serve only for visualisation.

The above two tweaks actually make Grid communication overhead very light, which is different from CAM software where every second I observed heavy traffic to and from the controller.

One time-consuming operation that I was unable to optimize further is the communication with Open Hardware Monitor: temperature sensor polling takes approx. 40 milliseconds, and I suspect most of the time is spent in the inter-process communication layers of the OS.

PyGrid has been made resilient to external errors: if the app is unable to communicate with the Grid or with Open Hardware Monitor, it will keep retrying until communication is re-established. This allows to handle scenarios of Grid being unplugged and plugged back again, or Hardware Monitor being restarted - both events will have no effect on PyGrid continuous operation.

PyGrid registers itself in the Windows registry in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` which allows to launch the executable on user login. This is controlled by "startwithwindows" option in the settings. Changing this option to *false* removes the corresponding value from the registry.

## Known issues
The app itself is stable but I noticed two minor issues with the Grid hardware itself:
* RPM readings returned by Grid are not always correct, especially at lower speed. The controller may be wrong by a factor of 2x (return 1000 rpms instead of 500).
* Very rarely the controller may not execute the command given to it (setting fan speed may fail or data polling may not return voltage, rpm or amperage). It may stop responding for a few seconds and then come back to life. This will be properly handled by PyGrid which will reconnect to the device, but a brief warning message may be displayed in the Status panel.

## Build
The code works with Python 3.6 and 3.5. The executable was built with Pyinstaller 3.3 using Python 3.6. The basic dependencies were part of Anaconda distribution. The corresponding batch files for installing additional dependencies and building the executable are supplied with the source code.  Pyinstaller 3.3 has some issues handling PyQT dependencies, so one DLL had to be copied over to the dist directory in order for the app to start - this is done in the batch file as part of the build process.


## Acknowledgements
I would like to thank [akej74](https://github.com/akej74) and [RoelGo](https://github.com/RoelGo) for the awesome work they did in the similar projects and whose source code helped me understand the way Grid operates. Project references:
* [Grid Control](https://github.com/akej74/grid-control) by [akej74](https://github.com/akej74)
* [CamSucks](https://github.com/RoelGo/CamSucks) by [RoelGo](https://github.com/RoelGo)

# 
<img src="https://github.com/andyatgh/pygrid/blob/master/ui/img/icon.png" width="96">
