"""
transmit_tab.py — Widget da Aba de Transmissão

Responsabilidade: UI e lógica para enviar frames CAN manualmente.

Seções:
  1. Disparo Único (Single Shot)
     - Campos: ID (HEX), Formato (HEX/BIN), Dados
     - Botão: Transmitir Pulso

  2. Transmissão Periódica (Cíclica)
     - Campos: ID, Formato, Dados, Frequência (Hz)
     - Tabela com colunas: ID, Dados, Freq (Hz), Status, Ações
     - Ações por linha: Pausar/Retomar (laranja→azul) + Excluir (vermelho)
     - Botões globais: Iniciar Cíclicos / Parar Todos

Dependências:
  can_thread_ref.send_message(can_id: int, data: list[int])
  can_thread_ref.mode  (str: "IDLE" | "SIMULATED" | "HARDWARE" | "PLAYBACK")

Conversão de frequência:
  O usuário digita em Hz. Internamente converte para ms: interval_ms = 1000 / hz
"""

import time
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox
)
from PyQt6.QtGui import QColor


class TransmitTab(QWidget):
    """Aba de transmissão de frames CAN (single-shot e periódico)."""

    def __init__(self, can_thread_ref, parent=None):
        super().__init__(parent)
        self.can_thread = can_thread_ref
        self.periodic_timers: dict[str, QTimer] = {}
        self._build_ui()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        # --- SINGLE SHOT ---
        lbl_single = QLabel("Disparo Único (Single Shot)")
        lbl_single.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 14px;")
        layout.addWidget(lbl_single)

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
        layout.addLayout(form_single)

        # --- PERIODIC ---
        lbl_periodic = QLabel("Transmissão Periódica (Cíclica)")
        lbl_periodic.setStyleSheet("color: #a1a1aa; font-weight: bold; font-size: 14px; margin-top: 20px;")
        layout.addWidget(lbl_periodic)

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
        layout.addLayout(form_periodic)

        self.tbl_periodic = QTableWidget(0, 5)
        self.tbl_periodic.setHorizontalHeaderLabels(["ID (HEX)", "Dados", "Freq (Hz)", "Status", "Ações"])
        self.tbl_periodic.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tbl_periodic, 1)

        btn_layout_per = QHBoxLayout()
        self.btn_start_all = QPushButton("▶️ Iniciar Cíclicos")
        self.btn_start_all.setStyleSheet("background-color: #10b981; color: white; padding: 8px; font-weight: bold;")
        self.btn_start_all.clicked.connect(self.start_all_periodic)

        self.btn_stop_all = QPushButton("⏹ Parar Todos")
        self.btn_stop_all.setStyleSheet("background-color: #e83f5b; color: white; padding: 8px; font-weight: bold;")
        self.btn_stop_all.clicked.connect(self.stop_all_periodic)

        btn_layout_per.addWidget(self.btn_start_all)
        btn_layout_per.addWidget(self.btn_stop_all)
        layout.addLayout(btn_layout_per)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def parse_payload(self, text: str, format_type: str) -> list:
        parts = text.strip().split()
        return [int(p, 16) if format_type == "HEX" else int(p, 2) for p in parts]

    def _check_connected(self) -> bool:
        if self.can_thread.mode == "IDLE":
            QMessageBox.warning(self, "Aviso", "Conecte-se ao barramento primeiro.")
            return False
        return True

    # ------------------------------------------------------------------
    # Single Shot
    # ------------------------------------------------------------------
    def send_single_shot(self):
        if not self._check_connected():
            return
        try:
            can_id = int(self.txt_single_id.text().strip(), 16)
            data = self.parse_payload(self.txt_single_data.text(), self.cb_single_format.currentText())
            self.can_thread.send_message(can_id, data)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Formato inválido:\n{e}")

    # ------------------------------------------------------------------
    # Tarefas periódicas
    # ------------------------------------------------------------------
    def add_periodic_task(self):
        try:
            can_id_str = self.txt_per_id.text().strip()
            data_str = self.txt_per_data.text().strip()
            hz = float(self.txt_per_freq.text().strip())
            if hz <= 0:
                raise ValueError("Frequência deve ser maior que zero.")
            fmt = self.cb_per_format.currentText()

            int(can_id_str, 16)       # valida HEX
            self.parse_payload(data_str, fmt)  # valida dados

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

    def remove_periodic_task(self, task_id: str):
        if task_id in self.periodic_timers:
            self.periodic_timers[task_id].stop()
            del self.periodic_timers[task_id]

        row_idx = -1
        for r in range(self.tbl_periodic.rowCount()):
            item = self.tbl_periodic.item(r, 0)
            if item and item.data(Qt.ItemDataRole.UserRole + 2) == task_id:
                row_idx = r
                break
        if row_idx >= 0:
            self.tbl_periodic.removeRow(row_idx)

    def export_data(self):
        tasks = []
        for i in range(self.tbl_periodic.rowCount()):
            can_id = self.tbl_periodic.item(i, 0).text()
            data_fmt = self.tbl_periodic.item(i, 1).text()
            fmt = self.tbl_periodic.item(i, 1).data(Qt.ItemDataRole.UserRole)
            freq = self.tbl_periodic.item(i, 2).text().replace(" Hz", "")
            
            tasks.append({
                "can_id": can_id,
                "data": data_fmt,
                "format": fmt,
                "freq": freq
            })
        return tasks

    def import_data(self, tasks: list):
        """Restaura tarefas periódicas a partir de uma lista de dicts exportados."""
        self.stop_all_periodic()
        # Remove todas as linhas existentes
        while self.tbl_periodic.rowCount() > 0:
            self.tbl_periodic.removeRow(0)
        for task in tasks:
            self.txt_per_id.setText(task.get("can_id", ""))
            self.txt_per_data.setText(task.get("data", ""))
            self.txt_per_freq.setText(str(task.get("freq", "10")))
            fmt = task.get("format", "HEX")
            self.cb_per_format.setCurrentText(fmt)
            self.add_periodic_task()

    def toggle_periodic_task(self, task_id: str):
        if task_id not in self.periodic_timers:
            return
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
                    timer.start(int(1000.0 / hz))
                    status_item.setText("Ativo")
                    status_item.setForeground(QColor("#10b981"))
                    btn_pause.setText("Pausar")
                    btn_pause.setStyleSheet("background-color: #f59e0b; color: white; border-radius: 4px; padding: 4px; font-weight: bold;")
                break

    def start_all_periodic(self):
        if not self._check_connected():
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
        for timer in self.periodic_timers.values():
            timer.stop()

        for r in range(self.tbl_periodic.rowCount()):
            item = self.tbl_periodic.item(r, 3)
            if item:
                item.setText("Parado")
                item.setForeground(QColor("white"))
