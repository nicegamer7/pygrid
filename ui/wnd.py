# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'wnd.ui'
#
# Created by: PyQt5 UI code generator 5.6
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(831, 454)
        self.closeButton = QtWidgets.QPushButton(Dialog)
        self.closeButton.setGeometry(QtCore.QRect(10, 420, 75, 23))
        self.closeButton.setObjectName("closeButton")
        self.applyButton = QtWidgets.QPushButton(Dialog)
        self.applyButton.setGeometry(QtCore.QRect(740, 420, 75, 23))
        self.applyButton.setObjectName("applyButton")
        self.statusEdit = QtWidgets.QPlainTextEdit(Dialog)
        self.statusEdit.setGeometry(QtCore.QRect(10, 30, 391, 381))
        font = QtGui.QFont()
        font.setFamily("Consolas")
        font.setPointSize(9)
        font.setBold(True)
        font.setWeight(75)
        self.statusEdit.setFont(font)
        self.statusEdit.setUndoRedoEnabled(False)
        self.statusEdit.setReadOnly(True)
        self.statusEdit.setObjectName("statusEdit")
        self.settingsEdit = QtWidgets.QPlainTextEdit(Dialog)
        self.settingsEdit.setGeometry(QtCore.QRect(420, 30, 401, 381))
        font = QtGui.QFont()
        font.setFamily("Consolas")
        font.setPointSize(9)
        font.setBold(True)
        font.setWeight(75)
        self.settingsEdit.setFont(font)
        self.settingsEdit.setObjectName("settingsEdit")
        self.label = QtWidgets.QLabel(Dialog)
        self.label.setGeometry(QtCore.QRect(10, 10, 47, 13))
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(Dialog)
        self.label_2.setGeometry(QtCore.QRect(420, 10, 47, 13))
        self.label_2.setObjectName("label_2")
        self.clipboardButton = QtWidgets.QPushButton(Dialog)
        self.clipboardButton.setGeometry(QtCore.QRect(300, 420, 101, 23))
        self.clipboardButton.setObjectName("clipboardButton")
        self.label_3 = QtWidgets.QLabel(Dialog)
        self.label_3.setGeometry(QtCore.QRect(676, 421, 61, 20))
        palette = QtGui.QPalette()
        brush = QtGui.QBrush(QtGui.QColor(107, 107, 107))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Active, QtGui.QPalette.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(107, 107, 107))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Inactive, QtGui.QPalette.WindowText, brush)
        brush = QtGui.QBrush(QtGui.QColor(120, 120, 120))
        brush.setStyle(QtCore.Qt.SolidPattern)
        palette.setBrush(QtGui.QPalette.Disabled, QtGui.QPalette.WindowText, brush)
        self.label_3.setPalette(palette)
        self.label_3.setObjectName("label_3")
        self.portsandsensorscheckBox = QtWidgets.QCheckBox(Dialog)
        self.portsandsensorscheckBox.setGeometry(QtCore.QRect(185, 423, 101, 17))
        self.portsandsensorscheckBox.setObjectName("portsandsensorscheckBox")

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Dialog"))
        self.closeButton.setText(_translate("Dialog", "Exit"))
        self.applyButton.setText(_translate("Dialog", "Apply"))
        self.label.setText(_translate("Dialog", "Status"))
        self.label_2.setText(_translate("Dialog", "Settings"))
        self.clipboardButton.setText(_translate("Dialog", "Copy to clipboard"))
        self.label_3.setText(_translate("Dialog", "(Ctrl+Enter)"))
        self.portsandsensorscheckBox.setText(_translate("Dialog", "ports && sensors"))

