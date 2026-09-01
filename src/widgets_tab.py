"""
widgets_tab.py — Widget da Aba de Painéis / Gauges
"""

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu, QProgressBar, QSlider, QSpinBox, QLineEdit, QPlainTextEdit
)
from PyQt6.QtGui import QAction, QColor, QPainter, QPen, QBrush, QFont, QTextCursor
import math

from src.widget_dialogs import (
    LabelDialog, IndicatorDialog, ControllerDialog, GaugeDialog, MultiIndicatorDialog,
    IncrementalControllerDialog, TerminalDialog
)

class CanvasWidget(QFrame):
    """Canvas com opção de grade e snap magnético para auxiliar no posicionamento."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_grid = False
        self.snap_to_grid = True
        self.grid_size = 20

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.show_grid:
            return
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#404040"), 1, Qt.PenStyle.DotLine))
        grid_size = self.grid_size
        for x in range(0, self.width(), grid_size):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_size):
            painter.drawLine(0, y, self.width(), y)

class DashboardWidget(QWidget):
    """Classe base para widgets arrastáveis no Canvas."""
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.edit_mode = False
        self._drag_start_pos = None
        self.edit_callback = None       # Definido por WidgetsTab ao posicionar o widget
        self.duplicate_callback = None  # Definido por WidgetsTab ao posicionar o widget

    def set_edit_mode(self, enabled):
        self.edit_mode = enabled
        if enabled:
            self.setStyleSheet("DashboardWidget { border: 1px dashed #a1a1aa; background-color: rgba(255,255,255,10); }")
            for child in self.findChildren(QWidget):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        else:
            self.setStyleSheet("")
            for child in self.findChildren(QWidget):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

    def mousePressEvent(self, event):
        if self.edit_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self.raise_()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.edit_mode and self._drag_start_pos is not None:
            raw_pos = self.pos() + event.pos() - self._drag_start_pos
            parent = self.parent()
            if parent and hasattr(parent, "snap_to_grid") and parent.snap_to_grid:
                grid_size = getattr(parent, "grid_size", 20)
                snapped_x = round(raw_pos.x() / grid_size) * grid_size
                snapped_y = round(raw_pos.y() / grid_size) * grid_size
                snapped_x = max(0, min(snapped_x, parent.width() - self.width()))
                snapped_y = max(0, min(snapped_y, parent.height() - self.height()))
                self.move(snapped_x, snapped_y)
            else:
                self.move(raw_pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.edit_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
            parent = self.parent()
            if parent and hasattr(parent, "snap_to_grid") and parent.snap_to_grid:
                self.snap_to_grid(getattr(parent, "grid_size", 20))
        else:
            super().mouseReleaseEvent(event)

    def center_horizontally(self):
        """Centraliza o widget na horizontal do canvas."""
        parent = self.parent()
        if parent:
            new_x = max(0, (parent.width() - self.width()) // 2)
            if hasattr(parent, "snap_to_grid") and parent.snap_to_grid:
                grid_size = getattr(parent, "grid_size", 20)
                new_x = round(new_x / grid_size) * grid_size
            self.move(new_x, self.y())

    def fit_to_width(self, margin=20):
        """Ajusta a largura do widget para ocupar toda a largura da tela/canvas com margens."""
        parent = self.parent()
        if parent:
            target_w = max(200, parent.width() - (margin * 2))
            self.setFixedWidth(target_w)
            self.move(margin, self.y())
            if isinstance(self.config, dict):
                self.config["width"] = target_w

    def snap_to_grid(self, grid_size=20):
        """Alinha a posição atual do widget para o múltiplo mais próximo da grade."""
        new_x = round(self.x() / grid_size) * grid_size
        new_y = round(self.y() / grid_size) * grid_size
        parent = self.parent()
        if parent:
            new_x = max(0, min(new_x, parent.width() - self.width()))
            new_y = max(0, min(new_y, parent.height() - self.height()))
        self.move(new_x, new_y)

    def contextMenuEvent(self, event):
        if self.edit_mode:
            menu = QMenu(self)
            menu.setStyleSheet(
                "QMenu { background-color: #202024; color: white; border: 1px solid #323238; }"
                "QMenu::item { padding: 6px 24px; }"
                "QMenu::item:selected { background-color: #3b82f6; }"
            )
            action_edit = QAction("✏️ Editar Widget", self)
            action_edit.triggered.connect(lambda: self.edit_callback(self) if self.edit_callback else None)

            action_center = QAction("↔️ Centralizar na Horizontal", self)
            action_center.triggered.connect(self.center_horizontally)

            action_full_width = QAction("📐 Ajustar à Largura da Tela (100%)", self)
            action_full_width.triggered.connect(lambda: self.fit_to_width(20))

            action_snap = QAction("🧲 Alinhar à Grade", self)
            action_snap.triggered.connect(lambda: self.snap_to_grid(20))

            action_dup = QAction("📋 Duplicar Widget", self)
            action_dup.triggered.connect(lambda: self.duplicate_callback(self) if self.duplicate_callback else None)
            
            action_del = QAction("🗑 Excluir Widget", self)
            action_del.triggered.connect(self.deleteLater)
            
            menu.addAction(action_edit)
            menu.addSeparator()
            menu.addAction(action_center)
            menu.addAction(action_full_width)
            menu.addAction(action_snap)
            menu.addSeparator()
            menu.addAction(action_dup)
            menu.addAction(action_del)
            menu.exec(event.globalPos())
        else:
            super().contextMenuEvent(event)


def normalize_can_id(val) -> int:
    """Converte ID CAN (int, hex str com ou sem 0x, decimal) para int de forma segura."""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return -1
        try:
            return int(val, 16)
        except ValueError:
            try:
                return int(val, 10)
            except ValueError:
                return -1
    return -1


class LabelWidget(DashboardWidget):
    def __init__(self, parent, config):
        super().__init__(parent, config)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.lbl = QLabel(str(config.get("text", "")))
        try:
            size = int(config.get("size", 14))
        except (ValueError, TypeError):
            size = 14
        bold = "font-weight: bold;" if config.get("bold", False) else ""
        italic = "font-style: italic;" if config.get("italic", False) else ""
        strike = "text-decoration: line-through;" if config.get("strikethrough", False) else ""
        color = config.get("color", "#ffffff")
        self.lbl.setStyleSheet(f"color: {color}; font-size: {size}px; {bold} {italic} {strike}")
        layout.addWidget(self.lbl)


class IndicatorWidget(DashboardWidget):
    def __init__(self, parent, config):
        super().__init__(parent, config)
        self.target_can_id = normalize_can_id(self.config.get("can_id"))
        try:
            self.config["byte"] = int(self.config.get("byte", 0))
        except (ValueError, TypeError):
            self.config["byte"] = 0
        try:
            self.config["bit"] = int(self.config.get("bit", 0))
        except (ValueError, TypeError):
            self.config["bit"] = 0
        self.config["visual_type"] = self.config.get("visual_type", "LED")
        self.config["val_off"] = str(self.config.get("val_off", "#52525b"))
        self.config["val_on"] = str(self.config.get("val_on", "#10b981"))
        try:
            self.config["led_size"] = int(self.config.get("led_size", 32))
        except (ValueError, TypeError):
            self.config["led_size"] = 32

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_title = QLabel(str(self.config.get("name", "")))
        self.lbl_title.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_display = QLabel()
        self.lbl_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_display)
        
        self.state = False
        self.update_visuals()

    def process_can_frame(self, can_id: int, freq: float, payload: list):
        if can_id != self.target_can_id:
            return
            
        byte_idx = self.config.get("byte", 0)
        if byte_idx < len(payload):
            bit_idx = self.config.get("bit", 0)
            val = payload[byte_idx]
            new_state = (val & (1 << bit_idx)) != 0
            if new_state != self.state:
                self.state = new_state
                self.update_visuals()

    def update_visuals(self):
        is_on = self.state
        val = self.config.get("val_on", "#10b981") if is_on else self.config.get("val_off", "#52525b")
        
        if self.config.get("visual_type") == "LED":
            color = val if isinstance(val, str) and val.startswith("#") else ("#10b981" if is_on else "#52525b")
            led_size = self.config.get("led_size", 32)
            self.lbl_display.setText("●")
            self.lbl_display.setStyleSheet(f"color: {color}; font-size: {led_size}px;")
        else:
            self.lbl_display.setText(str(val))
            self.lbl_display.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")




class MultiIndicatorWidget(DashboardWidget):
    def __init__(self, parent, config):
        super().__init__(parent, config)
        self.target_can_id = normalize_can_id(self.config.get("can_id"))
        self.config["visual_type"] = self.config.get("visual_type", "LED")
        try:
            self.config["led_size"] = int(self.config.get("led_size", 32))
        except (ValueError, TypeError):
            self.config["led_size"] = 32

        # Normaliza padrões de estados
        raw_states = self.config.get("states", [])
        normalized_states = []
        for st in raw_states:
            pat = []
            for p in st.get("pattern", []):
                if p is None or p == "" or str(p).lower() in ("xx", "x", "?", "-", "none", "null"):
                    pat.append(None)
                else:
                    try:
                        if isinstance(p, int):
                            pat.append(p)
                        else:
                            p_str = str(p).strip()
                            pat.append(int(p_str, 16 if "0x" in p_str or any(c in 'abcdefABCDEF' for c in p_str) else 10))
                    except Exception:
                        pat.append(None)
            st_dict = dict(st)
            st_dict["pattern"] = pat
            normalized_states.append(st_dict)
        self.config["states"] = normalized_states

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_title = QLabel(str(self.config.get("name", "")))
        self.lbl_title.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_display = QLabel()
        self.lbl_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_display)
        
        self.current_state_idx = -1
        self.update_visuals()

    def process_can_frame(self, can_id: int, freq: float, payload: list):
        if can_id != self.target_can_id:
            return
            
        matched_idx = -1
        states = self.config.get("states", [])
        
        for i, st in enumerate(states):
            pattern = st.get("pattern", [])
            match = True
            for j, p_val in enumerate(pattern):
                if p_val is not None and j < len(payload):
                    if payload[j] != p_val:
                        match = False
                        break
            if match:
                matched_idx = i
                break
                
        if matched_idx != self.current_state_idx:
            self.current_state_idx = matched_idx
            self.update_visuals()

    def update_visuals(self):
        if self.current_state_idx >= 0:
            states = self.config.get("states", [])
            st = states[self.current_state_idx]
            val = st.get("label", "")
            color = st.get("color", "#ffffff")
        else:
            val = self.config.get("default_label", "??")
            color = self.config.get("default_color", "#52525b")
            
        if self.config.get("visual_type") == "LED":
            if not isinstance(color, str) or not color.startswith("#"):
                color = "#52525b"
            led_size = self.config.get("led_size", 32)
            self.lbl_display.setText("●")
            self.lbl_display.setStyleSheet(f"color: {color}; font-size: {led_size}px;")
        else:
            self.lbl_display.setText(str(val))
            self.lbl_display.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold;")


class GaugeWidget(DashboardWidget):
    """Indicador analógico tipo gauge com arco de progresso ou barras."""

    def __init__(self, parent, config):
        super().__init__(parent, config)
        self.target_can_id = normalize_can_id(self.config.get("can_id"))
        try:
            self.config["byte"] = int(self.config.get("byte", 0))
        except (ValueError, TypeError):
            self.config["byte"] = 0
        try:
            self.config["byte_len"] = int(self.config.get("byte_len", 1))
        except (ValueError, TypeError):
            self.config["byte_len"] = 1
        try:
            self.config["val_min_raw"] = float(self.config.get("val_min_raw", 0))
        except (ValueError, TypeError):
            self.config["val_min_raw"] = 0.0
        try:
            self.config["val_max_raw"] = float(self.config.get("val_max_raw", 255))
        except (ValueError, TypeError):
            self.config["val_max_raw"] = 255.0
        try:
            self.config["val_min_conv"] = float(self.config.get("val_min_conv", 0.0))
        except (ValueError, TypeError):
            self.config["val_min_conv"] = 0.0
        try:
            self.config["val_max_conv"] = float(self.config.get("val_max_conv", 100.0))
        except (ValueError, TypeError):
            self.config["val_max_conv"] = 100.0
        try:
            self.config["gauge_size"] = int(self.config.get("gauge_size", 160))
        except (ValueError, TypeError):
            self.config["gauge_size"] = 160
        self.config["show_float"] = bool(self.config.get("show_float", False))
        self.config["invert_direction"] = bool(self.config.get("invert_direction", False))

        self._raw_value = self.config["val_min_raw"]
        size = self.config["gauge_size"]
        style = self.config.get("style", "Arco")
        if style == "Barra Horizontal":
            self.setFixedSize(size, max(60, size // 3) + 30)
        else:
            self.setFixedSize(size, size + 30)

    def _get_conv_value(self):
        v_min = self.config["val_min_raw"]
        v_max = self.config["val_max_raw"]
        c_min = self.config["val_min_conv"]
        c_max = self.config["val_max_conv"]

        if v_max == v_min:
            return c_min
        
        ratio = (self._raw_value - v_min) / (v_max - v_min)
        return c_min + ratio * (c_max - c_min)

    def process_can_frame(self, can_id: int, freq: float, payload: list):
        if can_id != self.target_can_id:
            return
        byte_idx = self.config["byte"]
        byte_len = self.config["byte_len"]
        if byte_idx + byte_len - 1 < len(payload):
            raw = 0
            for i in range(byte_len):
                raw = (raw << 8) | payload[byte_idx + i]
            
            # Clamp raw value
            v_min = self.config["val_min_raw"]
            v_max = self.config["val_max_raw"]
            real_min = min(v_min, v_max)
            real_max = max(v_min, v_max)
            raw = max(real_min, min(real_max, float(raw)))

            if raw != self._raw_value:
                self._raw_value = raw
                self.update()  # trigger paintEvent

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = self.config.get("gauge_size", 160)
        style = self.config.get("style", "Arco")
        name = self.config.get("name", "")
        unit = self.config.get("unit", "")
        show_float = self.config.get("show_float", False)
        
        c_min = self.config.get("val_min_conv", 0.0)
        c_max = self.config.get("val_max_conv", 100.0)
        
        val_conv = self._get_conv_value()

        # Format number
        if show_float:
            val_text = f"{val_conv:.2f}{' ' + unit if unit else ''}"
        else:
            val_text = f"{int(round(val_conv))}{' ' + unit if unit else ''}"

        # Calculate ratio (0 to 1) for coloring and bars
        c_real_min, c_real_max = min(c_min, c_max), max(c_min, c_max)
        if c_real_max == c_real_min:
            ratio = 0.0
        else:
            # regardless of whether the scale is inverted, ratio 0 is start, 1 is end
            ratio = (val_conv - c_min) / (c_max - c_min)
            ratio = max(0.0, min(1.0, ratio))

        # Color interpolation (green -> yellow -> red)
        if ratio < 0.5:
            r = int(255 * (ratio * 2))
            g = 220
        else:
            r = 255
            g = int(220 * (1 - (ratio - 0.5) * 2))
        bar_color = QColor(r, g, 60)

        # Draw Title
        painter.setPen(QColor("#a1a1aa"))
        font_name = QFont()
        font_name.setPixelSize(max(8, size // 14))
        painter.setFont(font_name)
        if style == "Barra Horizontal":
            widget_h = max(60, size // 3)
            painter.drawText(0, widget_h + 4, size, 24, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, name)
        else:
            painter.drawText(0, size + 4, size, 24, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, name)
            
        invert = self.config.get("invert_direction", False)

        if style == "Arco":
            margin = max(10, size // 15)
            cx = size // 2
            cy = size // 2
            radius = (size // 2) - margin
            pen_width = max(6, size // 12)

            # Arco de fundo
            pen_bg = QPen(QColor("#3f3f46"), pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_bg)
            start_angle = 225 * 16
            span_angle  = -270 * 16
            painter.drawArc(cx - radius, margin, radius * 2, radius * 2, start_angle, span_angle)

            # Arco de valor
            pen_val = QPen(bar_color, pen_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_val)
            if invert:
                painter.drawArc(cx - radius, margin, radius * 2, radius * 2,
                                start_angle + span_angle, -int(span_angle * ratio))
                angle_deg = 225 - 270 + ratio * 270
            else:
                painter.drawArc(cx - radius, margin, radius * 2, radius * 2,
                                start_angle, int(span_angle * ratio))
                angle_deg = 225 - ratio * 270

            # Ponteiro
            angle_rad = math.radians(angle_deg)
            needle_len = radius - pen_width - (size // 20)
            nx = cx + needle_len * math.cos(angle_rad)
            ny = cy - needle_len * math.sin(angle_rad)
            painter.setPen(QPen(QColor("#ffffff"), max(2, size // 50), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx), int(cy), int(nx), int(ny))

            # Ponto central
            painter.setBrush(QBrush(QColor("#a1a1aa")))
            painter.setPen(Qt.PenStyle.NoPen)
            center_dot = max(6, size // 15)
            painter.drawEllipse(cx - center_dot // 2, cy - center_dot // 2, center_dot, center_dot)

            # Valor numérico
            painter.setPen(QColor("#ffffff"))
            font_val = QFont()
            font_val.setPixelSize(max(10, size // 8))
            font_val.setBold(True)
            painter.setFont(font_val)
            painter.drawText(0, cy + radius // 3, size, 30,
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, val_text)

            # Min/Max labels
            painter.setPen(QColor("#71717a"))
            font_mm = QFont()
            font_mm.setPixelSize(max(8, size // 14))
            painter.setFont(font_mm)
            txt_min = f"{c_min:.1f}" if show_float else f"{int(c_min)}"
            txt_max = f"{c_max:.1f}" if show_float else f"{int(c_max)}"
            painter.drawText(margin, size - 18, 40, 16,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt_min)
            painter.drawText(size - margin - 40, size - 18, 40, 16,
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, txt_max)

        elif style == "Barra Horizontal":
            bar_h = max(20, size // 6)
            widget_h = max(60, size // 3)
            bar_y = (widget_h - bar_h) // 2
            painter.setBrush(QBrush(QColor("#3f3f46")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(10, bar_y, size - 20, bar_h, 4, 4)

            w_fill = int((size - 20) * ratio)
            if w_fill > 0:
                painter.setBrush(QBrush(bar_color))
                if invert:
                    painter.drawRoundedRect(10 + (size - 20) - w_fill, bar_y, w_fill, bar_h, 4, 4)
                else:
                    painter.drawRoundedRect(10, bar_y, w_fill, bar_h, 4, 4)

            painter.setPen(QColor("#ffffff"))
            font_val = QFont()
            font_val.setPixelSize(max(10, size // 8))
            font_val.setBold(True)
            painter.setFont(font_val)
            painter.drawText(10, bar_y, size - 20, bar_h,
                             Qt.AlignmentFlag.AlignCenter, val_text)

        elif style == "Barra Vertical":
            bar_w = max(20, size // 6)
            bar_x = (size - bar_w) // 2
            bar_h = size - 30
            bar_y = 10
            
            painter.setBrush(QBrush(QColor("#3f3f46")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_x, bar_y, bar_w, bar_h, 4, 4)

            h_fill = int(bar_h * ratio)
            if h_fill > 0:
                painter.setBrush(QBrush(bar_color))
                if invert:
                    painter.drawRoundedRect(bar_x, bar_y, bar_w, h_fill, 4, 4)
                else:
                    painter.drawRoundedRect(bar_x, bar_y + bar_h - h_fill, bar_w, h_fill, 4, 4)

            painter.setPen(QColor("#ffffff"))
            font_val = QFont()
            font_val.setPixelSize(max(10, size // 10))
            font_val.setBold(True)
            painter.setFont(font_val)
            painter.drawText(0, bar_y + bar_h // 2 - 15, size, 30,
                             Qt.AlignmentFlag.AlignCenter, val_text)

        elif style == "Texto Apenas":
            painter.setPen(bar_color)
            font_val = QFont()
            font_val.setPixelSize(max(14, size // 4))
            font_val.setBold(True)
            painter.setFont(font_val)
            painter.drawText(0, 0, size, size,
                             Qt.AlignmentFlag.AlignCenter, val_text)


class ControllerWidget(DashboardWidget):
    def __init__(self, parent, config, can_thread=None):
        super().__init__(parent, config)
        self._can_thread = can_thread
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.btn = QPushButton(str(config.get("name", "Botão")))
        self.btn.setStyleSheet("background-color: #4e44dd; color: white; padding: 10px; border-radius: 4px; font-weight: bold;")
        layout.addWidget(self.btn)
        
        b = str(config.get("behavior", ""))
        if "Pulso (Apenas Click" in b:
            self.btn.clicked.connect(self._send_on)
        elif "Segurar (Ao apertar" in b:
            self.btn.pressed.connect(self._send_on)
            self.btn.released.connect(self._send_off)
        elif "Segurar Contínuo" in b:
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._send_on)
            self.btn.pressed.connect(self._start_continuous)
            self.btn.released.connect(self._stop_continuous)
        elif "Toggle Chave" in b:
            self.btn.setCheckable(True)
            self.btn.toggled.connect(self._on_toggle_single)
        elif "Toggle Contínuo" in b:
            self.btn.setCheckable(True)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self._send_on)
            self.btn.toggled.connect(self._on_toggle_continuous)

    @property
    def can_thread(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "can_thread") and parent.can_thread is not None:
                return parent.can_thread
            parent = parent.parent()
        return self._can_thread

    def _parse_payload(self, text):
        fmt = self.config.get("format", "HEX")
        parts = str(text).strip().split()
        return [int(p, 16) if fmt == "HEX" else int(p, 2) for p in parts]

    def _send(self, payload_str):
        worker = self.can_thread
        if not worker or worker.mode == "IDLE":
            return
        try:
            can_id = normalize_can_id(self.config.get("can_id"))
            if can_id < 0:
                return
            data = self._parse_payload(payload_str)
            worker.send_message(can_id, data)
        except Exception:
            pass

    def _send_on(self):
        self._send(self.config.get("payload_on", ""))

    def _send_off(self):
        self._send(self.config.get("payload_off", ""))

    def _start_continuous(self):
        self._send_on()
        hz = self.config.get("hz", 10)
        try:
            hz = max(1, int(hz))
        except Exception:
            hz = 10
        if hasattr(self, 'timer'):
            self.timer.start(int(1000 / hz))

    def _stop_continuous(self):
        if hasattr(self, 'timer'):
            self.timer.stop()
        self._send_off()

    def _on_toggle_single(self, checked):
        if checked:
            self.btn.setStyleSheet("background-color: #10b981; color: white; padding: 10px; border-radius: 4px; font-weight: bold;")
            self._send_on()
        else:
            self.btn.setStyleSheet("background-color: #4e44dd; color: white; padding: 10px; border-radius: 4px; font-weight: bold;")
            self._send_off()

    def _on_toggle_continuous(self, checked):
        if checked:
            self.btn.setStyleSheet("background-color: #10b981; color: white; padding: 10px; border-radius: 4px; font-weight: bold;")
            self._start_continuous()
        else:
            self.btn.setStyleSheet("background-color: #4e44dd; color: white; padding: 10px; border-radius: 4px; font-weight: bold;")
            self._stop_continuous()


class IncrementalControllerWidget(DashboardWidget):
    """
    Widget de controle multicanal / incremental de variáveis CAN.
    Envia frames com dados de múltiplos bytes, suportando envio periódico (Hz),
    intertravamento (exclusão mútua), barras gráficas, sliders e botões de passo/mín/máx.
    """
    def __init__(self, parent, config, can_thread=None):
        super().__init__(parent, config)
        self._can_thread = can_thread
        self.target_can_id = normalize_can_id(self.config.get("can_id", "405"))
        self.hz = max(1, int(self.config.get("hz", 20)))
        self.is_transmitting = self.config.get("periodic", True)
        self.mutual_exclusion = self.config.get("mutual_exclusion", True)
        
        # Payload base de 8 bytes
        self.current_payload = self._parse_base_payload(self.config.get("base_payload", "00 00 00 00 00 00 00 00"))
        
        self.channel_uis = []
        self._is_updating = False
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._send_periodic_frame)
        
        self._build_ui()
        
        # Aplica os valores iniciais dos canais ao payload
        for info in self.channel_uis:
            byte_idx = info["byte"]
            val = info["slider"].value()
            if 0 <= byte_idx < len(self.current_payload):
                self.current_payload[byte_idx] = val
        
        if self.is_transmitting:
            self.timer.start(max(1, int(1000 / self.hz)))

    @property
    def can_thread(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "can_thread") and parent.can_thread is not None:
                return parent.can_thread
            parent = parent.parent()
        return self._can_thread

    def _parse_base_payload(self, text: str) -> list[int]:
        try:
            parts = str(text).strip().split()
            bytes_list = [int(p, 16) for p in parts]
            while len(bytes_list) < 8:
                bytes_list.append(0)
            return bytes_list[:8]
        except Exception:
            return [0] * 8

    def _build_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            IncrementalControllerWidget {
                background-color: #202024;
                border: 1px solid #323238;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── Header ──────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(8)

        title_lbl = QLabel(str(self.config.get("name", "Controlador Incremental")))
        title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 13px;")
        
        id_str = f"0x{self.target_can_id:03X}" if self.target_can_id >= 0 else "N/A"
        id_badge = QLabel(f"ID: {id_str}")
        id_badge.setStyleSheet(
            "background-color: #1e293b; color: #38bdf8; font-weight: bold; font-size: 11px;"
            " padding: 2px 6px; border-radius: 4px; border: 1px solid #0284c7;"
        )

        header.addWidget(title_lbl)
        header.addWidget(id_badge)
        header.addStretch()

        # Botão de disparo único
        btn_pulse = QPushButton("🚀 Pulso")
        btn_pulse.setToolTip("Envia 1 frame com os valores atuais")
        btn_pulse.setStyleSheet(
            "QPushButton { background-color: #2e3035; color: white; border: 1px solid #444;"
            "  border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3b82f6; border-color: #3b82f6; }"
        )
        btn_pulse.clicked.connect(self._send_frame_now)
        header.addWidget(btn_pulse)

        # Botão de Toggle de Transmissão Cíclica
        self.btn_toggle_tx = QPushButton("⏸ Tx ON" if self.is_transmitting else "▶ Tx OFF")
        self.btn_toggle_tx.setToolTip(f"Transmissão cíclica a {self.hz} Hz")
        self._update_tx_btn_style()
        self.btn_toggle_tx.clicked.connect(self._toggle_tx)
        header.addWidget(self.btn_toggle_tx)

        layout.addLayout(header)

        # ── Canais ──────────────────────────────────────────
        channels = self.config.get("channels", [])
        if not channels:
            channels = [
                {"name": "Canal A", "byte": 0, "min": 0, "max": 255, "step": 10, "default": 0, "color": "#3b82f6"},
                {"name": "Canal B", "byte": 1, "min": 0, "max": 255, "step": 10, "default": 0, "color": "#ef4444"}
            ]

        for i, ch in enumerate(channels):
            ch_frame = QFrame()
            ch_frame.setStyleSheet("""
                QFrame {
                    background-color: #18181b;
                    border: 1px solid #27272a;
                    border-radius: 6px;
                }
            """)
            ch_layout = QVBoxLayout(ch_frame)
            ch_layout.setContentsMargins(8, 6, 8, 6)
            ch_layout.setSpacing(4)

            ch_name = str(ch.get("name", f"Canal {i+1}"))
            byte_idx = int(ch.get("byte", i))
            min_val = int(ch.get("min", 0))
            max_val = int(ch.get("max", 255))
            step_val = int(ch.get("step", 10))
            def_val = int(ch.get("default", min_val))
            color_hex = str(ch.get("color", "#3b82f6"))

            # Linha de Identificação: Nome Destacado + Byte + Leitura Numérica
            info_row = QHBoxLayout()
            name_lbl = QLabel(ch_name)
            name_lbl.setStyleSheet(f"color: {color_hex}; font-weight: bold; font-size: 12px;")
            
            byte_lbl = QLabel(f"[Byte {byte_idx}]")
            byte_lbl.setStyleSheet("color: #71717a; font-size: 11px;")

            val_lbl = QLabel()
            val_lbl.setStyleSheet("color: #e4e4e7; font-weight: bold; font-size: 11px;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            info_row.addWidget(name_lbl)
            info_row.addWidget(byte_lbl)
            info_row.addStretch()
            info_row.addWidget(val_lbl)
            ch_layout.addLayout(info_row)

            # Barra Gráfica de Nível (Visual Progress Bar)
            pbar = QProgressBar()
            pbar.setRange(min_val, max_val)
            pbar.setValue(def_val)
            pbar.setTextVisible(False)
            pbar.setFixedHeight(8)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #27272a;
                    border: none;
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background-color: {color_hex};
                    border-radius: 4px;
                }}
            """)
            ch_layout.addWidget(pbar)

            # Slider para controle contínuo e suave
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(def_val)
            slider.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    border: none;
                    height: 4px;
                    background: #3f3f46;
                    border-radius: 2px;
                }}
                QSlider::sub-page:horizontal {{
                    background: {color_hex};
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: white;
                    border: 1px solid #52525b;
                    width: 14px;
                    margin-top: -5px;
                    margin-bottom: -5px;
                    border-radius: 7px;
                }}
            """)
            ch_layout.addWidget(slider)

            # Botões de Ação Rápida: [Min] [-Passo] [+Passo] [Max] + Ajuste de Passo
            btn_row = QHBoxLayout()
            btn_row.setSpacing(4)

            btn_min = QPushButton(f"Min ({min_val})")
            btn_min.setStyleSheet("QPushButton { background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 3px; font-size: 10px; padding: 2px 4px; } QPushButton:hover { background-color: #3f3f46; color: white; }")
            
            btn_dec = QPushButton(f"-{step_val}")
            btn_dec.setStyleSheet(f"QPushButton {{ background-color: #27272a; color: white; border: 1px solid #3f3f46; border-radius: 3px; font-size: 11px; font-weight: bold; padding: 2px 8px; }} QPushButton:hover {{ background-color: {color_hex}; color: white; }}")

            btn_inc = QPushButton(f"+{step_val}")
            btn_inc.setStyleSheet(f"QPushButton {{ background-color: #27272a; color: white; border: 1px solid #3f3f46; border-radius: 3px; font-size: 11px; font-weight: bold; padding: 2px 8px; }} QPushButton:hover {{ background-color: {color_hex}; color: white; }}")

            btn_max = QPushButton(f"Max ({max_val})")
            btn_max.setStyleSheet("QPushButton { background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 3px; font-size: 10px; padding: 2px 4px; } QPushButton:hover { background-color: #3f3f46; color: white; }")

            lbl_step = QLabel("Passo:")
            lbl_step.setStyleSheet("color: #71717a; font-size: 10px;")

            sp_step = QSpinBox()
            sp_step.setRange(1, max(1, max_val - min_val))
            sp_step.setValue(step_val)
            sp_step.setFixedWidth(50)
            sp_step.setStyleSheet("QSpinBox { background-color: #1e1e24; color: white; border: 1px solid #3f3f46; border-radius: 3px; font-size: 10px; }")

            btn_row.addWidget(btn_min)
            btn_row.addWidget(btn_dec)
            btn_row.addWidget(btn_inc)
            btn_row.addWidget(btn_max)
            btn_row.addSpacing(4)
            btn_row.addWidget(lbl_step)
            btn_row.addWidget(sp_step)

            ch_layout.addLayout(btn_row)
            layout.addWidget(ch_frame)

            ui_dict = {
                "index": i,
                "name": ch_name,
                "byte": byte_idx,
                "min": min_val,
                "max": max_val,
                "color": color_hex,
                "val_lbl": val_lbl,
                "pbar": pbar,
                "slider": slider,
                "btn_dec": btn_dec,
                "btn_inc": btn_inc,
                "sp_step": sp_step
            }
            self.channel_uis.append(ui_dict)

            idx = i
            slider.valueChanged.connect(lambda v, ch_i=idx: self._on_channel_value_changed(ch_i, v))
            btn_min.clicked.connect(lambda _, ch_i=idx: self._set_channel_value(ch_i, self.channel_uis[ch_i]["min"]))
            btn_max.clicked.connect(lambda _, ch_i=idx: self._set_channel_value(ch_i, self.channel_uis[ch_i]["max"]))
            btn_dec.clicked.connect(lambda _, ch_i=idx: self._step_channel(ch_i, -self.channel_uis[ch_i]["sp_step"].value()))
            btn_inc.clicked.connect(lambda _, ch_i=idx: self._step_channel(ch_i, +self.channel_uis[ch_i]["sp_step"].value()))
            sp_step.valueChanged.connect(lambda s, ch_i=idx: self._on_step_spin_changed(ch_i, s))

            self._update_channel_display(idx, def_val)

    def _update_tx_btn_style(self):
        if self.is_transmitting:
            self.btn_toggle_tx.setText(f"⏸ Tx {self.hz}Hz")
            self.btn_toggle_tx.setStyleSheet(
                "QPushButton { background-color: #10b981; color: white; border: 1px solid #059669;"
                "  border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background-color: #059669; }"
            )
        else:
            self.btn_toggle_tx.setText("▶ Tx OFF")
            self.btn_toggle_tx.setStyleSheet(
                "QPushButton { background-color: #2e3035; color: #a1a1aa; border: 1px solid #444;"
                "  border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background-color: #3b82f6; color: white; }"
            )

    def _toggle_tx(self):
        self.is_transmitting = not self.is_transmitting
        self._update_tx_btn_style()
        if self.is_transmitting:
            self.timer.start(max(1, int(1000 / self.hz)))
        else:
            self.timer.stop()

    def _on_step_spin_changed(self, ch_idx: int, new_step: int):
        ui = self.channel_uis[ch_idx]
        ui["btn_dec"].setText(f"-{new_step}")
        ui["btn_inc"].setText(f"+{new_step}")

    def _step_channel(self, ch_idx: int, delta: int):
        ui = self.channel_uis[ch_idx]
        cur = ui["slider"].value()
        new_val = max(ui["min"], min(ui["max"], cur + delta))
        self._set_channel_value(ch_idx, new_val)

    def _set_channel_value(self, ch_idx: int, val: int):
        ui = self.channel_uis[ch_idx]
        ui["slider"].setValue(val)

    def _on_channel_value_changed(self, ch_idx: int, val: int):
        if self._is_updating:
            return
        self._is_updating = True
        try:
            ui = self.channel_uis[ch_idx]
            byte_idx = ui["byte"]
            
            # Intertravamento / Exclusão Mútua: zerar os outros canais ao atuar em um
            if self.mutual_exclusion and val > ui["min"]:
                for other_idx, other_ui in enumerate(self.channel_uis):
                    if other_idx != ch_idx:
                        other_min = other_ui["min"]
                        if other_ui["slider"].value() != other_min:
                            other_ui["slider"].blockSignals(True)
                            other_ui["slider"].setValue(other_min)
                            other_ui["slider"].blockSignals(False)
                            self._update_channel_display(other_idx, other_min)
                            other_byte = other_ui["byte"]
                            if 0 <= other_byte < len(self.current_payload):
                                self.current_payload[other_byte] = other_min
            
            if 0 <= byte_idx < len(self.current_payload):
                self.current_payload[byte_idx] = val
                
            self._update_channel_display(ch_idx, val)
        finally:
            self._is_updating = False

    def _update_channel_display(self, ch_idx: int, val: int):
        ui = self.channel_uis[ch_idx]
        ui["pbar"].setValue(val)
        span = max(1, ui["max"] - ui["min"])
        pct = ((val - ui["min"]) / span) * 100.0
        ui["val_lbl"].setText(f"{val} / {ui['max']} ({pct:.1f}%) [0x{val:02X}]")

    def _send_periodic_frame(self):
        self._send_frame_now()

    def _send_frame_now(self):
        worker = self.can_thread
        if not worker or worker.mode == "IDLE":
            return
        try:
            if self.target_can_id < 0:
                return
            worker.send_message(self.target_can_id, list(self.current_payload))
        except Exception:
            pass


class TerminalWidget(DashboardWidget):
    """
    Widget de Terminal CAN (Somente Leitura).
    Permite monitorar frames CAN em tempo real com filtro dinâmico de IDs,
    controle de buffer, limpeza, pausa e auto-scroll.
    """
    def __init__(self, parent, config):
        super().__init__(parent, config)
        self.target_filter_raw = str(self.config.get("filter_ids", ""))
        self.max_lines = int(self.config.get("max_lines", 200))
        self.show_timestamp = self.config.get("show_timestamp", True)
        self.show_ascii = self.config.get("show_ascii", True)
        self.show_freq = self.config.get("show_freq", True)
        
        self.is_paused = False
        self.auto_scroll = True
        self._allowed_ids = self._parse_filter_ids(self.target_filter_raw)
        
        self._build_ui()

    def _parse_filter_ids(self, text: str) -> set[int]:
        result = set()
        for token in text.replace(";", ",").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                if token.lower().startswith("0x"):
                    result.add(int(token, 16))
                else:
                    try:
                        result.add(int(token, 16))
                    except ValueError:
                        result.add(int(token, 10))
            except Exception:
                pass
        return result

    def _build_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(440, 240)
        self.setStyleSheet("""
            TerminalWidget {
                background-color: #1a1a1e;
                border: 1px solid #323238;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        title_lbl = QLabel(str(self.config.get("name", "Terminal CAN")))
        title_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        toolbar.addWidget(title_lbl)

        # Campo de filtro rápido
        toolbar.addWidget(QLabel("Filtro ID:"))
        self.txt_filter_quick = QLineEdit(self.target_filter_raw)
        self.txt_filter_quick.setPlaceholderText("Todos ou 405, 180...")
        self.txt_filter_quick.setToolTip("Filtre IDs em tempo real (separados por vírgula)")
        self.txt_filter_quick.setFixedWidth(130)
        self.txt_filter_quick.setStyleSheet(
            "QLineEdit { background-color: #27272a; color: #38bdf8; border: 1px solid #3f3f46; border-radius: 3px; padding: 2px 4px; font-size: 11px; }"
        )
        self.txt_filter_quick.textChanged.connect(self._on_quick_filter_changed)
        toolbar.addWidget(self.txt_filter_quick)

        toolbar.addStretch()

        self.btn_clear = QPushButton("🧹 Limpar")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 3px; font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { background-color: #3f3f46; color: white; }"
        )
        self.btn_clear.clicked.connect(self._clear_terminal)
        toolbar.addWidget(self.btn_clear)

        self.btn_pause = QPushButton("⏸ Pausar")
        self.btn_pause.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 3px; font-size: 11px; padding: 2px 6px; }"
            "QPushButton:hover { background-color: #3f3f46; color: white; }"
        )
        self.btn_pause.clicked.connect(self._toggle_pause)
        toolbar.addWidget(self.btn_pause)

        self.btn_autoscroll = QPushButton("⬇ Scroll ON")
        self.btn_autoscroll.setStyleSheet(
            "QPushButton { background-color: #1e3a5f; color: #93c5fd; border: 1px solid #1d4ed8; border-radius: 3px; font-size: 11px; padding: 2px 6px; font-weight: bold; }"
        )
        self.btn_autoscroll.clicked.connect(self._toggle_autoscroll)
        toolbar.addWidget(self.btn_autoscroll)

        layout.addLayout(toolbar)

        # Console de texto
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumBlockCount(self.max_lines)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.txt_log.setFont(font)
        self.txt_log.setStyleSheet("""
            QPlainTextEdit {
                background-color: #101014;
                color: #34d399;
                border: 1px solid #27272a;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self.txt_log, 1)

    def _on_quick_filter_changed(self, text: str):
        self.target_filter_raw = text
        self.config["filter_ids"] = text
        self._allowed_ids = self._parse_filter_ids(text)

    def _clear_terminal(self):
        self.txt_log.clear()

    def _toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.setText("▶ Retomar")
            self.btn_pause.setStyleSheet(
                "QPushButton { background-color: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; border-radius: 3px; font-size: 11px; padding: 2px 6px; font-weight: bold; }"
            )
        else:
            self.btn_pause.setText("⏸ Pausar")
            self.btn_pause.setStyleSheet(
                "QPushButton { background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 3px; font-size: 11px; padding: 2px 6px; }"
                "QPushButton:hover { background-color: #3f3f46; color: white; }"
            )

    def _toggle_autoscroll(self):
        self.auto_scroll = not self.auto_scroll
        if self.auto_scroll:
            self.btn_autoscroll.setText("⬇ Scroll ON")
            self.btn_autoscroll.setStyleSheet(
                "QPushButton { background-color: #1e3a5f; color: #93c5fd; border: 1px solid #1d4ed8; border-radius: 3px; font-size: 11px; padding: 2px 6px; font-weight: bold; }"
            )
        else:
            self.btn_autoscroll.setText("⬇ Scroll OFF")
            self.btn_autoscroll.setStyleSheet(
                "QPushButton { background-color: #27272a; color: #71717a; border: 1px solid #3f3f46; border-radius: 3px; font-size: 11px; padding: 2px 6px; }"
            )

    def process_can_frame(self, can_id: int, freq: float, payload: list):
        if self.is_paused:
            return
        if self._allowed_ids and (can_id not in self._allowed_ids):
            return

        parts = []
        if self.show_timestamp:
            import time
            now = time.time()
            t_str = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int((now % 1)*1000):03d}"
            parts.append(f"[{t_str}]")

        id_str = f"0x{can_id:08X}" if can_id > 0x7FF else f"0x{can_id:03X}"
        parts.append(f"ID: {id_str}")
        parts.append(f"DLC: {len(payload)}")

        data_hex = " ".join(f"{b:02X}" for b in payload)
        parts.append(f"DATA: {data_hex:<23}")

        if self.show_freq:
            parts.append(f"({freq:5.1f} Hz)")

        if self.show_ascii:
            ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in payload)
            parts.append(f"| {ascii_str} |")

        line = "  ".join(parts)
        self.txt_log.appendPlainText(line)

        if self.auto_scroll:
            self.txt_log.moveCursor(QTextCursor.MoveOperation.End)


class WidgetsTab(QWidget):
    """Aba de painéis visuais (Dashboard)."""

    def __init__(self, can_thread_ref, parent=None):
        super().__init__(parent)
        self._can_thread = can_thread_ref
        self.edit_mode = False
        self.widgets_list = []
        
        # Conecta o frame_received ao método global de broadcast
        if self._can_thread:
            self._can_thread.frame_received.connect(self._broadcast_can_frame)
        self._build_ui()

    @property
    def can_thread(self):
        return self._can_thread

    @can_thread.setter
    def can_thread(self, new_worker):
        self._can_thread = new_worker

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        self.btn_edit = QPushButton("🔒 Layout Travado")
        self.btn_edit.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_edit.setCheckable(True)
        self.btn_edit.toggled.connect(self.toggle_edit_mode)
        
        self.btn_grid = QPushButton("🔲 Grade Visível")
        self.btn_grid.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_grid.setCheckable(True)
        self.btn_grid.toggled.connect(self.toggle_grid)
        self.btn_grid.hide()

        self.btn_snap = QPushButton("🧲 Snap Ativado")
        self.btn_snap.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        self.btn_snap.setCheckable(True)
        self.btn_snap.setChecked(True)
        self.btn_snap.toggled.connect(self.toggle_snap)
        self.btn_snap.hide()

        self.btn_center_all = QPushButton("↔️ Centralizar Todos")
        self.btn_center_all.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_center_all.setToolTip("Centraliza todos os widgets horizontalmente na tela")
        self.btn_center_all.clicked.connect(self.center_all_widgets)
        self.btn_center_all.hide()

        self.btn_snap_all = QPushButton("🧲 Alinhar Todos à Grade")
        self.btn_snap_all.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_snap_all.setToolTip("Alinha todos os widgets aos pontos da grade mais próximos")
        self.btn_snap_all.clicked.connect(self.snap_all_widgets)
        self.btn_snap_all.hide()
        
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_grid)
        toolbar.addWidget(self.btn_snap)
        toolbar.addWidget(self.btn_center_all)
        toolbar.addWidget(self.btn_snap_all)
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)

        # Canvas
        self.canvas = CanvasWidget()
        self.canvas.setStyleSheet("background-color: #1a1a1e; border: 1px solid #323238; border-radius: 8px;")
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.show_canvas_context_menu)
        
        main_layout.addWidget(self.canvas, 1)

    def show_canvas_context_menu(self, pos):
        if not self.edit_mode:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #202024; color: white; border: 1px solid #323238; } QMenu::item:selected { background-color: #3b82f6; }")
        
        action_label = QAction("📝 Inserir Texto", self)
        action_label.triggered.connect(lambda: self.add_label(pos))
        
        action_ind = QAction("💡 Inserir Indicador", self)
        action_ind.triggered.connect(lambda: self.add_indicator(pos))

        action_multi = QAction("🚥 Inserir Ind. Multi-Estado", self)
        action_multi.triggered.connect(lambda: self.add_multi_indicator(pos))
        
        action_ctrl = QAction("🎛️ Inserir Controlador", self)
        action_ctrl.triggered.connect(lambda: self.add_controller(pos))

        action_inc_ctrl = QAction("🎚️ Inserir Controlador Incremental", self)
        action_inc_ctrl.triggered.connect(lambda: self.add_incremental_controller(pos))

        action_gauge = QAction("📊 Inserir Gauge", self)
        action_gauge.triggered.connect(lambda: self.add_gauge(pos))

        action_terminal = QAction("💻 Inserir Terminal CAN", self)
        action_terminal.triggered.connect(lambda: self.add_terminal(pos))
        
        menu.addAction(action_label)
        menu.addAction(action_ind)
        menu.addAction(action_multi)
        menu.addAction(action_ctrl)
        menu.addAction(action_inc_ctrl)
        menu.addAction(action_gauge)
        menu.addAction(action_terminal)
        
        menu.exec(self.canvas.mapToGlobal(pos))

    def _broadcast_can_frame(self, can_id: int, freq: float, payload: list):
        for w in self.canvas.findChildren(DashboardWidget):
            if hasattr(w, "process_can_frame"):
                try:
                    w.process_can_frame(can_id, freq, payload)
                except Exception:
                    pass

    def toggle_edit_mode(self, checked):
        self.edit_mode = checked
        if checked:
            self.btn_edit.setText("🔓 Layout Destravado (Edição)")
            self.btn_edit.setStyleSheet("background-color: #10b981; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
            self.btn_grid.show()
            self.btn_snap.show()
            self.btn_center_all.show()
            self.btn_snap_all.show()
        else:
            self.btn_edit.setText("🔒 Layout Travado")
            self.btn_edit.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
            self.btn_grid.hide()
            self.btn_grid.setChecked(False)
            self.btn_snap.hide()
            self.btn_center_all.hide()
            self.btn_snap_all.hide()
            
        for child in self.canvas.findChildren(DashboardWidget):
            child.set_edit_mode(checked)

    def toggle_grid(self, checked):
        self.canvas.show_grid = checked
        if checked:
            self.btn_grid.setText("🔲 Grade Visível")
            self.btn_grid.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        else:
            self.btn_grid.setText("🔲 Grade Oculta")
            self.btn_grid.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.canvas.update()

    def toggle_snap(self, checked):
        self.canvas.snap_to_grid = checked
        if checked:
            self.btn_snap.setText("🧲 Snap Ativado")
            self.btn_snap.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        else:
            self.btn_snap.setText("🧲 Snap Desativado")
            self.btn_snap.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")

    def center_all_widgets(self):
        """Centraliza todos os widgets horizontalmente no canvas."""
        for w in self.canvas.findChildren(DashboardWidget):
            if hasattr(w, "center_horizontally"):
                w.center_horizontally()

    def snap_all_widgets(self):
        """Alinha todos os widgets para a grade."""
        for w in self.canvas.findChildren(DashboardWidget):
            if hasattr(w, "snap_to_grid"):
                w.snap_to_grid(getattr(self.canvas, "grid_size", 20))

    def add_label(self, pos):
        dlg = LabelDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = LabelWidget(self.canvas, cfg)
            self._place_widget(w, pos)

    def add_indicator(self, pos):
        dlg = IndicatorDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = IndicatorWidget(self.canvas, cfg)
            self._place_widget(w, pos)

    def add_multi_indicator(self, pos):
        dlg = MultiIndicatorDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = MultiIndicatorWidget(self.canvas, cfg)
            self._place_widget(w, pos)

    def add_controller(self, pos):
        dlg = ControllerDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = ControllerWidget(self.canvas, cfg, self.can_thread)
            self._place_widget(w, pos)

    def add_incremental_controller(self, pos):
        dlg = IncrementalControllerDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = IncrementalControllerWidget(self.canvas, cfg, self.can_thread)
            self._place_widget(w, pos)

    def add_gauge(self, pos):
        dlg = GaugeDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = GaugeWidget(self.canvas, cfg)
            self._place_widget(w, pos)

    def add_terminal(self, pos):
        dlg = TerminalDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = TerminalWidget(self.canvas, cfg)
            self._place_widget(w, pos)

    def _place_widget(self, w: DashboardWidget, pos):
        w.edit_callback = self._edit_widget
        w.duplicate_callback = self._duplicate_widget
        if w.config and w.config.get("width"):
            w.setFixedWidth(int(w.config["width"]))
        w.show()
        w.move(pos)
        w.set_edit_mode(self.edit_mode)
        
    def clear_all(self):
        """Remove todos os widgets do canvas — usado pelo 'Novo Projeto'."""
        for w in self.canvas.findChildren(DashboardWidget):
            w.setParent(None)
            w.deleteLater()
        if self.edit_mode:
            self.btn_edit.setChecked(False)

    def _edit_widget(self, widget: DashboardWidget):
        """Abre o diálogo de edição para o widget selecionado."""
        from src.widget_dialogs import (
            LabelDialog, IndicatorDialog, ControllerDialog, GaugeDialog, MultiIndicatorDialog,
            IncrementalControllerDialog, TerminalDialog
        )
        wtype = widget.config.get("type", "")
        pos = widget.pos()
        saved_width = widget.config.get("width")

        if wtype == "label":
            dlg = LabelDialog(self, config=widget.config)
        elif wtype == "indicator":
            dlg = IndicatorDialog(self, config=widget.config)
        elif wtype == "multi_indicator":
            dlg = MultiIndicatorDialog(self, config=widget.config)
        elif wtype == "controller":
            dlg = ControllerDialog(self, config=widget.config)
        elif wtype == "incremental_controller":
            dlg = IncrementalControllerDialog(self, config=widget.config)
        elif wtype == "gauge":
            dlg = GaugeDialog(self, config=widget.config)
        elif wtype == "terminal":
            dlg = TerminalDialog(self, config=widget.config)
        else:
            return

        if dlg.exec():
            new_cfg = dlg.get_config()
            if saved_width:
                new_cfg["width"] = saved_width
            widget.deleteLater()
            if wtype == "label":
                new_w = LabelWidget(self.canvas, new_cfg)
            elif wtype == "indicator":
                new_w = IndicatorWidget(self.canvas, new_cfg)
            elif wtype == "multi_indicator":
                new_w = MultiIndicatorWidget(self.canvas, new_cfg)
            elif wtype == "controller":
                new_w = ControllerWidget(self.canvas, new_cfg, self.can_thread)
            elif wtype == "incremental_controller":
                new_w = IncrementalControllerWidget(self.canvas, new_cfg, self.can_thread)
            elif wtype == "gauge":
                new_w = GaugeWidget(self.canvas, new_cfg)
            elif wtype == "terminal":
                new_w = TerminalWidget(self.canvas, new_cfg)
            else:
                return
            self._place_widget(new_w, pos)

    def _duplicate_widget(self, widget: DashboardWidget):
        """Cria uma cópia do widget com as mesmas configurações, deslocada 20 px."""
        import copy
        new_cfg = copy.deepcopy(widget.config)
        wtype = new_cfg.get("type", "")

        # Acrescenta ' (1)' no campo de texto/nome visível
        for key in ("text", "name"):
            if key in new_cfg:
                new_cfg[key] = new_cfg[key] + " (1)"
                break

        new_pos = QPoint(widget.pos().x() + 20, widget.pos().y() + 20)

        if wtype == "label":
            new_w = LabelWidget(self.canvas, new_cfg)
        elif wtype == "indicator":
            new_w = IndicatorWidget(self.canvas, new_cfg)
        elif wtype == "multi_indicator":
            new_w = MultiIndicatorWidget(self.canvas, new_cfg)
        elif wtype == "controller":
            new_w = ControllerWidget(self.canvas, new_cfg, self.can_thread)
        elif wtype == "incremental_controller":
            new_w = IncrementalControllerWidget(self.canvas, new_cfg, self.can_thread)
        elif wtype == "gauge":
            new_w = GaugeWidget(self.canvas, new_cfg)
        elif wtype == "terminal":
            new_w = TerminalWidget(self.canvas, new_cfg)
        else:
            return

        self._place_widget(new_w, new_pos)

    def export_data(self):
        widgets_data = []
        for w in self.canvas.findChildren(DashboardWidget):
            cfg = w.config.copy()
            cfg["pos_x"] = w.pos().x()
            cfg["pos_y"] = w.pos().y()
            if w.config.get("width"):
                cfg["width"] = w.config["width"]
            widgets_data.append(cfg)
        return widgets_data

    def import_data(self, widgets_data: list):
        """Restaura widgets no canvas a partir de uma lista de dicts exportados."""
        for w in self.canvas.findChildren(DashboardWidget):
            w.setParent(None)
            w.deleteLater()
        for cfg in widgets_data:
            pos = QPoint(int(cfg.get("pos_x", 20)), int(cfg.get("pos_y", 20)))
            wtype = cfg.get("type", "")
            if wtype == "label":
                widget = LabelWidget(self.canvas, cfg)
            elif wtype == "indicator":
                widget = IndicatorWidget(self.canvas, cfg)
            elif wtype == "multi_indicator":
                widget = MultiIndicatorWidget(self.canvas, cfg)
            elif wtype == "controller":
                widget = ControllerWidget(self.canvas, cfg, self.can_thread)
            elif wtype == "incremental_controller":
                widget = IncrementalControllerWidget(self.canvas, cfg, self.can_thread)
            elif wtype == "gauge":
                widget = GaugeWidget(self.canvas, cfg)
            elif wtype == "terminal":
                widget = TerminalWidget(self.canvas, cfg)
            else:
                continue
            self._place_widget(widget, pos)


