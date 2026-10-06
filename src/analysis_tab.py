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
from __future__ import annotations

import os
import csv
import time
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTableView, QPushButton,
    QTextEdit, QLabel, QHeaderView, QMenu, QCheckBox, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QMessageBox, QAbstractItemView,
    QFileDialog, QApplication
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
        self.lbl_format = QLabel("Exibição:")
        self.lbl_format.setStyleSheet("color: #a1a1aa; font-weight: bold;")

        self.cb_format = QComboBox()
        self.cb_format.addItems(["HEX", "BIN", "DEC"])
        self.cb_format.setToolTip("Selecionar formato de exibição dos bytes na tabela (HEX, BIN ou DEC)")
        self.cb_format.setStyleSheet(
            "QComboBox { background-color: #2e3035; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; border: 1px solid #3f3f46; }"
            "QComboBox::drop-down { border: none; width: 18px; }"
            "QComboBox QAbstractItemView { background-color: #202024; color: white; selection-background-color: #1e3a8a; }"
        )
        self.cb_format.currentTextChanged.connect(self.set_display_format)
        self.btn_format = self.cb_format

        self.chk_hide_static = QCheckBox("Ocultar Estáticos")
        self.chk_hide_static.setStyleSheet("color: white;")
        self.chk_hide_static.stateChanged.connect(self.toggle_static_filter)

        self.chk_fade = QCheckBox("Fade Inativos")
        self.chk_fade.setChecked(True)
        self.chk_fade.setStyleSheet("color: white;")

        self.chk_highlight_changes = QCheckBox("Destacar Mudanças")
        self.chk_highlight_changes.setChecked(True)
        self.chk_highlight_changes.setStyleSheet("color: white;")
        self.chk_highlight_changes.setToolTip("Destacar alterações em tempo real (quadradinhos verdes nos bits)")
        self.chk_highlight_changes.stateChanged.connect(self.toggle_highlight_changes)

        self.lbl_busload = QLabel("Busload: ---%")
        self.lbl_busload.setStyleSheet("color: #10b981; font-weight: bold; margin-left: 20px;")

        self.lbl_errors = QLabel("Erros CAN: 0")
        self.lbl_errors.setStyleSheet("color: #e83f5b; font-weight: bold; margin-left: 20px;")

        control_layout.addWidget(self.lbl_format)
        control_layout.addWidget(self.cb_format)
        control_layout.addWidget(self.chk_fade)
        control_layout.addWidget(self.chk_hide_static)
        control_layout.addWidget(self.chk_highlight_changes)
        control_layout.addWidget(self.lbl_busload)
        control_layout.addWidget(self.lbl_errors)
        control_layout.addStretch()
        left_layout.addLayout(control_layout)

        # Filtros
        filter_layout = QHBoxLayout()
        self.txt_filter_id = QLineEdit()
        self.txt_filter_id.setPlaceholderText("Filtrar por ID (ex: 0C0)")
        self.txt_filter_id.setClearButtonEnabled(True)
        self.txt_filter_id.textChanged.connect(self.apply_filters)

        self.cb_freq_op = QComboBox()
        self.cb_freq_op.addItems([">", "<"])
        self.cb_freq_op.currentIndexChanged.connect(self.apply_filters)

        self.txt_filter_freq = QLineEdit()
        self.txt_filter_freq.setPlaceholderText("Freq. Limit (Hz)")
        self.txt_filter_freq.textChanged.connect(self.apply_filters)

        self.btn_export_ids = QPushButton("📄 Exportar IDs (.csv)")
        self.btn_export_ids.setToolTip("Exportar lista de IDs únicos para arquivo CSV (um ID por linha)")
        self.btn_export_ids.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #38bdf8; border: 1px solid #38bdf8; "
            "padding: 5px 12px; border-radius: 4px; font-weight: bold; font-size: 11px; } "
            "QPushButton:hover { background-color: #38bdf8; color: #09090b; } "
            "QPushButton:pressed { background-color: #0284c7; color: white; }"
        )
        self.btn_export_ids.clicked.connect(self.export_unique_ids_csv)

        self.lbl_filtered_count = QLabel("Total: 0 IDs")
        self.lbl_filtered_count.setStyleSheet("color: #94a3b8; font-size: 12px; margin-left: 8px; font-weight: 500;")

        filter_layout.addWidget(QLabel("ID:"))
        filter_layout.addWidget(self.txt_filter_id)
        filter_layout.addWidget(QLabel("Freq:"))
        filter_layout.addWidget(self.cb_freq_op)
        filter_layout.addWidget(self.txt_filter_freq)
        filter_layout.addWidget(self.btn_export_ids)
        filter_layout.addWidget(self.lbl_filtered_count)
        filter_layout.addStretch()
        left_layout.addLayout(filter_layout)

        # Tabela
        self.table_view = QTableView()
        self.table_model = QStandardItemModel(0, 10)
        self.table_model.setHorizontalHeaderLabels(
            ["ID CAN", "Freq (Hz)", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"]
        )
        self.table_view.setModel(self.table_model)
        self.item_delegate = CANItemDelegate(self.table_view)
        self.table_view.setItemDelegate(self.item_delegate)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        left_layout.addWidget(self.table_view)

        # --- PAINEL DIREITO ---
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(10, 10, 10, 10)

        self.lbl_id_filter = QLabel("Visibilidade de IDs (0)")
        id_filter_btns_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Sel. Todos")
        self.btn_select_all.clicked.connect(self.select_all_ids)
        self.btn_deselect_all = QPushButton("Desmarc. Todos")
        self.btn_deselect_all.clicked.connect(self.deselect_all_ids)
        id_filter_btns_layout.addWidget(self.btn_select_all)
        id_filter_btns_layout.addWidget(self.btn_deselect_all)

        self.list_ids = QListWidget()
        self.list_ids.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_ids.customContextMenuRequested.connect(self.show_list_ids_context_menu)
        self.list_ids.itemChanged.connect(self.on_id_checkbox_changed)

        # Barra de pesquisa discreta na parte inferior da lista de IDs
        self.txt_search_list_ids = QLineEdit()
        self.txt_search_list_ids.setPlaceholderText("Filtrar lista de IDs...")
        self.txt_search_list_ids.setStyleSheet(
            "QLineEdit { background-color: #1a1a1e; color: white; border: 1px solid #323238; border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
            "QLineEdit:focus { border: 1px solid #3b82f6; }"
        )
        self.txt_search_list_ids.textChanged.connect(self._filter_list_ids_ui)

        right_layout.addWidget(self.lbl_id_filter)
        right_layout.addLayout(id_filter_btns_layout)
        right_layout.addWidget(self.list_ids, 1)
        right_layout.addWidget(self.txt_search_list_ids)

        main_layout.addLayout(left_layout, 7)
        main_layout.addLayout(right_layout, 3)

    def _filter_list_ids_ui(self, search_text: str):
        """Oculta/exibe itens na listWidget de IDs de acordo com a busca rápida."""
        search_upper = search_text.strip().upper()
        for i in range(self.list_ids.count()):
            item = self.list_ids.item(i)
            hex_id = item.data(Qt.ItemDataRole.UserRole) or item.text()
            if not search_upper or search_upper in str(hex_id).upper() or search_upper in item.text().upper():
                item.setHidden(False)
            else:
                item.setHidden(True)

    # ------------------------------------------------------------------
    # Slots de dados CAN
    # ------------------------------------------------------------------
    @pyqtSlot(int, str, str)
    def on_error_frame(self, can_id: int, error_type: str, description: str):
        if not hasattr(self, '_error_count'):
            self._error_count = 0
        self._error_count += 1
        self.lbl_errors.setText(f"Erros CAN: {self._error_count}")

    def _format_byte(self, val: int) -> str:
        b = val & 0xFF
        if self.display_format == "BIN":
            return f"{b:08b}"
        elif self.display_format == "DEC":
            return f"{b:d}"
        return f"{b:02X}"

    @pyqtSlot(int, float, list)
    def process_can_frame(self, can_id: int, frequency: float, payload: list):
        bits = (44 + 8 * len(payload)) * 1.2
        self.busload_accumulator += bits

        hex_id = f"{can_id:03X}" if can_id <= 0x7FF else f"{can_id:X}"
        current_time = time.time()
        payload_bytes = [b & 0xFF for b in payload]

        if hex_id not in self.can_database:
            list_item = QListWidgetItem(f"[{hex_id}] - 0.0 Hz")
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Checked)
            list_item.setData(Qt.ItemDataRole.UserRole, hex_id)

            self.can_database[hex_id] = {
                "row_index": self.table_model.rowCount(),
                "last_payload": list(payload_bytes),
                "last_change_time": [current_time] * 8,
                "is_static": False,
                "list_item": list_item
            }

            item_id = QStandardItem(hex_id)
            item_id.setEditable(False)
            tt_id = self.annotation_manager.get_tooltip_for_id(hex_id)
            if tt_id:
                item_id.setData(True, Qt.ItemDataRole.UserRole + 1)
                item_id.setToolTip(tt_id)

            item_freq = QStandardItem(f"{frequency:.1f}")
            item_freq.setEditable(False)
            row_items = [item_id, item_freq]
            has_any_annot_in_row = bool(tt_id)

            for i, b in enumerate(payload_bytes):
                item = QStandardItem(self._format_byte(b))
                item.setEditable(False)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(f"{b:08b}", Qt.ItemDataRole.UserRole)

                has_any, mask, has_byte = self.annotation_manager.get_annotation_info(hex_id, i)
                if has_any:
                    has_any_annot_in_row = True
                    item.setData(True, Qt.ItemDataRole.UserRole + 1)
                    item.setData(mask, Qt.ItemDataRole.UserRole + 3)
                    item.setData(has_byte, Qt.ItemDataRole.UserRole + 4)
                    item.setToolTip(self.annotation_manager.get_tooltip_for_byte(hex_id, i))

                row_items.append(item)

            if has_any_annot_in_row:
                list_item.setToolTip(tt_id or f"ID [{hex_id}] contém anotações nos bytes.")
                list_item.setForeground(QColor("#facc15"))

            self.list_ids.addItem(list_item)
            self.table_model.appendRow(row_items)
            self.update_row_visibility(hex_id)
            self._update_id_counts()
            return

        db_entry = self.can_database[hex_id]
        row_idx = db_entry["row_index"]
        self.table_model.item(row_idx, 1).setText(f"{frequency:.1f}")
        db_entry["list_item"].setText(f"[{hex_id}] - {frequency:.1f} Hz")

        payload_len = len(payload_bytes)
        while len(db_entry["last_payload"]) < payload_len:
            db_entry["last_payload"].append(0)
            db_entry["last_change_time"].append(current_time)

        for i in range(payload_len):
            b_val = payload_bytes[i]
            item = self.table_model.item(row_idx, i + 2)
            if item is None:
                item = QStandardItem(self._format_byte(b_val))
                item.setEditable(False)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setData(f"{b_val:08b}", Qt.ItemDataRole.UserRole)
                self.table_model.setItem(row_idx, i + 2, item)

            if db_entry["last_payload"][i] != b_val:
                item.setText(self._format_byte(b_val))
                item.setData(f"{db_entry['last_payload'][i]:08b}", Qt.ItemDataRole.UserRole)
                db_entry["last_change_time"][i] = current_time
                db_entry["last_payload"][i] = b_val
                if self.chk_highlight_changes.isChecked():
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
        self._update_id_counts()

    def apply_id_filter(self, filter_text: str):
        """Aplica filtro de texto no ID do sniffer programaticamente."""
        self.txt_filter_id.setText(filter_text)

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
        self._update_id_counts()

    @pyqtSlot()
    def toggle_highlight_changes(self):
        enabled = self.chk_highlight_changes.isChecked()
        if hasattr(self, "item_delegate") and self.item_delegate:
            self.item_delegate.set_highlight_changes(enabled)
        if not enabled:
            for hex_id, info in self.can_database.items():
                row_idx = info.get("row_index")
                if row_idx is None:
                    continue
                for i in range(len(info.get("last_payload", []))):
                    item = self.table_model.item(row_idx, i + 2)
                    if item:
                        bg = item.background()
                        if bg and bg.color().name() == "#1e3a8a":
                            item.setData(None, Qt.ItemDataRole.BackgroundRole)
                            item.setData(None, Qt.ItemDataRole.ForegroundRole)
        self.table_view.viewport().update()

    @pyqtSlot()
    def select_all_ids(self):
        self.list_ids.blockSignals(True)
        for i in range(self.list_ids.count()):
            self.list_ids.item(i).setCheckState(Qt.CheckState.Checked)
        self.list_ids.blockSignals(False)
        self.apply_filters()

    @pyqtSlot()
    def deselect_all_ids(self):
        self.list_ids.blockSignals(True)
        for i in range(self.list_ids.count()):
            self.list_ids.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.list_ids.blockSignals(False)
        self.apply_filters()

    @pyqtSlot(QListWidgetItem)
    def on_id_checkbox_changed(self, item):
        hex_id = item.data(Qt.ItemDataRole.UserRole)
        self.update_row_visibility(hex_id)
        self._update_id_counts()

    # ------------------------------------------------------------------
    # Formato de exibição
    # ------------------------------------------------------------------
    @pyqtSlot(str)
    def set_display_format(self, format_name: str):
        format_name = str(format_name).upper()
        if format_name not in ("HEX", "BIN", "DEC"):
            format_name = "HEX"
        self.display_format = format_name

        if hasattr(self, "cb_format") and self.cb_format.currentText() != self.display_format:
            self.cb_format.blockSignals(True)
            self.cb_format.setCurrentText(self.display_format)
            self.cb_format.blockSignals(False)

        for hex_id, info in self.can_database.items():
            row_idx = info.get("row_index")
            if row_idx is None:
                continue
            payload = info.get("last_payload", [])
            for i in range(len(payload)):
                item = self.table_model.item(row_idx, i + 2)
                if item:
                    item.setText(self._format_byte(payload[i]))
        self.table_view.viewport().update()

    @pyqtSlot()
    def toggle_display_format(self):
        order = ["HEX", "BIN", "DEC"]
        cur_idx = order.index(self.display_format) if self.display_format in order else 0
        next_format = order[(cur_idx + 1) % len(order)]
        self.set_display_format(next_format)

    # ------------------------------------------------------------------
    # Context menu, Cópia, Filtro e Anotações
    # ------------------------------------------------------------------
    def copy_id_to_clipboard(self, hex_id: str):
        """Copia o ID CAN para a área de transferência."""
        QApplication.clipboard().setText(hex_id)

    def copy_id_with_data_to_clipboard(self, hex_id: str):
        """Copia o ID CAN junto com os bytes de dados atuais formatados."""
        info = self.can_database.get(hex_id)
        if not info:
            QApplication.clipboard().setText(hex_id)
            return

        payload = info.get("last_payload", [])
        if payload:
            data_str = " ".join(self._format_byte(b) for b in payload)
            text_to_copy = f"{hex_id}  {data_str}"
        else:
            text_to_copy = hex_id

        QApplication.clipboard().setText(text_to_copy)

    def copy_data_to_clipboard(self, hex_id: str):
        """Copia apenas os bytes de dados atuais do ID CAN."""
        info = self.can_database.get(hex_id)
        if not info:
            return

        payload = info.get("last_payload", [])
        if payload:
            data_str = " ".join(self._format_byte(b) for b in payload)
            QApplication.clipboard().setText(data_str)

    def _show_id_actions_menu(self, can_id: str, target: str, global_pos: QPoint, index=None):
        """Cria e exibe o menu de contexto com opções de filtro, cópia e anotação."""
        menu = QMenu(self)

        # 1. Filtro por este ID
        action_filter = QAction(f"🔍 Filtrar por este ID ({can_id})", self)
        action_filter.triggered.connect(lambda: self.apply_id_filter(can_id))
        menu.addAction(action_filter)

        if self.txt_filter_id.text().strip():
            action_clear_filter = QAction("❌ Limpar Filtro de ID", self)
            action_clear_filter.triggered.connect(lambda: self.apply_id_filter(""))
            menu.addAction(action_clear_filter)

        menu.addSeparator()

        # 2. Cópia do ID e Dados
        action_copy_id = QAction(f"📋 Copiar ID ({can_id})", self)
        action_copy_id.triggered.connect(lambda: self.copy_id_to_clipboard(can_id))
        menu.addAction(action_copy_id)

        info = self.can_database.get(can_id, {})
        payload = info.get("last_payload", [])
        if payload:
            data_str = " ".join(self._format_byte(b) for b in payload)
            preview = data_str if len(data_str) <= 24 else data_str[:21] + "..."
            action_copy_with_data = QAction(f"📋 Copiar com Dado Atual ({can_id}  {preview})", self)
            action_copy_with_data.triggered.connect(lambda: self.copy_id_with_data_to_clipboard(can_id))
            menu.addAction(action_copy_with_data)

            action_copy_data = QAction(f"📋 Copiar Apenas Dado Atual ({preview})", self)
            action_copy_data.triggered.connect(lambda: self.copy_data_to_clipboard(can_id))
            menu.addAction(action_copy_data)
        else:
            action_copy_with_data = QAction(f"📋 Copiar com Dado Atual", self)
            action_copy_with_data.triggered.connect(lambda: self.copy_id_with_data_to_clipboard(can_id))
            menu.addAction(action_copy_with_data)

        menu.addSeparator()

        # 3. Comentários / Anotações
        action_comment = QAction(f"💬 Adicionar Comentário em {target}...", self)
        action_comment.triggered.connect(lambda: self.add_comment(can_id, target, index))
        menu.addAction(action_comment)

        menu.exec(global_pos)

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

        self._show_id_actions_menu(can_id, target, self.table_view.viewport().mapToGlobal(pos), index)

    def show_list_ids_context_menu(self, pos: QPoint):
        item = self.list_ids.itemAt(pos)
        if not item:
            return

        hex_id = item.data(Qt.ItemDataRole.UserRole)
        if not hex_id:
            t = item.text()
            if "[" in t and "]" in t:
                hex_id = t.split("[", 1)[1].split("]", 1)[0]
            else:
                hex_id = t.strip()

        if not hex_id:
            return

        target = f"ID {hex_id}"
        self._show_id_actions_menu(hex_id, target, self.list_ids.viewport().mapToGlobal(pos))

    def add_comment(self, can_id: str, target: str, index):
        dialog = CommentDialog(self, target)
        if dialog.exec():
            text = dialog.get_text()
            if text:
                try:
                    self.annotation_manager.add_comment(target, text)
                    self.refresh_annotations()
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Não foi possível salvar arquivo:\n{e}")

    def refresh_annotations(self):
        """Atualiza marcações visuais (bordas amarelas), tooltips e lista para todos os IDs."""
        for hex_id, info in self.can_database.items():
            row_idx = info.get("row_index")
            if row_idx is None or row_idx >= self.table_model.rowCount():
                continue

            # 1. Coluna ID (Coluna 0)
            item_id = self.table_model.item(row_idx, 0)
            tt_id = self.annotation_manager.get_tooltip_for_id(hex_id)
            if item_id:
                item_id.setData(bool(tt_id), Qt.ItemDataRole.UserRole + 1)
                item_id.setToolTip(tt_id or "")

            # 2. Colunas de Bytes (Colunas 2..9)
            payload = info.get("last_payload", [])
            has_any_byte_annot = False
            for i in range(len(payload)):
                item_byte = self.table_model.item(row_idx, i + 2)
                if not item_byte:
                    continue
                has_any, mask, has_byte = self.annotation_manager.get_annotation_info(hex_id, i)
                if has_any:
                    has_any_byte_annot = True
                item_byte.setData(has_any, Qt.ItemDataRole.UserRole + 1)
                item_byte.setData(mask, Qt.ItemDataRole.UserRole + 3)
                item_byte.setData(has_byte, Qt.ItemDataRole.UserRole + 4)
                item_byte.setToolTip(self.annotation_manager.get_tooltip_for_byte(hex_id, i) if has_any else "")

            # 3. Item na lista lateral de IDs (list_ids)
            list_item = info.get("list_item")
            if list_item:
                if tt_id or has_any_byte_annot:
                    list_item.setToolTip(tt_id or f"ID [{hex_id}] contém anotações nos bytes.")
                    list_item.setForeground(QColor("#facc15"))
                else:
                    list_item.setToolTip("")
                    list_item.setForeground(QColor("#f4f4f5"))

        self.table_view.viewport().update()

    def clear_data(self):
        """Limpa o banco de dados e a tabela ao reconectar."""
        self.can_database.clear()
        self.table_model.removeRows(0, self.table_model.rowCount())
        self.list_ids.clear()
        self._error_count = 0
        self.lbl_errors.setText("Erros CAN: 0")
        self._update_id_counts()

    def clear_stale_ids(self, timeout_s: float = 5.0):
        """Remove da tabela os IDs que não receberam frames há mais de timeout_s segundos."""
        current_time = time.time()

        # Identifica quais IDs estão velhos
        stale_ids = [
            hex_id for hex_id, info in self.can_database.items()
            if (current_time - max(info["last_change_time"])) > timeout_s
        ]

        if not stale_ids:
            return 0

        # Ordena pelos índices de linha em ordem DECRESCENTE para remover sem
        # invalidar os índices das linhas anteriores.
        stale_ids.sort(key=lambda h: self.can_database[h]["row_index"], reverse=True)

        for hex_id in stale_ids:
            info = self.can_database.pop(hex_id)
            row_idx = info["row_index"]

            # Remove da tabela
            self.table_model.removeRow(row_idx)

            # Remove do list widget
            for i in range(self.list_ids.count()):
                item = self.list_ids.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == hex_id:
                    self.list_ids.takeItem(i)
                    break

            # Ajusta o row_index dos IDs que ficaram abaixo da linha removida
            for other_info in self.can_database.values():
                if other_info["row_index"] > row_idx:
                    other_info["row_index"] -= 1

        self._update_id_counts()
        return len(stale_ids)

    def _update_id_counts(self):
        """Atualiza os contadores de IDs únicos no barramento e visíveis após filtros."""
        total_unique = len(self.can_database)
        if hasattr(self, "lbl_id_filter"):
            self.lbl_id_filter.setText(f"Visibilidade de IDs ({total_unique})")

        if hasattr(self, "lbl_filtered_count"):
            visible = sum(
                1 for info in self.can_database.values()
                if not self.table_view.isRowHidden(info["row_index"])
            )
            if visible < total_unique:
                self.lbl_filtered_count.setText(f"Exibindo: {visible} de {total_unique} IDs")
            else:
                self.lbl_filtered_count.setText(f"Total: {total_unique} IDs")

    @pyqtSlot()
    def export_unique_ids_csv(self, destination_path: str | None = None, ids_to_export: list[str] | None = None) -> str | None:
        """Exporta lista em CSV com os IDs CAN únicos pulando linha (um ID por linha)."""
        if not self.can_database:
            if not destination_path:
                QMessageBox.information(
                    self, "Exportar IDs", "Nenhum ID CAN detectado no barramento até o momento."
                )
            return None

        all_ids = sorted(self.can_database.keys(), key=lambda x: int(x, 16))
        visible_ids = [
            hex_id for hex_id in all_ids
            if not self.table_view.isRowHidden(self.can_database[hex_id]["row_index"])
        ]

        if ids_to_export is not None:
            target_ids = ids_to_export
        elif destination_path is not None:
            target_ids = visible_ids if visible_ids else all_ids
        else:
            target_ids = all_ids
            # Se houver filtro ativo e nem todos os IDs estiverem visíveis, permite escolher
            if 0 < len(visible_ids) < len(all_ids):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Exportar IDs CAN")
                msg_box.setText(
                    f"Filtro ativo detectado.\n\n"
                    f"• IDs visíveis com filtro: {len(visible_ids)}\n"
                    f"• Total de IDs no barramento: {len(all_ids)}\n\n"
                    f"Quais IDs você deseja exportar para o CSV?"
                )
                btn_visible = msg_box.addButton(f"Apenas Filtrados ({len(visible_ids)})", QMessageBox.ButtonRole.ActionRole)
                btn_all = msg_box.addButton(f"Todos do Barramento ({len(all_ids)})", QMessageBox.ButtonRole.ActionRole)
                btn_cancel = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
                msg_box.setDefaultButton(btn_visible)
                msg_box.exec()

                clicked = msg_box.clickedButton()
                if clicked == btn_cancel:
                    return None
                elif clicked == btn_visible:
                    target_ids = visible_ids
                else:
                    target_ids = all_ids
            elif len(visible_ids) == 0:
                QMessageBox.warning(
                    self, "Exportar IDs", "Nenhum ID corresponde ao filtro atual."
                )
                return None

        file_path = destination_path
        if not file_path:
            default_filename = f"ids_can_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Exportar Lista de IDs (CSV)",
                default_filename,
                "Arquivos CSV (*.csv);;Todos os Arquivos (*)"
            )
            if not file_path:
                return None

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID"])
                for hex_id in target_ids:
                    writer.writerow([hex_id])

            if not destination_path:
                QMessageBox.information(
                    self,
                    "Exportação Concluída",
                    f"Lista com {len(target_ids)} IDs únicos exportada com sucesso para:\n{os.path.basename(file_path)}"
                )
            return file_path
        except Exception as e:
            if not destination_path:
                QMessageBox.critical(
                    self,
                    "Erro ao Exportar",
                    f"Não foi possível salvar o arquivo:\n{e}"
                )
            return None
