import os
import sys
import math

import PyQt5.QtCore as QtCore
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QObject, Qt, pyqtSignal, pyqtSlot, QEvent
from PyQt5.QtWidgets import QApplication, QMainWindow, QDialog, QSystemTrayIcon, QStyle, QAction, QMenu

from ui import resources
from ui.wnd import Ui_Dialog
from settings import AppSettings
from controller import Controller
from hardware import list_comports, NZXTGrid, Hamon
from util import StrStream


APP_TITLE = "PyGrid 0.98"


class MainWindow(QMainWindow):
    app = None
    appsettings = None
    controller = None
    apptrayicon = None

    COLOR_TXT = "color: rgb(20, 20, 20);"
    COLOR_ERR = "color: rgb(255, 32, 32);"


    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.app = app

        # Set up the user interface from Designer
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)

        # wire up the UI
        self.ui.closeButton.clicked.connect(self.closeapp)
        self.ui.applyButton.clicked.connect(self.applysettings)
        self.ui.clipboardButton.clicked.connect(self.copytoclipboard)
        self.ui.portsandsensorscheckBox.stateChanged.connect(self.toggleportsandsensors)

        self.apptrayicon = AppTrayIcon(self)
        self.apptrayicon.onHide.connect(self.onHide)
        self.apptrayicon.onRestore.connect(self.onRestore)

        self.ui.statusEdit.setStyleSheet(self.COLOR_TXT)
        self.ui.settingsEdit.setStyleSheet(self.COLOR_TXT)

        self.setWindowIcon(self.apptrayicon.icon)

        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(self.size())

        # application logic
        self.appsettings = AppSettings()
        jsontxt = self.appsettings.getjson()
        self.ui.settingsEdit.setPlainText(jsontxt)
        self.ui.settingsEdit.keyPressEvent = self.keyPressClosure(self.ui.settingsEdit)

        self.controller = Controller(self.appsettings)
        self.controller.uiUpdate.connect(self.update)

        startminimized = False
        if (self.appsettings.ok):  
            startminimized = self.appsettings.settings["app"]["startminimized"]
            self.controller.start()
        else:
            # there may be a case when json is manually edited and corrupted.
            # we cannot start normally in this case.
            with StrStream() as x:
                print("Error reading settings from file.\nFan control cannot start.")
                print()
                print(self.appsettings.errorMessage)
            self.ui.statusEdit.setStyleSheet(self.COLOR_ERR)
            self.ui.statusEdit.setPlainText(x.data)
            
        if (not startminimized): 
            self.show()
            self.controller.enableUICallbacks = True
            

    def keyPressClosure(self, uiControl):
        """Wraps event with a closure to avoid subclassing PlainTextEdit"""
        baseEvent = uiControl.keyPressEvent
        # apply settings on Ctrl+Enter
        def settingsKeyPressEvent(event):
            if (event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter) \
                and event.modifiers() & Qt.ControlModifier:
                self.applysettings()
            else:
                baseEvent(event)
        return settingsKeyPressEvent


    def changeEvent(self, event):
        # tracks mimimize/restore events
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                self.apptrayicon.minimizeToTray()
            elif event.oldState() & Qt.WindowMinimized:
                #print ("window restore event")
                self.onRestore()
        super().changeEvent(event)


    def closeEvent(self, event):
        closeToSystemTray = False
        if (self.appsettings.ok): closeToSystemTray = self.appsettings.settings["app"]["closetotray"]
        if (closeToSystemTray and not self.apptrayicon.closeConfirmed):
            # instead of closing the app minimize it to tray
            self.apptrayicon.minimizeToTray()
            event.ignore()
        else:
            # close app for real, cleanup on application exit
            self.controller.stop()
            event.accept()


    def onRestore(self):
        self.controller.enableUICallbacks = True
        txt = self.ui.statusEdit.toPlainText()
        if (txt == ""): self.ui.statusEdit.setPlainText("Updating status...")
        #print ("window restored/maximized/fullscreen")


    def onHide(self):
        self.controller.enableUICallbacks = False
        #print ("window minimized")


    def closeapp(self):
        # button pressed: close app
        self.apptrayicon.doClose()


    def toggleportsandsensors(self):
        self.ui.statusEdit.setPlainText("updating...")


    def copytoclipboard(self):
        # button pressed: copy to clipboard
        cb = self.app.clipboard()
        txt = self.ui.statusEdit.toPlainText()
        cb.setText(txt)
        self.ui.statusEdit.setPlainText("Copied to clipboard.")


    def applysettings(self):
        # button pressed: update settings
        jsontxt = self.ui.settingsEdit.toPlainText()
        self.ui.statusEdit.setStyleSheet(self.COLOR_TXT)
        self.ui.statusEdit.setPlainText("Updating settings...")
        # apply new settings and save to file if no errors
        self.appsettings.parse(jsontxt, save=True)


    def update(self, data):
        # Displays current status in the UI
        # Connected to the signal from the polling thread.
        # When the window is not mimimized, updates UI every 1000 ms
        sensors = data["sensors"]
        signals = data["signals"]
        fans = data["fans"]
        speed = data["fanspeed"]
        fannames = []
        for f in range (1, NZXTGrid.NUM_FANS+1):
            fan = self.appsettings.settings["policy"]["fan"+str(f)]
            fannames.append(fan["name"])

        with StrStream() as x:  # dump the current status into a string:
            err = False
            # if there are any errors, print the error messages instead of real-time data
            if (not self.appsettings.ok):
                err = True
                print(self.appsettings.errorMessage)
                print()
                print()
            if (not self.controller.ok):
                err = True
                print (self.controller.errorMessage)
                print()
                print()
            if (not self.controller.hamon.ok):
                err = True
                print (self.controller.hamon.errorMessage)
                print()
                print()
            if (not self.controller.grid.ok):
                err = True
                print (self.controller.grid.errorMessage)
                print()
                self.listports()

            if (not err):
                # print current status
                self.ui.statusEdit.setStyleSheet(self.COLOR_TXT)
                portsandsensors = self.ui.portsandsensorscheckBox.isChecked()
                if (portsandsensors):
                    self.listports()
                    self.printsensors(sensors)
                self.printsignals(signals)
                self.printfans(fannames, fans, speed)
                if (portsandsensors and self.appsettings.gridstats):
                    print("\nGrid reads: {0}, writes: {1}, errors: {2}".format(
                        self.controller.grid.readCount,
                        self.controller.grid.writeCount, 
                        self.controller.grid.errorCount))
            else:
                self.ui.statusEdit.setStyleSheet(self.COLOR_ERR)

        # Output rendered string to the UI
        self.ui.statusEdit.setPlainText(x.data)


    # Various functions for printing various data
    def listports(self):
        ports = list_comports()
        print ("COM ports on this computer:")
        for port in ports:
            device, description, hardwareID = port
            #print("  {:10}{:30}{:30}".format(device, description, hardwareID))
            print("  {:10}{:30}".format(device, description))
        if len(ports) == 0:
            print("  No ports detected")
        print ()


    def printsensors(self, sensors):
        print("Sensor readings (\u2103):")
        if len(sensors) == 0:
            print ("  No data available")
        else:
            for sensor in sensors:
                print("  {:20}{:20}{:>4.1f}".format(sensor.parent, sensor.name, sensor.value))
        print ()


    def printsignals(self, signals):
        print(u"Temperature signals (\u2103):")
        for sname in signals.keys():
            s = signals[sname]
            print("  {0} - {1:>4.1f}  [{2:>4.1f} .. {3:>4.1f}]".format(sname.upper(), s.value, s.min, s.max))
        if len(signals) == 0:
            print ("  No data available")
        print ()


    def printfans(self, fannames, fandata, speeddata):
        print ("Fans:")
        index = 0
        for d in fandata:
            fanid, rpm, voltage, amperage = d
            fanname = fannames[index]
            fanspeed = speeddata[index]
            if (fanname != ""):
                print ("  {0:14} {1:4.0f}% {2:7d} rpm {3:8.2f} V".format(fanname, fanspeed, rpm, voltage))  #amperage*1000
            index += 1
        if len(fandata) == 0:
            print("  No fan data available")



