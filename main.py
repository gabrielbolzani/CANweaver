import sys
import random
import time
import csv
import can
import serial.tools.list_ports
import os
import ctypes
import re
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QTimer, QDateTime, QRect, QPoint
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTableView, QPushButton, QTextEdit, QLabel, QHeaderView, QDialog,
    QFormLayout, QComboBox, QLineEdit, QFileDialog, QMessageBox, QToolBar, QCheckBox,
    QStyledItemDelegate, QMenu, QInputDialog, QStyleOptionViewItem, QStyle, QListWidget, QListWidgetItem, QTabWidget, QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QAction, QPainter, QFont, QTextDocument, QIcon, QPen

class CANItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        is_annotated = index.data(Qt.ItemDataRole.UserRole + 1)
        text = index.data(Qt.ItemDataRole.DisplayRole)
        
        is_binary = text and len(text) == 8 and all(c in '01' for c in text) and index.column() >= 2
        
        if is_binary:
            painter.save()
            
            bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg_brush:
                painter.fillRect(option.rect, bg_brush)
            else:
                if option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(option.rect, option.palette.highlight())

            old_bin = index.data(Qt.ItemDataRole.UserRole)
            if not old_bin or len(old_bin) != 8:
                old_bin = text

            rect = option.rect
            header_str = "76543210"
            
            painter.setPen(QColor("#69697a"))
            header_font = QFont("Courier New", 7)
            painter.setFont(header_font)
            painter.drawText(rect.adjusted(0, 2, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, header_str)

            margin_x = 4
            available_width = rect.width() - (margin_x * 2)
            square_size = min(available_width // 8, rect.height() - 16)
            if square_size > 14: square_size = 14
            
            spacing = (available_width - (square_size * 8)) / 7 if available_width > (square_size * 8) else 1
            if spacing > 4: spacing = 4
            
            total_draw_width = (square_size * 8) + (spacing * 7)
            start_x = rect.x() + (rect.width() - total_draw_width) // 2
            start_y = rect.y() + 14
            
            for i in range(8):
                bit_rect = QRect(int(start_x + i * (square_size + spacing)), int(start_y), int(square_size), int(square_size))
                
                bit_val = text[i]
                changed = (bit_val != old_bin[i])
                
                bg_color_name = bg_brush.color().name() if bg_brush else ""
                
                if changed:
                    fill_color = QColor("#04d361")
                    pen_color = QColor("#04d361")
                else:
                    if bg_color_name == "#1a1a1e": # Beeeem apagado
                        fill_color = QColor("#202024") if bit_val == '1' else QColor("#1a1a1e")
                        pen_color = QColor("#29292e") if bit_val == '1' else QColor("#202024")
                    elif bg_color_name == "#1f2937": # Intermediário
                        fill_color = QColor("#323238") if bit_val == '1' else QColor("#1f2937")
                        pen_color = QColor("#404040") if bit_val == '1' else QColor("#29292e")
                    else: # Ativo
                        fill_color = QColor("#000000") if bit_val == '1' else QColor("#ffffff")
                        pen_color = QColor("#000000") if bit_val == '1' else QColor("#323238")
                        
                painter.setBrush(fill_color)
                painter.setPen(pen_color)
                painter.drawRect(bit_rect)

            painter.restore()
        else:
            super().paint(painter, option, index)
            
        if is_annotated:
            painter.save()
            pen = QPen(QColor("#facc15"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
            painter.restore()



class CANWorker(QThread):
    """
    Thread de CAN Bus que suporta Simulação, Hardware Real (python-can) e Playback.
    """
    frame_received = pyqtSignal(int, float, list)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.mode = "SIMULATED"
        self.bus = None
        self.playback_file = ""
        self.playback_transmit = False
        self.playback_loop = False
        self.last_timestamps = {}
        self.counters = {0x0C0: 0, 0x180: 0, 0x3F0: 0}

    def run(self):
        self.running = True
        
        if self.mode == "HARDWARE" and self.bus:
            self._run_hardware()
        elif self.mode == "PLAYBACK" and self.playback_file:
            self._run_playback()
        elif self.mode == "SIMULATED":
            self._run_simulated()
        else:
            while self.running:
                time.sleep(0.5)

    def _run_hardware(self):
        try:
            while self.running:
                msg = self.bus.recv(timeout=0.1)
                if msg and msg.arbitration_id is not None:
                    current_time = time.time()
                    can_id = msg.arbitration_id
                    
                    if can_id in self.last_timestamps:
                        period = current_time - self.last_timestamps[can_id]
                        freq = 1.0 / period if period > 0 else 0.0
                    else:
                        freq = 0.0
                        
                    self.last_timestamps[can_id] = current_time
                    self.frame_received.emit(can_id, freq, list(msg.data))
        except Exception as e:
            self.error_occurred.emit(f"Erro no barramento CAN: {e}")
            self.running = False

    def _run_playback(self):
        try:
            while self.running:
                with open(self.playback_file, mode='r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    last_msg_time = None
                    
                    for row in reader:
                        if not self.running:
                            break
                        if len(row) < 4:
                            continue
                            
                        timestamp = float(row[0])
                        can_id = int(row[1], 16)
                        payload = [int(x, 16) for x in row[3:]]
                        
                        if last_msg_time is not None:
                            delay = timestamp - last_msg_time
                            if delay > 0:
                                time.sleep(delay)
                                
                        last_msg_time = timestamp
                        
                        if self.playback_transmit and self.bus:
                            try:
                                msg = can.Message(arbitration_id=can_id, data=payload, is_extended_id=False)
                                self.bus.send(msg)
                            except Exception as e:
                                pass
                                
                        current_time = time.time()
                        if can_id in self.last_timestamps:
                            period = current_time - self.last_timestamps[can_id]
                            freq = 1.0 / period if period > 0 else 0.0
                        else:
                            freq = 0.0
                            
                        self.last_timestamps[can_id] = current_time
                        self.frame_received.emit(can_id, freq, payload)
                        
                if not self.running or not self.playback_loop:
                    break
                    
            if self.running:
                self.error_occurred.emit("Reprodução concluída com sucesso.")
                
        except Exception as e:
            self.error_occurred.emit(f"Erro no playback: {e}")
            
        self.running = False

    def _run_simulated(self):
        target_ids = [0x0C0, 0x180, 0x3F0]
        while self.running:
            time.sleep(random.choice([0.01, 0.05, 0.1]))
            can_id = random.choice(target_ids)
            current_time = time.time()
            
            if can_id in self.last_timestamps:
                period = current_time - self.last_timestamps[can_id]
                freq = 1.0 / period if period > 0 else 0.0
            else:
                freq = random.uniform(10.0, 80.0)
                
            self.last_timestamps[can_id] = current_time
            
            if can_id == 0x0C0:
                self.counters[0x0C0] = (self.counters[0x0C0] + 1) % 16
                payload = [0x01, random.randint(0x00, 0xFF), random.randint(0x00, 0x02), 0x00, 0x00, 0x00, 0x00, self.counters[0x0C0]]
            elif can_id == 0x180:
                payload = [0x20, 0x00, random.choice([0x00, 0x01]), 0x00, 0x00, 0x00, 0x00, 0x00]
            else:
                payload = [random.randint(0x08, 0x0F), random.randint(0x00, 0xFF), 0x55, 0xAA, 0x00, 0x00, 0x00, 0x00]
                
            self.frame_received.emit(can_id, freq, payload)

    def stop(self):
        self.running = False
        
    def send_message(self, can_id, data):
        if self.mode == "SIMULATED":
            current_time = time.time()
            if can_id in self.last_timestamps:
                period = current_time - self.last_timestamps[can_id]
                freq = 1.0 / period if period > 0 else 0.0
            else:
                freq = 0.0
            self.last_timestamps[can_id] = current_time
            self.frame_received.emit(can_id, freq, data)
        elif self.mode == "HARDWARE" and self.bus:
            try:
                msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
                self.bus.send(msg)
            except Exception as e:
                print(f"Erro de Tx no Barramento: {e}")

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
        
        self.row_interface = ("Interface:", self.cb_interface)
        self.row_channel = ("Canal/Porta:", self.cb_channel)
        self.row_bitrate = ("Velocidade:", self.cb_bitrate)
        self.row_file_btn = ("Arquivo Playback:", self.btn_file)
        self.row_file_lbl = ("", self.lbl_file)
        self.row_transmit = ("", self.chk_transmit)
        self.row_loop = ("", self.chk_loop)
        
        self.layout.addRow(*self.row_interface)
        self.layout.addRow(*self.row_channel)
        self.layout.addRow(*self.row_bitrate)
        self.layout.addRow(*self.row_file_btn)
        self.layout.addRow(*self.row_file_lbl)
        self.layout.addRow(*self.row_transmit)
        self.layout.addRow(*self.row_loop)
        
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
        if index == 0: # Simulado
            self.set_row_visible(self.cb_interface, False)
            self.set_row_visible(self.cb_channel, False)
            self.set_row_visible(self.cb_bitrate, False)
            self.set_row_visible(self.btn_file, False)
            self.set_row_visible(self.lbl_file, False)
            self.set_row_visible(self.chk_transmit, False)
            self.set_row_visible(self.chk_loop, False)
        elif index == 1: # Hardware Real
            self.set_row_visible(self.cb_interface, True)
            self.set_row_visible(self.cb_channel, True)
            self.set_row_visible(self.cb_bitrate, True)
            self.set_row_visible(self.btn_file, False)
            self.set_row_visible(self.lbl_file, False)
            self.set_row_visible(self.chk_transmit, False)
            self.set_row_visible(self.chk_loop, False)
        elif index == 2: # Playback
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
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo de Playback", "", "CSV Files (*.csv);;All Files (*)")
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
    def __init__(self, parent, target):
        super().__init__(parent)
        self.setWindowTitle("Adicionar Comentário")
        self.resize(400, 200)
        
        self.layout = QVBoxLayout(self)
        lbl = QLabel(f"Comentário para {target}:<br><small style='color:#a1a1aa'>(Shift+Enter para pular linha, Enter para Salvar)</small>")
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

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CANweaver v2.0 - AI Assisted CAN Reverse Engineering")
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ico.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1280, 720)
        
        # Dicionário local para guardar o estado histórico dos dados (para efeito de Fade e Detecção)
        # Estrutura: { can_id: { "last_payload": [...], "last_change_time": [...] } }
        self.can_database = {}
        self.annotations = {}
        self.hide_static = False
        self.is_recording = False
        self.record_file = None
        self.record_writer = None
        self.record_start_time = 0
        self.temp_record_filename = "temp_gravacao.csv"
        self.display_format = "HEX"
        self.periodic_timers = {}
        
        self.busload_accumulator = 0
        self.current_bitrate = 500000
        
        self.load_annotations()
        self.init_ui()
        self.load_stylesheet()
        
        # Inicializa a thread de captura ociosa
        self.can_thread = CANWorker()
        self.can_thread.mode = "IDLE"
        self.can_thread.frame_received.connect(self.process_can_frame)
        self.can_thread.error_occurred.connect(self.handle_worker_error)
        self.can_thread.start()
        
        # Timer para processar o decaimento (Fade) das cores a cada 100ms
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.apply_fade_effect)
        self.fade_timer.start(100)
        
        # Timer para cronômetro de gravação
        self.record_timer = QTimer()
        self.record_timer.timeout.connect(self.update_record_time)

        # Timer de Busload
        self.busload_timer = QTimer()
        self.busload_timer.timeout.connect(self.update_busload)
        self.busload_timer.start(1000)

    def toggle_recording(self):
        if not self.is_recording:
            filename, _ = QFileDialog.getSaveFileName(self, "Salvar Gravação", "", "CSV Files (*.csv)")
            if not filename: return
            self.record_file = open(filename, 'w', newline='')
            self.record_writer = csv.writer(self.record_file)
            self.record_writer.writerow(["Timestamp", "ID", "DLC", "Data..."])
            self.record_start_time = time.time()
            self.is_recording = True
            self.btn_record.setText("⏹ Parar Gravação")
            self.btn_record.setStyleSheet("background-color: #e83f5b; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;")
        else:
            self.is_recording = False
            if self.record_file:
                self.record_file.close()
            self.btn_record.setText("⏺ Gravar (REC)")
            self.btn_record.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;")

    def init_ui(self):
        # --- BARRA DE FERRAMENTAS GLOBAL (TOPO) ---
        toolbar = QToolBar("Global Controls")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.setMovable(False)
        toolbar.setStyleSheet("background-color: #202024; border-bottom: 1px solid #323238;")
        
        self.btn_connect = QPushButton("Conectar...")
        self.btn_connect.clicked.connect(self.open_connection_dialog)
        self.btn_connect.setStyleSheet("background-color: #4e44dd; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold; margin-right: 10px; margin-left: 10px;")
        
        self.btn_record = QPushButton("⏺ Gravar (REC)")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self.toggle_recording)
        self.btn_record.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;")
        
        self.lbl_status = QLabel("Status: Ocioso (Desconectado)")
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-weight: bold;")
        
        toolbar.addWidget(self.btn_connect)
        toolbar.addWidget(self.btn_record)
        toolbar.addWidget(self.lbl_status)
        
        # Layout Principal (Aba de Análise)
        main_layout = QHBoxLayout()
        
        # --- PAINEL DA GRELHA (ESQUERDO) ---
        left_layout = QVBoxLayout()
        
        # Cabeçalho de Controlos Específicos da Aba
        control_layout = QHBoxLayout()
        
        self.btn_format = QPushButton("Exibição: HEX")
        self.btn_format.clicked.connect(self.toggle_display_format)
        self.btn_format.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px;")
        
        self.chk_hide_static = QCheckBox("Ocultar Estáticos")
        self.chk_hide_static.setStyleSheet("color: white;")
        self.chk_hide_static.stateChanged.connect(self.toggle_static_filter)
        
        self.chk_fade = QCheckBox("Fade Inativos")
        self.chk_fade.setChecked(True)
        self.chk_fade.setStyleSheet("color: white;")
        
        self.lbl_busload = QLabel("Busload: ---%")
        self.lbl_busload.setStyleSheet("color: #10b981; font-weight: bold; margin-left: 20px;")
        
        control_layout.addWidget(self.btn_format)
        control_layout.addWidget(self.chk_fade)
        control_layout.addWidget(self.chk_hide_static)
        control_layout.addWidget(self.lbl_busload)
        control_layout.addStretch()
        left_layout.addLayout(control_layout)
        
        # Tabela (Live Data Grid)
        self.table_view = QTableView()
        self.table_model = QStandardItemModel(0, 10) # ID, Freq, B0, B1, B2, B3, B4, B5, B6, B7
        self.table_model.setHorizontalHeaderLabels(["ID CAN", "Freq (Hz)", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"])
        self.table_view.setModel(self.table_model)
        
        # Ativação do Delegate e Context Menu
        self.table_view.setItemDelegate(CANItemDelegate(self.table_view))
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        
        # Barra de Filtros
        filter_layout = QHBoxLayout()
        self.txt_filter_id = QLineEdit()
        self.txt_filter_id.setPlaceholderText("Filtrar por ID (ex: 0C0)")
        self.txt_filter_id.textChanged.connect(self.apply_filters)
        
        self.cb_freq_op = QComboBox()
        self.cb_freq_op.addItems([">", "<"])
        self.cb_freq_op.currentIndexChanged.connect(self.apply_filters)
        
        self.txt_filter_freq = QLineEdit()
        self.txt_filter_freq.setPlaceholderText("Freq. Limit (Hz)")
        self.txt_filter_freq.textChanged.connect(self.apply_filters)
        
        filter_layout.addWidget(QLabel("ID:"))
        filter_layout.addWidget(self.txt_filter_id)
        filter_layout.addWidget(QLabel("Freq:"))
        filter_layout.addWidget(self.cb_freq_op)
        filter_layout.addWidget(self.txt_filter_freq)
        filter_layout.addStretch()
        
        left_layout.addLayout(filter_layout)
        
        # Ajustes de visualização da tabela
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        left_layout.addWidget(self.table_view)
        
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_id_filter = QLabel("Visibilidade de IDs (Filtro)")
        id_filter_btns_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Sel. Todos")
        self.btn_select_all.clicked.connect(self.select_all_ids)
        self.btn_deselect_all = QPushButton("Desmarc. Todos")
        self.btn_deselect_all.clicked.connect(self.deselect_all_ids)
        id_filter_btns_layout.addWidget(self.btn_select_all)
        id_filter_btns_layout.addWidget(self.btn_deselect_all)
        
        self.list_ids = QListWidget()
        self.list_ids.itemChanged.connect(self.on_id_checkbox_changed)
        
        right_layout.addWidget(lbl_id_filter)
        right_layout.addLayout(id_filter_btns_layout)
        right_layout.addWidget(self.list_ids, 2)
        
        lbl_ia = QLabel("Assistente IA / Log")
        self.btn_simulate_ia = QPushButton("Simular Sugestão IA")
        self.btn_simulate_ia.clicked.connect(self.simulate_ia_documentation)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        
        right_layout.addWidget(lbl_ia)
        right_layout.addWidget(self.btn_simulate_ia)
        right_layout.addWidget(self.txt_log, 1)
        
        main_layout.addLayout(left_layout, 7)
        main_layout.addLayout(right_layout, 3)
        
        # Abas
        self.tab_widget = QTabWidget()
        
        self.tab_analysis = QWidget()
        self.tab_analysis.setLayout(main_layout)
        
        self.tab_transmit = QWidget()
        self.init_transmit_tab()
        
        self.tab_widgets = QWidget()
        widgets_layout = QVBoxLayout()
        widgets_layout.addWidget(QLabel("<h2 style='color:#a1a1aa; text-align:center;'>Aba de Painel / Gauges (Em Breve)</h2>"))
        self.tab_widgets.setLayout(widgets_layout)
        
        self.tab_widget.addTab(self.tab_analysis, "Análise (Sniffer)")
        self.tab_widget.addTab(self.tab_transmit, "Transmitir")
        self.tab_widget.addTab(self.tab_widgets, "Widgets")
        
        self.setCentralWidget(self.tab_widget)

    def init_transmit_tab(self):
        layout = QVBoxLayout()
        
        # --- SINGLE SHOT ---
        group_single = QWidget()
        single_layout = QVBoxLayout(group_single)
        lbl_single = QLabel("Disparo Único (Single Shot)")
        lbl_single.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 14px;")
        single_layout.addWidget(lbl_single)
        
        form_single = QHBoxLayout()
        self.txt_single_id = QLineEdit()
        self.txt_single_id.setPlaceholderText("ID (HEX)")
        
        self.cb_single_format = QComboBox()
        self.cb_single_format.addItems(["HEX", "BIN"])
        
        self.txt_single_data = QLineEdit()
        self.txt_single_data.setPlaceholderText("Dados (Ex: FF 00 1A)")
        
        self.btn_single_send = QPushButton("🚀 Transmitir Pulso")
        self.btn_single_send.setStyleSheet("background-color: #4e44dd; color: white; padding: 6px; border-radius: 4px;")
        self.btn_single_send.clicked.connect(self.send_single_shot)
        
        form_single.addWidget(QLabel("ID:"))
        form_single.addWidget(self.txt_single_id)
        form_single.addWidget(QLabel("Formato:"))
        form_single.addWidget(self.cb_single_format)
        form_single.addWidget(QLabel("Dados:"))
        form_single.addWidget(self.txt_single_data, 1)
        form_single.addWidget(self.btn_single_send)
        
        single_layout.addLayout(form_single)
        layout.addWidget(group_single)
        
        # --- PERIODIC ---
        group_periodic = QWidget()
        periodic_layout = QVBoxLayout(group_periodic)
        lbl_periodic = QLabel("Transmissão Periódica (Cíclica)")
        lbl_periodic.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 14px; margin-top: 20px;")
        periodic_layout.addWidget(lbl_periodic)
        
        form_periodic = QHBoxLayout()
        self.txt_per_id = QLineEdit()
        self.txt_per_id.setPlaceholderText("ID")
        self.cb_per_format = QComboBox()
        self.cb_per_format.addItems(["HEX", "BIN"])
        self.txt_per_data = QLineEdit()
        self.txt_per_data.setPlaceholderText("Dados")
        self.txt_per_freq = QLineEdit()
        self.txt_per_freq.setPlaceholderText("Frequência (Hz)")
        
        self.btn_per_add = QPushButton("Adicionar Tarefa")
        self.btn_per_add.clicked.connect(self.add_periodic_task)
        
        form_periodic.addWidget(self.txt_per_id)
        form_periodic.addWidget(self.cb_per_format)
        form_periodic.addWidget(self.txt_per_data, 1)
        form_periodic.addWidget(self.txt_per_freq)
        form_periodic.addWidget(self.btn_per_add)
        
        periodic_layout.addLayout(form_periodic)
        
        self.tbl_periodic = QTableWidget(0, 5)
        self.tbl_periodic.setHorizontalHeaderLabels(["ID (HEX)", "Dados", "Freq (Hz)", "Status", "Ações"])
        self.tbl_periodic.horizontalHeader().setStretchLastSection(True)
        periodic_layout.addWidget(self.tbl_periodic)
        
        btn_layout_per = QHBoxLayout()
        self.btn_start_all = QPushButton("▶️ Iniciar Cíclicos")
        self.btn_start_all.setStyleSheet("background-color: #10b981; color: white; padding: 8px; font-weight: bold;")
        self.btn_start_all.clicked.connect(self.start_all_periodic)
        
        self.btn_stop_all = QPushButton("⏹ Parar Todos")
        self.btn_stop_all.setStyleSheet("background-color: #e83f5b; color: white; padding: 8px; font-weight: bold;")
        self.btn_stop_all.clicked.connect(self.stop_all_periodic)
        
        btn_layout_per.addWidget(self.btn_start_all)
        btn_layout_per.addWidget(self.btn_stop_all)
        periodic_layout.addLayout(btn_layout_per)
        
        layout.addWidget(group_periodic, 1)
        self.tab_transmit.setLayout(layout)

    def load_stylesheet(self):
        try:
            with open("style.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Não foi possível carregar o style.qss: {e}")

    def load_annotations(self):
        filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CANweaver_Projeto.md")
        if not os.path.exists(filename): return
        
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except:
            return
            
        current_target = None
        current_comment = []
        
        for line in lines:
            if line.startswith("## ["):
                if current_target and current_comment:
                    self._save_annotation_to_dict(current_target, "\n".join(current_comment).strip())
                m = re.search(r"## \[(.*?)\]", line)
                if m:
                    current_target = m.group(1)
                current_comment = []
            else:
                if current_target and line.strip() != "":
                    current_comment.append(line.strip())
                    
        if current_target and current_comment:
            self._save_annotation_to_dict(current_target, "\n".join(current_comment).strip())
            
    def _save_annotation_to_dict(self, target, comment):
        if not comment: return
        if target not in self.annotations:
            self.annotations[target] = []
        self.annotations[target].append(comment)

    def get_tooltip_for_id(self, hex_id):
        target = f"ID {hex_id}"
        if target in self.annotations:
            return "\n---\n".join(self.annotations[target])
        return ""
        
    def get_tooltip_for_byte(self, hex_id, byte_idx):
        comments = []
        base_target = f"ID {hex_id} - Byte {byte_idx}"
        
        if base_target in self.annotations:
            comments.extend(self.annotations[base_target])
            
        for target, texts in self.annotations.items():
            if target.startswith(f"{base_target} - Bit"):
                bit_str = target.split(" - ")[-1]
                for t in texts:
                    comments.append(f"[{bit_str}] {t}")
                    
        return "\n---\n".join(comments) if comments else ""

    @pyqtSlot(int, float, list)
    def process_can_frame(self, can_id, frequency, payload):
        bits = (44 + 8 * len(payload)) * 1.2
        self.busload_accumulator += bits
        
        if self.is_recording and self.record_writer:
            self.record_writer.writerow([time.time(), f"{can_id:03X}", len(payload)] + list(payload))
            
        hex_id = f"{can_id:03X}"
        current_time = time.time()
        
        if hex_id not in self.can_database:
            list_item = QListWidgetItem(f"[{hex_id}] - 0.0 Hz")
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Checked)
            list_item.setData(Qt.ItemDataRole.UserRole, hex_id)
            self.list_ids.addItem(list_item)
            
            self.can_database[hex_id] = {
                "row_index": self.table_model.rowCount(),
                "last_payload": list(payload),
                "last_change_time": [current_time] * 8,
                "is_static": False,
                "list_item": list_item
            }
            
            item_id = QStandardItem(hex_id)
            tt_id = self.get_tooltip_for_id(hex_id)
            if tt_id:
                item_id.setData(True, Qt.ItemDataRole.UserRole + 1)
                item_id.setToolTip(tt_id)
                
            row_items = [item_id, QStandardItem(f"{frequency:.1f}")]
            for i, b in enumerate(payload):
                if self.display_format == "HEX":
                    item = QStandardItem(f"{b:02X}")
                else:
                    item = QStandardItem(f"{b:08b}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(f"{b:08b}", Qt.ItemDataRole.UserRole)
                
                tt_byte = self.get_tooltip_for_byte(hex_id, i)
                if tt_byte:
                    item.setData(True, Qt.ItemDataRole.UserRole + 1)
                    item.setToolTip(tt_byte)
                    
                row_items.append(item)
            self.table_model.appendRow(row_items)
            self.update_row_visibility(hex_id)
            return

        db_entry = self.can_database[hex_id]
        row_idx = db_entry["row_index"]
        self.table_model.item(row_idx, 1).setText(f"{frequency:.1f}")
        db_entry["list_item"].setText(f"[{hex_id}] - {frequency:.1f} Hz")
            
        payload_len = len(payload)
        while len(db_entry["last_payload"]) < payload_len:
            db_entry["last_payload"].append(0)
            db_entry["last_change_time"].append(current_time)
            
        for i in range(payload_len):
            item = self.table_model.item(row_idx, i + 2)
            if item is None:
                if self.display_format == "HEX":
                    item = QStandardItem(f"{payload[i]:02X}")
                else:
                    item = QStandardItem(f"{payload[i]:08b}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(f"{payload[i]:08b}", Qt.ItemDataRole.UserRole)
                self.table_model.setItem(row_idx, i + 2, item)
                
            if db_entry["last_payload"][i] != payload[i]:
                if self.display_format == "HEX":
                    item.setText(f"{payload[i]:02X}")
                else:
                    item.setText(f"{payload[i]:08b}")
                    
                item.setData(f"{db_entry['last_payload'][i]:08b}", Qt.ItemDataRole.UserRole)
                
                db_entry["last_change_time"][i] = current_time
                db_entry["last_payload"][i] = payload[i]
                item.setBackground(QColor("#1e3a8a"))
                item.setForeground(QColor("#ffffff"))

        db_entry["is_static"] = (current_time - max(db_entry["last_change_time"])) > 5.0
        self.update_row_visibility(hex_id)

    @pyqtSlot()
    def apply_fade_effect(self):
        if not self.chk_fade.isChecked(): return
        current_time = time.time()
        for hex_id, info in self.can_database.items():
            row_idx = info["row_index"]
            for i in range(len(info["last_payload"])):
                item = self.table_model.item(row_idx, i + 2)
                if item is None:
                    continue
                elapsed = current_time - info["last_change_time"][i]
                if elapsed > 1.0:
                    item.setBackground(QColor("#1a1a1e"))
                    item.setForeground(QColor("#69697a"))
                    item.setData(f"{info['last_payload'][i]:08b}", Qt.ItemDataRole.UserRole)
                elif elapsed > 0.3:
                    item.setBackground(QColor("#1f2937"))
                    item.setForeground(QColor("#a1a1aa"))

    @pyqtSlot()
    def update_busload(self):
        if self.current_bitrate > 0 and self.can_thread and self.can_thread.isRunning() and self.can_thread.mode != "IDLE":
            load_pct = (self.busload_accumulator / self.current_bitrate) * 100.0
            if load_pct > 100.0: load_pct = 100.0
            self.lbl_busload.setText(f"Busload: {load_pct:.1f}%")
            
            # Muda cor baseado na carga
            if load_pct < 50:
                self.lbl_busload.setStyleSheet("color: #10b981; font-weight: bold; margin-left: 20px;")
            elif load_pct < 80:
                self.lbl_busload.setStyleSheet("color: #f59e0b; font-weight: bold; margin-left: 20px;")
            else:
                self.lbl_busload.setStyleSheet("color: #e83f5b; font-weight: bold; margin-left: 20px;")
        else:
            self.lbl_busload.setText("Busload: ---%")
            self.lbl_busload.setStyleSheet("color: #69697a; font-weight: bold; margin-left: 20px;")
            
        self.busload_accumulator = 0

    @pyqtSlot()
    def apply_filters(self):
        for hex_id in self.can_database.keys():
            self.update_row_visibility(hex_id)

    @pyqtSlot()
    def update_row_visibility(self, hex_id):
        info = self.can_database.get(hex_id)
        if not info: return
        row_idx = info["row_index"]
        
        # Filtro de Checkbox (SavvyCAN)
        if info["list_item"].checkState() == Qt.CheckState.Unchecked:
            self.table_view.setRowHidden(row_idx, True)
            return
            
        # Filtro estático
        if self.hide_static and info["is_static"]:
            self.table_view.setRowHidden(row_idx, True)
            return
            
        # Filtro ID Textual
        filter_id = self.txt_filter_id.text().strip().upper()
        if filter_id and filter_id not in hex_id.upper():
            self.table_view.setRowHidden(row_idx, True)
            return
            
        # Filtro Freq Textual
        freq_text = self.txt_filter_freq.text().strip()
        if freq_text:
            try:
                limit = float(freq_text)
                freq_item = self.table_model.item(row_idx, 1)
                current_freq = float(freq_item.text()) if freq_item else 0.0
                op = self.cb_freq_op.currentText()
                if op == ">" and current_freq <= limit:
                    self.table_view.setRowHidden(row_idx, True)
                    return
                elif op == "<" and current_freq >= limit:
                    self.table_view.setRowHidden(row_idx, True)
                    return
            except ValueError:
                pass
                
        self.table_view.setRowHidden(row_idx, False)

    @pyqtSlot()
    def toggle_static_filter(self):
        self.hide_static = self.chk_hide_static.isChecked()
        for hex_id in self.can_database.keys():
            self.update_row_visibility(hex_id)

    @pyqtSlot()
    def select_all_ids(self):
        for i in range(self.list_ids.count()):
            self.list_ids.item(i).setCheckState(Qt.CheckState.Checked)

    @pyqtSlot()
    def deselect_all_ids(self):
        for i in range(self.list_ids.count()):
            self.list_ids.item(i).setCheckState(Qt.CheckState.Unchecked)

    @pyqtSlot(QListWidgetItem)
    def on_id_checkbox_changed(self, item):
        hex_id = item.data(Qt.ItemDataRole.UserRole)
        self.update_row_visibility(hex_id)

    @pyqtSlot()
    def simulate_ia_documentation(self):
        markdown_doc = """
        <table width='100%' style='border: 1px solid #29292e; color: #e1e1e6;'>
            <tr style='background-color: #202024;'>
                <th>ID Identificado</th>
                <th>Sinal Provável</th>
                <th>Tipo de Dado</th>
            </tr>
            <tr>
                <td><b>0x0C0</b></td>
                <td>Steering Angle Sensor</td>
                <td>16-bit Signed Integer</td>
            </tr>
        </table>
        <p><b>Varredura de Heurística de Ruído:</b></p>
        <ul>
            <li><b>Byte 7:</b> Identificado como <i>Rolling Counter</i> (Incremento linear de 0 a 15). <b>Descartado automaticamente da análise de telemetria.</b></li>
            <li><b>Bytes 1 e 2:</b> Modulação correspondente à variação dinâmica de direção. Mapeado como ângulo de esterço.</li>
        </ul>
        """
        self.txt_ia_doc.setHtml(markdown_doc)
        
        # Simula escrita física do markdown do projeto em background
        try:
            with open("CANweaver/documentation/0x0C0_steering_angle.md", "w", encoding="utf-8") as f:
                f.write("# CANweaver AI Reverse Engineering Report\n\n## ID: 0x0C0\n- **Signal**: Steering Angle\n- **Type**: 16-bit Signed\n- **Noise Filtered**: Byte 7 detected as Rolling Counter.")
        except Exception:
            pass

    def open_connection_dialog(self):
        dialog = ConnectionDialog(self)
        if dialog.exec():
            config = dialog.get_config()
            self.start_worker(config)
            
    def start_worker(self, config):
        if self.can_thread and self.can_thread.isRunning():
            self.can_thread.stop()
            
        self.current_bitrate = config.get("bitrate", 500000)
        
        self.can_thread = CANWorker()
        self.can_thread.mode = config["mode"]
        if config.get("playback_loop"):
            self.can_thread.playback_loop = config["playback_loop"]
        
        if config["mode"] == "HARDWARE":
            try:
                self.can_thread.bus = can.Bus(interface=config["interface"], channel=config["channel"], bitrate=config["bitrate"])
                self.lbl_status.setText(f"Status: Conectado ({config['interface']} em {config['channel']} @ {config['bitrate']})")
            except Exception as e:
                QMessageBox.critical(self, "Erro de Conexão", f"Não foi possível conectar ao hardware:\n{e}")
                self.lbl_status.setText("Status: Erro de Conexão")
                return
        elif config["mode"] == "PLAYBACK":
            if not config["playback_file"]:
                QMessageBox.warning(self, "Aviso", "Nenhum arquivo selecionado.")
                return
            self.can_thread.playback_file = config["playback_file"]
            self.lbl_status.setText(f"Status: Reproduzindo {config['playback_file'].split('/')[-1]}")
        else:
            self.lbl_status.setText("Status: Conectado ao Barramento (Simulado)")
            
        self.can_thread.frame_received.connect(self.process_can_frame)
        self.can_thread.error_occurred.connect(self.handle_worker_error)
        
        # Limpar banco de dados e resetar fade timer/grelha para uma nova conexão limpa
        self.can_database.clear()
        self.table_model.removeRows(0, self.table_model.rowCount())
        
        self.can_thread.start()

    @pyqtSlot(str)
    def handle_worker_error(self, err_msg):
        QMessageBox.warning(self, "Aviso da Thread", err_msg)
        if "Reprodução concluída" in err_msg:
            self.lbl_status.setText("Status: Reprodução Finalizada")

    def toggle_recording(self, checked):
        if checked:
            try:
                self.record_file = open(self.temp_record_filename, "w", newline="", encoding="utf-8")
                self.record_writer = csv.writer(self.record_file)
                self.record_writer.writerow(["Timestamp", "ID", "DLC", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"])
                self.record_start_time = time.time()
                self.is_recording = True
                self.btn_record.setStyleSheet("background-color: #e83f5b; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;")
                self.lbl_status.setText(self.lbl_status.text() + " [GRAVANDO]")
                
                self.record_timer.start(1000)
                self.btn_record.setText("⏹ Gravando (00:00)")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao criar cache de gravação:\n{e}")
                self.btn_record.setChecked(False)
        else:
            self.is_recording = False
            self.record_timer.stop()
            if self.record_file:
                self.record_file.close()
                self.record_file = None
                self.record_writer = None
            
            # Modal Rename
            timestamp_str = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            default_name = f"gravacao_can_{timestamp_str}.csv"
            text, ok = QInputDialog.getText(self, "Salvar Gravação", "Dê um nome para a sessão (CSV):", QLineEdit.EchoMode.Normal, default_name)
            
            if ok and text:
                if not text.endswith(".csv"):
                    text += ".csv"
                try:
                    if os.path.exists(text):
                        os.remove(text)
                    os.rename(self.temp_record_filename, text)
                    QMessageBox.information(self, "Salvo", f"Gravação salva como:\n{text}")
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível salvar o arquivo:\n{e}")
            else:
                try:
                    os.remove(self.temp_record_filename)
                except:
                    pass

            self.btn_record.setText("⏺ Gravar (REC)")
            self.btn_record.setStyleSheet("background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;")
            self.lbl_status.setText(self.lbl_status.text().replace(" [GRAVANDO]", ""))

    def update_record_time(self):
        if self.is_recording:
            elapsed = int(time.time() - self.record_start_time)
            mins, secs = divmod(elapsed, 60)
            self.btn_record.setText(f"⏹ Gravando ({mins:02d}:{secs:02d})")

    @pyqtSlot()
    def toggle_display_format(self):
        if self.display_format == "HEX":
            self.display_format = "BIN"
            self.btn_format.setText("Exibição: BIN")
        else:
            self.display_format = "HEX"
            self.btn_format.setText("Exibição: HEX")
            
        for hex_id, info in self.can_database.items():
            row_idx = info["row_index"]
            payload = info["last_payload"]
            for i in range(8):
                item = self.table_model.item(row_idx, i + 2)
                if item:
                    if self.display_format == "HEX":
                        item.setText(f"{payload[i]:02X}")
                    else:
                        item.setText(f"{payload[i]:08b}")

    def show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return
            
        row = index.row()
        col = index.column()
        
        id_item = self.table_model.item(row, 0)
        if not id_item: return
        can_id = id_item.text()
        
        target = f"ID {can_id}"
        if col >= 2:
            byte_idx = col - 2
            target = f"ID {can_id} - Byte {byte_idx}"
            
            if self.display_format == "BIN":
                cell_rect = self.table_view.visualRect(index)
                rel_x = pos.x() - cell_rect.x()
                width = cell_rect.width()
                bit_idx = int((rel_x / width) * 8)
                if bit_idx < 0: bit_idx = 0
                if bit_idx > 7: bit_idx = 7
                target += f" - Bit {7 - bit_idx}"
        
        menu = QMenu()
        action_comment = QAction(f"Adicionar Comentário em {target}...", self)
        action_comment.triggered.connect(lambda: self.add_comment(can_id, target, index))
        menu.addAction(action_comment)
        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def add_comment(self, can_id, target, index):
        dialog = CommentDialog(self, target)
        if dialog.exec():
            text = dialog.get_text()
            if text:
                filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CANweaver_Projeto.md")
                try:
                    with open(filename, "a", encoding="utf-8") as f:
                        f.write(f"\n## [{target}] - {QDateTime.currentDateTime().toString('yyyy-MM-dd HH:mm:ss')}\n")
                        f.write(f"{text}\n")
                    
                    self._save_annotation_to_dict(target, text)
                    
                    # Marca a célula visualmente (Borda amarela) e tooltips
                    item = self.table_model.itemFromIndex(index)
                    if item:
                        item.setData(True, Qt.ItemDataRole.UserRole + 1)
                        if "Byte" in target or "Bit" in target:
                            col = index.column()
                            byte_idx = col - 2
                            item.setToolTip(self.get_tooltip_for_byte(can_id, byte_idx))
                        else:
                            item.setToolTip(self.get_tooltip_for_id(can_id))
                            
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível salvar arquivo:\n{e}")

    def parse_payload(self, text, format_type):
        parts = text.strip().split()
        data = []
        for p in parts:
            if format_type == "HEX":
                data.append(int(p, 16))
            else:
                data.append(int(p, 2))
        return data

    def send_single_shot(self):
        if self.can_thread.mode == "IDLE":
            QMessageBox.warning(self, "Aviso", "Conecte-se ao barramento primeiro.")
            return
        try:
            can_id = int(self.txt_single_id.text().strip(), 16)
            data = self.parse_payload(self.txt_single_data.text(), self.cb_single_format.currentText())
            self.can_thread.send_message(can_id, data)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Formato inválido:\n{e}")

    def add_periodic_task(self):
        try:
            can_id_str = self.txt_per_id.text().strip()
            data_str = self.txt_per_data.text().strip()
            hz = float(self.txt_per_freq.text().strip())
            if hz <= 0:
                raise ValueError("Frequência deve ser maior que zero.")
            fmt = self.cb_per_format.currentText()
            
            int(can_id_str, 16)
            self.parse_payload(data_str, fmt)
            
            row = self.tbl_periodic.rowCount()
            self.tbl_periodic.insertRow(row)
            
            task_id = str(time.time())
            item_id = QTableWidgetItem(can_id_str)
            item_id.setData(Qt.ItemDataRole.UserRole + 2, task_id)
            self.tbl_periodic.setItem(row, 0, item_id)
            
            item_data = QTableWidgetItem(data_str)
            item_data.setData(Qt.ItemDataRole.UserRole, fmt)
            self.tbl_periodic.setItem(row, 1, item_data)
            
            self.tbl_periodic.setItem(row, 2, QTableWidgetItem(str(hz)))
            self.tbl_periodic.setItem(row, 3, QTableWidgetItem("Parado"))
            
            widget_actions = QWidget()
            layout_actions = QHBoxLayout(widget_actions)
            layout_actions.setContentsMargins(0, 0, 0, 0)
            
            btn_pause = QPushButton("Pausar")
            btn_pause.setStyleSheet("background-color: #f59e0b; color: white; border-radius: 4px; padding: 4px; font-weight: bold;")
            
            btn_del = QPushButton("Excluir")
            btn_del.setStyleSheet("background-color: #e83f5b; color: white; border-radius: 4px; padding: 4px; font-weight: bold;")
            
            layout_actions.addWidget(btn_pause)
            layout_actions.addWidget(btn_del)
            
            btn_del.clicked.connect(lambda _, t_id=task_id: self.remove_periodic_task(t_id))
            btn_pause.clicked.connect(lambda _, t_id=task_id: self.toggle_periodic_task(t_id))
            
            self.tbl_periodic.setCellWidget(row, 4, widget_actions)
            
            self.txt_per_id.clear()
            self.txt_per_data.clear()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Verifique os dados:\n{e}")

    def remove_periodic_task(self, task_id):
        if task_id in self.periodic_timers:
            self.periodic_timers[task_id].stop()
            del self.periodic_timers[task_id]
        
        for r in range(self.tbl_periodic.rowCount()):
            item = self.tbl_periodic.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole + 2) == task_id:
                self.tbl_periodic.removeRow(r)
                break

    def toggle_periodic_task(self, task_id):
        if task_id in self.periodic_timers:
            timer = self.periodic_timers[task_id]
            for r in range(self.tbl_periodic.rowCount()):
                item = self.tbl_periodic.item(r, 0)
                if item and item.data(Qt.ItemDataRole.UserRole + 2) == task_id:
                    status_item = self.tbl_periodic.item(r, 3)
                    widget = self.tbl_periodic.cellWidget(r, 4)
                    btn_pause = widget.findChildren(QPushButton)[0]
                    if timer.isActive():
                        timer.stop()
                        status_item.setText("Pausado")
                        status_item.setForeground(QColor("#f59e0b"))
                        btn_pause.setText("Retomar")
                        btn_pause.setStyleSheet("background-color: #3b82f6; color: white; border-radius: 4px; padding: 4px; font-weight: bold;")
                    else:
                        hz = float(self.tbl_periodic.item(r, 2).text())
                        interval_ms = int(1000.0 / hz)
                        timer.start(interval_ms)
                        status_item.setText("Ativo")
                        status_item.setForeground(QColor("#10b981"))
                        btn_pause.setText("Pausar")
                        btn_pause.setStyleSheet("background-color: #f59e0b; color: white; border-radius: 4px; padding: 4px; font-weight: bold;")
                    break

    def start_all_periodic(self):
        if self.can_thread.mode == "IDLE":
            QMessageBox.warning(self, "Aviso", "Conecte-se ao barramento primeiro.")
            return
            
        for r in range(self.tbl_periodic.rowCount()):
            item_id = self.tbl_periodic.item(r, 0)
            task_id = item_id.data(Qt.ItemDataRole.UserRole + 2)
            
            hz = float(self.tbl_periodic.item(r, 2).text())
            interval_ms = int(1000.0 / hz)
            
            if task_id not in self.periodic_timers:
                can_id = int(item_id.text(), 16)
                fmt = self.tbl_periodic.item(r, 1).data(Qt.ItemDataRole.UserRole)
                data = self.parse_payload(self.tbl_periodic.item(r, 1).text(), fmt)
                
                timer = QTimer()
                timer.timeout.connect(lambda cid=can_id, d=data: self.can_thread.send_message(cid, d))
                self.periodic_timers[task_id] = timer
                
            self.periodic_timers[task_id].start(interval_ms)
            self.tbl_periodic.item(r, 3).setText("Ativo")
            self.tbl_periodic.item(r, 3).setForeground(QColor("#10b981"))
                
    def stop_all_periodic(self):
        for task_id, timer in self.periodic_timers.items():
            timer.stop()
        
        for r in range(self.tbl_periodic.rowCount()):
            item = self.tbl_periodic.item(r, 3)
            if item:
                item.setText("Parado")
                item.setForeground(QColor("white"))

class PyInstallerDummy:
    pass

if __name__ == "__main__":
    try:
        myappid = 'canweaver.v2.ai.reverseengineering'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
