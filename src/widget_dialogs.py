"""
widget_dialogs.py — Diálogos de configuração para os Widgets do Dashboard.
"""

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
        _set_row_visible(self.sp_led_size,   is_led)
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
            "hz": self.sp_hz.value()
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

        self.sp_size = QSpinBox()
        self.sp_size.setRange(40, 600)
        self.sp_size.setValue(config.get("gauge_size", 160) if config else 160)
        self.sp_size.setSuffix(" px")
        self.sp_size.setSingleStep(20)

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
        form.addRow('Formato do padrao:', self.cb_fmt)
        form.addRow('Estado padrao (label + cor):', default_row_layout)
        outer.addLayout(form)

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
            'pattern_format': self._fmt,
            'states': [r.get_state() for r in valid],
            'default_label': self.txt_default_label.text().strip(),
            'default_color': self.btn_default_color._color,
        }
