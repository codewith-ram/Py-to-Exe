#!/usr/bin/env python3
"""
html_to_exe_converter.py
GUI to package a local HTML folder (or single HTML file) into a Windows .exe using PyInstaller
Requires: PyQt6, PyQt6-WebEngine, PyInstaller
Usage: python html_to_exe_converter.py
"""
import sys
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from PyQt6 import QtWidgets, QtGui, QtCore

APP_TITLE = "HTML → EXE Converter (PyInstaller + PyQt6-WebEngine)"

LAUNCHER_TEMPLATE = r'''# launcher.py - auto generated
import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QUrl
# QWebEngineWidgets is required
from PyQt6.QtWebEngineWidgets import QWebEngineView

def resource_path(rel_path: str) -> str:
    """Return absolute path to resource, works for dev and PyInstaller onefile/onedir."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return str(base / rel_path)

def main():
    app = QApplication(sys.argv)
    view = QWebEngineView()
    index = resource_path("{html_rel_path}")
    url = QUrl.fromLocalFile(index)
    view.setUrl(url)
    view.setWindowTitle("{window_title}")
    view.resize({width}, {height})
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
'''

class Worker(QtCore.QObject):
    output = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal(int)

    def __init__(self, cmd, cwd=None):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd

    @QtCore.pyqtSlot()
    def run(self):
        try:
            proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    universal_newlines=True, cwd=self.cwd, shell=False)
        except Exception as e:
            self.output.emit(f"Failed to start process: {e}")
            self.finished.emit(-1)
            return

        for line in proc.stdout:
            self.output.emit(line.rstrip("\n"))
        proc.stdout.close()
        code = proc.wait()
        self.finished.emit(code)

class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(760, 520)
        self._tempdir = None
        self._last_dist = None
        self._thread = None
        self._worker = None
        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # HTML source selection
        src_row = QtWidgets.QHBoxLayout()
        self.src_edit = QtWidgets.QLineEdit()
        self.src_edit.setPlaceholderText("Select HTML folder or single HTML file (index.html)")
        src_btn = QtWidgets.QPushButton("Browse HTML")
        src_btn.clicked.connect(self.browse_html)
        src_row.addWidget(self.src_edit)
        src_row.addWidget(src_btn)
        layout.addLayout(src_row)

        # Entry HTML (index)
        entry_row = QtWidgets.QHBoxLayout()
        self.entry_edit = QtWidgets.QLineEdit("index.html")
        self.entry_edit.setPlaceholderText("Entry HTML filename (e.g. index.html)")
        entry_row.addWidget(QtWidgets.QLabel("Entry:"))
        entry_row.addWidget(self.entry_edit)
        entry_row.addStretch()
        layout.addLayout(entry_row)

        # Window size and title
        size_row = QtWidgets.QHBoxLayout()
        self.title_edit = QtWidgets.QLineEdit("My HTML App")
        self.width_spin = QtWidgets.QSpinBox(); self.width_spin.setRange(200, 3840); self.width_spin.setValue(1024)
        self.height_spin = QtWidgets.QSpinBox(); self.height_spin.setRange(200, 2160); self.height_spin.setValue(768)
        size_row.addWidget(QtWidgets.QLabel("Window title:"))
        size_row.addWidget(self.title_edit)
        size_row.addWidget(QtWidgets.QLabel("Width:"))
        size_row.addWidget(self.width_spin)
        size_row.addWidget(QtWidgets.QLabel("Height:"))
        size_row.addWidget(self.height_spin)
        layout.addLayout(size_row)

        # Options group
        options = QtWidgets.QGroupBox("Packaging options")
        opt_layout = QtWidgets.QGridLayout()
        self.onefile_cb = QtWidgets.QCheckBox("Onefile (.exe single file)")
        self.onefile_cb.setChecked(True)
        self.windowed_cb = QtWidgets.QCheckBox("Windowed (no console)")
        self.windowed_cb.setChecked(True)
        opt_layout.addWidget(self.onefile_cb, 0, 0)
        opt_layout.addWidget(self.windowed_cb, 0, 1)

        # Icon
        icon_row = QtWidgets.QHBoxLayout()
        self.icon_edit = QtWidgets.QLineEdit()
        self.icon_edit.setPlaceholderText("Optional .ico file for the EXE")
        icon_btn = QtWidgets.QPushButton("Browse .ico")
        icon_btn.clicked.connect(self.browse_icon)
        icon_row.addWidget(self.icon_edit)
        icon_row.addWidget(icon_btn)
        opt_layout.addLayout(icon_row, 1, 0, 1, 2)

        # Output dir
        out_row = QtWidgets.QHBoxLayout()
        self.outdir_edit = QtWidgets.QLineEdit()
        self.outdir_edit.setPlaceholderText("Output directory (default: current folder)")
        out_btn = QtWidgets.QPushButton("Browse output dir")
        out_btn.clicked.connect(self.browse_outdir)
        out_row.addWidget(self.outdir_edit)
        out_row.addWidget(out_btn)
        opt_layout.addLayout(out_row, 2, 0, 1, 2)

        options.setLayout(opt_layout)
        layout.addWidget(options)

        # Buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.build_btn = QtWidgets.QPushButton("Build .exe")
        self.build_btn.clicked.connect(self.on_build)
        self.open_btn = QtWidgets.QPushButton("Open dist folder")
        self.open_btn.clicked.connect(self.open_dist)
        self.open_btn.setEnabled(False)
        btn_row.addWidget(self.build_btn)
        btn_row.addWidget(self.open_btn)
        layout.addLayout(btn_row)

        # Output console
        self.output_view = QtWidgets.QPlainTextEdit()
        self.output_view.setReadOnly(True)
        font = QtGui.
