"""
dialogs.py — Diálogos modais da aplicação

Contém:
  - AboutDialog: diálogo de créditos e verificação de atualizações.
  - ExportDialog: diálogo de exportação seletiva (.cwp, .md, .json).
  - BusDiscoveryDialog & BusScannerThread: auto-descoberta de velocidade CAN (Auto-Baudrate) e subida de interface.
  - ConnectionDialog: configuração de modo (Hardware Real / Simulado / Playback),
    interface, canal, bitrate e arquivo de playback.
  - CommentDialog: caixa de texto multilinhas para anotações.
    Enter confirma, Shift+Enter insere nova linha.
"""

import sys
import time
import subprocess
import urllib.request
import json
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QLineEdit, QPushButton,
    QLabel, QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout, QTextEdit,
    QProgressBar, QFrame, QMessageBox, QApplication
)
from src.version import __version__


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sobre o CANweaver")
        self.resize(450, 250)
        
        layout = QVBoxLayout(self)
        
        lbl_title = QLabel(f"<h2>CANweaver v{__version__}</h2>")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_credits = QLabel(
            "<b>Autores:</b> Gabriel Bolzani & Gemini e Companhia<br><br>"
            "<b>Repositório:</b> <a href='https://github.com/gabrielbolzani/CANweaver' style='color: #3b82f6;'>https://github.com/gabrielbolzani/CANweaver</a>"
        )
        lbl_credits.setOpenExternalLinks(True)
        lbl_credits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_license = QLabel(
            "<b>Licença:</b><br>"
            "É estritamente proibida a venda ou uso comercial deste software.<br>"
            "Qualquer modificação ou fork do código-fonte deve obrigatoriamente "
            "creditar os autores originais do projeto."
        )
        lbl_license.setWordWrap(True)
        lbl_license.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_license.setStyleSheet("color: #a1a1aa; font-size: 13px; margin-top: 15px; border-top: 1px solid #323238; padding-top: 10px;")
        
        self.btn_update = QPushButton("Verificar Atualizações")
        self.btn_update.clicked.connect(self._check_updates)
        self.btn_update.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px; border-radius: 4px;")
        
        btn_ok = QPushButton("Fechar")
        btn_ok.clicked.connect(self.accept)
        btn_ok.setStyleSheet("background-color: #2e3035; color: white; padding: 6px; border-radius: 4px; min-width: 80px;")
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_update)
        btn_layout.addWidget(btn_ok)
        btn_layout.addStretch()
        
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_credits)
        layout.addWidget(lbl_license)
        layout.addLayout(btn_layout)

    def _check_updates(self):
        self.btn_update.setText("Verificando...")
        self.btn_update.setEnabled(False)
        QApplication.processEvents()

        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/gabrielbolzani/CANweaver/releases/latest",
                headers={"User-Agent": "CANweaver-App"}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_tag = data.get("tag_name", "")
                
                def parse_ver(v):
                    return [int(x) for x in v.replace('v', '').split('.') if x.isdigit()]
                
                cur_v = parse_ver(f"v{__version__}")
                lat_v = parse_ver(latest_tag)
                
                while len(cur_v) < len(lat_v): cur_v.append(0)
                while len(lat_v) < len(cur_v): lat_v.append(0)
                
                if lat_v > cur_v:
                    url = data.get("html_url", "https://github.com/gabrielbolzani/CANweaver/releases")
                    msg = QMessageBox(self)
                    msg.setWindowTitle("Nova Versão Disponível!")
                    msg.setText(f"A versão <b>{latest_tag}</b> está disponível no GitHub.<br><br><a href='{url}'>Clique aqui para baixar</a>")
                    msg.setTextFormat(Qt.TextFormat.RichText)
                    msg.setOpenExternalLinks(True)
                    msg.exec()
                else:
                    QMessageBox.information(self, "Atualizado", f"Você já está na versão mais recente (v{__version__}).")
                    
        except urllib.error.HTTPError as e:
            if e.code == 404:
                QMessageBox.information(self, "Aviso", "Nenhuma release foi publicada neste repositório ainda.")
            else:
                QMessageBox.warning(self, "Erro", f"Erro de rede ao verificar atualizações:\n{e}")
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível verificar atualizações:\n{e}")
        finally:
            self.btn_update.setText("Verificar Atualizações")
            self.btn_update.setEnabled(True)


