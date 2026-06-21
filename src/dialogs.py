"""
dialogs.py — Diálogos modais da aplicação

Contém:
  - ConnectionDialog: configuração de modo (Simulado / Hardware / Playback),
    interface, canal, bitrate e arquivo de playback.
  - CommentDialog: caixa de texto multilinhas para anotações.
    Enter confirma, Shift+Enter insere nova linha.
"""

import serial.tools.list_ports
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QLineEdit, QPushButton,
    QLabel, QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout, QTextEdit
)


class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conectar Dispositivo CAN")
        self.resize(350, 250)

        self.mode = "SIMULATED"
        self.interface = "slcan"
        self.channel = "COM3"
        self.bitrate = 500000
        self.playback_file = ""
        self.playback_transmit = False
        self.playback_loop = False

        self.layout = QFormLayout(self)

        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Simulado", "Hardware Real", "Playback"])
        self.cb_mode.currentIndexChanged.connect(self.on_mode_change)

        self.cb_interface = QComboBox()
        self.cb_interface.addItems(["slcan", "socketcan", "vector", "virtual", "ixxat", "pcan"])

        self.cb_channel = QComboBox()
        self.cb_channel.setEditable(True)
        self.populate_ports()

        self.cb_bitrate = QComboBox()
        self.cb_bitrate.addItems(["125000", "250000", "500000", "1000000"])
        self.cb_bitrate.setCurrentText("500000")

        self.btn_file = QPushButton("Selecionar Arquivo...")
        self.btn_file.clicked.connect(self.select_file)
        self.lbl_file = QLabel("Nenhum arquivo selecionado")

        self.chk_transmit = QCheckBox("Transmitir no Hardware Real")
        self.chk_transmit.stateChanged.connect(self.on_transmit_change)

        self.chk_loop = QCheckBox("Repetir em Loop")

        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.clicked.connect(self.accept)

        self.layout.addRow("Modo:", self.cb_mode)
        self.layout.addRow("Interface:", self.cb_interface)
        self.layout.addRow("Canal/Porta:", self.cb_channel)
        self.layout.addRow("Velocidade:", self.cb_bitrate)
        self.layout.addRow("Arquivo Playback:", self.btn_file)
        self.layout.addRow("", self.lbl_file)
        self.layout.addRow("", self.chk_transmit)
        self.layout.addRow("", self.chk_loop)
        self.layout.addRow(self.btn_connect)

        self.on_mode_change(0)

    def populate_ports(self):
        ports = serial.tools.list_ports.comports()
        for port, desc, hwid in sorted(ports):
            self.cb_channel.addItem(port)
        if not ports:
            self.cb_channel.addItem("can0")
            self.cb_channel.addItem("COM3")

    def set_row_visible(self, widget, visible):
        pos = self.layout.getWidgetPosition(widget)
        if pos:
            row = pos[0]
            label_item = self.layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if label_item and label_item.widget():
                label_item.widget().setVisible(visible)
            field_item = self.layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if field_item and field_item.widget():
                field_item.widget().setVisible(visible)

    def on_mode_change(self, index):
        if index == 0:  # Simulado
            self.set_row_visible(self.cb_interface, False)
            self.set_row_visible(self.cb_channel, False)
            self.set_row_visible(self.cb_bitrate, False)
            self.set_row_visible(self.btn_file, False)
            self.set_row_visible(self.lbl_file, False)
            self.set_row_visible(self.chk_transmit, False)
            self.set_row_visible(self.chk_loop, False)
        elif index == 1:  # Hardware Real
            self.set_row_visible(self.cb_interface, True)
            self.set_row_visible(self.cb_channel, True)
            self.set_row_visible(self.cb_bitrate, True)
            self.set_row_visible(self.btn_file, False)
            self.set_row_visible(self.lbl_file, False)
            self.set_row_visible(self.chk_transmit, False)
            self.set_row_visible(self.chk_loop, False)
        elif index == 2:  # Playback
            self.set_row_visible(self.btn_file, True)
            self.set_row_visible(self.lbl_file, True)
            self.set_row_visible(self.chk_transmit, True)
            self.set_row_visible(self.chk_loop, True)
            self.on_transmit_change(self.chk_transmit.checkState().value)

    def on_transmit_change(self, state):
        if state == 2 and self.cb_mode.currentIndex() == 2:
            self.set_row_visible(self.cb_interface, True)
            self.set_row_visible(self.cb_channel, True)
            self.set_row_visible(self.cb_bitrate, True)
        else:
            if self.cb_mode.currentIndex() == 2:
                self.set_row_visible(self.cb_interface, False)
                self.set_row_visible(self.cb_channel, False)
                self.set_row_visible(self.cb_bitrate, False)

    def select_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo de Playback", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_name:
            self.playback_file = file_name
            self.lbl_file.setText(file_name.split("/")[-1])

    def get_config(self):
        mode_str = self.cb_mode.currentText()
        if mode_str == "Simulado":
            self.mode = "SIMULATED"
        elif mode_str == "Hardware Real":
            self.mode = "HARDWARE"
        else:
            self.mode = "PLAYBACK"

        self.interface = self.cb_interface.currentText()
        self.channel = self.cb_channel.currentText()
        self.bitrate = int(self.cb_bitrate.currentText())
        self.playback_transmit = self.chk_transmit.isChecked()
        return {
            "mode": self.mode,
            "interface": self.interface,
            "channel": self.channel,
            "bitrate": self.bitrate,
            "playback_file": self.playback_file,
            "playback_transmit": self.playback_transmit,
            "playback_loop": self.chk_loop.isChecked()
        }


class CommentDialog(QDialog):
    """Diálogo de anotação. Enter confirma, Shift+Enter pula linha."""

    def __init__(self, parent, target):
        super().__init__(parent)
        self.setWindowTitle("Adicionar Comentário")
        self.resize(400, 200)

        self.layout = QVBoxLayout(self)
        lbl = QLabel(
            f"Comentário para {target}:<br>"
            "<small style='color:#a1a1aa'>(Shift+Enter para pular linha, Enter para Salvar)</small>"
        )
        self.layout.addWidget(lbl)

        self.text_edit = QTextEdit()
        self.text_edit.installEventFilter(self)
        self.layout.addWidget(self.text_edit)

        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK (Enter)")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)

    def eventFilter(self, obj, event):
        if obj is self.text_edit and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                else:
                    self.accept()
                    return True
        return super().eventFilter(obj, event)

    def get_text(self):
        return self.text_edit.toPlainText().strip()
