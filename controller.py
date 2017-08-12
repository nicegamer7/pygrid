import time
import threading
import datetime
from collections import OrderedDict

import PyQt5.QtCore as QtCore
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QEvent

from hardware import NZXTGrid, Hamon, Signal
from settings import AppSettings
from util import timediff


class Controller(QThread):
    """Polls data from Hardware Monitor and Grid, applies control policy to fans, emits update signal to UI."""       
    ok = True
    errorMessage = ""
    appsettings = None
    settingsTS = datetime.datetime(year=1900, month=1, day=1)   # current timestamp of settings
    
    current_fan_speed = []    # holds latest uploaded fan speeds. Init to -1 to ensure first write-through
    new_fan_speed     = []    # if new values are same as current, no updates are sent to Grid
    movingaverage     = []
    hysteresis        = []
    signals           = None

    uiUpdate = pyqtSignal(dict, name="uiUpdateSignal")
    enableUICallbacks = False

    grid = None
    hamon = None
    shutdown = False    # shutdown is requested by the UI thread


    def __init__(self, appsettings):
        QThread.__init__(self)
        self.appsettings = appsettings


    def _err(self, errtext):
        if self.ok: self.errorMessage = ""
        if (self.errorMessage != ""): self.errorMessage += "\n"
        self.errorMessage += errtext
        print (errtext)
        self.ok = False


    def run(self):
        """threadproc"""
        self.hamon = Hamon()
        self.grid = NZXTGrid()
        print ("Controller has started")

        TIME_SLICE = 1000         # sampling period, msec
        MAX_SLEEP = 250           # max sleep interval (sleep in smaller intervals, makes UI more responsive)
        counter = 0
        td = timediff()
        while not self.shutdown:
            td.reset()
            self.dowork()   # do all controller stuff, once per time slice
            td.now()
            exec_time = td.ms
            remaining = TIME_SLICE
            sleep_count = 0
            while remaining > 0:
                if self.shutdown or self.settingsTS < self.appsettings.timestamp: break    # early exit if needed
                td.now()
                remaining = TIME_SLICE - td.ms
                if (remaining > MAX_SLEEP): remaining = MAX_SLEEP
                if (remaining > 0): 
                    time.sleep(remaining / 1000.0)
                    sleep_count += 1

            td.now()
            slice_time = td.ms
            #print ("loop={0}, exec={1}, slice={2}, sleep count={3}".format(counter, exec_time, slice_time, sleep_count))
            counter += 1
            
        self.grid.close()
        self.hamon.close()
        print ("Controller has stopped")


    def stop(self):
        self.shutdown = True
        self.wait()


    def dowork(self):
        """Fan controller logic"""
        self.ok = True   # reset prior errors

        NFANS = NZXTGrid.NUM_FANS

        # in terms of race conditions we can only clash with the UI on settings update, so we need a lock:
        with self.appsettings.lock:
            settings = self.appsettings.settings

            # check if settings have been changed based on timestamps
            reset = self.settingsTS < self.appsettings.timestamp

            # if grid is not responding, retry opening port. This also allows to unplug the grid and plug it back at any time
            reset = reset or not self.grid.ok
            if (reset):
                #print("Resetting controller...")
                port = settings["grid"]["port"]
                self.grid.close()
                self.grid.open(port)
                if self.grid.ok: self.grid.hello()

                # create fan speed caches
                self.current_fan_speed = [-1] * (NFANS+1)   # reset caches
                self.new_fan_speed     = [0]  * (NFANS+1)

                # create moving average filters
                mavalue = settings["policy"]["movingaverage"]
                self.movingaverage = [ MovingAverage(mavalue) for i in range(0, NFANS) ]

                # create hysteresis filters
                hystvalue = settings["policy"]["hysteresis"]
                self.hysteresis = [ Hysteresis(hystvalue) for i in range(0, NFANS) ]

                # create list of signal objects from settings
                signaldefs = settings["signals"]
                self.signals = OrderedDict()
                for sname in signaldefs.keys():
                    s = signaldefs[sname]
                    sig = Signal(sname, s["fn"], s["sensors"])
                    self.signals[sname] = sig

                # save the timestamp of newest settings to track further changes
                self.settingsTS = self.appsettings.timestamp

            # get recent readings from hardware monitor and apply control policy
            self.hamon.update()
            if self.hamon.ok:
                self.hamon.updateSignals(self.signals)

            if (self.hamon.ok and self.grid.ok): 
                self.control()

        # pack data into a dict for visualization, emit signal to UI
        #self.enableUICallbacks = True
        if self.enableUICallbacks:
            fans = []
            if (self.grid.ok): fans = self.grid.poll(pollrpm=True, pollvoltage=True, pollamperage=False)
            signalData = {
                "sensors": self.hamon.sensors, "signals": self.signals,
                "fans": fans, "fanspeed": self.current_fan_speed[1:NFANS+1]
            }
            self.uiUpdate.emit(signalData)
            

    def control(self):
        """Loops through all fans, applies control policy to each, sends updates to Grid"""
        settings = self.appsettings.settings

        # for each fan, apply control policy to determine the new fan speed
        for f in range(1, NZXTGrid.NUM_FANS+1):
            policy = settings["policy"]["fan{}".format(f)]
            self.new_fan_speed[f] = self.control_fan(f, policy)

        # apply changes: we only send new data to Grid. No changes to RPM - no command issued
        # this means almost 100% of the time there is no traffic on the COM port
        writethrough = False
        writethrough = self.appsettings.gridstats    # true for debugging
        for f in range(1, NZXTGrid.NUM_FANS+1):
            speed = self.new_fan_speed[f]
            if (self.current_fan_speed[f] != speed or writethrough):
                self.grid.setfanspeed(f, speed)
                # for some reason occasionally (once in ~10000 commands) grid will fail to respond and produce an error
                # we will try to reestablish communication with the controller and will update RPMs during the next cycle
                if (not self.grid.ok): break
                # update the cache only if fan speed update was successful
                self.current_fan_speed[f] = speed


    def control_fan(self, fanindex, policy):
        """Applies control policy to a given fan, fanindex starts with 1, returns new speed in [0..100] range """
        speed = 0
        mode = policy["mode"].lower()

        if (mode == "off" or mode == ""):
            pass

        elif (mode == "manual" or mode == "m"):
            manual_speed_str = policy["speed"]
            try: speed = float(manual_speed_str)
            except Exception as e: pass

        elif (mode == "auto" or mode == "a"):
            curve = policy["curve"]
            signal_name = policy["signal"].lower()

            temp = 100   # if no matching singnal is found, assume the system is rather hot than cold.
            if (signal_name in self.signals):
                signal = self.signals[signal_name]
                temp = signal.value
            elif (signal_name == ""):
                temp = 0
            else:
                self._err("Signal '{0}' is used for fan{1} but is not defined in settings.".format(signal_name, fanindex))
            orig_temp = temp

            # apply signal filters:
            temp = self.movingaverage[fanindex-1].apply(temp)
            temp = self.hysteresis[fanindex-1].apply(temp)

            tempA, speedA = (temp, 0)  # zero default speed if the curve is empty
            tempB, speedB = (temp, 0)
            
            # find two points on the curve to the left and to the right of the current temp
            for i in range(0, len(curve)):
                c = curve[i]
                if c[0] <= temp:
                    tempA, speedA = c
                    if i < len (curve)-1:
                        tempB, speedB = curve[i+1]
                    else:
                        tempB, speedB = (temp, speedA)

            # linear interpolation between two points:
            t = 0
            if (tempB != tempA): t = (temp - tempA) / (tempB - tempA)
            speed = (1 - t) * speedA + t * speedB

            #print ("temp={0}, hist={1}, tempA={2}, speedA={3}, tempB={4}, speedB={5}, speed={6}".format(orig_temp, temp, tempA, speedA, tempB, speedB, speed))

        #final check of speed correctness
        speed = int(speed)
        if (speed < 0): speed = 0
        elif (speed > 100): speed = 100
        return speed



