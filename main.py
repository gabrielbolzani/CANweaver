"""
main.py — Ponto de entrada do CANweaver v2.0

Responsabilidade: criar a janela principal, montar a toolbar global
(Conectar / Gravar) e as três abas. Toda a lógica pesada está nos módulos:

  src/worker.py        → CANWorker (thread de captura/envio)
  src/dialogs.py       → ConnectionDialog, CommentDialog
  src/annotations.py   → AnnotationManager (leitura/escrita .md)
  src/delegate.py      → CANItemDelegate (renderização de bits)
  src/analysis_tab.py  → AnalysisTab (aba sniffer)
  src/transmit_tab.py  → TransmitTab (aba de transmissão)
  src/widgets_tab.py   → WidgetsTab (aba de painéis - em dev)

Assets (ícone, stylesheet):
  assets/ico.ico
  assets/style.qss
"""

import sys
import os
import csv
import time
import ctypes

import can

from PyQt6.QtCore import Qt, QTimer, QDateTime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QPushButton, QLabel,
    QMessageBox, QInputDialog, QLineEdit
)
from PyQt6.QtGui import QIcon

from src.worker import CANWorker
from src.dialogs import ConnectionDialog
from src.annotations import AnnotationManager
from src.analysis_tab import AnalysisTab
from src.transmit_tab import TransmitTab
from src.widgets_tab import WidgetsTab

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CANweaver v2.0 - AI Assisted CAN Reverse Engineering")
        icon_path = os.path.join(BASE_DIR, "assets", "ico.ico")
        self.setWindowIcon(QIcon(icon_path))
        self.resize(1280, 720)

        # Gravação
        self.is_recording = False
        self.record_file = None
        self.record_writer = None
        self.record_start_time = 0
        self.temp_record_filename = os.path.join(BASE_DIR, "temp_gravacao.csv")

        # Anotações
        self.annotation_manager = AnnotationManager(BASE_DIR)
        self.annotation_manager.load()

        # Thread CAN (começa ociosa)
        self.can_thread = CANWorker()
        self.can_thread.mode = "IDLE"

        # Abas
        self.analysis_tab = AnalysisTab(self.annotation_manager, self.can_thread)
        self.transmit_tab = TransmitTab(self.can_thread)
        self.widgets_tab = WidgetsTab(self.can_thread)

        # Conectar sinal CAN → análise
        self.can_thread.frame_received.connect(self.analysis_tab.process_can_frame)
        self.can_thread.error_occurred.connect(self._handle_worker_error)
        self.can_thread.start()

        self._build_ui()
        self._load_stylesheet()

        # Timer de gravação
        self.record_timer = QTimer()
        self.record_timer.timeout.connect(self._update_record_time)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        from PyQt6.QtWidgets import QTabWidget

        # Toolbar global
        toolbar = QToolBar("Global Controls")
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        toolbar.setMovable(False)
        toolbar.setStyleSheet("background-color: #202024; border-bottom: 1px solid #323238;")

        self.btn_connect = QPushButton("Conectar...")
        self.btn_connect.clicked.connect(self._open_connection_dialog)
        self.btn_connect.setStyleSheet(
            "background-color: #4e44dd; color: white; padding: 6px 12px; "
            "border-radius: 4px; font-weight: bold; margin-right: 10px; margin-left: 10px;"
        )

        self.btn_record = QPushButton("⏺ Gravar (REC)")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_record.setStyleSheet(
            "background-color: #2e3035; color: white; padding: 6px 12px; "
            "border-radius: 4px; margin-right: 20px;"
        )

        self.lbl_status = QLabel("Status: Ocioso (Desconectado)")
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-weight: bold;")

        toolbar.addWidget(self.btn_connect)
        toolbar.addWidget(self.btn_record)
        toolbar.addWidget(self.lbl_status)

        # Abas
        tab_widget = QTabWidget()
        tab_widget.addTab(self.analysis_tab, "Análise (Sniffer)")
        tab_widget.addTab(self.transmit_tab, "Transmitir")
        tab_widget.addTab(self.widgets_tab, "Widgets")
        self.setCentralWidget(tab_widget)

    def _load_stylesheet(self):
        qss_path = os.path.join(BASE_DIR, "assets", "style.qss")
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Não foi possível carregar o style.qss: {e}")

    # ------------------------------------------------------------------
    # Conexão
    # ------------------------------------------------------------------
    def _open_connection_dialog(self):
        dialog = ConnectionDialog(self)
        if dialog.exec():
            self._start_worker(dialog.get_config())

    def _start_worker(self, config: dict):
        if self.can_thread and self.can_thread.isRunning():
            self.can_thread.stop()

        self.analysis_tab.current_bitrate = config.get("bitrate", 500000)

        self.can_thread = CANWorker()
        self.can_thread.mode = config["mode"]

        if config.get("playback_loop"):
            self.can_thread.playback_loop = config["playback_loop"]

        if config["mode"] == "HARDWARE":
            try:
                self.can_thread.bus = can.Bus(
                    interface=config["interface"],
                    channel=config["channel"],
                    bitrate=config["bitrate"]
                )
                self.lbl_status.setText(
                    f"Status: Conectado ({config['interface']} em {config['channel']} @ {config['bitrate']})"
                )
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

        # Atualizar referência da thread nas abas
        self.analysis_tab.can_thread = self.can_thread
        self.transmit_tab.can_thread = self.can_thread
        self.widgets_tab.can_thread = self.can_thread

        self.can_thread.frame_received.connect(self.analysis_tab.process_can_frame)
        self.can_thread.error_occurred.connect(self._handle_worker_error)

        self.analysis_tab.clear_data()
        self.can_thread.start()

    def _handle_worker_error(self, err_msg: str):
        QMessageBox.warning(self, "Aviso da Thread", err_msg)
        if "Reprodução concluída" in err_msg:
            self.lbl_status.setText("Status: Reprodução Finalizada")

    # ------------------------------------------------------------------
    # Gravação
    # ------------------------------------------------------------------
    def _toggle_recording(self, checked: bool):
        if checked:
            try:
                self.record_file = open(self.temp_record_filename, "w", newline="", encoding="utf-8")
                self.record_writer = csv.writer(self.record_file)
                self.record_writer.writerow(["Timestamp", "ID", "DLC", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"])
                self.record_start_time = time.time()
                self.is_recording = True

                # Conectar gravação ao processamento de frames
                self.can_thread.frame_received.connect(self._record_frame)

                self.btn_record.setStyleSheet(
                    "background-color: #e83f5b; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;"
                )
                self.lbl_status.setText(self.lbl_status.text() + " [GRAVANDO]")
                self.record_timer.start(1000)
                self.btn_record.setText("⏹ Gravando (00:00)")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao criar cache de gravação:\n{e}")
                self.btn_record.setChecked(False)
        else:
            self.is_recording = False
            self.record_timer.stop()

            try:
                self.can_thread.frame_received.disconnect(self._record_frame)
            except Exception:
                pass

            if self.record_file:
                self.record_file.close()
                self.record_file = None
                self.record_writer = None

            timestamp_str = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            default_name = f"gravacao_can_{timestamp_str}.csv"
            text, ok = QInputDialog.getText(
                self, "Salvar Gravação", "Dê um nome para a sessão (CSV):",
                QLineEdit.EchoMode.Normal, default_name
            )

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
                except Exception:
                    pass

            self.btn_record.setText("⏺ Gravar (REC)")
            self.btn_record.setStyleSheet(
                "background-color: #2e3035; color: white; padding: 6px 12px; border-radius: 4px; margin-right: 20px;"
            )
            self.lbl_status.setText(self.lbl_status.text().replace(" [GRAVANDO]", ""))

    def _record_frame(self, can_id: int, frequency: float, payload: list):
        if self.is_recording and self.record_writer:
            self.record_writer.writerow([time.time(), f"{can_id:03X}", len(payload)] + list(payload))

    def _update_record_time(self):
        if self.is_recording:
            elapsed = int(time.time() - self.record_start_time)
            mins, secs = divmod(elapsed, 60)
            self.btn_record.setText(f"⏹ Gravando ({mins:02d}:{secs:02d})")


if __name__ == "__main__":
    try:
        myappid = "canweaver.v2.ai.reverseengineering"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
