"""
widgets_tab.py — Widget da Aba de Painéis / Gauges
"""

from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu
)
from PyQt6.QtGui import QAction, QColor, QPainter, QPen, QBrush, QFont
import math

from src.widget_dialogs import LabelDialog, IndicatorDialog, ControllerDialog, GaugeDialog

class CanvasWidget(QFrame):
    """Canvas com opção de grade para auxiliar no posicionamento."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_grid = False

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.show_grid:
            return
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#404040"), 1, Qt.PenStyle.DotLine))
        grid_size = 20
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
        self.edit_callback = None  # Definido por WidgetsTab ao posicionar o widget

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
            self.move(self.pos() + event.pos() - self._drag_start_pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.edit_mode and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = None
        else:
            super().mouseReleaseEvent(event)

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
            action_del = QAction("🗑 Excluir Widget", self)
            action_del.triggered.connect(self.deleteLater)
            menu.addAction(action_edit)
            menu.addSeparator()
            menu.addAction(action_del)
            menu.exec(event.globalPos())
        else:
            super().contextMenuEvent(event)


class LabelWidget(DashboardWidget):
    def __init__(self, parent, config):
        super().__init__(parent, config)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        self.lbl = QLabel(config["text"])
        size = config.get("size", 14)
        bold = "font-weight: bold;" if config.get("bold", False) else ""
        italic = "font-style: italic;" if config.get("italic", False) else ""
        strike = "text-decoration: line-through;" if config.get("strikethrough", False) else ""
        color = config.get("color", "#ffffff")
        self.lbl.setStyleSheet(f"color: {color}; font-size: {size}px; {bold} {italic} {strike}")
        layout.addWidget(self.lbl)


class IndicatorWidget(DashboardWidget):
    def __init__(self, parent, config):
        super().__init__(parent, config)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_title = QLabel(config["name"])
        self.lbl_title.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_display = QLabel()
        self.lbl_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_display)
        
        self.state = False
        self.update_visuals()

    def process_can_frame(self, can_id: int, freq: float, payload: list):
        # print(f"[IndicatorWidget] Received ID: {can_id:03X}, payload: {payload}, targeting config: {self.config['can_id']}")
        if f"{can_id:03X}" != self.config["can_id"]:
            return
            
        byte_idx = self.config["byte"]
        if byte_idx < len(payload):
            bit_idx = self.config["bit"]
            val = payload[byte_idx]
            new_state = (val & (1 << bit_idx)) != 0
            # print(f"[IndicatorWidget] Matching state change! Old: {self.state}, New: {new_state}")
            if new_state != self.state:
                self.state = new_state
                self.update_visuals()

    def update_visuals(self):
        is_on = self.state
        val = self.config["val_on"] if is_on else self.config["val_off"]
        # print(f"[IndicatorWidget] update_visuals called. is_on: {is_on}, val: {val}, type: {self.config['visual_type']}")
        
        if self.config["visual_type"] == "LED":
            color = val if val.startswith("#") else ("#10b981" if is_on else "#52525b")
            led_size = self.config.get("led_size", 32)
            self.lbl_display.setText("●")
            self.lbl_display.setStyleSheet(f"color: {color}; font-size: {led_size}px;")
            # print(f"[IndicatorWidget] Applied stylesheet: color: {color}")
        else:
            self.lbl_display.setText(val)
            self.lbl_display.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")




class GaugeWidget(DashboardWidget):
    """Indicador analógico tipo gauge com arco de progresso ou barras."""

    def __init__(self, parent, config):
        super().__init__(parent, config)
        self._raw_value = config.get("val_min_raw", 0)
        size = config.get("gauge_size", 160)
        self.setFixedSize(size, size + 30)

    def _get_conv_value(self):
        v_min = self.config.get("val_min_raw", 0)
        v_max = self.config.get("val_max_raw", 255)
        c_min = self.config.get("val_min_conv", 0.0)
        c_max = self.config.get("val_max_conv", 100.0)

        if v_max == v_min:
            return c_min
        
        ratio = (self._raw_value - v_min) / (v_max - v_min)
        return c_min + ratio * (c_max - c_min)

    def process_can_frame(self, can_id: int, freq: float, payload: list):
        if f"{can_id:03X}" != self.config["can_id"]:
            return
        byte_idx = self.config["byte"]
        byte_len = self.config.get("byte_len", 1)
        if byte_idx + byte_len - 1 < len(payload):
            raw = 0
            for i in range(byte_len):
                raw = (raw << 8) | payload[byte_idx + i]
            
            # Clamp raw value
            v_min = self.config.get("val_min_raw", 0)
            v_max = self.config.get("val_max_raw", 255)
            # handle cases where min > max in raw configuration
            real_min = min(v_min, v_max)
            real_max = max(v_min, v_max)
            raw = max(real_min, min(real_max, raw))

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
        painter.drawText(0, size + 4, size, 24,
                         Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, name)

        if style == "Arco":
            margin = 10
            cx = size // 2
            cy = size // 2
            radius = (size // 2) - margin

            # Arco de fundo
            pen_bg = QPen(QColor("#3f3f46"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_bg)
            start_angle = 225 * 16
            span_angle  = -270 * 16
            painter.drawArc(cx - radius, margin, radius * 2, radius * 2, start_angle, span_angle)

            # Arco de valor
            pen_val = QPen(bar_color, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_val)
            painter.drawArc(cx - radius, margin, radius * 2, radius * 2,
                            start_angle, int(span_angle * ratio))

            # Ponteiro
            angle_deg = 225 - ratio * 270
            angle_rad = math.radians(angle_deg)
            needle_len = radius - 18
            nx = cx + needle_len * math.cos(angle_rad)
            ny = cy - needle_len * math.sin(angle_rad)
            painter.setPen(QPen(QColor("#ffffff"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(int(cx), int(cy), int(nx), int(ny))

            # Ponto central
            painter.setBrush(QBrush(QColor("#a1a1aa")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - 5, cy - 5, 10, 10)

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
            bar_y = (size - bar_h) // 2
            painter.setBrush(QBrush(QColor("#3f3f46")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(10, bar_y, size - 20, bar_h, 4, 4)

            w_fill = int((size - 20) * ratio)
            if w_fill > 0:
                painter.setBrush(QBrush(bar_color))
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
    def __init__(self, parent, config, can_thread):
        super().__init__(parent, config)
        self.can_thread = can_thread
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.btn = QPushButton(config["name"])
        self.btn.setStyleSheet("background-color: #4e44dd; color: white; padding: 10px; border-radius: 4px; font-weight: bold;")
        layout.addWidget(self.btn)
        
        b = config["behavior"]
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

    def _parse_payload(self, text):
        fmt = self.config["format"]
        parts = text.strip().split()
        return [int(p, 16) if fmt == "HEX" else int(p, 2) for p in parts]

    def _send(self, payload_str):
        if not self.can_thread or self.can_thread.mode == "IDLE":
            return
        try:
            can_id = int(self.config["can_id"], 16)
            data = self._parse_payload(payload_str)
            self.can_thread.send_message(can_id, data)
        except Exception:
            pass

    def _send_on(self):
        self._send(self.config["payload_on"])

    def _send_off(self):
        self._send(self.config["payload_off"])

    def _start_continuous(self):
        self._send_on()
        hz = self.config.get("hz", 10)
        self.timer.start(int(1000 / hz))

    def _stop_continuous(self):
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


class WidgetsTab(QWidget):
    """Aba de painéis visuais (Dashboard)."""

    def __init__(self, can_thread_ref, parent=None):
        super().__init__(parent)
        self.can_thread = can_thread_ref
        self.edit_mode = False
        self.widgets_list = []
        
        # Conecta o frame_received ao método global de broadcast
        self.can_thread.frame_received.connect(self._broadcast_can_frame)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        
        self.btn_edit = QPushButton("🔒 Layout Travado")
        self.btn_edit.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_edit.setCheckable(True)
        self.btn_edit.toggled.connect(self.toggle_edit_mode)
        
        self.btn_grid = QPushButton("🔲 Grade Oculta")
        self.btn_grid.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_grid.setCheckable(True)
        self.btn_grid.toggled.connect(self.toggle_grid)
        self.btn_grid.hide() # Somente mostrar quando destravado
        
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_grid)
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
        
        action_ctrl = QAction("🎛️ Inserir Controlador", self)
        action_ctrl.triggered.connect(lambda: self.add_controller(pos))

        action_gauge = QAction("📊 Inserir Gauge", self)
        action_gauge.triggered.connect(lambda: self.add_gauge(pos))
        
        menu.addAction(action_label)
        menu.addAction(action_ind)
        menu.addAction(action_ctrl)
        menu.addAction(action_gauge)
        
        menu.exec(self.canvas.mapToGlobal(pos))

    def _broadcast_can_frame(self, can_id: int, freq: float, payload: list):
        widgets = self.canvas.findChildren(IndicatorWidget)
        # if widgets:
        #     print(f"[WidgetsTab] Broadcasting frame {can_id:03X} to {len(widgets)} widgets")
        for w in widgets:
            w.process_can_frame(can_id, freq, payload)
        for w in self.canvas.findChildren(GaugeWidget):
            w.process_can_frame(can_id, freq, payload)

    def toggle_edit_mode(self, checked):
        self.edit_mode = checked
        if checked:
            self.btn_edit.setText("🔓 Layout Destravado (Edição)")
            self.btn_edit.setStyleSheet("background-color: #10b981; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
            self.btn_grid.show()
        else:
            self.btn_edit.setText("🔒 Layout Travado")
            self.btn_edit.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
            self.btn_grid.hide()
            self.btn_grid.setChecked(False) # Turn off grid when locking
            
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

    def add_controller(self, pos):
        dlg = ControllerDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = ControllerWidget(self.canvas, cfg, self.can_thread)
            self._place_widget(w, pos)

    def add_gauge(self, pos):
        dlg = GaugeDialog(self)
        if dlg.exec():
            cfg = dlg.get_config()
            w = GaugeWidget(self.canvas, cfg)
            self._place_widget(w, pos)

    def _place_widget(self, w: DashboardWidget, pos):
        w.edit_callback = self._edit_widget
        w.show()
        w.move(pos)
        w.set_edit_mode(self.edit_mode)
        
    def clear_all(self):
        """Remove todos os widgets do canvas — usado pelo 'Novo Projeto'."""
        for w in self.canvas.findChildren(DashboardWidget):
            w.deleteLater()
        # Desliga modo de edição
        if self.edit_mode:
            self.btn_edit.setChecked(False)

    def _edit_widget(self, widget: DashboardWidget):
        """Abre o diálogo de edição para o widget selecionado."""
        from src.widget_dialogs import LabelDialog, IndicatorDialog, ControllerDialog
        wtype = widget.config.get("type", "")
        pos = widget.pos()

        if wtype == "label":
            dlg = LabelDialog(self, config=widget.config)
        elif wtype == "indicator":
            dlg = IndicatorDialog(self, config=widget.config)
        elif wtype == "controller":
            dlg = ControllerDialog(self, config=widget.config)
        elif wtype == "gauge":
            dlg = GaugeDialog(self, config=widget.config)
        else:
            return

        if dlg.exec():
            new_cfg = dlg.get_config()
            widget.deleteLater()
            if wtype == "label":
                new_w = LabelWidget(self.canvas, new_cfg)
            elif wtype == "indicator":
                new_w = IndicatorWidget(self.canvas, new_cfg)
            elif wtype == "controller":
                new_w = ControllerWidget(self.canvas, new_cfg, self.can_thread)
            elif wtype == "gauge":
                new_w = GaugeWidget(self.canvas, new_cfg)
            else:
                return
            self._place_widget(new_w, pos)

    def export_data(self):
        widgets_data = []
        for w in self.canvas.findChildren(DashboardWidget):
            cfg = w.config.copy()
            cfg["pos_x"] = w.pos().x()
            cfg["pos_y"] = w.pos().y()
            widgets_data.append(cfg)
        return widgets_data

    def import_data(self, widgets_data: list):
        """Restaura widgets no canvas a partir de uma lista de dicts exportados."""
        # Remove widgets existentes
        for w in self.canvas.findChildren(DashboardWidget):
            w.deleteLater()
        for cfg in widgets_data:
            pos = QPoint(cfg.get("pos_x", 20), cfg.get("pos_y", 20))
            wtype = cfg.get("type", "")
            if wtype == "label":
                widget = LabelWidget(self.canvas, cfg)
            elif wtype == "indicator":
                widget = IndicatorWidget(self.canvas, cfg)
            elif wtype == "controller":
                widget = ControllerWidget(self.canvas, cfg, self.can_thread)
            elif wtype == "gauge":
                widget = GaugeWidget(self.canvas, cfg)
            else:
                continue
            self._place_widget(widget, pos)
