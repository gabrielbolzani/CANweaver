"""
widgets_tab.py — Widget da Aba de Painéis / Gauges
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMenu
)
from PyQt6.QtGui import QAction

from src.widget_dialogs import LabelDialog, IndicatorDialog, ControllerDialog

class DashboardWidget(QWidget):
    """Classe base para widgets arrastáveis no Canvas."""
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.edit_mode = False
        self._drag_start_pos = None

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
            action_del = QAction("🗑 Excluir Widget", self)
            action_del.triggered.connect(self.deleteLater)
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
        self.lbl.setStyleSheet(f"color: white; font-size: {size}px; {bold}")
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
        if f"{can_id:03X}" != self.config["can_id"]:
            return
            
        byte_idx = self.config["byte"]
        if byte_idx < len(payload):
            bit_idx = self.config["bit"]
            val = payload[byte_idx]
            new_state = (val & (1 << bit_idx)) != 0
            if new_state != self.state:
                self.state = new_state
                self.update_visuals()

    def update_visuals(self):
        is_on = self.state
        val = self.config["val_on"] if is_on else self.config["val_off"]
        
        if self.config["visual_type"] == "LED":
            color = val if val.startswith("#") else ("#10b981" if is_on else "#52525b")
            self.lbl_display.setText("●")
            self.lbl_display.setStyleSheet(f"color: {color}; font-size: 32px;")
        else:
            self.lbl_display.setText(val)
            self.lbl_display.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")


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
        
        self.btn_edit = QPushButton("🔒 Travar Layout")
        self.btn_edit.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        self.btn_edit.setCheckable(True)
        self.btn_edit.toggled.connect(self.toggle_edit_mode)
        
        toolbar.addWidget(self.btn_edit)
        toolbar.addStretch()
        
        main_layout.addLayout(toolbar)

        # Canvas
        self.canvas = QFrame()
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
        
        menu.addAction(action_label)
        menu.addAction(action_ind)
        menu.addAction(action_ctrl)
        
        menu.exec(self.canvas.mapToGlobal(pos))

    def _broadcast_can_frame(self, can_id: int, freq: float, payload: list):
        for w in self.canvas.findChildren(IndicatorWidget):
            w.process_can_frame(can_id, freq, payload)

    def toggle_edit_mode(self, checked):
        self.edit_mode = checked
        if checked:
            self.btn_edit.setText("🔓 Destravar Layout")
            self.btn_edit.setStyleSheet("background-color: #f59e0b; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;")
        else:
            self.btn_edit.setText("🔒 Travar Layout")
            self.btn_edit.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
            
        for w in self.canvas.findChildren(DashboardWidget):
            w.set_edit_mode(checked)

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

    def _place_widget(self, w: DashboardWidget, pos):
        w.show()
        w.move(pos)
        w.set_edit_mode(self.edit_mode)
        
    def export_data(self):
        widgets_data = []
        for w in self.canvas.findChildren(DashboardWidget):
            cfg = w.config.copy()
            cfg["pos_x"] = w.pos().x()
            cfg["pos_y"] = w.pos().y()
            widgets_data.append(cfg)
        return widgets_data
