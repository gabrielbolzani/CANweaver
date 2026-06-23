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
import re
import csv
import time
import ctypes

import can

from PyQt6.QtCore import Qt, QTimer, QDateTime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel,
    QMessageBox, QInputDialog, QLineEdit, QWidget, QHBoxLayout
)
from PyQt6.QtGui import QIcon

from src.worker import CANWorker
from src.dialogs import ConnectionDialog, AboutDialog
from src.annotations import AnnotationManager
from src.analysis_tab import AnalysisTab
from src.transmit_tab import TransmitTab
from src.widgets_tab import WidgetsTab

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CANweaver 0.1b - AI Assisted CAN Reverse Engineering")
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

        # Caminho do projeto aberto (None = nenhum projeto)
        self.current_project_path = None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        from PyQt6.QtWidgets import QTabWidget
        from PyQt6.QtGui import QAction

        menubar = self.menuBar()
        menubar.setStyleSheet(
            "QMenuBar { background-color: #202024; color: white; padding: 0px 4px; }"
            "QMenuBar::item { background: transparent; padding: 5px 14px; border-radius: 4px; }"
            "QMenuBar::item:selected { background-color: #2e3035; }"
            "QMenu { background-color: #202024; color: white; border: 1px solid #323238;"
            "        min-width: 220px; padding: 4px 0px; }"
            "QMenu::item { padding: 6px 20px; }"
            "QMenu::item:selected { background-color: #3b82f6; }"
            "QMenu::item:disabled { color: #52525b; }"
            "QMenu::separator { height: 1px; background: #323238; margin: 4px 8px; }"
        )

        # ── Menu Arquivo ───────────────────────────────────────────────────────
        menu_file = menubar.addMenu("Arquivo")

        action_new = QAction("Novo", self)
        action_new.setShortcut("Ctrl+N")
        action_new.triggered.connect(self._new_project)
        menu_file.addAction(action_new)

        menu_file.addSeparator()

        action_open = QAction("Abrir Projeto (.cwp)...", self)
        action_open.triggered.connect(self._open_project)
        menu_file.addAction(action_open)

        menu_file.addSeparator()

        self.action_save = QAction("Salvar Projeto", self)
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.setEnabled(False)
        self.action_save.triggered.connect(self._save_project)
        menu_file.addAction(self.action_save)

        action_save_as = QAction("Salvar Como...", self)
        action_save_as.setShortcut("Ctrl+Shift+S")
        action_save_as.triggered.connect(self._save_project_as)
        menu_file.addAction(action_save_as)

        # ── Menu Conexão ─────────────────────────────────────────────
        menu_conn = menubar.addMenu("Conexão")

        action_connect = QAction("🔌  Conectar ao Barramento...", self)
        action_connect.triggered.connect(self._open_connection_dialog)
        menu_conn.addAction(action_connect)

        # ── Corner widget: Gravar | Status | Sobre ────────────────────
        corner = QWidget()
        corner.setStyleSheet("background-color: #202024;")
        corner_layout = QHBoxLayout(corner)
        corner_layout.setContentsMargins(0, 0, 8, 0)
        corner_layout.setSpacing(8)

        self.btn_record = QPushButton("⏺  Gravar")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self._toggle_recording)
        self.btn_record.setMinimumWidth(90)
        self.btn_record.setStyleSheet(
            "QPushButton { background-color: #2e3035; color: white; padding: 4px 10px;"
            " border-radius: 4px; font-size: 12px; min-width: 90px; }"
            "QPushButton:checked { background-color: #e83f5b; color: white; }"
        )

        self.lbl_status = QLabel("Desconectado")
        self.lbl_status.setStyleSheet(
            "color: #a1a1aa; font-weight: bold; font-size: 11px; padding: 0 4px;"
        )

        self.btn_about = QPushButton("ℹ️")
        self.btn_about.setToolTip("Sobre o CANweaver")
        self.btn_about.clicked.connect(self._show_about)
        self.btn_about.setStyleSheet(
            "QPushButton { background: transparent; color: #3b82f6; font-size: 16px;"
            " border: none; padding: 0 4px; }"
            "QPushButton:hover { color: #60a5fa; }"
        )

        corner_layout.addWidget(self.btn_record)
        corner_layout.addWidget(self.lbl_status)
        corner_layout.addWidget(self.btn_about)

        menubar.setCornerWidget(corner, Qt.Corner.TopRightCorner)

        # ── Abas ───────────────────────────────────────────────────
        tab_widget = QTabWidget()
        tab_widget.addTab(self.analysis_tab, "Análise (Sniffer)")
        tab_widget.addTab(self.transmit_tab, "Transmitir")
        tab_widget.addTab(self.widgets_tab, "Widgets")
        self.setCentralWidget(tab_widget)

    def _show_about(self):
        from src.dialogs import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Novo Projeto
    # ------------------------------------------------------------------
    def _new_project(self):
        """Limpa toda a sessão atual após confirmação do usuário."""
        reply = QMessageBox.question(
            self, "Novo Projeto",
            "Isso vai apagar todas as abas, widgets, tarefas e anotações da sessão atual.\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Limpa cada aba
        self.analysis_tab.clear_data()
        self.transmit_tab.clear_all()
        self.widgets_tab.clear_all()

        # Apaga anotações da memória e do arquivo
        self.annotation_manager.clear()

        # Reseta o estado do projeto
        self.current_project_path = None
        self.action_save.setEnabled(False)
        self.setWindowTitle("CANweaver v2.0 - AI Assisted CAN Reverse Engineering")
        self.statusBar().showMessage("Novo projeto criado.", 3000)

    # ------------------------------------------------------------------
    # Projeto: Salvar / Abrir
    # ------------------------------------------------------------------
    def _set_project_path(self, path: str):
        """Atualiza o caminho e habilita o menu Salvar."""
        self.current_project_path = path
        self.action_save.setEnabled(True)
        name = os.path.basename(path)
        self.setWindowTitle(f"CANweaver v2.0 — {name}")

    def _collect_project_data(self):
        """Coleta os dados de todas as abas para montar o pacote."""
        import json
        data = {}
        md_path = os.path.join(BASE_DIR, "CANweaver_Projeto.md")
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                data["annotations_md"] = f.read()
        data["transmit_tasks"] = self.transmit_tab.export_data()
        data["dashboard_layout"] = self.widgets_tab.export_data()
        return data

    def _write_project(self, file_path: str, selection: dict):
        """Empacota os dados selecionados e salva no caminho dado."""
        import json, zipfile

        checked = [k for k, v in selection.items() if v]
        full_data = self._collect_project_data()

        # Caso especial: só 1 item — salva diretamente sem ZIP
        if len(checked) == 1:
            key = checked[0]
            if key == "annotations":
                content = full_data.get("annotations_md", "")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            elif key == "transmit":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(full_data["transmit_tasks"], f, indent=4)
            elif key == "dashboard":
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(full_data["dashboard_layout"], f, indent=4)
            return

        # Múltiplos itens — ZIP
        with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if selection.get("annotations") and "annotations_md" in full_data:
                zipf.writestr("CANweaver_Projeto.md", full_data["annotations_md"])
            if selection.get("transmit"):
                zipf.writestr("transmit_tasks.json",
                              json.dumps(full_data["transmit_tasks"], indent=4))
            if selection.get("dashboard"):
                zipf.writestr("dashboard_layout.json",
                              json.dumps(full_data["dashboard_layout"], indent=4))

    def _save_project(self):
        """Salva no caminho já conhecido (sem abrir dialog)."""
        if not self.current_project_path:
            self._save_project_as()
            return
        try:
            # Ao salvar no mesmo arquivo, assume seleção total (era um .cwp)
            sel = {"annotations": True, "transmit": True, "dashboard": True}
            self._write_project(self.current_project_path, sel)
            self.statusBar().showMessage("Projeto salvo.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar:\n{e}")

    def _save_project_as(self):
        """Abre o diálogo completo de exportação."""
        from src.dialogs import ExportDialog
        from PyQt6.QtWidgets import QFileDialog

        default = os.path.splitext(os.path.basename(self.current_project_path))[0] \
            if self.current_project_path else "MeuProjeto"

        dlg = ExportDialog(self, default_name=default)
        if not dlg.exec():
            return

        selection = dlg.get_selection()
        if not any(selection.values()):
            QMessageBox.warning(self, "Aviso", "Nenhuma opção selecionada.")
            return

        checked = [k for k, v in selection.items() if v]
        if len(checked) == 1:
            ext_map = {"annotations": "Markdown (*.md)",
                       "transmit": "JSON (*.json)",
                       "dashboard": "JSON (*.json)"}
            filter_str = ext_map[checked[0]]
        else:
            filter_str = "CANweaver Project (*.cwp)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Projeto", dlg.get_name(), filter_str
        )
        if not file_path:
            return

        try:
            self._write_project(file_path, selection)
            # Só atualiza o projeto "ativo" se salvou como .cwp completo
            if file_path.endswith(".cwp"):
                self._set_project_path(file_path)
            QMessageBox.information(self, "Sucesso",
                                    f"Arquivo salvo em:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar:\n{e}")

    def _open_project(self):
        """Abre um .cwp e restaura o estado de todas as abas."""
        from PyQt6.QtWidgets import QFileDialog
        import json, zipfile

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Projeto", "",
            "CANweaver Project (*.cwp);;Arquivos ZIP (*.zip)"
        )
        if not file_path:
            return

        try:
            with zipfile.ZipFile(file_path, 'r') as zipf:
                names = zipf.namelist()

                if "CANweaver_Projeto.md" in names:
                    md_content = zipf.read("CANweaver_Projeto.md").decode("utf-8")
                    md_path = os.path.join(BASE_DIR, "CANweaver_Projeto.md")
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(md_content)
                    self.annotation_manager.load()

                if "transmit_tasks.json" in names:
                    tasks = json.loads(zipf.read("transmit_tasks.json").decode("utf-8"))
                    self.transmit_tab.import_data(tasks)

                if "dashboard_layout.json" in names:
                    layout = json.loads(zipf.read("dashboard_layout.json").decode("utf-8"))
                    self.widgets_tab.import_data(layout)

            self._set_project_path(file_path)
            QMessageBox.information(self, "Projeto Aberto",
                                    f"Projeto carregado:\n{os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao abrir projeto:\n{e}")

    # Manter compatibilidade com chamada antiga (se houver)
    def _export_project(self):
        self._save_project_as()

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
                    f"{config['interface']} | {config['channel']} @ {config['bitrate']}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Erro de Conexão", f"Não foi possível conectar ao hardware:\n{e}")
                self.lbl_status.setText(f"Erro de Conexão")
                return
        elif config["mode"] == "PLAYBACK":
            if not config["playback_file"]:
                QMessageBox.warning(self, "Aviso", "Nenhum arquivo selecionado.")
                return
            self.can_thread.playback_file = config["playback_file"]
            self.lbl_status.setText(f"Playback: {config['playback_file'].split('/')[-1]}")
        else:
            self.lbl_status.setText("Simulado")

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
            self.lbl_status.setText("Reprodução Finalizada")

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

                old_txt = self.lbl_status.text().replace(" [REC]", "")
                self.lbl_status.setText(old_txt + " [REC]")
                self.record_timer.start(1000)
                self.btn_record.setText("⏹  REC")
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

            self.btn_record.setText("⏺  Gravar")
            self.lbl_status.setText(self.lbl_status.text().replace(" ⏹ 00:00 [REC]", "").replace(" [REC]", ""))

    def _record_frame(self, can_id: int, frequency: float, payload: list):
        if self.is_recording and self.record_writer:
            self.record_writer.writerow([time.time(), f"{can_id:03X}", len(payload)] + list(payload))

    def _update_record_time(self):
        if self.is_recording:
            elapsed = int(time.time() - self.record_start_time)
            mins, secs = divmod(elapsed, 60)
            # Remove tempo anterior e atualiza status
            base = re.sub(r' ⏹ \d+:\d+', '', self.lbl_status.text()).replace(" [REC]", "")
            self.lbl_status.setText(f"{base} ⏹ {mins:02d}:{secs:02d} [REC]")


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