class AppTrayIcon(QObject):
    wnd = None
    icon = None
    trayicon = None

    onHide = pyqtSignal(dict, name="onHideToTray")
    onRestore = pyqtSignal(dict, name="onRestoreFromTray")

    def __init__(self, wnd):
        super(AppTrayIcon, self).__init__()
        self.wnd = wnd
        self.trayicon = QSystemTrayIcon(wnd)

        #self.trayicon.setIcon(wnd.style().standardIcon(QStyle.SP_ComputerIcon))
        APP_ICON = ":/icon.png"
        self.icon = QIcon(QPixmap(APP_ICON))
        self.trayicon.setIcon(self.icon)

        self.trayicon.setToolTip("{0}. Click to show/hide.".format(APP_TITLE))

        showhide_action = QAction("Show/Hide", wnd)
        quit_action = QAction("Exit", wnd)

        showhide_action.triggered.connect(self.toggleVisibility)
        quit_action.triggered.connect(self.doClose)

        tray_menu = QMenu()
        tray_menu.addAction(showhide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.trayicon.activated.connect(self.sysTrayIconActivated)
        self.trayicon.setContextMenu(tray_menu)
        self.trayicon.show()


    def sysTrayIconActivated(self, reason):
        # react on mouse left click
        if (reason == QSystemTrayIcon.Trigger):   # reason == QSystemTrayIcon.DoubleClick
            self.toggleVisibility()


    def toggleVisibility(self):
        if self.wnd.isVisible():
            self.minimizeToTray()
        else:
            self.restoreFromTray()


    def minimizeToTray(self):
        self.onHide.emit({})
        self.wnd.hide()


    def restoreFromTray(self):
        self.onRestore.emit({})
        self.wnd.setWindowState(self.wnd.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.wnd.show()
        self.wnd.activateWindow()


    # The "Exit" command has been selected from system tray menu: initiate applications shutdown
    closeConfirmed = False
    def doClose(self):
        self.trayicon.hide()
        self.closeConfirmed = True
        self.wnd.close()




""" Application startup """
def showGui():
    app = QApplication(sys.argv)
    wnd = MainWindow(app)
    sys.exit(app.exec_())   # QT message loop

def showConsole():
    appsettings = AppSettings()
    controller = Controller(appsettings)
    controller.start()
    pause()
    controller.stop()

def pause():
    module = __import__("os")
    module.system("pause")


if __name__ == '__main__':
    ui = True
    print(APP_TITLE)

    if (ui):
        showGui()
    else:
        showConsole()

