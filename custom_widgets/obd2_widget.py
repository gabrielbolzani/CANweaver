"""
obd2_widget.py — Super Scanner OBD-II, Telemetria Avançada, Central de Documentação
e Motor de Engenharia Reversa por Correlação (CAN Signal Finder).

Funcionalidades:
1. Telemetria Completa (Modo 01):
   - Velocidade, RPM, Tensão da Bateria (0x42), Nível de Combustível (0x2F)
   - Consumo Instantâneo (L/h e km/L calculados via MAF 0x10)
   - Temp. Motor (0x05), Temp. Admissão IAT (0x0F), Pressão Coletor MAP (0x0B)
   - Carga do Motor (0x04), Borboleta TPS (0x11), Pressão Combustível Rail (0x23)
   - Avanço de Ignição (0x0E)
2. PID Discovery (0x00, 0x20, 0x40): identifica automaticamente os PIDs suportados pela ECU.
3. Diagnóstico (Modo 03 / Modo 04): Leitura detalhada e limpeza de DTCs.
4. Central de Documentação Integrada: Janela didática com o guia técnico do protocolo CAN OBD-II.
5. Motor de Engenharia Reversa (CAN Signal Finder):
   - Usa o valor OBD-II como "Ground Truth" (Referência Conhecida).
   - Analisa todo o tráfego do barramento proprietário.
   - Calcula correlação estatística de Pearson (8-bit e 16-bit Big/Little Endian)
     para descobrir em qual ID e byte trafega a velocidade, RPM ou TPS do fabricante!
6. Simulação Realista Integrada: Permite testar todas as funções na bancada sem veículo conectado.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QComboBox, QCheckBox, QTabWidget,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QTextBrowser, QScrollArea, QSplitter
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from src.custom_widget_api import CustomWidgetBase


# ==============================================================================
# DIÁLOGO DE DOCUMENTAÇÃO INTEGRADA DO PROTOCOLO OBD-II
# ==============================================================================

class OBD2DocumentationDialog(QDialog):
    """Janela de guia técnico e didático do protocolo OBD-II sobre CAN."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Guia Técnico: Protocolo OBD-II sobre Barramento CAN")
        self.resize(750, 600)
        self.setStyleSheet("""
            QDialog {
                background-color: #18181b;
                color: #e4e4e7;
                font-family: 'Segoe UI', sans-serif;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Cabeçalho
        lbl_title = QLabel("📖 Como Funciona a Comunicação CAN OBD-II (SAE J1979 / ISO 15765-4)", self)
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(lbl_title)

        browser = QTextBrowser(self)
        browser.setStyleSheet("""
            QTextBrowser {
                background-color: #202024;
                color: #d4d4d8;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)

        doc_html = """
        <h3 style="color:#60a5fa;">1. Estrutura de Perguntas e Respostas</h3>
        <p>A comunicação OBD-II no barramento CAN segue o modelo <b>Cliente-Servidor (Request/Response)</b>:</p>
        <ul>
            <li><b>ID de Pergunta (Request Broadcast):</b> <code>0x7DF</code> (ou <code>0x7E0</code> para a ECU do motor diretamente).</li>
            <li><b>ID de Resposta (Response ECU):</b> <code>0x7E8</code> (Motor Principal), <code>0x7E9</code> (Transmissão), até <code>0x7EF</code>.</li>
        </ul>

        <h3 style="color:#60a5fa;">2. Anatomia do Frame CAN (ISO 15765-2 Single Frame)</h3>
        <p>Cada frame CAN possui até 8 bytes. No OBD-II padrão:</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; border-color:#3f3f46; width:100%;">
            <tr style="background-color:#27272a; color:#38bdf8;">
                <th>Byte 0</th><th>Byte 1</th><th>Byte 2</th><th>Byte 3</th><th>Byte 4 a 7</th>
            </tr>
            <tr>
                <td><b>Qtd Bytes Úteis</b><br>(Geralmente <code>0x02</code>)</td>
                <td><b>Modo de Serviço</b><br><code>0x01</code> = Dados Vivos<br><code>0x03</code> = Ler Falhas</td>
                <td><b>PID Solicitado</b><br>Ex: <code>0x0C</code> (RPM)<br><code>0x0D</code> (Velocidade)</td>
                <td><b>Padding</b><br><code>0x55</code> ou <code>0xAA</code></td>
                <td><b>Padding</b><br><code>0x55</code> ou <code>0xAA</code></td>
            </tr>
        </table>

        <h3 style="color:#60a5fa;">3. Anatomia da Resposta da ECU</h3>
        <p>Quando a ECU responde ao Modo 01 no ID <code>0x7E8</code>:</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; border-color:#3f3f46; width:100%;">
            <tr style="background-color:#27272a; color:#4ade80;">
                <th>Byte 0</th><th>Byte 1</th><th>Byte 2</th><th>Byte 3 (A)</th><th>Byte 4 (B)</th><th>Byte 5 a 7</th>
            </tr>
            <tr>
                <td><b>Qtd Bytes</b><br>Ex: <code>0x04</code></td>
                <td><b>Modo + 0x40</b><br><code>0x41</code> (Confirmação)</td>
                <td><b>PID Ecoado</b><br>Ex: <code>0x0C</code></td>
                <td><b>Dado Byte A</b></td>
                <td><b>Dado Byte B</b></td>
                <td>Demais dados ou padding</td>
            </tr>
        </table>

        <h3 style="color:#60a5fa;">4. Fórmulas de Conversão dos Principais Sensores</h3>
        <ul>
            <li><b>RPM do Motor (PID 0x0C):</b> <code>((A * 256) + B) / 4</code> [rpm]</li>
            <li><b>Velocidade (PID 0x0D):</b> <code>A</code> [km/h]</li>
            <li><b>Tensão da Bateria (PID 0x42):</b> <code>((A * 256) + B) / 1000</code> [Volts]</li>
            <li><b>Nível de Combustível (PID 0x2F):</b> <code>(A * 100) / 255</code> [%]</li>
            <li><b>Fluxo de Massa de Ar - MAF (PID 0x10):</b> <code>((A * 256) + B) / 100</code> [g/s]</li>
            <li><b>Consumo Instantâneo (Estequiométrico Gasolina 14.7:1):</b><br>
                <code>Consumo (L/h) = (MAF * 3600) / (14.7 * 740) ≈ MAF * 0.331</code><br>
                <code>Consumo (km/L) = Velocidade / Consumo (L/h)</code></li>
            <li><b>Temperatura do Motor (PID 0x05):</b> <code>A - 40</code> [°C]</li>
            <li><b>Temp. do Ar de Admissão - IAT (PID 0x0F):</b> <code>A - 40</code> [°C]</li>
            <li><b>Pressão Absoluta do Coletor - MAP (PID 0x0B):</b> <code>A</code> [kPa]</li>
            <li><b>Posição da Borboleta - TPS (PID 0x11):</b> <code>(A * 100) / 255</code> [%]</li>
            <li><b>Carga Calculada do Motor - Load (PID 0x04):</b> <code>(A * 100) / 255</code> [%]</li>
            <li><b>Pressão da Linha de Combustível (PID 0x23):</b> <code>((A * 256) + B) * 10</code> [kPa]</li>
        </ul>

        <h3 style="color:#60a5fa;">5. Como Funciona a Engenharia Reversa com "Ground Truth"</h3>
        <p>No barramento interno do veículo, os fabricantes transmitem os dados em IDs proprietários (ex: <code>0x150</code>, <code>0x280</code>). Como essas mensagens não vêm identificadas, usamos o OBD-II como <b>Verdade Absoluta (Ground Truth)</b>:</p>
        <ol>
            <li>O CANweaver interroga a velocidade ou RPM real pelo OBD-II (ex: 45 km/h).</li>
            <li>Simultaneamente, grava todos os bytes de todos os IDs proprietários desconhecidos.</li>
            <li>Calculamos o <b>Coeficiente de Correlação de Pearson</b> entre a curva do OBD-II e as curvas dos bytes proprietários.</li>
            <li>O ID e bytes com correlação próxima de <b>100%</b> revelam exatamente onde o fabricante colocou aquele sinal no barramento interno!</li>
        </ol>
        """
        browser.setHtml(doc_html)
        layout.addWidget(browser)

        btn_close = QPushButton("Entendido (Fechar)", self)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)


# ==============================================================================
# WIDGET PRINCIPAL: OBD2ScannerWidget
# ==============================================================================

class OBD2ScannerWidget(CustomWidgetBase):
    WIDGET_NAME = "Scanner OBD-II Pro"
    WIDGET_DESC = "Telemetria avançada, diagnóstico, documentação e engenharia reversa por correlação"
    DEFAULT_SIZE = (460, 420)

    # Identificadores CAN padrão OBD-II
    OBD_REQUEST_ID = 0x7DF
    OBD_RESP_START = 0x7E8
    OBD_RESP_END   = 0x7EF

    # Catálogo de PIDs Modo 01
    PID_SUPPORTED_1_20  = 0x00
    PID_ENGINE_LOAD     = 0x04
    PID_COOLANT_TEMP    = 0x05
    PID_MAP_PRESSURE    = 0x0B
    PID_ENGINE_RPM      = 0x0C
    PID_VEHICLE_SPEED   = 0x0D
    PID_TIMING_ADVANCE  = 0x0E
    PID_INTAKE_TEMP     = 0x0F
    PID_MAF_AIR_FLOW    = 0x10
    PID_THROTTLE_POS    = 0x11
    PID_SUPPORTED_21_40 = 0x20
    PID_FUEL_RAIL_PRESS = 0x23
    PID_FUEL_LEVEL      = 0x2F
    PID_SUPPORTED_41_60 = 0x40
    PID_BATTERY_VOLT    = 0x42

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                color: #f4f4f5;
                font-family: 'Segoe UI', sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #27272a;
                background-color: #18181b;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #202024;
                color: #a1a1aa;
                padding: 6px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #27272a;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # -------------------------------------------------------------
        # CABEÇALHO COM CONTROLES GLOBAIS E STATUS
        # -------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        self.lbl_title = QLabel("🚘 OBD-II Pro Scanner", self)
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        self.btn_doc = QPushButton("📖 Guia do Protocolo", self)
        self.btn_doc.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #38bdf8;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #38bdf8; color: #18181b; }
        """)
        self.btn_doc.clicked.connect(self._open_documentation)
        header_layout.addWidget(self.btn_doc)

        self.btn_poll = QPushButton("Iniciar Polling", self)
        self.btn_poll.setCheckable(True)
        self.btn_poll.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #2563eb; }
            QPushButton:checked { background-color: #ef4444; }
        """)
        self.btn_poll.toggled.connect(self.toggle_polling)
        header_layout.addWidget(self.btn_poll)

        main_layout.addLayout(header_layout)

        # Barra de status da ECU
        status_bar = QHBoxLayout()
        self.lbl_ecu_status = QLabel("ECU: Offline", self)
        self.lbl_ecu_status.setStyleSheet("font-size: 10px; color: #71717a; font-weight: bold;")
        status_bar.addWidget(self.lbl_ecu_status)

        status_bar.addStretch()

        self.chk_simulate = QCheckBox("Simular ECU na Bancada", self)
        self.chk_simulate.setStyleSheet("font-size: 10px; color: #a1a1aa;")
        self.chk_simulate.setToolTip("Responde às mensagens OBD-II e gera tráfego de fundo para testar o Signal Finder")
        status_bar.addWidget(self.chk_simulate)

        main_layout.addLayout(status_bar)

        # -------------------------------------------------------------
        # ABAS INTERNAS
        # -------------------------------------------------------------
        self.tabs = QTabWidget(self)
        self.tab_dashboard = QWidget()
        self.tab_engine = QWidget()
        self.tab_dtc = QWidget()
        self.tab_reverse = QWidget()

        self.tabs.addTab(self.tab_dashboard, "📊 Painel Geral")
        self.tabs.addTab(self.tab_engine, "⚙️ Motor & Sensores")
        self.tabs.addTab(self.tab_dtc, "⚠️ Diagnóstico (DTC)")
        self.tabs.addTab(self.tab_reverse, "🔍 Signal Finder (Eng. Reversa)")

        self._build_tab_dashboard()
        self._build_tab_engine()
        self._build_tab_dtc()
        self._build_tab_reverse()

        main_layout.addWidget(self.tabs)

        # -------------------------------------------------------------
        # TIMER DE POLLING E CONTROLE DE FLUXO OBD
        # -------------------------------------------------------------
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(80)  # ~12 Hz entre requisições
        self.poll_timer.timeout.connect(self.on_poll_tick)

        # Sequência padrão de PIDs a interrogar
        self.pids_sequence = [
            self.PID_ENGINE_RPM,
            self.PID_VEHICLE_SPEED,
            self.PID_BATTERY_VOLT,
            self.PID_FUEL_LEVEL,
            self.PID_COOLANT_TEMP,
            self.PID_MAF_AIR_FLOW,
            self.PID_ENGINE_LOAD,
            self.PID_THROTTLE_POS,
            self.PID_MAP_PRESSURE,
            self.PID_INTAKE_TEMP,
            self.PID_FUEL_RAIL_PRESS,
            self.PID_TIMING_ADVANCE
        ]
        self.current_seq_idx = 0

        # Armazenamento de valores atuais
        self.val_rpm = 0.0
        self.val_speed = 0.0
        self.val_maf = 0.0
        self.val_battery = 0.0
        self.val_fuel = 0.0
        self.val_temp = 0.0
        self.val_iat = 0.0
        self.val_map = 0.0
        self.val_load = 0.0
        self.val_tps = 0.0
        self.val_rail = 0.0
        self.val_timing = 0.0

        # PIDs suportados descobertos pela ECU
        self.supported_pids = set()

        # -------------------------------------------------------------
        # MOTOR DE ENGENHARIA REVERSA (CAN SIGNAL FINDER)
        # -------------------------------------------------------------
        self.finder_active = False
        self.finder_pairs_8 = defaultdict(lambda: deque(maxlen=60))  # (id, byte_idx) -> [(x, y_ref)]
        self.finder_pairs_16 = defaultdict(lambda: deque(maxlen=60))  # (id, byte_idx, endian) -> [(x, y_ref)]
        self.finder_last_calc_time = 0.0

        # Simulação
        self._sim_t = 0.0
        self._sim_rpm = 850.0
        self._sim_speed = 0.0

    # ==========================================================================
    # CONSTRUÇÃO DAS ABAS
    # ==========================================================================

    def _build_tab_dashboard(self):
        """Aba 1: Mostradores principais de condução e bateria/combustível."""
        layout = QVBoxLayout(self.tab_dashboard)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)

        # 1. RPM
        card_rpm = self._create_metric_card("RPM DO MOTOR", "0 rpm", "#4ade80")
        self.lbl_val_rpm = card_rpm.findChild(QLabel, "val")
        grid.addWidget(card_rpm, 0, 0)

        # 2. Velocidade
        card_spd = self._create_metric_card("VELOCIDADE", "0 km/h", "#60a5fa")
        self.lbl_val_speed = card_spd.findChild(QLabel, "val")
        grid.addWidget(card_spd, 0, 1)

        # 3. Tensão da Bateria
        card_bat = self._create_metric_card("TENSÃO BATERIA (0x42)", "-- V", "#fbbf24")
        self.lbl_val_bat = card_bat.findChild(QLabel, "val")
        grid.addWidget(card_bat, 1, 0)

        # 4. Nível de Combustível
        card_fuel = self._create_metric_card("COMBUSTÍVEL (0x2F)", "-- %", "#a78bfa")
        self.lbl_val_fuel = card_fuel.findChild(QLabel, "val")
        grid.addWidget(card_fuel, 1, 1)

        # 5. Consumo Instantâneo (Calculado)
        card_cons = self._create_metric_card("CONSUMO INSTANTÂNEO", "-- km/L", "#34d399")
        self.lbl_val_cons = card_cons.findChild(QLabel, "val")
        grid.addWidget(card_cons, 2, 0)

        # 6. Temp. Arrefecimento
        card_temp = self._create_metric_card("TEMP. MOTOR (0x05)", "-- °C", "#f87171")
        self.lbl_val_temp = card_temp.findChild(QLabel, "val")
        grid.addWidget(card_temp, 2, 1)

        layout.addLayout(grid)

    def _build_tab_engine(self):
        """Aba 2: Sensores de injeção, admissão e pressão."""
        layout = QVBoxLayout(self.tab_engine)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)

        # MAF
        card_maf = self._create_metric_card("FLUXO DE AR (MAF 0x10)", "-- g/s", "#38bdf8")
        self.lbl_val_maf = card_maf.findChild(QLabel, "val")
        grid.addWidget(card_maf, 0, 0)

        # MAP
        card_map = self._create_metric_card("PRESSÃO COLETOR (MAP 0x0B)", "-- kPa", "#38bdf8")
        self.lbl_val_map = card_map.findChild(QLabel, "val")
        grid.addWidget(card_map, 0, 1)

        # Carga do Motor
        card_load = self._create_metric_card("CARGA MOTOR (LOAD 0x04)", "-- %", "#f472b6")
        self.lbl_val_load = card_load.findChild(QLabel, "val")
        grid.addWidget(card_load, 1, 0)

        # TPS
        card_tps = self._create_metric_card("BORBOLETA (TPS 0x11)", "-- %", "#f472b6")
        self.lbl_val_tps = card_tps.findChild(QLabel, "val")
        grid.addWidget(card_tps, 1, 1)

        # Temp Admissão IAT
        card_iat = self._create_metric_card("TEMP. ADMISSÃO (IAT 0x0F)", "-- °C", "#fb923c")
        self.lbl_val_iat = card_iat.findChild(QLabel, "val")
        grid.addWidget(card_iat, 2, 0)

        # Pressão Rail Combustível
        card_rail = self._create_metric_card("PRESSÃO RAIL (0x23)", "-- kPa", "#fb923c")
        self.lbl_val_rail = card_rail.findChild(QLabel, "val")
        grid.addWidget(card_rail, 2, 1)

        layout.addLayout(grid)

        # Botão para varrer PIDs suportados de fábrica
        btn_disc = QPushButton("🔍 Interrogar PIDs Suportados pela ECU (0x00, 0x20, 0x40)", self.tab_engine)
        btn_disc.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #3b82f6; color: white; }
        """)
        btn_disc.clicked.connect(self.request_supported_pids)
        layout.addWidget(btn_disc)

        self.lbl_supported_info = QLabel("PIDs suportados: Aguardando varredura...", self.tab_engine)
        self.lbl_supported_info.setStyleSheet("font-size: 10px; color: #a1a1aa;")
        layout.addWidget(self.lbl_supported_info)

    def _build_tab_dtc(self):
        """Aba 3: Diagnóstico de Falhas (DTCs) e Reset."""
        layout = QVBoxLayout(self.tab_dtc)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        btn_bar = QHBoxLayout()
        btn_read_dtc = QPushButton("Ler Códigos de Falha (Modo 03)", self.tab_dtc)
        btn_read_dtc.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        btn_read_dtc.clicked.connect(self.request_dtcs)
        btn_bar.addWidget(btn_read_dtc)

        btn_clear_dtc = QPushButton("Limpar Falhas (Modo 04)", self.tab_dtc)
        btn_clear_dtc.setStyleSheet("background-color: #dc2626; color: white; padding: 6px; border-radius: 4px; font-weight: bold;")
        btn_clear_dtc.clicked.connect(self.clear_dtcs)
        btn_bar.addWidget(btn_clear_dtc)

        layout.addLayout(btn_bar)

        self.lbl_dtc_count = QLabel("Nenhuma leitura realizada.", self.tab_dtc)
        self.lbl_dtc_count.setStyleSheet("font-size: 11px; color: #e4e4e7; font-weight: bold;")
        layout.addWidget(self.lbl_dtc_count)

        self.table_dtc = QTableWidget(self.tab_dtc)
        self.table_dtc.setColumnCount(3)
        self.table_dtc.setHorizontalHeaderLabels(["Código DTC", "Sistema", "Descrição Estimada"])
        self.table_dtc.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_dtc.setStyleSheet("""
            QTableWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                color: #e4e4e7;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #202024;
                color: #a1a1aa;
                padding: 4px;
                border: 1px solid #27272a;
            }
        """)
        layout.addWidget(self.table_dtc)

    def _build_tab_reverse(self):
        """Aba 4: CAN Signal Finder — Engenharia reversa estatística usando OBD como Ground Truth."""
        layout = QVBoxLayout(self.tab_reverse)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        info_box = QLabel(
            "Descubra quais mensagens CAN internas do carro contêm Velocidade, RPM ou TPS "
            "comparando o sinal real com o tráfego proprietário desconhecido em tempo real.",
            self.tab_reverse
        )
        info_box.setStyleSheet("font-size: 11px; color: #a1a1aa;")
        info_box.setWordWrap(True)
        layout.addWidget(info_box)

        # Seleção de sinal de referência (Ground Truth)
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Referência OBD-II:", self.tab_reverse))

        self.cb_reference_signal = QComboBox(self.tab_reverse)
        self.cb_reference_signal.addItem("Velocidade do Veículo (PID 0x0D)", "speed")
        self.cb_reference_signal.addItem("RPM do Motor (PID 0x0C)", "rpm")
        self.cb_reference_signal.addItem("Posição Borboleta - TPS (PID 0x11)", "tps")
        self.cb_reference_signal.setStyleSheet("""
            QComboBox {
                background-color: #27272a;
                color: white;
                border: 1px solid #3f3f46;
                padding: 4px;
                border-radius: 4px;
            }
        """)
        ctrl_layout.addWidget(self.cb_reference_signal)

        self.btn_toggle_finder = QPushButton("Iniciar Varredura & Correlação", self.tab_reverse)
        self.btn_toggle_finder.setCheckable(True)
        self.btn_toggle_finder.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:checked { background-color: #ef4444; }
        """)
        self.btn_toggle_finder.toggled.connect(self.toggle_signal_finder)
        ctrl_layout.addWidget(self.btn_toggle_finder)

        layout.addLayout(ctrl_layout)

        # Status da correlação
        self.lbl_finder_status = QLabel("Status: Parado. Acelere ou ande com o veículo após iniciar.", self.tab_reverse)
        self.lbl_finder_status.setStyleSheet("font-size: 10px; color: #facc15; font-weight: bold;")
        layout.addWidget(self.lbl_finder_status)

        # Tabela de Melhores Candidatos Encontrados
        self.table_candidates = QTableWidget(self.tab_reverse)
        self.table_candidates.setColumnCount(5)
        self.table_candidates.setHorizontalHeaderLabels([
            "ID CAN Candidato", "Localização (Bytes)", "Formato", "Correlação (r)", "Escala Estimada"
        ])
        self.table_candidates.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_candidates.setStyleSheet("""
            QTableWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                color: #e4e4e7;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #202024;
                color: #a1a1aa;
                padding: 4px;
                border: 1px solid #27272a;
            }
        """)
        layout.addWidget(self.table_candidates)

    def _create_metric_card(self, title: str, default_val: str, color_hex: str) -> QFrame:
        """Cria um card visual padronizado para uma métrica."""
        frame = QFrame(self)
        frame.setStyleSheet("""
            QFrame {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(6, 4, 6, 4)
        vbox.setSpacing(2)

        lbl_t = QLabel(title, frame)
        lbl_t.setStyleSheet("font-size: 9px; color: #a1a1aa; font-weight: bold;")
        vbox.addWidget(lbl_t)

        lbl_v = QLabel(default_val, frame)
        lbl_v.setObjectName("val")
        lbl_v.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color_hex};")
        lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight)
        vbox.addWidget(lbl_v)

        return frame

    def _open_documentation(self):
        """Abre a janela de guia técnico interativo."""
        dlg = OBD2DocumentationDialog(self)
        dlg.exec()

    # ==========================================================================
    # FLUXO DE TRANSMISSÃO E RECEPÇÃO CAN OBD-II
    # ==========================================================================

    def toggle_polling(self, checked: bool):
        if checked:
            self.btn_poll.setText("Parar Polling")
            self.poll_timer.start()
        else:
            self.btn_poll.setText("Iniciar Polling")
            self.poll_timer.stop()
            self.lbl_ecu_status.setText("ECU: Pausado")
            self.lbl_ecu_status.setStyleSheet("font-size: 10px; color: #71717a; font-weight: bold;")

    def on_poll_tick(self):
        """Dispara a próxima requisição OBD-II cíclica."""
        pid = self.pids_sequence[self.current_seq_idx]
        self.current_seq_idx = (self.current_seq_idx + 1) % len(self.pids_sequence)

        # ISO 15765-2 Single Frame: [len=2, Mode=0x01, PID, padding...]
        req = [0x02, 0x01, pid, 0x55, 0x55, 0x55, 0x55, 0x55]
        self.send_can(self.OBD_REQUEST_ID, req)

        # Se simulação estiver ativada, gera respostas automáticas
        if self.chk_simulate.isChecked():
            self._handle_simulated_cycle(pid)

    def request_supported_pids(self):
        """Consulta os PIDs suportados (0x00, 0x20, 0x40)."""
        self.send_can(self.OBD_REQUEST_ID, [0x02, 0x01, self.PID_SUPPORTED_1_20, 0x55, 0x55, 0x55, 0x55, 0x55])
        self.lbl_supported_info.setText("Solicitando PIDs suportados da ECU...")

        if self.chk_simulate.isChecked():
            # Simula suporte aos PIDs comuns (RPM, Speed, Load, Temp, MAP, MAF, TPS, Volt, Fuel)
            # 0xBE 0x3E 0xB8 0x11
            self.on_can_frame(0x7E8, 10.0, [0x06, 0x41, 0x00, 0xBE, 0x3E, 0xB8, 0x11, 0x00])

    def request_dtcs(self):
        """Envia solicitação do Modo 03 (Request Trouble Codes)."""
        self.send_can(self.OBD_REQUEST_ID, [0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.lbl_dtc_count.setText("Solicitando DTCs ao barramento...")

        if self.chk_simulate.isChecked():
            # Simula códigos P0300 e P0171
            self.on_can_frame(0x7E8, 10.0, [0x04, 0x43, 0x03, 0x00, 0x01, 0x71, 0x00, 0x00])

    def clear_dtcs(self):
        """Envia solicitação do Modo 04 (Clear Trouble Codes / Reset MIL)."""
        self.send_can(self.OBD_REQUEST_ID, [0x01, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.table_dtc.setRowCount(0)
        self.lbl_dtc_count.setText("Comando de reset enviado (Modo 04).")

    def on_can_frame(self, can_id: int, freq: float, payload: list[int]):
        """
        Recebe mensagens do barramento CAN.
        Decodifica respostas OBD-II (0x7E8..0x7EF) e alimenta o Signal Finder com o tráfego proprietário.
        """
        # 1. Trata respostas OBD-II
        if self.OBD_RESP_START <= can_id <= self.OBD_RESP_END:
            if len(payload) >= 2:
                self.lbl_ecu_status.setText(f"ECU: 0x{can_id:03X} (Online)")
                self.lbl_ecu_status.setStyleSheet("font-size: 10px; color: #10b981; font-weight: bold;")

                mode = payload[1]
                # Modo 01 (0x41 = 0x01 + 0x40)
                if mode == 0x41 and len(payload) >= 3:
                    pid = payload[2]
                    self._decode_mode1(pid, payload)

                # Modo 03 (0x43 = 0x03 + 0x40)
                elif mode == 0x43:
                    self._decode_mode3_dtcs(payload)

        # 2. Se o Signal Finder estiver ativo, alimenta o tráfego proprietário para correlação
        elif self.finder_active and can_id != self.OBD_REQUEST_ID:
            self._feed_signal_finder(can_id, payload)

    # ==========================================================================
    # DECODIFICAÇÃO DOS SENSORES MODO 01
    # ==========================================================================

    def _decode_mode1(self, pid: int, payload: list[int]):
        """Aplica fórmulas matemáticas oficiais da norma SAE J1979."""
        # PID 0x00: PIDs suportados (01 a 20)
        if pid == self.PID_SUPPORTED_1_20 and len(payload) >= 7:
            pids_text = []
            for byte_idx, b in enumerate(payload[3:7]):
                for bit in range(8):
                    if (b >> (7 - bit)) & 1:
                        p_num = byte_idx * 8 + bit + 1
                        self.supported_pids.add(p_num)
                        pids_text.append(f"0x{p_num:02X}")
            self.lbl_supported_info.setText(f"PIDs detectados: {', '.join(pids_text[:10])}...")

        # RPM (0x0C): ((A * 256) + B) / 4
        elif pid == self.PID_ENGINE_RPM and len(payload) >= 5:
            self.val_rpm = ((payload[3] * 256) + payload[4]) / 4.0
            self.lbl_val_rpm.setText(f"{int(self.val_rpm):,} rpm")
            self._update_calculated_fuel_consumption()

        # Velocidade (0x0D): A km/h
        elif pid == self.PID_VEHICLE_SPEED and len(payload) >= 4:
            self.val_speed = float(payload[3])
            self.lbl_val_speed.setText(f"{int(self.val_speed)} km/h")
            self._update_calculated_fuel_consumption()

        # Tensão Bateria (0x42): ((A * 256) + B) / 1000 V
        elif pid == self.PID_BATTERY_VOLT and len(payload) >= 5:
            self.val_battery = ((payload[3] * 256) + payload[4]) / 1000.0
            self.lbl_val_bat.setText(f"{self.val_battery:.2f} V")

        # Nível Combustível (0x2F): (A * 100) / 255 %
        elif pid == self.PID_FUEL_LEVEL and len(payload) >= 4:
            self.val_fuel = (payload[3] * 100.0) / 255.0
            self.lbl_val_fuel.setText(f"{self.val_fuel:.1f} %")

        # Temp Motor (0x05): A - 40 °C
        elif pid == self.PID_COOLANT_TEMP and len(payload) >= 4:
            self.val_temp = float(payload[3] - 40)
            self.lbl_val_temp.setText(f"{int(self.val_temp)} °C")

        # MAF (0x10): ((A * 256) + B) / 100 g/s
        elif pid == self.PID_MAF_AIR_FLOW and len(payload) >= 5:
            self.val_maf = ((payload[3] * 256) + payload[4]) / 100.0
            self.lbl_val_maf.setText(f"{self.val_maf:.2f} g/s")
            self._update_calculated_fuel_consumption()

        # MAP (0x0B): A kPa
        elif pid == self.PID_MAP_PRESSURE and len(payload) >= 4:
            self.val_map = float(payload[3])
            self.lbl_val_map.setText(f"{int(self.val_map)} kPa")

        # Carga Motor (0x04): (A * 100) / 255 %
        elif pid == self.PID_ENGINE_LOAD and len(payload) >= 4:
            self.val_load = (payload[3] * 100.0) / 255.0
            self.lbl_val_load.setText(f"{self.val_load:.1f} %")

        # TPS Borboleta (0x11): (A * 100) / 255 %
        elif pid == self.PID_THROTTLE_POS and len(payload) >= 4:
            self.val_tps = (payload[3] * 100.0) / 255.0
            self.lbl_val_tps.setText(f"{self.val_tps:.1f} %")

        # IAT Temp Admissão (0x0F): A - 40 °C
        elif pid == self.PID_INTAKE_TEMP and len(payload) >= 4:
            self.val_iat = float(payload[3] - 40)
            self.lbl_val_iat.setText(f"{int(self.val_iat)} °C")

        # Pressão Linha Combustível Rail (0x23): ((A * 256) + B) * 10 kPa
        elif pid == self.PID_FUEL_RAIL_PRESS and len(payload) >= 5:
            self.val_rail = float(((payload[3] * 256) + payload[4]) * 10)
            self.lbl_val_rail.setText(f"{int(self.val_rail):,} kPa")

        # Avanço de Ignição (0x0E): (A / 2) - 64 graus
        elif pid == self.PID_TIMING_ADVANCE and len(payload) >= 4:
            self.val_timing = (payload[3] / 2.0) - 64.0

    def _update_calculated_fuel_consumption(self):
        """Calcula consumo instantâneo usando o fluxo de massa de ar (MAF) e velocidade."""
        # Se MAF > 0: Vazão de combustível = MAF / 14.7 (g/s)
        # Densidade gasolina ~740 g/L -> Litros/s = MAF / (14.7 * 740)
        # Litros/hora = (MAF * 3600) / (14.7 * 740) ≈ MAF * 0.3309
        if self.val_maf > 0.1:
            litros_hora = self.val_maf * 0.3309
            if self.val_speed > 3.0:
                # km/L = velocidade / litros_por_hora
                km_por_l = self.val_speed / litros_hora
                self.lbl_val_cons.setText(f"{km_por_l:.1f} km/L")
            else:
                self.lbl_val_cons.setText(f"{litros_hora:.1f} L/h")
        else:
            self.lbl_val_cons.setText("-- km/L")

    def _decode_mode3_dtcs(self, payload: list[int]):
        """Decodifica falhas DTC da resposta do Modo 03."""
        num_codes = (payload[0] - 1) // 2
        self.table_dtc.setRowCount(0)

        if num_codes <= 0 or len(payload) < 4:
            self.lbl_dtc_count.setText("Nenhuma falha ativa registrada (ECU OK).")
            return

        self.lbl_dtc_count.setText(f"Falhas detectadas: {num_codes}")
        row = 0
        tipo_map = {0b00: ("P", "Powertrain / Motor"), 0b01: ("C", "Chassi / Freios"),
                    0b10: ("B", "Carroceria / Body"), 0b11: ("U", "Rede / Comunicação")}

        for i in range(2, min(len(payload) - 1, 2 + num_codes * 2), 2):
            b1, b2 = payload[i], payload[i + 1]
            if b1 == 0 and b2 == 0:
                continue

            tipo_code, tipo_desc = tipo_map.get((b1 >> 6) & 0x03, ("P", "Powertrain"))
            n1 = (b1 >> 4) & 0x03
            n2 = b1 & 0x0F
            n3 = (b2 >> 4) & 0x0F
            n4 = b2 & 0x0F
            dtc_str = f"{tipo_code}{n1}{n2:X}{n3:X}{n4:X}"

            self.table_dtc.insertRow(row)
            self.table_dtc.setItem(row, 0, QTableWidgetItem(dtc_str))
            self.table_dtc.setItem(row, 1, QTableWidgetItem(tipo_desc))
            self.table_dtc.setItem(row, 2, QTableWidgetItem("Código padrão SAE J2012"))
            row += 1

    # ==========================================================================
    # MOTOR DE ENGENHARIA REVERSA (CAN SIGNAL FINDER)
    # ==========================================================================

    def toggle_signal_finder(self, checked: bool):
        """Inicia ou pausa o analisador estatístico de correlação."""
        self.finder_active = checked
        if checked:
            self.btn_toggle_finder.setText("Parar Varredura")
            self.lbl_finder_status.setText("🟢 Varredura ATIVA: Coletando amostras e correlacionando...")
            self.lbl_finder_status.setStyleSheet("font-size: 10px; color: #4ade80; font-weight: bold;")
            self.finder_pairs_8.clear()
            self.finder_pairs_16.clear()
        else:
            self.btn_toggle_finder.setText("Iniciar Varredura & Correlação")
            self.lbl_finder_status.setText("Status: Pausado.")
            self.lbl_finder_status.setStyleSheet("font-size: 10px; color: #facc15; font-weight: bold;")

    def _feed_signal_finder(self, can_id: int, payload: list[int]):
        """Grava dados do tráfego proprietário e calcula correlação de Pearson em tempo real."""
        # Obtém o valor de referência atual
        ref_type = self.cb_reference_signal.currentData()
        if ref_type == "speed":
            ref_val = self.val_speed
        elif ref_type == "rpm":
            ref_val = self.val_rpm
        else:
            ref_val = self.val_tps

        # Grava cada byte individual (8-bit) pareado com a referência OBD atual
        for idx, val in enumerate(payload):
            self.finder_pairs_8[(can_id, idx)].append((float(val), float(ref_val)))

        # Grava palavras de 16-bit (Big Endian e Little Endian)
        for idx in range(len(payload) - 1):
            b_high, b_low = payload[idx], payload[idx + 1]
            val_be = float((b_high << 8) | b_low)
            val_le = float((b_low << 8) | b_high)
            self.finder_pairs_16[(can_id, idx, "BE")].append((val_be, float(ref_val)))
            self.finder_pairs_16[(can_id, idx, "LE")].append((val_le, float(ref_val)))

        # Atualiza a tabela a cada 0.5s se tivermos amostras
        now = time.time()
        if now - self.finder_last_calc_time >= 0.5:
            self.finder_last_calc_time = now
            self._calculate_correlation_candidates()

    def _compute_pearson(self, pairs) -> tuple[float, float] | None:
        """Calcula correlação de Pearson r e escala estimada entre sinal e referência."""
        n = len(pairs)
        if n < 15:
            return None
        sum_x = sum(p[0] for p in pairs)
        sum_y = sum(p[1] for p in pairs)
        mean_x = sum_x / n
        mean_y = sum_y / n

        var_x = sum((p[0] - mean_x) ** 2 for p in pairs)
        var_y = sum((p[1] - mean_y) ** 2 for p in pairs)

        if var_x < 1e-4 or var_y < 1e-4:
            return None

        cov = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pairs)
        r = cov / math.sqrt(var_x * var_y)
        scale = math.sqrt(var_y / var_x)
        return r, scale

    def _calculate_correlation_candidates(self):
        """Calcula o coeficiente de Pearson para todos os sinais gravados e ranqueia."""
        candidates = []

        # 1. Avalia sinais de 8-bit
        for (cid, b_idx), pairs_deque in self.finder_pairs_8.items():
            res = self._compute_pearson(pairs_deque)
            if res:
                r, scale = res
                if r > 0.70:
                    candidates.append((r, cid, f"Byte {b_idx}", "8-bit", scale))

        # 2. Avalia sinais de 16-bit
        for (cid, b_idx, endian), pairs_deque in self.finder_pairs_16.items():
            res = self._compute_pearson(pairs_deque)
            if res:
                r, scale = res
                if r > 0.70:
                    fmt_str = f"16-bit ({'Big Endian' if endian == 'BE' else 'Little Endian'})"
                    candidates.append((r, cid, f"Bytes {b_idx}-{b_idx+1}", fmt_str, scale))

        # Ordena pelos melhores coeficientes de correlação (mais próximos de 1.0)
        candidates.sort(key=lambda item: item[0], reverse=True)

        self.table_candidates.setRowCount(0)
        for row, (r, cid, loc, fmt, scale) in enumerate(candidates[:8]):
            self.table_candidates.insertRow(row)
            self.table_candidates.setItem(row, 0, QTableWidgetItem(f"0x{cid:03X}"))
            self.table_candidates.setItem(row, 1, QTableWidgetItem(loc))
            self.table_candidates.setItem(row, 2, QTableWidgetItem(fmt))
            
            # Formatação percentual de confiança
            conf = min(100.0, r * 100.0)
            item_r = QTableWidgetItem(f"{conf:.1f}% (r={r:.3f})")
            if conf >= 95.0:
                item_r.setForeground(QColor("#4ade80"))  # Verde
            else:
                item_r.setForeground(QColor("#facc15"))  # Amarelo
            self.table_candidates.setItem(row, 3, item_r)

            self.table_candidates.setItem(row, 4, QTableWidgetItem(f"× {scale:.4f}"))

        if candidates:
            best = candidates[0]
            self.lbl_finder_status.setText(
                f"🎯 Candidato Encontrado! ID 0x{best[1]:03X} ({best[2]}) com {best[0]*100:.1f}% de correlação!"
            )
            self.lbl_finder_status.setStyleSheet("font-size: 10px; color: #4ade80; font-weight: bold;")

    # ==========================================================================
    # SIMULAÇÃO REALISTA PARA TESTES NA BANCADA
    # ==========================================================================

    def _handle_simulated_cycle(self, pid: int):
        """Gera dados dinâmicos e tráfego de fundo para testar o Signal Finder na bancada."""
        self._sim_t += 0.1
        # Simula ciclo de aceleração e desaceleração
        self._sim_rpm = 850 + int((math.sin(self._sim_t * 0.4) + 1.0) * 1200)
        self._sim_speed = max(0, int((self._sim_rpm - 850) / 25.0))

        # Resposta oficial da ECU no ID 0x7E8
        if pid == self.PID_ENGINE_RPM:
            raw_rpm = int(self._sim_rpm * 4)
            a, b = (raw_rpm >> 8) & 0xFF, raw_rpm & 0xFF
            self.on_can_frame(0x7E8, 10.0, [0x04, 0x41, pid, a, b, 0, 0, 0])

        elif pid == self.PID_VEHICLE_SPEED:
            self.on_can_frame(0x7E8, 10.0, [0x03, 0x41, pid, int(self._sim_speed), 0, 0, 0, 0])

        elif pid == self.PID_BATTERY_VOLT:
            # 14.1 V = 14100 -> 0x3714
            self.on_can_frame(0x7E8, 2.0, [0x04, 0x41, pid, 0x37, 0x14, 0, 0, 0])

        elif pid == self.PID_FUEL_LEVEL:
            # 72% = 183
            self.on_can_frame(0x7E8, 1.0, [0x03, 0x41, pid, 183, 0, 0, 0, 0])

        elif pid == self.PID_COOLANT_TEMP:
            # 89 °C -> A = 129
            self.on_can_frame(0x7E8, 1.0, [0x03, 0x41, pid, 129, 0, 0, 0, 0])

        elif pid == self.PID_MAF_AIR_FLOW:
            # MAF varia de 3.5 a 45 g/s proporcional ao RPM
            maf_val = 3.5 + (self._sim_rpm / 3000.0) * 25.0
            raw_maf = int(maf_val * 100)
            a, b = (raw_maf >> 8) & 0xFF, raw_maf & 0xFF
            self.on_can_frame(0x7E8, 5.0, [0x04, 0x41, pid, a, b, 0, 0, 0])

        elif pid == self.PID_THROTTLE_POS:
            tps_val = min(255, int(((self._sim_rpm - 850) / 2400.0) * 255))
            self.on_can_frame(0x7E8, 5.0, [0x03, 0x41, pid, tps_val, 0, 0, 0, 0])

        elif pid == self.PID_MAP_PRESSURE:
            # 35 a 105 kPa
            map_val = 35 + int(((self._sim_rpm - 850) / 2400.0) * 65)
            self.on_can_frame(0x7E8, 5.0, [0x03, 0x41, pid, map_val, 0, 0, 0, 0])

        # Se o Signal Finder estiver ativo na simulação:
        # Gera tráfego de fundo proprietário com a velocidade embutida no ID 0x280 (Bytes 2-3)
        # e RPM no ID 0x180 (Bytes 0-1) para provar a correlação estatística!
        if self.finder_active:
            # ID 0x280 (Simula mensagem de Velocidade do ABS proprietário: escala 100x em Big Endian)
            speed_raw = int(self._sim_speed * 100)
            sp_h, sp_l = (speed_raw >> 8) & 0xFF, speed_raw & 0xFF
            self.on_can_frame(0x280, 20.0, [0x01, 0xFF, sp_h, sp_l, 0x00, 0xAA, 0x55, 0x10])

            # ID 0x180 (Simula mensagem de RPM do Painel proprietário: escala 4x)
            rpm_raw = int(self._sim_rpm * 4)
            rp_h, rp_l = (rpm_raw >> 8) & 0xFF, rpm_raw & 0xFF
            self.on_can_frame(0x180, 20.0, [rp_h, rp_l, 0x30, 0x12, 0x00, 0x00, 0x00, 0x00])

            # Tráfego aleatório (ruído de fundo sem correlação)
            self.on_can_frame(0x350, 10.0, [int((self._sim_t * 13) % 255), 0x22, 0x33, 0x44, 0, 0, 0, 0])

    def get_custom_config(self) -> dict:
        return {
            "polling_active": self.btn_poll.isChecked(),
            "sim_active": self.chk_simulate.isChecked(),
            "finder_active": self.btn_toggle_finder.isChecked()
        }

    def set_custom_config(self, config: dict):
        if config.get("sim_active"):
            self.chk_simulate.setChecked(True)
        if config.get("polling_active"):
            self.btn_poll.setChecked(True)
        if config.get("finder_active"):
            self.btn_toggle_finder.setChecked(True)

    def on_close(self):
        if hasattr(self, "poll_timer"):
            self.poll_timer.stop()
