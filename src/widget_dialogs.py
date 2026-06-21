"""
widget_dialogs.py — Diálogos de configuração para os Widgets do Dashboard.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QComboBox, 
    QSpinBox, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox, QCheckBox
)

class LabelDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Label")
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        
        self.txt_text = QLineEdit(config.get("text", "Novo Label") if config else "Novo Label")
        
        self.sp_size = QSpinBox()
        self.sp_size.setRange(8, 72)
        self.sp_size.setValue(config.get("size", 14) if config else 14)
        
        self.chk_bold = QCheckBox("Texto em Negrito")
        self.chk_bold.setChecked(config.get("bold", False) if config else False)
        
        layout.addWidget(QLabel("Texto da Label:"))
        layout.addWidget(self.txt_text)
        
        opts_layout = QHBoxLayout()
        opts_layout.addWidget(QLabel("Tamanho:"))
        opts_layout.addWidget(self.sp_size)
        opts_layout.addWidget(self.chk_bold)
        opts_layout.addStretch()
        layout.addLayout(opts_layout)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        layout.addLayout(btn_layout)

    def get_config(self):
        return {
            "type": "label",
            "text": self.txt_text.text().strip(),
            "size": self.sp_size.value(),
            "bold": self.chk_bold.isChecked()
        }


class IndicatorDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Indicador")
        self.resize(350, 300)
        
        layout = QFormLayout(self)
        
        self.txt_name = QLineEdit(config.get("name", "Meu Indicador") if config else "Meu Indicador")
        self.txt_can_id = QLineEdit(config.get("can_id", "0C0") if config else "0C0")
        self.txt_can_id.setPlaceholderText("ID em HEX (ex: 0C0)")
        
        self.sp_byte = QSpinBox()
        self.sp_byte.setRange(0, 7)
        self.sp_byte.setValue(config.get("byte", 0) if config else 0)
        
        self.sp_bit = QSpinBox()
        self.sp_bit.setRange(0, 7)
        self.sp_bit.setValue(config.get("bit", 0) if config else 0)
        
        self.cb_type = QComboBox()
        self.cb_type.addItems(["LED", "Texto"])
        if config and config.get("visual_type") == "Texto":
            self.cb_type.setCurrentText("Texto")
            
        # Cores / Texto OFF
        self.txt_off = QLineEdit(config.get("val_off", "#52525b") if config else "#52525b")
        self.txt_off.setPlaceholderText("Cor HEX ou Texto Desligado")
        
        # Cores / Texto ON
        self.txt_on = QLineEdit(config.get("val_on", "#10b981") if config else "#10b981")
        self.txt_on.setPlaceholderText("Cor HEX ou Texto Ligado")
        
        layout.addRow("Nome:", self.txt_name)
        layout.addRow("ID (HEX):", self.txt_can_id)
        layout.addRow("Byte Index:", self.sp_byte)
        layout.addRow("Bit Index:", self.sp_bit)
        layout.addRow("Tipo Visual:", self.cb_type)
        layout.addRow("Desligado (Cor/Texto):", self.txt_off)
        layout.addRow("Ligado (Cor/Texto):", self.txt_on)
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

    def get_config(self):
        return {
            "type": "indicator",
            "name": self.txt_name.text().strip(),
            "can_id": self.txt_can_id.text().strip().upper(),
            "byte": self.sp_byte.value(),
            "bit": self.sp_bit.value(),
            "visual_type": self.cb_type.currentText(),
            "val_off": self.txt_off.text().strip(),
            "val_on": self.txt_on.text().strip()
        }


class ControllerDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Controlador")
        self.resize(400, 350)
        
        layout = QFormLayout(self)
        
        self.txt_name = QLineEdit(config.get("name", "Botão 1") if config else "Botão 1")
        self.txt_can_id = QLineEdit(config.get("can_id", "0C0") if config else "0C0")
        
        self.cb_format = QComboBox()
        self.cb_format.addItems(["HEX", "BIN"])
        
        self.txt_payload_on = QLineEdit(config.get("payload_on", "01 00 00 00 00 00 00 00") if config else "01 00 00 00 00 00 00 00")
        self.txt_payload_off = QLineEdit(config.get("payload_off", "00 00 00 00 00 00 00 00") if config else "00 00 00 00 00 00 00 00")
        
        self.cb_behavior = QComboBox()
        self.cb_behavior.addItems([
            "Pulso (Apenas Click - envia ON)",
            "Segurar (Ao apertar ON, Ao soltar OFF)",
            "Segurar Contínuo (Envia ON a X Hz, soltar OFF)",
            "Toggle Chave (Liga ON, Desliga OFF)",
            "Toggle Contínuo (Liga ON a X Hz, Desliga OFF)"
        ])
        
        if config and "behavior" in config:
            idx = self.cb_behavior.findText(config["behavior"])
            if idx >= 0:
                self.cb_behavior.setCurrentIndex(idx)
                
        self.sp_hz = QSpinBox()
        self.sp_hz.setRange(1, 1000)
        self.sp_hz.setValue(config.get("hz", 10) if config else 10)
        
        layout.addRow("Nome do Botão:", self.txt_name)
        layout.addRow("ID (HEX):", self.txt_can_id)
        layout.addRow("Formato dos Dados:", self.cb_format)
        layout.addRow("Payload Ligado (ON):", self.txt_payload_on)
        layout.addRow("Payload Desligado (OFF):", self.txt_payload_off)
        layout.addRow("Comportamento:", self.cb_behavior)
        layout.addRow("Frequência (Hz):", self.sp_hz)
        
        self.cb_behavior.currentIndexChanged.connect(self.update_visibility)
        self.update_visibility()
        
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.validate_and_accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

    def update_visibility(self):
        txt = self.cb_behavior.currentText()
        show_hz = "Contínuo" in txt
        show_off = "Pulso (Apenas" not in txt
        
        self.sp_hz.setVisible(show_hz)
        self.layout().labelForField(self.sp_hz).setVisible(show_hz)
        
        self.txt_payload_off.setVisible(show_off)
        self.layout().labelForField(self.txt_payload_off).setVisible(show_off)

    def validate_and_accept(self):
        try:
            int(self.txt_can_id.text().strip(), 16)
        except ValueError:
            QMessageBox.warning(self, "Erro", "ID CAN deve ser hexadecimal.")
            return
        self.accept()

    def get_config(self):
        return {
            "type": "controller",
            "name": self.txt_name.text().strip(),
            "can_id": self.txt_can_id.text().strip().upper(),
            "format": self.cb_format.currentText(),
            "payload_on": self.txt_payload_on.text().strip(),
            "payload_off": self.txt_payload_off.text().strip(),
            "behavior": self.cb_behavior.currentText(),
            "hz": self.sp_hz.value()
        }
