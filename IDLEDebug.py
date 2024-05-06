import sys
from threading import Thread
from idlelib.pyshell import main
def Debug():
    sys.argv = ["", "-n"]
    t = Thread(target = main)
    t.start()
    return t