class MovingAverage():
    """Moving Average filter"""

    init = False
    numsamples = 0
    recent = []
    position = 0

    def __init__(self, numsamples=1):
        if (numsamples < 1): numsamples = 1
        self.numsamples = numsamples

    def apply(self, value):
        _value = value

        if (not self.init):
            self.recent = [value] * self.numsamples  #set all recent samples to the current value
            self.init = True

        self.recent[self.position] = value
        self.position = (self.position + 1) % self.numsamples

        if (self.numsamples > 1):
            _value = sum(self.recent) / float(self.numsamples)

        #print ("value={}, ma={}, position={}, numsamples={}".format(value, _value, self.position, self.numsamples))
        return _value



class Hysteresis():
    """Hysteresis filter"""

    init = False
    hystvalue = 0
    lower = 0
    upper = 0
    latest = 0

    def __init__(self, hystvalue):
        self.hystvalue = hystvalue

    def apply(self, value):
        _value = value
        if (self.hystvalue > 0):
            if (not self.init):   # initialize bounds
                self.lower = value
                self.upper = value
                self.latest = value
                self.init = True

            _value = value
            # check if value is outside bounds, update bounds if needed
            if (value >= self.upper):
                self.upper = value
                self.latest = value
                # push the lower bound upwards if the upper bound has moved:
                if (self.upper - self.lower > self.hystvalue): self.lower = self.upper - self.hystvalue
            elif (value <= self.lower):
                self.lower = value
                self.latest = value
                # drag the higher bound down if the lower bound has moved:
                if (self.upper - self.lower > self.hystvalue): self.upper = self.lower + self.hystvalue
            else:
                # if value does not move the boundaries, return the latest one that moved
                _value = self.latest
        #print ("value={}, hyst={}, lower={}, upper={}, latest={}".format(value, _value, self.lower, self.upper, self.latest))
        return _value

