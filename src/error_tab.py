"""
error_tab.py — Widget da Aba de Error Frames CAN

Responsabilidade: exibir os error frames recebidos do barramento (is_error_frame=True)
em uma tabela dedicada, separados da aba de Análise.

Colunas: Timestamp | ID (HEX) | Tipo de Erro | Descrição

Conectar ao sinal:
    can_thread.error_frame_received.connect(error_tab.add_error_frame)
"""

from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)
from PyQt6.QtGui import QColor

# Máximo de linhas mantidas na tabela para não crescer infinitamente
MAX_ROWS = 500

# Mapeamento de tipo de erro → cor de destaque
_ERROR_COLORS = {
    "Bus-Off":           QColor("#7f1d1d"),   # vermelho escuro
    "No ACK":            QColor("#7c2d12"),   # laranja escuro
    "TX Timeout":        QColor("#78350f"),   # âmbar escuro
    "Lost Arbitration":  QColor("#1e3a5f"),   # azul escuro
    "Controller Error":  QColor("#4a1d96"),   # roxo escuro
    "Protocol Violation":QColor("#6b21a8"),   # roxo médio
    "Transceiver Error": QColor("#14532d"),   # verde escuro
    "Bus Error":         QColor("#7f1d1d"),   # vermelho escuro
    "Bus Restarted":     QColor("#1e3a8a"),   # azul (informativo)
}
_DEFAULT_ERROR_COLOR = QColor("#3f3f46")  # cinza


class ErrorTab(QWidget):
    """Aba dedicada à exibição de error frames CAN."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._error_count = 0
        self._build_ui()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # ── Cabeçalho ────────────────────────────────────────────────
        header_layout = QHBoxLayout()

        lbl_title = QLabel("⚠️  Error Frames CAN")
        lbl_title.setStyleSheet(
            "color: #f59e0b; font-weight: bold; font-size: 15px;"
        )

        lbl_info = QLabel(
            "Error frames são gerados pelo SocketCAN quando há falhas físicas no barramento "
            "(desconexão, Bus-Off, ausência de ACK etc.). Eles não são frames CAN reais dos nós."
        )
        lbl_info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        lbl_info.setWordWrap(True)

        header_layout.addWidget(lbl_title)
        layout.addLayout(header_layout)
        layout.addWidget(lbl_info)

        # ── Barra de controle ─────────────────────────────────────────
        bar_layout = QHBoxLayout()

        self.lbl_count = QLabel("Total de erros: 0")
        self.lbl_count.setStyleSheet("color: #e83f5b; font-weight: bold; font-size: 12px;")

        self.btn_clear = QPushButton("🧹  Limpar")
        self.btn_clear.setToolTip("Remove todos os erros da tabela e zera o contador")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #3f3f46; color: white; padding: 5px 14px;"
            " border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background-color: #52525b; }"
        )
        self.btn_clear.clicked.connect(self.clear_errors)

        bar_layout.addWidget(self.lbl_count)
        bar_layout.addStretch()
        bar_layout.addWidget(self.btn_clear)
        layout.addLayout(bar_layout)

        # ── Tabela ────────────────────────────────────────────────────
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "ID (HEX)", "Tipo de Erro", "Descrição"]
        )

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget { gridline-color: #27272a; }"
            "QTableWidget::item { padding: 4px 8px; }"
        )

        layout.addWidget(self.table, 1)

    # ------------------------------------------------------------------
    # Slot público
    # ------------------------------------------------------------------
    @pyqtSlot(int, str, str)
    def add_error_frame(self, can_id: int, error_type: str, description: str):
        """Recebe um error frame e adiciona ao topo da tabela."""
        self._error_count += 1
        self.lbl_count.setText(f"Total de erros: {self._error_count}")

        # Limitar tamanho: remove linha mais antiga (última) quando passar do limite
        if self.table.rowCount() >= MAX_ROWS:
            self.table.removeRow(self.table.rowCount() - 1)

        # Inserir no topo (índice 0)
        self.table.insertRow(0)

        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        id_hex = f"{can_id:03X}"
        color = _ERROR_COLORS.get(error_type, _DEFAULT_ERROR_COLOR)

        values = [ts, id_hex, error_type, description]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            item.setBackground(color)
            item.setForeground(QColor("#f4f4f5"))
            if col == 2:
                item.setFont(item.font())
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(0, col, item)

    # ------------------------------------------------------------------
    # Limpeza
    # ------------------------------------------------------------------
    @pyqtSlot()
    def clear_errors(self):
        """Remove todas as linhas e reseta o contador."""
        self.table.setRowCount(0)
        self._error_count = 0
        self.lbl_count.setText("Total de erros: 0")
