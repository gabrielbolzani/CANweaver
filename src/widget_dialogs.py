"""
widget_dialogs.py — Diálogos de configuração para os Widgets do Dashboard.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QComboBox,
    QSpinBox, QDoubleSpinBox, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox, QCheckBox,
    QColorDialog, QFrame, QSizePolicy, QWidget
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


def _get_grid_size(parent, explicit_grid_size=None) -> int:
    if explicit_grid_size is not None and isinstance(explicit_grid_size, int) and explicit_grid_size > 0:
        return explicit_grid_size
    g = getattr(parent, "grid_size", None)
    if g and isinstance(g, int) and g > 0:
        return g
    c = getattr(parent, "canvas", None)
    if c and hasattr(c, "grid_size") and isinstance(c.grid_size, int) and c.grid_size > 0:
        return c.grid_size
    return 20


# ---------------------------------------------------------------------------
# LabelDialog
# ---------------------------------------------------------------------------

class LabelDialog(QDialog):
    def __init__(self, parent=None, config=None, grid_size=None):
        super().__init__(parent)
        self.grid_size = _get_grid_size(parent, grid_size)
        self.setWindowTitle("Configurar Label")
        self.resize(360, 240)

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

        # Largura opcional com snap
        dim_layout = QHBoxLayout()
        dim_layout.addWidget(QLabel("Largura Fixa (0 = Auto):"))
        self.sp_width = QSpinBox()
        self.sp_width.setRange(0, 3000)
        self.sp_width.setValue(int(config.get("width", 0)) if config and config.get("width") else 0)
        self.sp_width.setSpecialValueText("Automático")
        self.sp_width.setSuffix(" px")
        dim_layout.addWidget(self.sp_width)
        layout.addLayout(dim_layout)

        self.chk_snap_size = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap_size.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap_size.toggled.connect(self._on_snap_toggled)
        layout.addWidget(self.chk_snap_size)

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

        if self.chk_snap_size.isChecked():
            self._on_snap_toggled(True)

    def _on_snap_toggled(self, checked: bool):
        if checked and self.sp_width.value() > 0:
            val = round(self.sp_width.value() / self.grid_size) * self.grid_size
            self.sp_width.setValue(max(self.grid_size, val))
            self.sp_width.setSingleStep(self.grid_size)
        else:
            self.sp_width.setSingleStep(10)

    def _pick_color(self):
        _open_color_picker(self.btn_color, self)
        self.btn_color.setText(self.btn_color._color)

    def get_config(self):
        cfg = {
            "type": "label",
            "text": self.txt_text.text().strip(),
            "size": self.sp_size.value(),
            "bold": self.btn_bold.isChecked(),
            "italic": self.btn_italic.isChecked(),
            "strikethrough": self.btn_strike.isChecked(),
            "color": self.btn_color._color,
            "snap_size": self.chk_snap_size.isChecked(),
        }
        if self.sp_width.value() > 0:
            cfg["width"] = self.sp_width.value()
        return cfg


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
        self.txt_can_id = QLineEdit(config.get("can_id", "111") if config else "111")
        self.txt_can_id.setPlaceholderText("ID em HEX (ex: 111)")

        self.sp_byte = QSpinBox()
        self.sp_byte.setRange(0, 7)
        self.sp_byte.setValue(config.get("byte", 0) if config else 0)

        self.sp_bit = QSpinBox()
        self.sp_bit.setRange(0, 7)
        self.sp_bit.setValue(config.get("bit", 1) if config else 1)

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
        init_is_led = not config or config.get("visual_type", "LED") == "LED"
        init_off_color = (config.get("val_off", "#52525b") if config else "#52525b") if not init_is_led or (config and config.get("val_off", "").startswith("#")) else (config.get("val_off", "#52525b") if config else "#52525b")
        init_on_color  = (config.get("val_on",  "#10b981") if config else "#10b981") if not init_is_led or (config and config.get("val_on",  "").startswith("#")) else (config.get("val_on",  "#10b981") if config else "#10b981")

        # Garante valores de cor válidos para o botão de cor
        if not init_off_color.startswith("#"):
            init_off_color = "#52525b"
        if not init_on_color.startswith("#"):
            init_on_color = "#10b981"

        self.btn_color_off = _color_preview_btn(init_off_color, init_off_color)
        self.btn_color_off.clicked.connect(lambda: self._pick(self.btn_color_off))

        self.btn_color_on = _color_preview_btn(init_on_color, init_on_color)
        self.btn_color_on.clicked.connect(lambda: self._pick(self.btn_color_on))

        # Tamanho do LED
        self.sp_led_size = QSpinBox()
        self.sp_led_size.setRange(12, 96)
        self.sp_led_size.setValue(config.get("led_size", 32) if config else 32)
        self.sp_led_size.setSuffix(" px")

        self.grid_size = _get_grid_size(parent)
        self.chk_snap_size = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap_size.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap_size.toggled.connect(self._on_snap_toggled)

        # --- Controles de texto ---
        # Usa textos padrão quando o tipo é Texto (evita hexadecimais de cor)
        if config and config.get("visual_type") == "Texto":
            default_off = config.get("val_off", "DESLIGADO")
            default_on  = config.get("val_on",  "LIGADO")
        else:
            default_off = "DESLIGADO"
            default_on  = "LIGADO"

        self.txt_off = QLineEdit(default_off)
        self.txt_off.setPlaceholderText("Texto quando DESLIGADO")
        self.txt_on  = QLineEdit(default_on)
        self.txt_on.setPlaceholderText("Texto quando LIGADO")

        # Guarda referências às labels de formulário para mostrar/ocultar
        layout.addRow("Cor DESLIGADO:", self.btn_color_off)
        layout.addRow("Cor LIGADO:", self.btn_color_on)
        layout.addRow("Tamanho LED:", self.sp_led_size)
        layout.addRow("Snap de Tamanho:", self.chk_snap_size)
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

        if self.chk_snap_size.isChecked():
            self._on_snap_toggled(True)

    def _on_snap_toggled(self, checked: bool):
        if checked:
            val = round(self.sp_led_size.value() / self.grid_size) * self.grid_size
            self.sp_led_size.setValue(max(self.grid_size, val))
            self.sp_led_size.setSingleStep(self.grid_size)
        else:
            self.sp_led_size.setSingleStep(4)

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
        _set_row_visible(self.sp_led_size,   is_led)
        _set_row_visible(self.chk_snap_size, is_led)
        _set_row_visible(self.txt_off, not is_led)
        _set_row_visible(self.txt_on,  not is_led)

    def get_config(self):
        is_led = self.cb_type.currentText() == "LED"
        can_id_text = self.txt_can_id.text().strip()
        try:
            can_id_str = f"{int(can_id_text, 16):03X}"
        except ValueError:
            can_id_str = can_id_text.upper().replace("0X", "")
            
        return {
            "type": "indicator",
            "name": self.txt_name.text().strip(),
            "can_id": can_id_str,
            "byte": self.sp_byte.value(),
            "bit": self.sp_bit.value(),
            "visual_type": self.cb_type.currentText(),
            "led_size": self.sp_led_size.value(),
            "snap_size": self.chk_snap_size.isChecked(),
            "val_off": self.btn_color_off._color if is_led else self.txt_off.text().strip(),
            "val_on":  self.btn_color_on._color  if is_led else self.txt_on.text().strip(),
        }


# ---------------------------------------------------------------------------
# ControllerDialog
# ---------------------------------------------------------------------------

class ControllerDialog(QDialog):
    def __init__(self, parent=None, config=None, grid_size=None):
        super().__init__(parent)
        self.grid_size = _get_grid_size(parent, grid_size)
        self.setWindowTitle("Configurar Controlador / Botão")
        self.resize(420, 420)

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

        # Dimensões e Snap do botão
        self.sp_width = QSpinBox()
        self.sp_width.setRange(40, 1500)
        self.sp_width.setValue(int(config.get("width", 140)) if config and config.get("width") else 140)
        self.sp_width.setSuffix(" px")

        self.sp_height = QSpinBox()
        self.sp_height.setRange(20, 800)
        self.sp_height.setValue(int(config.get("height", 45)) if config and config.get("height") else 45)
        self.sp_height.setSuffix(" px")

        self.chk_snap_size = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap_size.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap_size.toggled.connect(self._on_snap_toggled)

        layout.addRow("Nome do Botão:", self.txt_name)
        layout.addRow("ID (HEX):", self.txt_can_id)
        layout.addRow("Formato dos Dados:", self.cb_format)
        layout.addRow("Payload Ligado (ON):", self.txt_payload_on)
        layout.addRow("Payload Desligado (OFF):", self.txt_payload_off)
        layout.addRow("Comportamento:", self.cb_behavior)
        layout.addRow("Frequência (Hz):", self.sp_hz)
        layout.addRow("Largura do Botão:", self.sp_width)
        layout.addRow("Altura do Botão:", self.sp_height)
        layout.addRow("Snap de Tamanho:", self.chk_snap_size)

        self.cb_behavior.currentIndexChanged.connect(self.update_visibility)
        self.update_visibility()

        if self.chk_snap_size.isChecked():
            self._on_snap_toggled(True)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.validate_and_accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

    def _on_snap_toggled(self, checked: bool):
        if checked:
            w = round(self.sp_width.value() / self.grid_size) * self.grid_size
            h = round(self.sp_height.value() / self.grid_size) * self.grid_size
            self.sp_width.setValue(max(self.grid_size, w))
            self.sp_height.setValue(max(self.grid_size, h))
            self.sp_width.setSingleStep(self.grid_size)
            self.sp_height.setSingleStep(self.grid_size)
        else:
            self.sp_width.setSingleStep(10)
            self.sp_height.setSingleStep(5)

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
        can_id_text = self.txt_can_id.text().strip()
        try:
            can_id_str = f"{int(can_id_text, 16):03X}"
        except ValueError:
            can_id_str = can_id_text.upper().replace("0X", "")

        return {
            "type": "controller",
            "name": self.txt_name.text().strip(),
            "can_id": can_id_str,
            "format": self.cb_format.currentText(),
            "payload_on": self.txt_payload_on.text().strip(),
            "payload_off": self.txt_payload_off.text().strip(),
            "behavior": self.cb_behavior.currentText(),
            "hz": self.sp_hz.value(),
            "width": self.sp_width.value(),
            "height": self.sp_height.value(),
            "snap_size": self.chk_snap_size.isChecked(),
        }


# ---------------------------------------------------------------------------
# GaugeDialog
# ---------------------------------------------------------------------------

class GaugeDialog(QDialog):
    """Diálogo de configuração para o Gauge (indicador analógico)."""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Gauge")
        self.resize(450, 480)

        layout = QFormLayout(self)

        self.txt_name = QLineEdit(config.get("name", "Meu Gauge") if config else "Meu Gauge")

        self.cb_style = QComboBox()
        self.cb_style.addItems(["Arco", "Barra Horizontal", "Barra Vertical", "Texto Apenas"])
        self.cb_style.setCurrentText(config.get("style", "Arco") if config else "Arco")

        self.txt_can_id = QLineEdit(config.get("can_id", "111") if config else "111")
        self.txt_can_id.setPlaceholderText("ID em HEX (ex: 111)")

        self.sp_byte = QSpinBox()
        self.sp_byte.setRange(0, 7)
        self.sp_byte.setValue(config.get("byte", 0) if config else 0)

        self.sp_byte_len = QSpinBox()
        self.sp_byte_len.setRange(1, 4)
        self.sp_byte_len.setValue(config.get("byte_len", 1) if config else 1)
        self.sp_byte_len.setToolTip("Número de bytes consecutivos que formam o valor (1–4)")

        self.txt_unit = QLineEdit(config.get("unit", "") if config else "")
        self.txt_unit.setPlaceholderText("Unidade (ex: km/h, °C, bar)")

        # Raw values (Hex / Int)
        self.sp_min_raw = QSpinBox()
        self.sp_min_raw.setRange(-2147483648, 2147483647)
        self.sp_min_raw.setValue(config.get("val_min_raw", 0) if config else 0)

        self.sp_max_raw = QSpinBox()
        self.sp_max_raw.setRange(-2147483648, 2147483647)
        self.sp_max_raw.setValue(config.get("val_max_raw", 255) if config else 255)

        # Converted values (Float)
        self.sp_min_conv = QDoubleSpinBox()
        self.sp_min_conv.setRange(-9999999.0, 9999999.0)
        self.sp_min_conv.setDecimals(4)
        self.sp_min_conv.setValue(config.get("val_min_conv", 0.0) if config else 0.0)

        self.sp_max_conv = QDoubleSpinBox()
        self.sp_max_conv.setRange(-9999999.0, 9999999.0)
        self.sp_max_conv.setDecimals(4)
        self.sp_max_conv.setValue(config.get("val_max_conv", 100.0) if config else 100.0)

        self.chk_float = QCheckBox("Exibir casas decimais na tela")
        self.chk_float.setChecked(config.get("show_float", False) if config else False)

        self.lbl_factor = QLabel("Fator: --")
        self.lbl_factor.setStyleSheet("color: #a1a1aa; font-style: italic;")

        self.grid_size = _get_grid_size(parent)
        self.sp_size = QSpinBox()
        self.sp_size.setRange(40, 600)
        self.sp_size.setValue(config.get("gauge_size", 160) if config else 160)
        self.sp_size.setSuffix(" px")
        self.sp_size.setSingleStep(self.grid_size)

        self.chk_snap_size = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap_size.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap_size.toggled.connect(self._on_snap_toggled)

        self.chk_invert = QCheckBox("Inverter direção de crescimento")
        self.chk_invert.setChecked(config.get("invert_direction", False) if config else False)
        self.chk_invert.setToolTip("Inverte o sentido do preenchimento gráfico (o valor numérico não muda)")

        layout.addRow("Nome:", self.txt_name)
        layout.addRow("Estilo Visual:", self.cb_style)
        layout.addRow("ID CAN (HEX):", self.txt_can_id)
        layout.addRow("Byte Inicial:", self.sp_byte)
        layout.addRow("Nº de Bytes:", self.sp_byte_len)
        layout.addRow("Unidade:", self.txt_unit)
        layout.addRow("Valor Inicial (HEX/INT):", self.sp_min_raw)
        layout.addRow("Valor Final (HEX/INT):", self.sp_max_raw)
        layout.addRow("Valor Inicial Convertido:", self.sp_min_conv)
        layout.addRow("Valor Final Convertido:", self.sp_max_conv)
        layout.addRow("", self.chk_float)
        layout.addRow("", self.lbl_factor)
        layout.addRow("Tamanho do Gauge:", self.sp_size)
        layout.addRow("Snap de Tamanho:", self.chk_snap_size)
        layout.addRow("", self.chk_invert)

        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self._validate_and_accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addRow(btn_layout)

        self.sp_min_raw.valueChanged.connect(self._update_factor)
        self.sp_max_raw.valueChanged.connect(self._update_factor)
        self.sp_min_conv.valueChanged.connect(self._update_factor)
        self.sp_max_conv.valueChanged.connect(self._update_factor)
        self._update_factor()

        if self.chk_snap_size.isChecked():
            self._on_snap_toggled(True)

    def _on_snap_toggled(self, checked: bool):
        if checked:
            val = round(self.sp_size.value() / self.grid_size) * self.grid_size
            self.sp_size.setValue(max(self.grid_size, val))
            self.sp_size.setSingleStep(self.grid_size)
        else:
            self.sp_size.setSingleStep(10)

    def _update_factor(self):
        d_raw = self.sp_max_raw.value() - self.sp_min_raw.value()
        d_conv = self.sp_max_conv.value() - self.sp_min_conv.value()
        if d_raw == 0:
            self.lbl_factor.setText("Fator: N/A (delta zero)")
        else:
            self.lbl_factor.setText(f"Fator de conversão: {d_conv / d_raw:.4f}")

    def _validate_and_accept(self):
        try:
            int(self.txt_can_id.text().strip(), 16)
        except ValueError:
            QMessageBox.warning(self, "Erro", "ID CAN deve ser hexadecimal.")
            return
        if self.sp_min_raw.value() == self.sp_max_raw.value():
            QMessageBox.warning(self, "Erro", "O valor inicial e final raw não podem ser iguais.")
            return
        self.accept()

    def get_config(self):
        can_id_text = self.txt_can_id.text().strip()
        try:
            can_id_str = f"{int(can_id_text, 16):03X}"
        except ValueError:
            can_id_str = can_id_text.upper().replace("0X", "")

        return {
            "type": "gauge",
            "name": self.txt_name.text().strip(),
            "style": self.cb_style.currentText(),
            "can_id": can_id_str,
            "byte": self.sp_byte.value(),
            "byte_len": self.sp_byte_len.value(),
            "unit": self.txt_unit.text().strip(),
            "val_min_raw": self.sp_min_raw.value(),
            "val_max_raw": self.sp_max_raw.value(),
            "val_min_conv": self.sp_min_conv.value(),
            "val_max_conv": self.sp_max_conv.value(),
            "show_float": self.chk_float.isChecked(),
            "gauge_size": self.sp_size.value(),
            "snap_size": self.chk_snap_size.isChecked(),
            "invert_direction": self.chk_invert.isChecked(),
        }



# ---------------------------------------------------------------------------
# MultiIndicatorDialog  (Beta)
# ---------------------------------------------------------------------------

def _parse_pattern(pattern_str: str, fmt: str) -> list:
    """
    Converte string de padrao em lista de 8 itens (int ou None = don't care).
    Exemplo HEX: '01 xx FF xx xx xx xx xx'  -> [1, None, 255, None, None, None, None, None]
    Exemplo BIN: '00000001 xxxxxxxx ...'    -> [1, None, ...]
    """
    parts = pattern_str.strip().split()
    result = []
    for p in parts[:8]:
        if all(c in ('x', 'X', '?', '-') for c in p) and len(p) > 0:
            result.append(None)
        else:
            try:
                result.append(int(p, 16 if fmt == 'HEX' else 2))
            except ValueError:
                result.append(None)
    while len(result) < 8:
        result.append(None)
    return result


def _format_pattern(pattern: list, fmt: str) -> str:
    """Converte lista interna -> string legivel para o campo de texto."""
    parts = []
    for v in pattern:
        if v is None:
            parts.append('xx' if fmt == 'HEX' else 'xxxxxxxx')
        else:
            parts.append(f'{v:02X}' if fmt == 'HEX' else f'{v:08b}')
    return ' '.join(parts)


class _StateRow:
    """Agrupa os widgets de uma linha de estado no MultiIndicatorDialog."""

    def __init__(self, parent_layout, label: str, color: str,
                 pattern: list, fmt: str):
        self.fmt = fmt
        self.destroyed = False

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(6)

        self.txt_label = QLineEdit(label)
        self.txt_label.setPlaceholderText('Nome do estado')
        self.txt_label.setFixedWidth(110)

        self.btn_color = _color_preview_btn(color, color)
        self.btn_color.setFixedWidth(80)
        self.btn_color.clicked.connect(lambda: self._pick_color())

        self.txt_pattern = QLineEdit(_format_pattern(pattern, fmt))
        self.txt_pattern.setPlaceholderText('ex: 01 xx xx xx xx xx xx xx')
        self.txt_pattern.setToolTip(
            "Define quais bytes devem ser verificados.\n"
            "'xx' = qualquer valor (don't care).\n"
            "Exemplo HEX: 01 xx FF xx xx xx xx xx\n"
            "Exemplo BIN: 00000001 xxxxxxxx xxxxxxxx ...\n"
            "O primeiro estado que casar com o payload recebido e exibido."
        )

        btn_del = QPushButton('x')
        btn_del.setFixedSize(26, 26)
        btn_del.setStyleSheet(
            'QPushButton { background-color: #7f1d1d; color: white; border-radius: 4px; }'
            'QPushButton:hover { background-color: #b91c1c; }'
        )
        btn_del.clicked.connect(lambda: self._remove(row_widget, parent_layout))

        row_layout.addWidget(self.txt_label)
        row_layout.addWidget(self.btn_color)
        row_layout.addWidget(self.txt_pattern, 1)
        row_layout.addWidget(btn_del)

        self.row_widget = row_widget
        parent_layout.addWidget(row_widget)

    def _pick_color(self):
        _open_color_picker(self.btn_color)
        self.btn_color.setText(self.btn_color._color)

    def _remove(self, widget, layout):
        self.destroyed = True
        layout.removeWidget(widget)
        widget.deleteLater()

    def update_format(self, new_fmt: str):
        if self.destroyed:
            return
        old_pattern = _parse_pattern(self.txt_pattern.text(), self.fmt)
        self.fmt = new_fmt
        self.txt_pattern.setText(_format_pattern(old_pattern, new_fmt))

    def get_state(self) -> dict:
        return {
            'label': self.txt_label.text().strip(),
            'color': self.btn_color._color,
            'pattern': _parse_pattern(self.txt_pattern.text(), self.fmt),
        }

    def is_alive_and_valid(self) -> bool:
        return (not self.destroyed) and bool(self.txt_label.text().strip())


class MultiIndicatorDialog(QDialog):
    """
    Dialogo para o Indicador Multi-Estado (Beta).

    Permite criar N estados com nome, cor e padrao de bytes.
    Suporta HEX e BIN. 'xx' / 'xxxxxxxx' = don't care (byte ignorado na comparacao).
    O primeiro estado cujo padrao casar com o payload recebido e exibido.
    """

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle('Configurar Indicador Multi-Estado (Beta)')
        self.resize(640, 540)
        self._state_rows = []
        self._fmt = config.get('pattern_format', 'HEX') if config else 'HEX'

        outer = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_name = QLineEdit(config.get('name', 'Indicador') if config else 'Indicador')
        self.txt_can_id = QLineEdit(config.get('can_id', '100') if config else '100')
        self.txt_can_id.setPlaceholderText('ID em HEX (ex: 100)')

        self.cb_visual = QComboBox()
        self.cb_visual.addItems(['LED', 'Texto'])
        if config and config.get('visual_type') == 'Texto':
            self.cb_visual.setCurrentText('Texto')

        self.sp_led_size = QSpinBox()
        self.sp_led_size.setRange(12, 96)
        self.sp_led_size.setValue(config.get('led_size', 32) if config else 32)
        self.sp_led_size.setSuffix(' px')

        self.grid_size = _get_grid_size(parent)
        self.chk_snap_size = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap_size.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap_size.toggled.connect(self._on_snap_toggled)

        self.cb_fmt = QComboBox()
        self.cb_fmt.addItems(['HEX', 'BIN'])
        self.cb_fmt.setCurrentText(self._fmt)
        self.cb_fmt.currentTextChanged.connect(self._on_fmt_changed)

        default_lbl   = config.get('default_label', '??') if config else '??'
        default_color = config.get('default_color', '#52525b') if config else '#52525b'
        self.txt_default_label = QLineEdit(default_lbl)
        self.txt_default_label.setPlaceholderText('Texto quando nenhum estado casa')
        self.btn_default_color = _color_preview_btn(default_color, default_color)
        self.btn_default_color.setFixedWidth(80)
        self.btn_default_color.clicked.connect(lambda: self._pick_default_color())

        default_row_layout = QHBoxLayout()
        default_row_layout.addWidget(self.txt_default_label)
        default_row_layout.addWidget(self.btn_default_color)

        form.addRow('Nome:', self.txt_name)
        form.addRow('ID CAN (HEX):', self.txt_can_id)
        form.addRow('Tipo Visual:', self.cb_visual)
        form.addRow('Tamanho LED:', self.sp_led_size)
        form.addRow('Snap de Tamanho:', self.chk_snap_size)
        form.addRow('Formato do padrao:', self.cb_fmt)
        form.addRow('Estado padrao (label + cor):', default_row_layout)
        outer.addLayout(form)

        if self.chk_snap_size.isChecked():
            self._on_snap_toggled(True)

    def _on_snap_toggled(self, checked: bool):
        if checked:
            val = round(self.sp_led_size.value() / self.grid_size) * self.grid_size
            self.sp_led_size.setValue(max(self.grid_size, val))
            self.sp_led_size.setSingleStep(self.grid_size)
        else:
            self.sp_led_size.setSingleStep(4)

        hdr_layout = QHBoxLayout()
        lbl_h = QLabel('Estados  (ordem importa: primeiro que casar e exibido)')
        lbl_h.setStyleSheet('font-weight: bold; margin-top: 6px;')
        tip = QLabel("  xx = don't care")
        tip.setStyleSheet('color: #a1a1aa; font-size: 11px;')
        hdr_layout.addWidget(lbl_h)
        hdr_layout.addWidget(tip)
        hdr_layout.addStretch()
        outer.addLayout(hdr_layout)

        col_hdr = QHBoxLayout()
        for txt, fixed in [('Nome', 110), ('Cor', 80), ('Padrao de bytes (B0 B1 B2 B3 B4 B5 B6 B7)', -1), ('', 26)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet('color: #71717a; font-size: 10px;')
            if fixed > 0:
                lbl.setFixedWidth(fixed)
            col_hdr.addWidget(lbl, 0 if fixed > 0 else 1)
        outer.addLayout(col_hdr)

        self.states_area = QVBoxLayout()
        self.states_area.setSpacing(2)
        states_container = QWidget()
        states_container.setLayout(self.states_area)
        outer.addWidget(states_container, 1)

        if config and config.get('states'):
            for st in config['states']:
                self._add_state_row(st.get('label', ''), st.get('color', '#10b981'),
                                    st.get('pattern', [None]*8))
        else:
            self._add_state_row('Estado 0', '#52525b', [0] + [None]*7)
            self._add_state_row('Estado 1', '#10b981', [1] + [None]*7)

        btn_add = QPushButton('+ Adicionar Estado')
        btn_add.setStyleSheet(
            'QPushButton { background-color: #1e3a5f; color: white; padding: 5px 14px;'
            ' border-radius: 4px; }'
            'QPushButton:hover { background-color: #1d4ed8; }'
        )
        btn_add.clicked.connect(lambda: self._add_state_row('Novo Estado', '#3b82f6', [None]*8))
        outer.addWidget(btn_add)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet('color: #323238;')
        outer.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton('Salvar')
        btn_ok.clicked.connect(self._validate_and_accept)
        btn_cancel = QPushButton('Cancelar')
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        outer.addLayout(btn_row)

        self.cb_visual.currentTextChanged.connect(self._update_led_visibility)
        self._update_led_visibility(self.cb_visual.currentText())

    def _add_state_row(self, label: str, color: str, pattern: list):
        row = _StateRow(self.states_area, label, color, pattern, self._fmt)
        self._state_rows.append(row)

    def _pick_default_color(self):
        _open_color_picker(self.btn_default_color, self)
        self.btn_default_color.setText(self.btn_default_color._color)

    def _on_fmt_changed(self, new_fmt: str):
        self._fmt = new_fmt
        for row in self._state_rows:
            row.update_format(new_fmt)

    def _update_led_visibility(self, visual_type: str):
        self.sp_led_size.setVisible(visual_type == 'LED')

    def _validate_and_accept(self):
        try:
            int(self.txt_can_id.text().strip(), 16)
        except ValueError:
            QMessageBox.warning(self, 'Erro', 'ID CAN deve ser hexadecimal.')
            return
        valid = [r for r in self._state_rows if r.is_alive_and_valid()]
        if not valid:
            QMessageBox.warning(self, 'Erro',
                                'Adicione pelo menos um estado com nome preenchido.')
            return
        self.accept()

    def get_config(self) -> dict:
        can_id_text = self.txt_can_id.text().strip()
        try:
            can_id_str = f'{int(can_id_text, 16):03X}'
        except ValueError:
            can_id_str = can_id_text.upper().replace('0X', '')

        valid = [r for r in self._state_rows if r.is_alive_and_valid()]
        return {
            'type': 'multi_indicator',
            'name': self.txt_name.text().strip(),
            'can_id': can_id_str,
            'visual_type': self.cb_visual.currentText(),
            'led_size': self.sp_led_size.value(),
            'snap_size': self.chk_snap_size.isChecked(),
            'pattern_format': self._fmt,
            'states': [r.get_state() for r in valid],
            'default_label': self.txt_default_label.text().strip(),
            'default_color': self.btn_default_color._color,
        }


# ---------------------------------------------------------------------------
# IncrementalControllerDialog
# ---------------------------------------------------------------------------

class _ChannelRow:
    def __init__(self, parent_layout, name: str, byte_idx: int, min_val: int, max_val: int, step_val: int, def_val: int, color_hex: str, on_delete=None):
        self.parent_layout = parent_layout
        self.on_delete = on_delete
        self.widget = QWidget()
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self.txt_name = QLineEdit(name)
        self.txt_name.setPlaceholderText("Nome do Canal")
        self.txt_name.setMinimumWidth(120)

        self.sp_byte = QSpinBox()
        self.sp_byte.setRange(0, 7)
        self.sp_byte.setValue(byte_idx)
        self.sp_byte.setFixedWidth(50)

        self.sp_min = QSpinBox()
        self.sp_min.setRange(0, 255)
        self.sp_min.setValue(min_val)
        self.sp_min.setFixedWidth(60)

        self.sp_max = QSpinBox()
        self.sp_max.setRange(0, 255)
        self.sp_max.setValue(max_val)
        self.sp_max.setFixedWidth(60)

        self.sp_step = QSpinBox()
        self.sp_step.setRange(1, 255)
        self.sp_step.setValue(step_val)
        self.sp_step.setFixedWidth(55)

        self.sp_def = QSpinBox()
        self.sp_def.setRange(0, 255)
        self.sp_def.setValue(def_val)
        self.sp_def.setFixedWidth(55)

        self.btn_color = _color_preview_btn(color_hex, color_hex)
        self.btn_color.setFixedWidth(75)
        self.btn_color.clicked.connect(self._pick_color)

        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(26, 26)
        self.btn_del.setStyleSheet(
            "QPushButton { background-color: #3f1d24; color: #ef4444; border: 1px solid #7f1d1d; border-radius: 3px; font-weight: bold; }"
            "QPushButton:hover { background-color: #7f1d1d; color: white; }"
        )
        self.btn_del.clicked.connect(self._delete_self)

        layout.addWidget(self.txt_name, 2)
        layout.addWidget(self.sp_byte, 1)
        layout.addWidget(self.sp_min, 1)
        layout.addWidget(self.sp_max, 1)
        layout.addWidget(self.sp_step, 1)
        layout.addWidget(self.sp_def, 1)
        layout.addWidget(self.btn_color, 1)
        layout.addWidget(self.btn_del)

        parent_layout.addWidget(self.widget)
        self._alive = True

    def _pick_color(self):
        _open_color_picker(self.btn_color, self.widget)
        self.btn_color.setText(self.btn_color._color)

    def _delete_self(self):
        self._alive = False
        self.widget.deleteLater()
        if self.on_delete:
            self.on_delete(self)

    def is_alive_and_valid(self) -> bool:
        return self._alive and bool(self.txt_name.text().strip())

    def get_channel_config(self) -> dict:
        return {
            "name": self.txt_name.text().strip(),
            "byte": self.sp_byte.value(),
            "min": self.sp_min.value(),
            "max": self.sp_max.value(),
            "step": self.sp_step.value(),
            "default": self.sp_def.value(),
            "color": self.btn_color._color
        }


class IncrementalControllerDialog(QDialog):
    """Diálogo de configuração para o Controlador Incremental (Multi-Canais / Variáveis)."""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Controlador Incremental")
        self.resize(680, 520)

        self._channel_rows: list[_ChannelRow] = []

        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        # Dados Básicos
        form = QFormLayout()
        self.txt_name = QLineEdit(config.get("name", "Controlador Incremental") if config else "Controlador Incremental")
        self.txt_can_id = QLineEdit(config.get("can_id", "405") if config else "405")
        
        self.txt_base_payload = QLineEdit(config.get("base_payload", "00 00 00 00 00 00 00 00") if config else "00 00 00 00 00 00 00 00")
        self.txt_base_payload.setPlaceholderText("8 bytes em HEX (ex: 00 00 00 00 00 00 00 00)")

        # Periodicidade e Intertravamento
        timing_layout = QHBoxLayout()
        self.chk_periodic = QCheckBox("Transmissão Cíclica (Periódica)")
        self.chk_periodic.setChecked(config.get("periodic", True) if config else True)
        
        self.sp_hz = QSpinBox()
        self.sp_hz.setRange(1, 500)
        self.sp_hz.setValue(config.get("hz", 20) if config else 20)
        self.sp_hz.setSuffix(" Hz")
        
        timing_layout.addWidget(self.chk_periodic)
        timing_layout.addWidget(QLabel("Frequência:"))
        timing_layout.addWidget(self.sp_hz)
        timing_layout.addStretch()

        self.chk_mutual_exclusion = QCheckBox("Exclusão Mútua / Intertravamento (Zerar os demais canais ao alterar um canal)")
        self.chk_mutual_exclusion.setToolTip("Garante que somente um canal tenha valor ativo (> mín) por vez, zerando os outros.")
        self.chk_mutual_exclusion.setChecked(config.get("mutual_exclusion", True) if config else True)

        form.addRow("Nome do Widget:", self.txt_name)
        form.addRow("ID CAN (HEX):", self.txt_can_id)
        form.addRow("Payload Base:", self.txt_base_payload)
        form.addRow("Transmissão:", timing_layout)
        form.addRow("Intertravamento:", self.chk_mutual_exclusion)

        outer.addLayout(form)

        # Divisor
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #323238;")
        outer.addWidget(sep1)

        # Cabeçalho dos Canais
        lbl_channels = QLabel("Canais de Controle / Bytes:")
        lbl_channels.setStyleSheet("font-weight: bold; color: white; font-size: 13px;")
        outer.addWidget(lbl_channels)

        col_hdr = QHBoxLayout()
        col_hdr.setSpacing(6)
        headers = [
            ("Nome do Canal", 2),
            ("Byte (0-7)", 1),
            ("Mín", 1),
            ("Máx", 1),
            ("Passo", 1),
            ("Inicial", 1),
            ("Cor", 1),
            ("", 26)
        ]
        for txt, stretch in headers:
            lbl = QLabel(txt)
            lbl.setStyleSheet("color: #a1a1aa; font-size: 11px; font-weight: bold;")
            if txt == "":
                lbl.setFixedWidth(26)
                col_hdr.addWidget(lbl)
            else:
                col_hdr.addWidget(lbl, stretch)
        outer.addLayout(col_hdr)

        # Área de Canais
        self.channels_area = QVBoxLayout()
        self.channels_area.setSpacing(4)
        channels_container = QWidget()
        channels_container.setLayout(self.channels_area)
        outer.addWidget(channels_container, 1)

        # Inicialização dos canais
        if config and config.get("channels"):
            for ch in config["channels"]:
                self._add_channel_row(
                    ch.get("name", "Canal"),
                    ch.get("byte", 0),
                    ch.get("min", 0),
                    ch.get("max", 255),
                    ch.get("step", 10),
                    ch.get("default", 0),
                    ch.get("color", "#3b82f6")
                )
        else:
            # Padrão: 2 canais (ex: Canal A no Byte 0 e Canal B no Byte 1)
            self._add_channel_row("Canal A", 0, 0, 255, 10, 0, "#3b82f6")
            self._add_channel_row("Canal B", 1, 0, 255, 10, 0, "#ef4444")

        btn_add = QPushButton("+ Adicionar Canal")
        btn_add.setStyleSheet(
            "QPushButton { background-color: #1e3a5f; color: white; padding: 5px 14px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        btn_add.clicked.connect(self._add_new_channel_auto)
        outer.addWidget(btn_add)

        # Divisor
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #323238;")
        outer.addWidget(sep2)

        # Botões Rodapé
        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self._validate_and_accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        outer.addLayout(btn_row)

    def _add_channel_row(self, name: str, byte_idx: int, min_val: int, max_val: int, step_val: int, def_val: int, color_hex: str):
        row = _ChannelRow(
            self.channels_area, name, byte_idx, min_val, max_val, step_val, def_val, color_hex,
            on_delete=lambda r: self._channel_rows.remove(r) if r in self._channel_rows else None
        )
        self._channel_rows.append(row)

    def _add_new_channel_auto(self):
        existing_bytes = [r.sp_byte.value() for r in self._channel_rows if r._alive]
        next_byte = 0
        for b in range(8):
            if b not in existing_bytes:
                next_byte = b
                break
        colors = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"]
        next_color = colors[len(self._channel_rows) % len(colors)]
        self._add_channel_row(f"Canal {chr(65 + len(self._channel_rows))}", next_byte, 0, 255, 10, 0, next_color)

    def _validate_and_accept(self):
        try:
            int(self.txt_can_id.text().strip(), 16)
        except ValueError:
            QMessageBox.warning(self, "Erro", "ID CAN deve ser hexadecimal válido (ex: 405 ou 0C0).")
            return

        valid = [r for r in self._channel_rows if r.is_alive_and_valid()]
        if not valid:
            QMessageBox.warning(self, "Erro", "Adicione pelo menos um canal com nome preenchido.")
            return

        for r in valid:
            if r.sp_min.value() >= r.sp_max.value():
                QMessageBox.warning(self, "Erro", f"No canal '{r.txt_name.text()}', o valor mínimo deve ser menor que o máximo.")
                return

        self.accept()

    def get_config(self) -> dict:
        can_id_text = self.txt_can_id.text().strip()
        try:
            can_id_str = f"{int(can_id_text, 16):03X}"
        except ValueError:
            can_id_str = can_id_text.upper().replace("0X", "")

        valid = [r for r in self._channel_rows if r.is_alive_and_valid()]
        return {
            "type": "incremental_controller",
            "name": self.txt_name.text().strip(),
            "can_id": can_id_str,
            "base_payload": self.txt_base_payload.text().strip(),
            "periodic": self.chk_periodic.isChecked(),
            "hz": self.sp_hz.value(),
            "mutual_exclusion": self.chk_mutual_exclusion.isChecked(),
            "channels": [r.get_channel_config() for r in valid]
        }


# ---------------------------------------------------------------------------
# TerminalDialog
# ---------------------------------------------------------------------------

class TerminalDialog(QDialog):
    """Diálogo de configuração para o Terminal CAN (somente leitura com filtros)."""

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Terminal CAN")
        self.resize(440, 280)

        outer = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_name = QLineEdit(config.get("name", "Terminal CAN") if config else "Terminal CAN")
        self.txt_filter = QLineEdit(config.get("filter_ids", "") if config else "")
        self.txt_filter.setPlaceholderText("Ex: 405, 180 (ou deixe vazio para exibir todos)")

        self.sp_max_lines = QSpinBox()
        self.sp_max_lines.setRange(50, 5000)
        self.sp_max_lines.setValue(config.get("max_lines", 200) if config else 200)

        self.grid_size = _get_grid_size(parent)
        self.sp_width = QSpinBox()
        self.sp_width.setRange(160, 3000)
        self.sp_width.setValue(int(config.get("width", 400)) if config and config.get("width") else 400)
        self.sp_width.setSuffix(" px")

        self.sp_height = QSpinBox()
        self.sp_height.setRange(100, 2000)
        self.sp_height.setValue(int(config.get("height", 250)) if config and config.get("height") else 250)
        self.sp_height.setSuffix(" px")

        self.chk_snap_size = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap_size.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap_size.toggled.connect(self._on_snap_toggled)

        self.chk_timestamp = QCheckBox("Exibir Timestamp (Hora:Min:Seg.ms)")
        self.chk_timestamp.setChecked(config.get("show_timestamp", True) if config else True)

        self.chk_ascii = QCheckBox("Exibir Decodificação ASCII do Payload")
        self.chk_ascii.setChecked(config.get("show_ascii", True) if config else True)

        self.chk_freq = QCheckBox("Exibir Frequência (Hz) Calculada")
        self.chk_freq.setChecked(config.get("show_freq", True) if config else True)

        form.addRow("Nome do Widget:", self.txt_name)
        form.addRow("Filtro de IDs CAN:", self.txt_filter)
        form.addRow("Limite de Linhas (Buffer):", self.sp_max_lines)
        form.addRow("Largura:", self.sp_width)
        form.addRow("Altura:", self.sp_height)
        form.addRow("Snap de Tamanho:", self.chk_snap_size)
        form.addRow("Opções Visuais:", self.chk_timestamp)
        form.addRow("", self.chk_ascii)
        form.addRow("", self.chk_freq)

        outer.addLayout(form)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #323238;")
        outer.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        outer.addLayout(btn_row)

        if self.chk_snap_size.isChecked():
            self._on_snap_toggled(True)

    def _on_snap_toggled(self, checked: bool):
        if checked:
            w = round(self.sp_width.value() / self.grid_size) * self.grid_size
            h = round(self.sp_height.value() / self.grid_size) * self.grid_size
            self.sp_width.setValue(max(self.grid_size, w))
            self.sp_height.setValue(max(self.grid_size, h))
            self.sp_width.setSingleStep(self.grid_size)
            self.sp_height.setSingleStep(self.grid_size)
        else:
            self.sp_width.setSingleStep(20)
            self.sp_height.setSingleStep(20)

    def get_config(self) -> dict:
        return {
            "type": "terminal",
            "name": self.txt_name.text().strip(),
            "filter_ids": self.txt_filter.text().strip(),
            "max_lines": self.sp_max_lines.value(),
            "width": self.sp_width.value(),
            "height": self.sp_height.value(),
            "snap_size": self.chk_snap_size.isChecked(),
            "show_timestamp": self.chk_timestamp.isChecked(),
            "show_ascii": self.chk_ascii.isChecked(),
            "show_freq": self.chk_freq.isChecked()
        }


# ---------------------------------------------------------------------------
# ShapeDialog
# ---------------------------------------------------------------------------

class ShapeDialog(QDialog):
    """Diálogo para criação e edição de formas geométricas livres (Linha, Retângulo, Círculo)."""

    def __init__(self, parent=None, config=None, default_shape="rectangle", grid_size=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Forma Livre")
        self.resize(440, 460)

        self.grid_size = _get_grid_size(parent, grid_size)

        outer = QVBoxLayout(self)
        self.form = QFormLayout()

        # Tipo da Forma
        self.cb_shape_type = QComboBox()
        self.cb_shape_type.addItem("Retângulo / Quadrado", "rectangle")
        self.cb_shape_type.addItem("Círculo / Elipse", "circle")
        self.cb_shape_type.addItem("Linha", "line")

        init_shape = config.get("shape_type", default_shape) if config else default_shape
        idx = self.cb_shape_type.findData(init_shape)
        if idx >= 0:
            self.cb_shape_type.setCurrentIndex(idx)

        # Orientação da Linha
        self.cb_orientation = QComboBox()
        self.cb_orientation.addItem("Horizontal", "horizontal")
        self.cb_orientation.addItem("Vertical", "vertical")
        self.cb_orientation.addItem("Diagonal (Descendente)", "diagonal_down")
        self.cb_orientation.addItem("Diagonal (Ascendente)", "diagonal_up")
        if config and config.get("orientation"):
            idx_o = self.cb_orientation.findData(config["orientation"])
            if idx_o >= 0:
                self.cb_orientation.setCurrentIndex(idx_o)

        # Dimensões
        init_w = int(config.get("width", 200 if init_shape == "line" else 160)) if config else (200 if init_shape == "line" else 160)
        init_h = int(config.get("height", 20 if init_shape == "line" else 160)) if config else (20 if init_shape == "line" else 160)

        self.sp_width = QSpinBox()
        self.sp_width.setRange(4, 3000)
        self.sp_width.setValue(init_w)
        self.sp_width.setSuffix(" px")

        self.sp_height = QSpinBox()
        self.sp_height.setRange(4, 3000)
        self.sp_height.setValue(init_h)
        self.sp_height.setSuffix(" px")

        # Snap
        self.chk_snap = QCheckBox(f"Ajustar tamanho ao snap da grade ({self.grid_size} px)")
        self.chk_snap.setChecked(bool(config.get("snap_size", False)) if config else False)
        self.chk_snap.toggled.connect(self._on_snap_toggled)

        # Cor do traço e espessura
        init_stroke = config.get("stroke_color", "#3b82f6") if config else "#3b82f6"
        self.btn_stroke_color = _color_preview_btn(init_stroke, init_stroke)
        self.btn_stroke_color.clicked.connect(lambda: self._pick_color(self.btn_stroke_color))

        self.sp_stroke_width = QSpinBox()
        self.sp_stroke_width.setRange(1, 40)
        self.sp_stroke_width.setValue(int(config.get("stroke_width", 2)) if config else 2)
        self.sp_stroke_width.setSuffix(" px")

        self.cb_stroke_style = QComboBox()
        self.cb_stroke_style.addItem("Sólido", "solid")
        self.cb_stroke_style.addItem("Tracejado", "dash")
        self.cb_stroke_style.addItem("Pontilhado", "dot")
        if config and config.get("stroke_style"):
            idx_s = self.cb_stroke_style.findData(config["stroke_style"])
            if idx_s >= 0:
                self.cb_stroke_style.setCurrentIndex(idx_s)

        # Preenchimento
        self.cb_fill_type = QComboBox()
        self.cb_fill_type.addItem("Transparente (Vazado)", "transparent")
        self.cb_fill_type.addItem("Cor Sólida", "solid")
        init_fill = config.get("fill_color", "transparent") if config else "transparent"
        if init_fill != "transparent":
            self.cb_fill_type.setCurrentIndex(1)

        fill_btn_color = init_fill if init_fill != "transparent" else "#1e293b"
        self.btn_fill_color = _color_preview_btn(fill_btn_color, fill_btn_color)
        self.btn_fill_color.clicked.connect(lambda: self._pick_color(self.btn_fill_color))

        # Arredondamento
        self.sp_radius = QSpinBox()
        self.sp_radius.setRange(0, 100)
        self.sp_radius.setValue(int(config.get("corner_radius", 0)) if config else 0)
        self.sp_radius.setSuffix(" px")

        self.form.addRow("Tipo de Forma:", self.cb_shape_type)
        self.form.addRow("Orientação da Linha:", self.cb_orientation)
        self.form.addRow("Largura:", self.sp_width)
        self.form.addRow("Altura:", self.sp_height)
        self.form.addRow("Snap de Tamanho:", self.chk_snap)
        self.form.addRow("Cor da Linha/Borda:", self.btn_stroke_color)
        self.form.addRow("Espessura:", self.sp_stroke_width)
        self.form.addRow("Estilo do Traço:", self.cb_stroke_style)
        self.form.addRow("Preenchimento:", self.cb_fill_type)
        self.form.addRow("Cor de Fundo:", self.btn_fill_color)
        self.form.addRow("Raio dos Cantos:", self.sp_radius)

        outer.addLayout(self.form)

        # Botões
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #323238;")
        outer.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("Salvar")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        outer.addLayout(btn_row)

        self.cb_shape_type.currentIndexChanged.connect(self._update_visibility)
        self.cb_fill_type.currentIndexChanged.connect(self._update_visibility)
        self._update_visibility()

        if self.chk_snap.isChecked():
            self._on_snap_toggled(True)

    def _on_snap_toggled(self, checked: bool):
        if checked:
            w = round(self.sp_width.value() / self.grid_size) * self.grid_size
            h = round(self.sp_height.value() / self.grid_size) * self.grid_size
            self.sp_width.setValue(max(self.grid_size, w))
            self.sp_height.setValue(max(self.grid_size, h))
            self.sp_width.setSingleStep(self.grid_size)
            self.sp_height.setSingleStep(self.grid_size)
        else:
            self.sp_width.setSingleStep(10)
            self.sp_height.setSingleStep(10)

    def _pick_color(self, btn: QPushButton):
        _open_color_picker(btn, self)
        btn.setText(btn._color)

    def _update_visibility(self):
        shape = self.cb_shape_type.currentData()
        is_line = (shape == "line")
        is_rect = (shape == "rectangle")
        fill_solid = (self.cb_fill_type.currentData() == "solid")

        def _set_row_visible(widget, visible):
            lbl = self.form.labelForField(widget)
            widget.setVisible(visible)
            if lbl:
                lbl.setVisible(visible)

        _set_row_visible(self.cb_orientation, is_line)
        _set_row_visible(self.cb_fill_type, not is_line)
        _set_row_visible(self.btn_fill_color, not is_line and fill_solid)
        _set_row_visible(self.sp_radius, is_rect)

    def get_config(self) -> dict:
        shape_type = self.cb_shape_type.currentData()
        fill_color = self.btn_fill_color._color if (shape_type != "line" and self.cb_fill_type.currentData() == "solid") else "transparent"
        return {
            "type": "shape",
            "shape_type": shape_type,
            "orientation": self.cb_orientation.currentData(),
            "width": self.sp_width.value(),
            "height": self.sp_height.value(),
            "snap_size": self.chk_snap.isChecked(),
            "stroke_color": self.btn_stroke_color._color,
            "stroke_width": self.sp_stroke_width.value(),
            "stroke_style": self.cb_stroke_style.currentData(),
            "fill_color": fill_color,
            "corner_radius": self.sp_radius.value() if shape_type == "rectangle" else 0
        }
