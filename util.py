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
    """Calculates the time difference in milliseconds between two time stamps"""
    def __init(self):
        self.reset()

    def reset(self):
        self.t1 = datetime.datetime.now()
        self.ms = 0

    def now(self):
        self.t2 = datetime.datetime.now()
        self.delta = self.t2 - self.t1
        self.ms = int(self.delta.days*86400*1000000 + self.delta.seconds*1000000 + self.delta.microseconds)/1000

