import sys, os, inspect
import datetime
import threading
import winreg
import json
from collections import OrderedDict

from prettyjson import prettyjson
from hardware import list_comports, NZXTGrid, Hamon
from util import StrStream



class AppSettings():
    """ Holds application settings, saves/read them from file, provides default settings if the file is missing"""
    scriptpath = ""    
    settings = {}    # dictionary with all settings
    gridstats = False

    ok = True           # True if all settings are valid and complete
    errorMessage = ""   # if ok=False, contains error description
    lock = threading.Lock()
    timestamp = datetime.datetime.now()     # last time settings have been updated. Used for change tracking

    # Python 3.6 maintains order of entries in the dictionary.
    # In Python 3.5 we needs to use an OrderedDict wrapper, otherwise JSON serialization will be unordered
    # https://stackoverflow.com/questions/10844064/items-in-json-object-are-out-of-order-using-json-dumps    
    
    default_settings_txt = """{
            "grid": {"port": "%PORT%"},
            "policy": {
                "movingaverage": 5,
                "hysteresis": 5,
                "fan1": {
                    "name": "fan1", "signal": "cpu", "mode": "auto", "speed": 100,
                    "curve": [[0, 75], [65, 75], [75, 100]]
                },
                "fan2": {
                    "name": "fan2", "signal": "cpu", "mode": "auto", "speed": 100,
                    "curve": [[0, 75], [65, 75], [75, 100]]
                },
                "fan3": {
                    "name": "fan3", "signal": "cpu", "mode": "auto", "speed": 100,
                    "curve": [[0, 75], [65, 75], [75, 100]]
                },
                "fan4": {
                    "name": "fan4", "signal": "cpu", "mode": "auto", "speed": 100,
                    "curve": [[0, 75], [65, 75], [75, 100]]
                },
                "fan5": {
                    "name": "fan5", "signal": "cpu", "mode": "auto", "speed": 100,
                    "curve": [[0, 75], [65, 75], [75, 100]]
                },
                "fan6": {
                    "name": "fan6", "signal": "cpu", "mode": "auto", "speed": 100,
                    "curve": [[0, 75], [65, 75], [75, 100]]
                }
            },
            "signals": {
            },
            "app": {
                "startwithwindows": true, "startminimized": false, "closetotray": true
            }
        }"""


    def __init__(self):
        """Loads settings from file, if file does not exist, inits with default settings and saves file"""
        self.scriptpath = self.get_script_dir()
        self.path = self.scriptpath + "\\pygrid.json"
        self.ok = True
        print ("Loading settings from {0}".format(self.path))
        useDefault = False
        try:
            with open(self.path, "r") as f:
                jsontxt = f.read()
        except Exception as e:
            useDefault = True

        if (useDefault):
            print ("Failed to load user settings, using default")
            jsontxt = self.default_settings_txt

        self.parse(jsontxt, save=useDefault)


    def _err(self, errtext):
        if self.ok: self.errorMessage = "Settings have errors:"
        if (self.errorMessage != ""): self.errorMessage += "\n"
        self.errorMessage += "  " + errtext
        print (errtext)
        self.ok = False


    def parse(self, jsontxt, save=False):
        """Parses settings from json source"""
        self.ok = True
        s = {}

        try:
            jsonlines = jsontxt.splitlines()
            s  = json.loads(jsontxt, object_pairs_hook=OrderedDict)     # Py3.6:  s = json.loads(jsontxt)
        except json.JSONDecodeError as je:
            line = str(jsonlines[je.lineno-1])
            line = line[0:-2]
            self._err("JSON error: '{0}'\n{1}".format(line, str(je)))

        # check semantics if parsing is OK
        if (self.ok): self.check(s)

        # add missing items to the default settings: port, signals
        if (self.ok):
            # fill in port:
            port = s["grid"]["port"]
            if (port == "%PORT%"):
                port = "N/A"
                # select the first COM port from the list. Assume this is NZXT Grid
                ports = list_comports()
                if len(ports)>0:
                    device, description, hardwareID = ports[0]
                    port = device
                s["grid"]["port"] = port
                save = True

            # add signals:
            signals = s["signals"]
            if len(signals) == 0:
                hamon = Hamon()
                hamon.update()
                
                if hamon.ok:
                    sensors = hamon.createSignal("CPU")
                    signal = OrderedDict()
                    signal["fn"] = "max"
                    signal["sensors"] = sensors
                    signals["cpu"] = signal

                    sensors = hamon.createSignal("GPU")
                    signal = OrderedDict()
                    signal["fn"] = "max"
                    signal["sensors"] = sensors
                    signals["gpu"] = signal

                    hamon.close()
                    save = True


        # make new settings current if all checks are OK
        if (self.ok): 
            with self.lock:
                self.settings = s
                self.timestamp = datetime.datetime.now()
            if (save):
                jsontxt = self.getjson()    # re-render from dictionary
                with open(self.path, "w") as f:
                    f.write(jsontxt)

        if (self.ok):
            startwithwindows = self.settings["app"]["startwithwindows"]
            self.updateAutoStart(startwithwindows)  # add/remove registrty record for application auto-start
                    

    def check(self, s):
        """Checks semantics: all keys must be present and contain values of correct types"""
        if self.require(s, "root", "app", dict):
            _app = s["app"]
            self.require(_app, "app", "startwithwindows", bool)
            self.require(_app, "app", "startminimized", bool)
            self.require(_app, "app", "closetotray", bool)

        if self.require(s, "root", "grid", dict):
            _grid = s["grid"]
            self.require(_grid, "grid", "port", str)

        if self.require(s, "root", "policy", dict):
            _policy = s["policy"]
            self.require(_policy, "policy", "hysteresis", int)
            self.require(_policy, "policy", "movingaverage", int)

            for f in range (1, NZXTGrid.NUM_FANS+1):
                fanid = "fan{}".format(f)
                if self.require(_policy, "policy", fanid, dict):
                    _fan = _policy[fanid]
                    self.require(_fan, fanid, "name", str)
                    if self.require(_fan, fanid, "mode", str):
                        _mode = _fan["mode"].lower()
                        if (not _mode in ["off", "manual", "auto", "", "m", "a"]):
                            self._err("{0}.mode must be 'off', 'manual' or 'auto'".format(fanid))
                        else:
                            s["policy"][fanid]["mode"] = _mode   # ensure lowercase
                    if self.require(_fan, fanid, "signal", str):
                        s["policy"][fanid]["signal"] = _fan["signal"].lower()   # ensure lowercase
                    self.require(_fan, fanid, "speed", int)       # [0...100] - checked by controller
                    if self.require(_fan, fanid, "curve", list):
                        _curve = _fan["curve"]
                        for c in range (0, len(_curve)):
                            if self.require(_curve, "curve", c, list):
                                ci = _curve[c]
                                self.require(ci, "{0}.curve[{1}]".format(fanid, c), 0, int)    # [0..100]
                                self.require(ci, "{0}.curve[{1}]".format(fanid, c), 1, int)    # [0..100] - checked by controller

                    if self.ok:
                        #sort curve data by temperature
                        _curve = sorted(_curve, key = lambda x: (x[0]))
                        s["policy"][fanid]["curve"] = _curve

            if self.require(s, "root", "signals", dict):
                _signals = s["signals"]
                for sig in _signals.keys():
                    if self.require(_signals, "signals", sig, dict):
                        _signal = _signals[sig]
                        if self.require(_signal, "signals['{0}']".format(sig), "fn", str):
                            _fn = _signal["fn"].lower()
                            if (not _fn in ["max", "avg"]):
                                self._err("signals['{0}'].fn must be 'max' or 'avg'".format(sig))
                            else:
                                s["signals"][sig]["fn"] = _fn   # ensure lowercase
                            
                        if self.require(_signal, "signals['{0}']".format(sig), "sensors", list):
                            _sensors = _signal["sensors"]
                            for sens in range (0, len(_sensors)):
                                self.require(_sensors, "signals['{0}'].sensors".format(sig), sens, str)
                if (self.ok):
                    _signalsLower = OrderedDict()
                    for sig in _signals.keys():
                        _signalsLower[sig.lower()] = _signals[sig]
                    s["signals"] = _signalsLower



    def require(self, obj, dictname, key, valuetype):
        res = True
        keyexists = False
        if (isinstance(obj, dict)): keyexists = key in obj
        if (isinstance(obj, list)): keyexists = key >= 0 and key < len(obj)

        if not keyexists:
            self._err("The field '{0}' is missing in '{1}'".format(str(key), dictname))
            res = False
        else:
            item = obj[key]
            if not isinstance(item, valuetype):
                self._err("The field '{0}[{1}]' is expected to be of type '{2}'".format(dictname, str(key), str(valuetype.__name__)))
                res = False
        return res

    def getjson(self):
        return prettyjson(self.settings, maxlinelength=45)




    """Set application to auto-start with Windows by making appropriate registry changes:"""

    REG_PATH = "Software\Microsoft\Windows\CurrentVersion\Run"
    REG_VALUE = "pygrid"

    def updateAutoStart(self, startwithwindows):
        if (startwithwindows): 
            self.windowsStartAdd()
        else: 
            self.windowsStartRemove()


    # https://stackoverflow.com/questions/15128225/python-script-to-read-and-write-a-path-to-registry
    def windowsStartAdd(self):
        exepath = self.scriptpath + "\\pygrid.exe"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        registryNeedsUpdate = True
        try:
            value, regtype = winreg.QueryValueEx(key, self.REG_VALUE)
            if value == exepath: registryNeedsUpdate = False
        except:
            pass
        if (registryNeedsUpdate): 
            # set value if it is absent in the registry or if its value points to a wrong path
            winreg.SetValueEx(key, self.REG_VALUE, 0, winreg.REG_SZ, exepath)
    

    def windowsStartRemove(self):
        # delete registry value, ignore exception if the value is not there
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.REG_PATH, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        try:
            winreg.DeleteValue(key, self.REG_VALUE)
        except:
            pass


    # https://stackoverflow.com/questions/5137497/find-current-directory-and-files-directory
    # https://stackoverflow.com/questions/3718657/how-to-properly-determine-current-script-directory-in-python
    def get_script_dir(self, follow_symlinks=True):
        if getattr(sys, 'frozen', False): # py2exe, PyInstaller, cx_Freeze
            path = os.path.abspath(sys.executable)
        else:
            path = inspect.getabsfile(self.get_script_dir)
        if follow_symlinks:
            path = os.path.realpath(path)
        return os.path.dirname(path)

