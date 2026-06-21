"""
analysis_tab.py — Widget da Aba de Análise (Sniffer)

Responsabilidade: toda a UI e lógica da aba "Análise (Sniffer)":
  - Grelha CAN com QTableView / QStandardItemModel
  - Fade visual dos bytes inativos (timer 100ms)
  - Cálculo e exibição de Busload (timer 1s)
  - Filtros por ID e Frequência
  - Lista de IDs com checkboxes (visibilidade por linha)
  - Painel do Assistente IA (Em Desenvolvimento)
  - Context menu para anotações (click direito em qualquer célula)

Dependências internas:
  src.delegate.CANItemDelegate
  src.annotations.AnnotationManager
  src.dialogs.CommentDialog

Sinais que o widget espera receber de fora:
  can_thread.frame_received  → process_can_frame(can_id, freq, payload)

Exemplo de uso:
  tab = AnalysisTab(annotation_manager, can_thread_ref)
  main_window.tab_widget.addTab(tab, "Análise (Sniffer)")
"""

import time
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableView, QPushButton,
    QTextEdit, QLabel, QHeaderView, QMenu, QCheckBox, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QMessageBox
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QColor, QAction

from src.delegate import CANItemDelegate
from src.dialogs import CommentDialog


class AnalysisTab(QWidget):
    """Aba de análise ao vivo do barramento CAN."""

    def __init__(self, annotation_manager, can_thread_ref, parent=None):
        super().__init__(parent)
        self.annotation_manager = annotation_manager
        self.can_thread = can_thread_ref

        # Estado
        self.can_database: dict = {}
        self.hide_static = False
        self.display_format = "HEX"
        self.busload_accumulator = 0
        self.current_bitrate = 500000

        self._build_ui()

        # Timers internos
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.apply_fade_effect)
        self.fade_timer.start(100)

        self.busload_timer = QTimer()
        self.busload_timer.timeout.connect(self.update_busload)
        self.busload_timer.start(1000)

        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_statics)
        self.cleanup_timer.start(1000)

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        # --- PAINEL ESQUERDO ---
        left_layout = QVBoxLayout()

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

        # Filtros
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

        # Tabela
        self.table_view = QTableView()
        self.table_model = QStandardItemModel(0, 10)
        self.table_model.setHorizontalHeaderLabels(
            ["ID CAN", "Freq (Hz)", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"]
        )
        self.table_view.setModel(self.table_model)
        self.table_view.setItemDelegate(CANItemDelegate(self.table_view))
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        left_layout.addWidget(self.table_view)

        # --- PAINEL DIREITO ---
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

        lbl_ia = QLabel("Assistente IA / Log (Em Desenvolvimento)")
        lbl_ia.setStyleSheet("color: #a1a1aa; font-weight: bold; margin-top: 10px;")
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)

        right_layout.addWidget(lbl_ia)
        right_layout.addWidget(self.txt_log, 1)

        main_layout.addLayout(left_layout, 7)
        main_layout.addLayout(right_layout, 3)

    # ------------------------------------------------------------------
    # Slots de dados CAN
    # ------------------------------------------------------------------
    @pyqtSlot(int, float, list)
    def process_can_frame(self, can_id: int, frequency: float, payload: list):
        bits = (44 + 8 * len(payload)) * 1.2
        self.busload_accumulator += bits

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
            tt_id = self.annotation_manager.get_tooltip_for_id(hex_id)
            if tt_id:
                item_id.setData(True, Qt.ItemDataRole.UserRole + 1)
                item_id.setToolTip(tt_id)

            row_items = [item_id, QStandardItem(f"{frequency:.1f}")]
            for i, b in enumerate(payload):
                item = QStandardItem(f"{b:02X}" if self.display_format == "HEX" else f"{b:08b}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(f"{b:08b}", Qt.ItemDataRole.UserRole)

                has_any, mask, has_byte = self.annotation_manager.get_annotation_info(hex_id, i)
                if has_any:
                    item.setData(True, Qt.ItemDataRole.UserRole + 1)
                    item.setData(mask, Qt.ItemDataRole.UserRole + 3)
                    item.setData(has_byte, Qt.ItemDataRole.UserRole + 4)
                    item.setToolTip(self.annotation_manager.get_tooltip_for_byte(hex_id, i))

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
                item = QStandardItem(f"{payload[i]:02X}" if self.display_format == "HEX" else f"{payload[i]:08b}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(f"{payload[i]:08b}", Qt.ItemDataRole.UserRole)
                self.table_model.setItem(row_idx, i + 2, item)

            if db_entry["last_payload"][i] != payload[i]:
                item.setText(f"{payload[i]:02X}" if self.display_format == "HEX" else f"{payload[i]:08b}")
                item.setData(f"{db_entry['last_payload'][i]:08b}", Qt.ItemDataRole.UserRole)
                db_entry["last_change_time"][i] = current_time
                db_entry["last_payload"][i] = payload[i]
                item.setBackground(QColor("#1e3a8a"))
                item.setForeground(QColor("#ffffff"))

        db_entry["is_static"] = (current_time - max(db_entry["last_change_time"])) > 5.0
        self.update_row_visibility(hex_id)

    # ------------------------------------------------------------------
    # Timers internos
    # ------------------------------------------------------------------
    @pyqtSlot()
    def apply_fade_effect(self):
        current_time = time.time()
        fade_enabled = self.chk_fade.isChecked()
        for hex_id, info in self.can_database.items():
            row_idx = info["row_index"]
            for i in range(len(info["last_payload"])):
                item = self.table_model.item(row_idx, i + 2)
                if item is None:
                    continue
                elapsed = current_time - info["last_change_time"][i]
                if elapsed > 1.0:
                    if fade_enabled:
                        item.setBackground(QColor("#1a1a1e"))
                        item.setForeground(QColor("#69697a"))
                    else:
                        item.setData(None, Qt.ItemDataRole.BackgroundRole)
                        item.setData(None, Qt.ItemDataRole.ForegroundRole)
                    item.setData(f"{info['last_payload'][i]:08b}", Qt.ItemDataRole.UserRole)
                elif elapsed > 0.3:
                    if fade_enabled:
                        item.setBackground(QColor("#1f2937"))
                        item.setForeground(QColor("#a1a1aa"))
                    else:
                        item.setData(None, Qt.ItemDataRole.BackgroundRole)
                        item.setData(None, Qt.ItemDataRole.ForegroundRole)

    @pyqtSlot()
    def update_busload(self):
        if self.current_bitrate > 0 and self.can_thread and self.can_thread.isRunning() \
                and self.can_thread.mode != "IDLE":
            load_pct = min((self.busload_accumulator / self.current_bitrate) * 100.0, 100.0)
            self.lbl_busload.setText(f"Busload: {load_pct:.1f}%")
            if load_pct < 50:
                color = "#10b981"
            elif load_pct < 80:
                color = "#f59e0b"
            else:
                color = "#e83f5b"
            self.lbl_busload.setStyleSheet(f"color: {color}; font-weight: bold; margin-left: 20px;")
        else:
            self.lbl_busload.setText("Busload: ---%")
            self.lbl_busload.setStyleSheet("color: #69697a; font-weight: bold; margin-left: 20px;")
        self.busload_accumulator = 0

    @pyqtSlot()
    def cleanup_statics(self):
        current_time = time.time()
        for hex_id, info in self.can_database.items():
            if not info["is_static"]:
                if (current_time - max(info["last_change_time"])) > 5.0:
                    info["is_static"] = True
                    self.update_row_visibility(hex_id)

    # ------------------------------------------------------------------
    # Filtros e visibilidade
    # ------------------------------------------------------------------
    @pyqtSlot()
    def apply_filters(self):
        for hex_id in self.can_database.keys():
            self.update_row_visibility(hex_id)

    def update_row_visibility(self, hex_id: str):
        info = self.can_database.get(hex_id)
        if not info:
            return
        row_idx = info["row_index"]

        if info["list_item"].checkState() == Qt.CheckState.Unchecked:
            self.table_view.setRowHidden(row_idx, True)
            return

        if self.hide_static and info["is_static"]:
            self.table_view.setRowHidden(row_idx, True)
            return

        filter_id = self.txt_filter_id.text().strip().upper()
        if filter_id and filter_id not in hex_id.upper():
            self.table_view.setRowHidden(row_idx, True)
            return

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

    # ------------------------------------------------------------------
    # Formato de exibição
    # ------------------------------------------------------------------
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
            for i in range(len(payload)):
                item = self.table_model.item(row_idx, i + 2)
                if item:
                    item.setText(f"{payload[i]:02X}" if self.display_format == "HEX" else f"{payload[i]:08b}")

    # ------------------------------------------------------------------
    # Context menu e anotações
    # ------------------------------------------------------------------
    def show_context_menu(self, pos: QPoint):
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        row = index.row()
        col = index.column()

        id_item = self.table_model.item(row, 0)
        if not id_item:
            return
        can_id = id_item.text()

        target = f"ID {can_id}"
        if col >= 2:
            byte_idx = col - 2
            target = f"ID {can_id} - Byte {byte_idx}"
            if self.display_format == "BIN":
                cell_rect = self.table_view.visualRect(index)
                rel_x = pos.x() - cell_rect.x()
                width = cell_rect.width()
                bit_idx = max(0, min(7, int((rel_x / width) * 8)))
                target += f" - Bit {7 - bit_idx}"

        menu = QMenu()
        action_comment = QAction(f"Adicionar Comentário em {target}...", self)
        action_comment.triggered.connect(lambda: self.add_comment(can_id, target, index))
        menu.addAction(action_comment)
        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def add_comment(self, can_id: str, target: str, index):
        dialog = CommentDialog(self, target)
        if dialog.exec():
            text = dialog.get_text()
            if text:
                try:
                    self.annotation_manager.add_comment(target, text)

                    item = self.table_model.itemFromIndex(index)
                    if item:
                        if "Byte" in target or "Bit" in target:
                            byte_idx = index.column() - 2
                            has_any, mask, has_byte = self.annotation_manager.get_annotation_info(can_id, byte_idx)
                            item.setData(True, Qt.ItemDataRole.UserRole + 1)
                            item.setData(mask, Qt.ItemDataRole.UserRole + 3)
                            item.setData(has_byte, Qt.ItemDataRole.UserRole + 4)
                            item.setToolTip(self.annotation_manager.get_tooltip_for_byte(can_id, byte_idx))
                        else:
                            item.setData(True, Qt.ItemDataRole.UserRole + 1)
                            item.setToolTip(self.annotation_manager.get_tooltip_for_id(can_id))
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível salvar arquivo:\n{e}")

    def clear_data(self):
        """Limpa o banco de dados e a tabela ao reconectar."""
        self.can_database.clear()
        self.table_model.removeRows(0, self.table_model.rowCount())
        self.list_ids.clear()