class ExportDialog(QDialog):
    def __init__(self, parent=None, default_name="MeuProjeto"):
        super().__init__(parent)
        self.setWindowTitle("Salvar Projeto Como...")
        self.resize(380, 260)

        layout = QVBoxLayout(self)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nome do arquivo:"))
        self.txt_name = QLineEdit(default_name)
        name_layout.addWidget(self.txt_name)
        layout.addLayout(name_layout)

        layout.addWidget(QLabel("Selecione o que incluir:"))

        self.chk_annotations = QCheckBox("Anotações e Documentação (.md)")
        self.chk_annotations.setChecked(True)

        self.chk_transmit = QCheckBox("Tarefas Cíclicas de Transmissão (.json)")
        self.chk_transmit.setChecked(True)

        self.chk_dashboard = QCheckBox("Layout do Dashboard/Widgets (.json)")
        self.chk_dashboard.setChecked(True)

        for chk in (self.chk_annotations, self.chk_transmit, self.chk_dashboard):
            chk.stateChanged.connect(self._update_btn_label)

        layout.addWidget(self.chk_annotations)
        layout.addWidget(self.chk_transmit)
        layout.addWidget(self.chk_dashboard)

        self.lbl_hint = QLabel()
        self.lbl_hint.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        layout.addWidget(self.lbl_hint)

        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Salvar Como...")
        self.btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(btn_cancel)

        layout.addStretch()
        layout.addLayout(btn_layout)

        self._update_btn_label()

    def _update_btn_label(self):
        sel = self.get_selection()
        checked = [k for k, v in sel.items() if v]
        ext_map = {"annotations": ".md", "transmit": ".json", "dashboard": ".json"}
        if len(checked) == 1:
            ext = ext_map[checked[0]]
            self.lbl_hint.setText(f"💡 Apenas 1 item selecionado — será salvo diretamente como {ext}")
        else:
            self.lbl_hint.setText("💡 Múltiplos itens — serão compactados em .cwp")

    def get_selection(self):
        return {
            "annotations": self.chk_annotations.isChecked(),
            "transmit": self.chk_transmit.isChecked(),
            "dashboard": self.chk_dashboard.isChecked()
        }

    def get_name(self):
        return self.txt_name.text().strip() or "MeuProjeto"


def bring_up_socketcan(channel: str, bitrate: int, listen_only: bool = False) -> tuple:
    """
    Tenta configurar e subir a interface SocketCAN no Linux (ip link).
    Retorna (sucesso: bool, mensagem: str).
    """
    if sys.platform == "win32":
        return True, "Ambiente Windows (configuração via driver nativo)"

    channel = channel.strip()
    if not channel:
        channel = "can0"

    # 1. Tenta derrubar interface se estiver up para permitir reconfiguração
    cmd_down = ["ip", "link", "set", channel, "down"]
    try:
        res = subprocess.run(cmd_down, capture_output=True, text=True, timeout=3)
        if res.returncode != 0 and "Operation not permitted" in (res.stderr or ""):
            subprocess.run(["sudo", "-n"] + cmd_down, capture_output=True, text=True, timeout=3)
    except Exception:
        pass

    # 2. Configurar bitrate
    type_args = ["type", "can", "bitrate", str(bitrate)]
    if listen_only:
        type_args.extend(["listen-only", "on"])

    cmd_config = ["ip", "link", "set", channel] + type_args
    try:
        res = subprocess.run(cmd_config, capture_output=True, text=True, timeout=3)
        if res.returncode != 0:
            if listen_only:
                cmd_no_lo = ["ip", "link", "set", channel, "type", "can", "bitrate", str(bitrate)]
                res = subprocess.run(cmd_no_lo, capture_output=True, text=True, timeout=3)
            if res.returncode != 0:
                subprocess.run(["sudo", "-n"] + cmd_config, capture_output=True, text=True, timeout=3)
    except Exception as e:
        return False, f"Erro ao configurar bitrate: {e}"

    # 3. Subir interface
    cmd_up = ["ip", "link", "set", channel, "up"]
    try:
        res = subprocess.run(cmd_up, capture_output=True, text=True, timeout=3)
        if res.returncode != 0:
            res_sudo = subprocess.run(["sudo", "-n"] + cmd_up, capture_output=True, text=True, timeout=3)
            if res_sudo.returncode != 0:
                err = res_sudo.stderr.strip() or res.stderr.strip()
                return False, f"Não foi possível subir {channel}: {err}"
        return True, f"Interface {channel} ativa a {bitrate} bps"
    except Exception as e:
        return False, f"Erro ao subir interface: {e}"


