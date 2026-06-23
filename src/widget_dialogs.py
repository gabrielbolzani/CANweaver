"""
widget_dialogs.py — Diálogos de configuração para os Widgets do Dashboard.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox, QCheckBox,
    QColorDialog, QFrame, QSizePolicy
)
from PyQt6.QtGui import QColor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_toggle_btn(label: str, checked: bool = False, tooltip: str = "") -> QPushButton:
    """Cria um QPushButton checkável estilizado para formatação de texto."""
    btn = QPushButton(label)
    btn.setCheckable(True)
    btn.setChecked(checked)
    btn.setFixedSize(30, 30)
    btn.setToolTip(tooltip)
    btn.setStyleSheet(
        "QPushButton { background-color: #2e3035; color: white; border: 1px solid #444;"
        "  border-radius: 4px; font-weight: bold; }"
        "QPushButton:checked { background-color: #3b82f6; border-color: #3b82f6; }"
        "QPushButton:hover { background-color: #3a3f47; }"
    )
    return btn


def _color_preview_btn(color_hex: str, label: str) -> QPushButton:
    """Botão que exibe uma cor e abre QColorDialog ao clicar."""
    btn = QPushButton(label)
    btn.setFixedHeight(30)
    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    btn._color = color_hex
    _apply_color_style(btn, color_hex)
    return btn


def _apply_color_style(btn: QPushButton, color_hex: str):
    """Atualiza o estilo do botão de cor com o hex fornecido."""
    try:
        c = QColor(color_hex)
        text_color = "#000000" if c.lightness() > 128 else "#ffffff"
    except Exception:
        text_color = "#ffffff"
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color_hex}; color: {text_color};"
        f"  border: 1px solid #444; border-radius: 4px; padding: 0 8px; }}"
        f"QPushButton:hover {{ border-color: #3b82f6; }}"
    )
    btn._color = color_hex


def _open_color_picker(btn: QPushButton, parent=None):
    """Abre QColorDialog e atualiza o botão com a cor escolhida."""
    initial = QColor(btn._color) if hasattr(btn, "_color") else QColor("#ffffff")
    color = QColorDialog.getColor(initial, parent, "Escolher Cor")
    if color.isValid():
        _apply_color_style(btn, color.name())


# ---------------------------------------------------------------------------
# LabelDialog
# ---------------------------------------------------------------------------

class LabelDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Label")
        self.resize(340, 200)

        layout = QVBoxLayout(self)

        # Texto
        self.txt_text = QLineEdit(config.get("text", "Novo Label") if config else "Novo Label")
        layout.addWidget(QLabel("Texto da Label:"))
        layout.addWidget(self.txt_text)

        # Tamanho + botões de formatação
        opts_layout = QHBoxLayout()
        opts_layout.addWidget(QLabel("Tamanho:"))
        self.sp_size = QSpinBox()
        self.sp_size.setRange(8, 72)
        self.sp_size.setValue(config.get("size", 14) if config else 14)
        opts_layout.addWidget(self.sp_size)

        opts_layout.addSpacing(12)
        opts_layout.addWidget(QLabel("Formatação:"))

        self.btn_bold = _make_toggle_btn("N", config.get("bold", False) if config else False, "Negrito")
        self.btn_bold.setStyleSheet(
            self.btn_bold.styleSheet().replace("font-weight: bold;", "") +
            " font-weight: bold;"
        )
        self.btn_italic = _make_toggle_btn("I", config.get("italic", False) if config else False, "Itálico")
        self.btn_italic.setStyleSheet(
            self.btn_italic.styleSheet() + " font-style: italic;"
        )
        self.btn_strike = _make_toggle_btn("S̶", config.get("strikethrough", False) if config else False, "Tachado")

        opts_layout.addWidget(self.btn_bold)
        opts_layout.addWidget(self.btn_italic)
        opts_layout.addWidget(self.btn_strike)
        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Cor do texto
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Cor do texto:"))
        init_color = config.get("color", "#ffffff") if config else "#ffffff"
        self.btn_color = _color_preview_btn(init_color, init_color)
        self.btn_color.clicked.connect(lambda: self._pick_color())
        color_layout.addWidget(self.btn_color)
        layout.addLayout(color_layout)

        # Botões OK/Cancelar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def _pick_color(self):
        _open_color_picker(self.btn_color, self)
        self.btn_color.setText(self.btn_color._color)

    def get_config(self):
        return {
            "type": "label",
            "text": self.txt_text.text().strip(),
            "size": self.sp_size.value(),
            "bold": self.btn_bold.isChecked(),
            "italic": self.btn_italic.isChecked(),
            "strikethrough": self.btn_strike.isChecked(),
            "color": self.btn_color._color,
        }


# ---------------------------------------------------------------------------
# IndicatorDialog
# ---------------------------------------------------------------------------

class IndicatorDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Indicador")
        self.resize(380, 340)

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

        layout.addRow("Nome:", self.txt_name)
        layout.addRow("ID (HEX):", self.txt_can_id)
        layout.addRow("Byte Index:", self.sp_byte)
        layout.addRow("Bit Index:", self.sp_bit)
        layout.addRow("Tipo Visual:", self.cb_type)

        # --- Controles de cor (LED) ---
        init_off = config.get("val_off", "#52525b") if config else "#52525b"
        init_on  = config.get("val_on",  "#10b981") if config else "#10b981"

        self.btn_color_off = _color_preview_btn(init_off, init_off)
        self.btn_color_off.clicked.connect(lambda: self._pick(self.btn_color_off))

        self.btn_color_on = _color_preview_btn(init_on, init_on)
        self.btn_color_on.clicked.connect(lambda: self._pick(self.btn_color_on))

        # --- Controles de texto ---
        self.txt_off = QLineEdit(init_off)
        self.txt_off.setPlaceholderText("Texto quando DESLIGADO")
        self.txt_on  = QLineEdit(init_on)
        self.txt_on.setPlaceholderText("Texto quando LIGADO")

        # Guarda referências às labels de formulário para mostrar/ocultar
        layout.addRow("Cor DESLIGADO:", self.btn_color_off)
        layout.addRow("Cor LIGADO:", self.btn_color_on)
        layout.addRow("Texto DESLIGADO:", self.txt_off)
        layout.addRow("Texto LIGADO:", self.txt_on)

        # Botões OK/Cancelar
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

        # Conectar mudança de tipo
        self.cb_type.currentTextChanged.connect(self._update_color_mode)
        self._update_color_mode(self.cb_type.currentText())

    def _pick(self, btn: QPushButton):
        _open_color_picker(btn, self)
        btn.setText(btn._color)

    def _update_color_mode(self, mode: str):
        is_led = (mode == "LED")
        form = self.layout()

        def _set_row_visible(widget, visible):
            lbl = form.labelForField(widget)
            widget.setVisible(visible)
            if lbl:
                lbl.setVisible(visible)

        _set_row_visible(self.btn_color_off, is_led)
        _set_row_visible(self.btn_color_on,  is_led)
        _set_row_visible(self.txt_off, not is_led)
        _set_row_visible(self.txt_on,  not is_led)

    def get_config(self):
        is_led = self.cb_type.currentText() == "LED"
        return {
            "type": "indicator",
            "name": self.txt_name.text().strip(),
            "can_id": self.txt_can_id.text().strip().upper(),
            "byte": self.sp_byte.value(),
            "bit": self.sp_bit.value(),
            "visual_type": self.cb_type.currentText(),
            "val_off": self.btn_color_off._color if is_led else self.txt_off.text().strip(),
            "val_on":  self.btn_color_on._color  if is_led else self.txt_on.text().strip(),
        }


# ---------------------------------------------------------------------------
# ControllerDialog
# ---------------------------------------------------------------------------

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
        if config and config.get("format"):
            self.cb_format.setCurrentText(config["format"])

        self.txt_payload_on  = QLineEdit(config.get("payload_on",  "01 00 00 00 00 00 00 00") if config else "01 00 00 00 00 00 00 00")
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
        show_hz  = "Contínuo" in txt
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
