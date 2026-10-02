"""
widget_template.py — Arquivo Modelo / Boilerplate para Criação de Widgets Customizados no CANweaver.

Como usar:
1. Copie este arquivo ou edite-o como desejar.
2. Adicione seus botões, labels, sliders ou qualquer componente PyQt6 no método `init_ui`.
3. Use `self.send_can(can_id, payload)` para transmitir mensagens CAN.
4. Sobrescreva `on_can_frame(can_id, freq, payload)` para reagir a mensagens recebidas.
5. No CANweaver, clique com botão direito no Canvas da aba Widgets -> 'Inserir Widget Python (.py)'.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QProgressBar, QFrame, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer
from src.custom_widget_api import CustomWidgetBase


class TemplateCustomWidget(CustomWidgetBase):
    # Metadados opcionais para identificação no CANweaver
    WIDGET_NAME = "Modelo de Exemplo"
    WIDGET_DESC = "Template base com botões e recepção CAN"
    DEFAULT_SIZE = (280, 220)

    def init_ui(self):
        """Monta a interface do widget usando componentes do PyQt6."""
        # Estilo do container
        self.setStyleSheet("""
            QWidget {
                color: #e4e4e7;
                font-family: 'Segoe UI', sans-serif;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 1. Título / Cabeçalho
        self.lbl_title = QLabel("Meu Widget Customizado", self)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #60a5fa;")
        layout.addWidget(self.lbl_title)

        # 2. Informação de Status / Recepção CAN
        self.lbl_status = QLabel("Aguardando frame CAN...", self)
        self.lbl_status.setStyleSheet("background-color: #27272a; padding: 6px; border-radius: 4px; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # 3. Barra de Progresso ou Medidor
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #18181b;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 4. Linha de Botões
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        self.btn_send_a = QPushButton("Disparar 0x100", self)
        self.btn_send_a.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                padding: 6px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:pressed { background-color: #1d4ed8; }
        """)
        self.btn_send_a.clicked.connect(self.on_click_send_a)
        btn_layout.addWidget(self.btn_send_a)

        self.btn_toggle = QPushButton("Ciclo (1 Hz): OFF", self)
        self.btn_toggle.setCheckable(True)
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #3f3f46;
                color: white;
                padding: 6px 10px;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #10b981;
                font-weight: bold;
            }
        """)
        self.btn_toggle.toggled.connect(self.on_toggle_timer)
        btn_layout.addWidget(self.btn_toggle)

        layout.addLayout(btn_layout)

        # 5. Timer de exemplo para transmissão cíclica opcional
        self.timer_ciclico = QTimer(self)
        self.timer_ciclico.setInterval(1000)  # 1000 ms = 1 Hz
        self.timer_ciclico.timeout.connect(self.on_timer_tick)
        self.counter = 0

    def on_click_send_a(self):
        """Ao clicar no botão, transmite um frame CAN de exemplo (ID 0x100 com payload)."""
        can_id = 0x100
        payload = [0x01, 0x02, 0x03, 0x04, 0x05, 0x00, 0x00, 0x00]
        sucesso = self.send_can(can_id, payload)
        if sucesso:
            self.lbl_status.setText(f"Tx Enviado: ID 0x{can_id:03X} -> {payload[:4]}...")

    def on_toggle_timer(self, checked: bool):
        """Inicia ou para o envio periódico em segundo plano."""
        if checked:
            self.btn_toggle.setText("Ciclo (1 Hz): ON")
            self.timer_ciclico.start()
        else:
            self.btn_toggle.setText("Ciclo (1 Hz): OFF")
            self.timer_ciclico.stop()

    def on_timer_tick(self):
        """Executado a cada 1 segundo quando o ciclo está ativado."""
        self.counter = (self.counter + 1) % 256
        self.send_can(can_id=0x110, payload=[self.counter, 0xAA, 0x55, 0x00])

    def on_can_frame(self, can_id: int, freq: float, payload: list[int]):
        """
        Recebe mensagens do barramento CAN.
        Filtre pelo ID que seu widget precisa monitorar.
        """
        if can_id == 0x100 or can_id == 0x110:
            val = payload[0] if len(payload) > 0 else 0
            self.progress_bar.setValue(int((val / 255.0) * 100))
            hex_data = " ".join(f"{b:02X}" for b in payload)
            self.lbl_status.setText(f"Rx [0x{can_id:03X}]: {hex_data} ({freq:.1f} Hz)")

    def get_custom_config(self) -> dict:
        """Salva o estado do botão cíclico no arquivo do projeto."""
        return {"ciclo_ativo": self.btn_toggle.isChecked()}

    def set_custom_config(self, config: dict):
        """Restaura o estado quando o projeto for reaberto."""
        if config.get("ciclo_ativo"):
            self.btn_toggle.setChecked(True)

    def on_close(self):
        """Limpeza ao fechar: garante que o timer pare."""
        if hasattr(self, "timer_ciclico"):
            self.timer_ciclico.stop()