class BusScannerThread(QThread):
    progress_updated = pyqtSignal(int, int, int, str)
    log_message = pyqtSignal(str)
    baudrate_found = pyqtSignal(int, int, list)
    scan_finished = pyqtSignal(bool, int, str)

    CANDIDATE_BITRATES = [
        500000, 250000, 125000, 1000000, 100000, 50000, 20000, 33333, 83333, 10000
    ]

    def __init__(self, interface="socketcan", channel="can0", auto_up=True, listen_only=True, timeout_per_rate=1.5):
        super().__init__()
        self.interface = interface
        self.channel = channel
        self.auto_up = auto_up
        self.listen_only = listen_only
        self.timeout_per_rate = timeout_per_rate
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        total = len(self.CANDIDATE_BITRATES)
        self.log_message.emit(f"🔍 Iniciando varredura na interface '{self.interface}' (canal: {self.channel})...")

        for idx, rate in enumerate(self.CANDIDATE_BITRATES):
            if not self.running:
                self.scan_finished.emit(False, 0, "Varredura interrompida pelo usuário.")
                return

            rate_kbps = rate / 1000.0
            self.progress_updated.emit(idx + 1, total, rate, f"Testando {rate_kbps:.1f} kbps ({rate} bps)...")
            self.log_message.emit(f"\n⏱ [{idx+1}/{total}] Testando {rate_kbps:.1f} kbps ({rate} bps)...")

            if self.interface == "socketcan" and self.auto_up:
                ok, up_msg = bring_up_socketcan(self.channel, rate, self.listen_only)
                self.log_message.emit(f"   ↳ {up_msg}")

            bus = None
            try:
                import can
                bus = can.Bus(
                    interface=self.interface,
                    channel=self.channel,
                    bitrate=rate,
                    receive_own_messages=False
                )
            except Exception as e:
                self.log_message.emit(f"   ❌ Falha ao inicializar can.Bus: {e}")
                continue

            frames_count = 0
            unique_ids = set()
            start_t = time.time()

            try:
                while (time.time() - start_t < self.timeout_per_rate) and self.running:
                    msg = bus.recv(timeout=0.1)
                    if msg is not None:
                        if getattr(msg, "is_error_frame", False):
                            continue
                        if msg.arbitration_id is not None:
                            frames_count += 1
                            unique_ids.add(f"0x{msg.arbitration_id:03X}")
                            if frames_count >= 2:
                                break
            except Exception as e:
                self.log_message.emit(f"   ⚠️ Erro ao receber frames: {e}")
            finally:
                try:
                    bus.shutdown()
                except Exception:
                    pass

            if frames_count > 0:
                id_sample = list(unique_ids)[:6]
                self.log_message.emit(
                    f"   ✅ SUCESSO! {frames_count} frame(s) válido(s) capturado(s) a {rate_kbps:.1f} kbps!"
                )
                self.log_message.emit(f"   ↳ IDs detectados: {', '.join(id_sample)}")
                self.baudrate_found.emit(rate, frames_count, id_sample)
                self.scan_finished.emit(True, rate, f"Barramento encontrado: {rate_kbps:.1f} kbps ({rate} bps)")
                return
            else:
                self.log_message.emit(f"   ↳ Nenhum frame detectado nesta velocidade.")

        if self.running:
            self.scan_finished.emit(False, 0, "Varredura concluída. Nenhum frame CAN detectado nas velocidades testadas.")


