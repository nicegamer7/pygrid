import time
import math
import wmi
import threading
import serial
from serial.tools import list_ports
from pythoncom import CoInitialize, CoUninitialize


def list_comports():
    ports = sorted(list_ports.comports(), key = lambda x: (x[0]))
    return ports


class NZXTGrid():
    """ Provides low-level access to NZXT Grid """

    # NZXT Grid+ V2 accepts the following commands via a COM port, and returns the following values:
    # Command            command sequence (hex)      return sequence (hex)
    # Init:              C0                      ->  21
    # Set fan voltage:   44 XX C0 00 00 NN NN    ->  01 - success, (tbc: 02 - error)
    # Get fan voltage:   84 XX                   ->  C0 00 00 NN NN
    # Get fan amperage:  85 XX                   ->  C0 00 00 NN NN
    # Get fan RPM:       8A XX                   ->  C0 00 00 RR RR
    #
    # Parameters:
    #   XX:    fan ID         (01, 02, 03, 04, 05, 06)
    #   NN NN: volts/amperes  (07 50: 7.80V, 02 12: 2.18 amps)
    #   RR RR: RPM in HEX     (05 28: 05*256 + 40 = 1064 RPM)

    ok = True
    errorMessage = ""
    errorCount = 0
    writeCount = 0   # nr of fan voltage writes
    readCount = 0    # nr of reads (voltage, amperage, rpm)
    port = ""
    com = serial.Serial()
    lock = threading.Lock()

    NUM_FANS = 6

    def __init__(self):
        pass

    def open(self, port):
        """Opens communication with the Grid on a specified port (e.g. "COM5")"""
        print("Opening NZXT Grid at {}".format(port))
        self.ok = True   # reset errors of any
        try:
            self.port = port
            self.com.port = port
            self.com.baudrate = 4800    # this is the maximum supported baud rate, setting it higher will not work
            self.com.bytesize = serial.EIGHTBITS
            self.com.parity = serial.PARITY_NONE
            self.com.stopbits = serial.STOPBITS_ONE
            self.com.timeout = 0.1
            self.com.write_timeout = 0.1
            self.com.open()
            self.com.flushInput()
            self.com.flushOutput()
        except Exception as e:
            errtxt = e.args[0]
            if errtxt.find("FileNotFoundError") >= 0:
                self._err("Could not open port {0}. No device found.".format(port))
            elif errtxt.find("PermissionError") >= 0:
                self._err("Could not open port {0}. Access denied. The port may be in use by another application.".format(port))
            else:
                self._err(str(e))


    def close(self):
        if (not self.com.closed):
            self.com.close()


    def _err(self, errtext):
        if self.ok: self.errorMessage = ""
        self.errorMessage += "NZXT Grid error: " + errtext + "\n"
        print (errtext)
        self.ok = False
        self.errorCount += 1


    def _cmd(self, data, response_length=1):
        """Sends an arbitrary command to Grid and returns a response"""
        response = []
        try:
            with self.lock:
                bytes = serial.to_bytes(data)
                nbytes = self.com.write(bytes)
                response = self.com.read(size=response_length)
        except Exception as e:
            self._err ("Failed to send command to grid. {0}.".format(str(e)))
        return response


    def hello(self):
        """Handshake with the controller."""
        data = [0xC0]
        response = self._cmd(data, 1)
        if (not response or len(response) == 0):
            self._err ("No response from controller.")
        elif response[0] != int("0x21", 16):
            self._err ("Failed to establish comms with controller. Invalid response: {0}".format(str(response)))


    def setfanspeed(self, fanid, speed):
        """Sets speed in % for a given fanid.
           The speed % is mapped to fan voltage in the range of 0..12 Volts.
           40% is the mimimum to which Grid will react. 0% sets the fan speed to zero.
        """
        if speed > 100: speed = 100
        if speed < 40: speed = 0

        voltage = speed / 100.0 * 12                   # map speed to 12-volt range. 0V = 0%, 12V = 100%
        voltage_dec, voltage_int = math.modf(voltage)  # split voltage into integer and decimal part
        voltage_dec = voltage_dec / 10                 # double-digit decimal part is accepted by Grid. 11.50 = (11, 50)

        #TODO: check voltage granularity (steps of 0.5?)
        data = [0x44, fanid, 0xC0, 0x00, 0x00, int(voltage_int), int(voltage_dec)]
        response = self._cmd(data, 1)
        self.writeCount += 1
        if (not response or len(response) == 0):
            self._err ("Failed to set fan speed. No response from controller.")
        elif response[0] != int("0x01", 16):
            self._err ("Failed to set fan speed. Invalid response: {0}".format(str(response)))


    def poll(self, pollrpm=True, pollvoltage=True, pollamperage=True):
        """Returns fan voltage, amperage and RPM for all 6 fans"""
        # The process is slow due to low baud rate of the COM port.
        # Polling RPM, voltage and amperage for all 6 fans takes nearly 500 msec.
        fandata = []

        for fanid in range(1, NZXTGrid.NUM_FANS+1):
            voltage = 0
            amperage = 0
            rpm = 0

            if (pollrpm):
                cmd = [0x8A, fanid] # request RPM
                response = self._cmd(cmd, response_length=5)
                self.readCount += 1
                if response and len(response) == 5:
                    if (response[0]) == int("0xC0", 16) and (response[1]) == int("0x00", 16) and (response[2]) == int("0x00", 16):
                        rpm = int(response[3])*256 + int(response[4])
                else:
                    self._err ("Failed to receive RPM data from controller. Invalid response: {0}".format(str(response)))
                    break

            if (pollvoltage):
                cmd = [0x84, fanid] # request voltage
                response = self._cmd(cmd, response_length=5)
                self.readCount += 1
                if response and len(response) == 5:
                    if (response[0]) == int("0xC0", 16) and (response[1]) == int("0x00", 16) and (response[2]) == int("0x00", 16):
                        voltage = float(response[3]) + float(response[4])/100
                else:
                    print ("Failed to receive voltage data from controller. Invalid response: {0}".format(str(response)))
                    break

            if (pollamperage):
                cmd = [0x85, fanid] # request amperage
                response = self._cmd(cmd, response_length=5)
                self.readCount += 1
                if response and len(response) == 5:
                    if (response[0]) == int("0xC0", 16) and (response[1]) == int("0x00", 16) and (response[2]) == int("0x00", 16):
                        amperage = float(response[3]) + float(response[4])/100
                else:
                    self._err ("Failed to receive amperage data from controller. Invalid response: {0}".format(str(response)))
                    break

            fandata.append((fanid, rpm, voltage, amperage))

        return fandata



