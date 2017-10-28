import sys
import datetime

# https://stackoverflow.com/questions/21341096/redirect-print-to-string-list
class StrStream():
    def __init__(self):
        self.data = ""

    def write(self, s):
        self.data += s

    def __enter__(self):
        sys.stdout = self
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        sys.stdout = sys.__stdout__  



class timediff():
    """Calculates the time difference in milliseconds between two timestamps"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.t1 = datetime.datetime.now()
        self.t2 = self.t1
        self._update()

    def now(self):
        self.t2 = datetime.datetime.now()
        self._update()

    def _update(self):
        self.delta = self.t2 - self.t1
        self.ms = int(self.delta.days*86400*1000000 + self.delta.seconds*1000000 + self.delta.microseconds)/1000

        self.milliseconds = self.ms - int(self.ms/1000)*1000
        self.seconds = int(self.ms/1000)
        self.minutes = 0
        self.hours = 0
        if (self.seconds > 60):
            self.minutes = int(self.seconds/60)
            self.seconds -= self.minutes * 60
        if (self.minutes > 60):
            self.hours = int(self.minutes/60)
            self.minutes -= self.hours * 60

        self.str = ""
        if (self.hours > 0): self.str += "{0} h ".format(self.hours)
        if (self.minutes == 0 and self.hours == 0):
            if (self.ms >= 1000):
                self.str += "{0:.1f} sec".format(self.ms/1000)
            else:
                self.str += "{0:3.0f} milliseconds".format(self.ms)
        else:
            self.str += "{0} m {1} s".format(self.minutes, self.seconds)

    def __str__(self):
        return self.str

    def __enter__(self):
        self.reset()
        return self

    def __exit__(self, ext_type, exc_value, traceback):
        self.now()