class BusDiscoveryDialog(QDialog):
    """Diálogo para auto-descoberta de velocidade (Auto-Baudrate) e subida de barramento."""

    def __init__(self, parent=None, initial_interface="socketcan", initial_channel="can0"):
        super().__init__(parent)
        self.setWindowTitle("Descobrir Barramento CAN (Auto-Baudrate)")
        self.resize(520, 500)

        self.scanner_thread = None
        self.detected_bitrate = None

        layout = QVBoxLayout(self)

        # Form de configuração
        form_frame = QFrame()
        form_frame.setStyleSheet("background-color: #202024; border-radius: 6px; padding: 6px;")
        form = QFormLayout(form_frame)

        self.cb_interface = QComboBox()
        self.cb_interface.addItems(["socketcan", "slcan", "vector", "virtual", "ixxat", "pcan"])
        idx_iface = self.cb_interface.findText(initial_interface)
        if idx_iface >= 0:
            self.cb_interface.setCurrentIndex(idx_iface)

        self.txt_channel = QLineEdit(initial_channel or "can0")
        self.txt_channel.setPlaceholderText("ex: can0, COM3, /dev/ttyUSB0")

        self.chk_auto_up = QCheckBox("Subir interface automaticamente no Linux (ip link set up)")
        self.chk_auto_up.setChecked(True)

        self.chk_listen_only = QCheckBox("Modo Somente Escuta / Listen-Only (seguro para veículos)")
        self.chk_listen_only.setChecked(True)

        form.addRow("Interface:", self.cb_interface)
        form.addRow("Canal/Porta:", self.txt_channel)
        form.addRow("", self.chk_auto_up)
        form.addRow("", self.chk_listen_only)
        layout.addWidget(form_frame)

        # Painel de Status e Progresso
        status_frame = QFrame()
        status_frame.setStyleSheet("background-color: #18181b; border: 1px solid #323238; border-radius: 6px; padding: 8px;")
        status_layout = QVBoxLayout(status_frame)
        status_layout.setSpacing(6)

        self.lbl_status = QLabel("Pronto para iniciar a descoberta de velocidade.")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #e4e4e7;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #3b82f6; border-radius: 4px; }")

        status_layout.addWidget(self.lbl_status)
        status_layout.addWidget(self.progress_bar)
        layout.addWidget(status_frame)

        # Console de Logs
        layout.addWidget(QLabel("Log de Varredura:"))
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet(
            "QTextEdit { background-color: #121214; color: #a1a1aa; border: 1px solid #27272a;"
            " font-family: monospace; font-size: 11px; border-radius: 4px; }"
        )
        layout.addWidget(self.txt_log, 1)

        # Botões de Ação
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶ Iniciar Busca")
        self.btn_start.setStyleSheet("background-color: #3b82f6; color: white; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
        self.btn_start.clicked.connect(self._start_scan)

        self.btn_stop = QPushButton("⏹ Parar")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background-color: #ef4444; color: white; padding: 8px 16px; border-radius: 4px;")
        self.btn_stop.clicked.connect(self._stop_scan)

        self.btn_apply = QPushButton("🔌 Conectar nesta Velocidade")
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet("background-color: #10b981; color: white; padding: 8px 16px; border-radius: 4px; font-weight: bold;")
        self.btn_apply.clicked.connect(self.accept)

        self.btn_close = QPushButton("Fechar")
        self.btn_close.setStyleSheet("background-color: #2e3035; color: white; padding: 8px 16px; border-radius: 4px;")
        self.btn_close.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _start_scan(self):
        self.detected_bitrate = None
        self.txt_log.clear()
        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_apply.setEnabled(False)
        self.lbl_status.setText("Iniciando varredura...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #3b82f6;")

        iface = self.cb_interface.currentText()
        chan = self.txt_channel.text().strip() or "can0"
        auto_up = self.chk_auto_up.isChecked()
        listen_only = self.chk_listen_only.isChecked()

        self.scanner_thread = BusScannerThread(
            interface=iface,
            channel=chan,
            auto_up=auto_up,
            listen_only=listen_only,
            timeout_per_rate=1.5
        )
        self.scanner_thread.progress_updated.connect(self._on_progress)
        self.scanner_thread.log_message.connect(self._on_log)
        self.scanner_thread.baudrate_found.connect(self._on_baudrate_found)
        self.scanner_thread.scan_finished.connect(self._on_finished)
        self.scanner_thread.start()

    def _stop_scan(self):
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_thread.stop()
            self._on_log("\n⚠️ Solicitada interrupção da busca...")

    def _on_progress(self, current, total, bitrate, msg):
        pct = int((current / total) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_status.setText(msg)

    def _on_log(self, text):
        self.txt_log.append(text)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())

    def _on_baudrate_found(self, bitrate, count, sample_ids):
        self.detected_bitrate = bitrate
        rate_kbps = bitrate / 1000.0
        self.lbl_status.setText(f"🎯 Sucesso! {rate_kbps:.1f} kbps detectado ({count} frames)")
        self.lbl_status.setStyleSheet("font-weight: bold; color: #10b981;")
        self.progress_bar.setValue(100)
        self.btn_apply.setEnabled(True)

    def _on_finished(self, success, bitrate, msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not success and not self.detected_bitrate:
            self.lbl_status.setText(msg)
            self.lbl_status.setStyleSheet("font-weight: bold; color: #f59e0b;")

    def closeEvent(self, event):
        self._stop_scan()
        if self.scanner_thread:
            self.scanner_thread.wait(1000)
        super().closeEvent(event)

    def reject(self):
        self._stop_scan()
        if self.scanner_thread:
            self.scanner_thread.wait(1000)
        super().reject()

    def get_config(self):
        if not self.detected_bitrate:
            return None
        return {
            "mode": "HARDWARE",
            "interface": self.cb_interface.currentText(),
            "channel": self.txt_channel.text().strip() or "can0",
            "bitrate": self.detected_bitrate,
            "playback_file": "",
            "playback_transmit": False,
            "playback_loop": False
        }


class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conectar Dispositivo CAN")
        self.resize(380, 280)

        self.mode = "HARDWARE"
        self.interface = "socketcan"
        self.channel = "can0"
        self.bitrate = 500000
        self.playback_file = ""
        self.playback_transmit = False
        self.playback_loop = False

        self.layout = QFormLayout(self)

        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Hardware Real", "Simulado", "Playback"])
        self.cb_mode.currentIndexChanged.connect(self.on_mode_change)

        self.cb_interface = QComboBox()
        self.cb_interface.addItems(["socketcan", "slcan", "vector", "virtual", "ixxat", "pcan"])

        self.txt_channel = QLineEdit("can0")
        self.txt_channel.setPlaceholderText("ex: can0, COM3, /dev/ttyUSB0")

        self.cb_bitrate = QComboBox()
        self.cb_bitrate.addItems(["500000", "250000", "125000", "1000000", "100000", "50000", "20000"])
        self.cb_bitrate.setCurrentText("500000")

        self.btn_autodetect = QPushButton("🔍 Descobrir Barramento (Auto-Baudrate)...")
        self.btn_autodetect.setStyleSheet("background-color: #1e3a5f; color: white; padding: 6px; border-radius: 4px;")
        self.btn_autodetect.clicked.connect(self._open_autodetect)

        self.btn_file = QPushButton("Selecionar Arquivo...")
        self.btn_file.clicked.connect(self.select_file)
        self.lbl_file = QLabel("Nenhum arquivo selecionado")

        self.chk_transmit = QCheckBox("Transmitir no Hardware Real")
        self.chk_transmit.stateChanged.connect(self.on_transmit_change)

        self.chk_loop = QCheckBox("Repetir em Loop")

        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setStyleSheet("background-color: #10b981; color: white; padding: 8px; border-radius: 4px; font-weight: bold;")
        self.btn_connect.clicked.connect(self.accept)

        self.layout.addRow("Modo:", self.cb_mode)
        self.layout.addRow("Interface:", self.cb_interface)
        self.layout.addRow("Canal/Porta:", self.txt_channel)
        self.layout.addRow("Velocidade:", self.cb_bitrate)
        self.layout.addRow("", self.btn_autodetect)
        self.layout.addRow("Arquivo Playback:", self.btn_file)
        self.layout.addRow("", self.lbl_file)
        self.layout.addRow("", self.chk_transmit)
        self.layout.addRow("", self.chk_loop)
        self.layout.addRow(self.btn_connect)

        self.on_mode_change(0)

    def _open_autodetect(self):
        dlg = BusDiscoveryDialog(
            parent=self,
            initial_interface=self.cb_interface.currentText(),
            initial_channel=self.txt_channel.text().strip() or "can0"
        )
        if dlg.exec():
            cfg = dlg.get_config()
            if cfg:
                idx_iface = self.cb_interface.findText(cfg["interface"])
                if idx_iface >= 0:
                    self.cb_interface.setCurrentIndex(idx_iface)
                self.txt_channel.setText(cfg["channel"])
                idx_rate = self.cb_bitrate.findText(str(cfg["bitrate"]))
                if idx_rate >= 0:
                    self.cb_bitrate.setCurrentIndex(idx_rate)
                else:
                    self.cb_bitrate.addItem(str(cfg["bitrate"]))
                    self.cb_bitrate.setCurrentText(str(cfg["bitrate"]))

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
        if index == 0:  # Hardware Real
            self.set_row_visible(self.cb_interface, True)
            self.set_row_visible(self.txt_channel, True)
            self.set_row_visible(self.cb_bitrate, True)
            self.set_row_visible(self.btn_autodetect, True)
            self.set_row_visible(self.btn_file, False)
            self.set_row_visible(self.lbl_file, False)
            self.set_row_visible(self.chk_transmit, False)
            self.set_row_visible(self.chk_loop, False)
        elif index == 1:  # Simulado
            self.set_row_visible(self.cb_interface, False)
            self.set_row_visible(self.txt_channel, False)
            self.set_row_visible(self.cb_bitrate, False)
            self.set_row_visible(self.btn_autodetect, False)
            self.set_row_visible(self.btn_file, False)
            self.set_row_visible(self.lbl_file, False)
            self.set_row_visible(self.chk_transmit, False)
            self.set_row_visible(self.chk_loop, False)
        elif index == 2:  # Playback
            self.set_row_visible(self.btn_file, True)
            self.set_row_visible(self.lbl_file, True)
            self.set_row_visible(self.chk_transmit, True)
            self.set_row_visible(self.chk_loop, True)
            self.on_transmit_change(self.chk_transmit.checkState().value)

    def on_transmit_change(self, state):
        if state == 2 and self.cb_mode.currentIndex() == 2:
            self.set_row_visible(self.cb_interface, True)
            self.set_row_visible(self.txt_channel, True)
            self.set_row_visible(self.cb_bitrate, True)
            self.set_row_visible(self.btn_autodetect, True)
        else:
            if self.cb_mode.currentIndex() == 2:
                self.set_row_visible(self.cb_interface, False)
                self.set_row_visible(self.txt_channel, False)
                self.set_row_visible(self.cb_bitrate, False)
                self.set_row_visible(self.btn_autodetect, False)

    def select_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo de Playback", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_name:
            self.playback_file = file_name
            self.lbl_file.setText(file_name.split("/")[-1])

    def get_config(self):
        mode_str = self.cb_mode.currentText()
        if mode_str == "Hardware Real":
            self.mode = "HARDWARE"
        elif mode_str == "Simulado":
            self.mode = "SIMULATED"
        else:
            self.mode = "PLAYBACK"

        self.interface = self.cb_interface.currentText()
        self.channel = self.txt_channel.text().strip() or "can0"
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
    """Diálogo de anotação. Enter confirma, Shift+Enter pula linha."""

    def __init__(self, parent, target):
        super().__init__(parent)
        self.setWindowTitle("Adicionar Comentário")
        self.resize(400, 200)

        self.layout = QVBoxLayout(self)
        lbl = QLabel(
            f"Comentário para {target}:<br>"
            "<small style='color:#a1a1aa'>(Shift+Enter para pular linha, Enter para Salvar)</small>"
        )
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