# WMI cookbook:
# http://timgolden.me.uk/python/wmi/cookbook.html

class Hamon():
    """Provides WMI interface to Libre Hardware Monitor and its temperature readings"""
    ok = True
    errorMessage = ""
    initialized = False
    hamon = None
    devicenames = []
    sensors = []

    def __init__(self):
        try:
            CoInitialize()
            self.hamon = wmi.WMI(namespace="root\LibreHardwareMonitor")
            self.initialized = True
        except Exception as e:
            self._err ("Error: Libre Hardware Monitor not installed.\nPlease install it and restart the application.")


    def _err(self, errtext):
        self.ok = False
        self.errorMessage = errtext
        print (errtext)


    def update(self):
        # run only if initialization was successful
        if (self.initialized):
            # it is possible that at boot time Libre Hardware Monitor starts later than the app,
            # so the sensor readings will not be available immediately - we need to retry until the monitor is loaded.
            self.ok = True  # reset error

            # request temperature sensor data, only request what's really needed - this is a slow operation:
            # the next one line consumes 95% of CPU time during each control cycle:
            _sensors = self.hamon.Sensor(["Parent", "Name", "Value"], SensorType="Temperature")

            # sort by parent and then by name
            _sensors = sorted(_sensors, key = lambda x: (x.Parent, x.Name))
            self.sensors = [Sensor(x) for x in _sensors]
            self.devicenames = set([x.parent for x in self.sensors])


    def createSignal(self, signature):
        """Returns a list of sensor names matching the required signature
           The signature is either "CPU" or "GPU" """
        res = []
        for device in self.devicenames:
            count = 0
            matches = 0
            deviceItems = []
            for s in self.sensors:
                if s.parent == device:
                    count += 1
                    if s.isMatch(signature):
                        deviceItems.append("{0}, {1}".format(s.parent, s.name))
                        matches += 1
            if count == matches:
                res.append(device)
                #res.append("{0}, *".format(device))
            else:
                res.extend(deviceItems)
        return res


    def updateSignals(self, signals):
        """Updates signal values in the supplied dictionary of signals"""
        totalsum = 0
        for sname in signals.keys():
            s = signals[sname]
            val = self.getSignalValue(s.fn, s.sensors)
            s.update(val)
            totalsum += val

        # if no readings were found assume Libre Hardware Monitor is not (yet) running
        if (totalsum == 0):
            self._err("The data from Libre Hardware Monitor is unavailable.\nPlease check if it is running.")


    def getSignalValue(self, fn, sensors):
        """Returns signal value for a given signal function (max, avg) and list of sensors"""
        count = 0
        max = 0
        avg = 0
        for s in sensors:
            parts = [x.strip() for x in s.split (",")]
            parts.append("")
            devicename = parts[0]
            sensorname = parts[1]
            if sensorname == "*": sensorname = ""
            for _s in self.sensors:
                if _s.parent == devicename and ( sensorname == "" or _s.name == sensorname):
                    val = _s.value
                    if (val > max): max = val
                    avg += val
                    count += 1

        res = max
        if (fn == "avg"): res = avg / float(count)
        return res


    def close(self):
        CoUninitialize()
        self.initialized = False



class Sensor():
    """Sensor value wrapper"""
    parent = ""
    name = ""
    value = 0

    def __init__(self, wmiSensor):
        self.parent = wmiSensor.Parent
        self.name = wmiSensor.Name
        self.value = wmiSensor.Value

    def isMatch(self, sig):
        return self.name.find(sig) >= 0

    def __repr__(self):
        return "<{0}, {1}, {2}>".format(self.parent, self.name, self.value)



class Signal():
    """Calculates and holds signal value"""
    name = ""
    fn = ""
    sensornames = []
    value = 0
    min = 0
    max = 0

    def __init__(self, name, fn, sensors):
        self.name = name
        self.fn = fn
        self.sensors = sensors

    def update(self, value):
        self.value = value
        if (self.min == 0): self.min = value
        if (self.max == 0): self.max = value
        if (value < self.min): self.min = value
        if (value > self.max): self.max = value

