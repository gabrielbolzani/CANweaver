"""
ai_panel.py — Interface visual do CAN Copilot com balões estilo SMS / Mensagens.
Balões nativos arredondados com cones direcionais (Usuário em azul à direita, IA em cinza à esquerda),
suporte a anexo de arquivos, gravação de ações, streaming de texto e execução de ações.
"""
from __future__ import annotations

import os
import json
import re
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QFrame, QInputDialog,
    QMessageBox, QFileDialog, QScrollArea, QSizePolicy, QComboBox
)
from PyQt6.QtGui import QTextCursor, QFont

from src.ai_assistant.ai_config import load_ai_config, save_ai_config
from src.ai_assistant.ai_dialogs import AIConfigDialog
from src.ai_assistant.ai_client import AICopilotWorker
from src.ai_assistant.action_capture import ActionCaptureEngine


class CANCopilotInput(QTextEdit):
    """QTextEdit que envia com Enter e adiciona nova linha com Shift+Enter."""
    send_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.send_requested.emit()
        else:
            super().keyPressEvent(event)


class UserBubbleWidget(QWidget):
    """Balão de mensagem do Usuário (Azul, à direita, com cone no canto inferior direito)."""
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(40, 4, 8, 4)
        layout.setSpacing(0)
        layout.addStretch()

        self.bubble = QFrame()
        self.bubble.setStyleSheet("""
            QFrame {
                background-color: #0284c7;
                color: #ffffff;
                border-radius: 18px;
                border-bottom-right-radius: 3px;
                padding: 10px 14px;
            }
        """)
        bubble_layout = QVBoxLayout(self.bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(2)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setStyleSheet("color: #ffffff; font-size: 12px; font-weight: 500; background: transparent;")
        bubble_layout.addWidget(lbl)

        layout.addWidget(self.bubble)


class AIBubbleWidget(QWidget):
    """Balão de mensagem da IA (Cinza, à esquerda, com cone no canto inferior esquerdo e suporte a Markdown/Ações)."""
    create_widget_clicked = pyqtSignal(dict)
    apply_filter_clicked = pyqtSignal(str)
    update_doc_clicked = pyqtSignal(str)
    retry_clicked = pyqtSignal()

    def __init__(self, text: str = "", is_streaming: bool = False, parent=None):
        super().__init__(parent)
        self.is_streaming = is_streaming
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 40, 4)
        layout.setSpacing(0)

        self.bubble = QFrame()
        self.bubble.setStyleSheet("""
            QFrame {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 18px;
                border-bottom-left-radius: 3px;
                padding: 10px 14px;
            }
        """)
        self.bubble_layout = QVBoxLayout(self.bubble)
        self.bubble_layout.setContentsMargins(12, 10, 12, 10)
        self.bubble_layout.setSpacing(8)

        # Cabeçalho do Copilot
        self.hdr = QLabel("CAN Copilot")
        self.hdr.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; background: transparent;")
        self.bubble_layout.addWidget(self.hdr)

        # Conteúdo de Texto
        self.lbl_text = QLabel()
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lbl_text.setOpenExternalLinks(True)
        self.lbl_text.setStyleSheet("color: #f4f4f5; font-size: 12px; line-height: 1.5; background: transparent;")
        self.bubble_layout.addWidget(self.lbl_text)

        # Container para botões de ação
        self.actions_box = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_box)
        self.actions_layout.setContentsMargins(0, 4, 0, 0)
        self.actions_layout.setSpacing(6)
        self.actions_box.hide()
        self.bubble_layout.addWidget(self.actions_box)

        layout.addWidget(self.bubble)
        layout.addStretch()

        if text:
            self.set_content(text)

    def set_content(self, text: str):
        # Restaura estilo normal
        self.hdr.setText("CAN Copilot")
        self.hdr.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; background: transparent;")
        self.bubble.setStyleSheet("""
            QFrame {
                background-color: #27272a;
                color: #e4e4e7;
                border: 1px solid #3f3f46;
                border-radius: 18px;
                border-bottom-left-radius: 3px;
                padding: 10px 14px;
            }
        """)

        # Remove blocos de ação do texto visível
        clean_text = re.sub(r'```(?:json:create_widget|json:apply_filter|markdown:update_doc)[\s\S]*?```', '', text).strip()
        
        # Formatação rica básica
        html = clean_text.replace("\n", "<br>")
        html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
        html = re.sub(r'`(.*?)`', r"<code style='background-color: #18181b; padding: 2px 4px; border-radius: 4px; color: #38bdf8; font-family: monospace;'>\1</code>", html)
        self.lbl_text.setText(html)

        # Extrai e renderiza botões de ação
        self._extract_actions(text)

    def set_error(self, err_msg: str, allow_retry: bool = True):
        """Apresenta a mensagem em formato de erro e adiciona botão de retentativa."""
        self.hdr.setText("CAN Copilot • Falha na requisição")
        self.hdr.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold; background: transparent;")
        self.bubble.setStyleSheet("""
            QFrame {
                background-color: #201416;
                color: #fecaca;
                border: 1px solid #7f1d1d;
                border-radius: 18px;
                border-bottom-left-radius: 3px;
                padding: 10px 14px;
            }
        """)

        clean_err = err_msg.replace("\n", "<br>")
        self.lbl_text.setText(f"<span style='color: #fca5a5;'>{clean_err}</span>")

        # Limpa ações anteriores
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if allow_retry:
            btn_retry = QPushButton("🔄 Tentar Novamente")
            btn_retry.setToolTip("Reenviar esta solicitação para o CAN Copilot")
            btn_retry.setStyleSheet("""
                QPushButton {
                    background-color: #dc2626;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #b91c1c;
                }
                QPushButton:pressed {
                    background-color: #991b1b;
                }
            """)
            btn_retry.clicked.connect(self.retry_clicked.emit)
            self.actions_layout.addWidget(btn_retry)
            self.actions_box.show()
        else:
            self.actions_box.hide()

    def _extract_actions(self, full_text: str):
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_actions = False

        # 1. Widget Creation
        for block in re.findall(r'```json:create_widget\s*([\s\S]*?)\s*```', full_text):
            try:
                cfg = json.loads(block)
                w_name = cfg.get("name", "Widget")
                btn = QPushButton(f"+ Inserir '{w_name}' no Dashboard")
                btn.setStyleSheet(
                    "QPushButton { background-color: #10b981; color: white; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 11px; text-align: left; }"
                    "QPushButton:hover { background-color: #059669; }"
                )
                btn.clicked.connect(lambda _, c=cfg: self.create_widget_clicked.emit(c))
                self.actions_layout.addWidget(btn)
                has_actions = True
            except Exception:
                pass

        # 2. Filter Application
        for block in re.findall(r'```json:apply_filter\s*([\s\S]*?)\s*```', full_text):
            try:
                f_cfg = json.loads(block)
                f_ids = f_cfg.get("filter_ids", "")
                if f_ids:
                    btn = QPushButton(f"Aplicar Filtro ({f_ids})")
                    btn.setStyleSheet(
                        "QPushButton { background-color: #0284c7; color: white; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 11px; text-align: left; }"
                        "QPushButton:hover { background-color: #0369a1; }"
                    )
                    btn.clicked.connect(lambda _, ids=f_ids: self.apply_filter_clicked.emit(ids))
                    self.actions_layout.addWidget(btn)
                    has_actions = True
            except Exception:
                pass

        # 3. Documentation Update
        for block in re.findall(r'```markdown:update_doc\s*([\s\S]*?)\s*```', full_text):
            btn = QPushButton("Atualizar Documentação (.md)")
            btn.setStyleSheet(
                "QPushButton { background-color: #8b5cf6; color: white; border: none; border-radius: 6px; padding: 6px 12px; font-weight: bold; font-size: 11px; text-align: left; }"
                "QPushButton:hover { background-color: #7c3aed; }"
            )
            btn.clicked.connect(lambda _, doc=block.strip(): self.update_doc_clicked.emit(doc))
            self.actions_layout.addWidget(btn)
            has_actions = True

        if has_actions:
            self.actions_box.show()


class CANCopilotPanel(QWidget):
    """
    Painel de Chat do CAN Copilot com interface de balões de conversa nativos.
    """
    create_widget_requested = pyqtSignal(dict)
    apply_filter_requested = pyqtSignal(str)
    update_doc_requested = pyqtSignal(str)

    def __init__(self, can_worker_ref=None, annotation_mgr_ref=None, parent=None):
        super().__init__(parent)
        self.can_worker = can_worker_ref
        self.annotation_manager = annotation_mgr_ref
        
        self.history: list[dict] = []
        self.current_worker = None
        self.pending_attachment_text = ""
        self.attached_filename = ""
        self.current_ai_bubble: AIBubbleWidget = None

        self.capture_engine = ActionCaptureEngine(self.can_worker, self)
        self.capture_engine.capture_progress.connect(self._on_capture_progress)
        self.capture_engine.capture_finished.connect(self._on_capture_finished)

        self._build_ui()
        self._populate_model_selector()
        self._update_record_button_text()
        self._set_status("ready", "Pronto")

    def set_worker(self, can_worker_ref):
        """Atualiza a referência do worker CAN e do motor de captura."""
        self.can_worker = can_worker_ref
        if hasattr(self, "capture_engine") and self.capture_engine:
            self.capture_engine.set_worker(can_worker_ref)

    def _set_status(self, kind: str, text: str):
        """Atualiza o status com uma bolinha colorida em HTML universal."""
        colors = {
            "ready": "#22c55e",
            "recording": "#ef4444",
            "thinking": "#eab308",
            "error": "#ef4444",
            "info": "#38bdf8",
        }
        c = colors.get(kind, "#a1a1aa")
        self.lbl_status.setText(f"<span style='color: {c}; font-size: 13px;'>●</span> <span style='color: #d4d4d8;'>{text}</span>")

    def _update_record_button_text(self):
        cfg = load_ai_config()
        duration = float(cfg.get("capture_duration", 3.0))
        self.btn_record_action.setText(f"Gravar Ação ({duration:g}s)")
        self.btn_record_action.setToolTip(f"Grava {duration:g}s do barramento CAN e anexa variações de sinal")

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # ── Toolbar Superior ─────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        title_lbl = QLabel("<b>CAN Copilot</b>")
        title_lbl.setStyleSheet("font-size: 13px; color: #38bdf8; font-weight: bold;")
        
        self.cb_quick_model = QComboBox()
        self.cb_quick_model.setToolTip("Selecione o modelo de IA diretamente")
        self.cb_quick_model.setStyleSheet("""
            QComboBox {
                background-color: #202024;
                color: #38bdf8;
                border: 1px solid #323238;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
                min-width: 140px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
            QComboBox QAbstractItemView {
                background-color: #202024;
                color: #f4f4f5;
                selection-background-color: #0284c7;
                selection-color: white;
                border: 1px solid #323238;
                padding: 4px;
            }
        """)
        self.cb_quick_model.currentTextChanged.connect(self._on_quick_model_changed)

        toolbar.addWidget(title_lbl)
        toolbar.addWidget(self.cb_quick_model)
        toolbar.addStretch()

        self.btn_clear = QPushButton("Limpar")
        self.btn_clear.setToolTip("Limpar histórico da conversa")
        self.btn_clear.setStyleSheet(
            "QPushButton { background-color: #202024; color: #e1e1e6; border: 1px solid #323238; border-radius: 4px; font-size: 11px; padding: 4px 10px; font-weight: 500; }"
            "QPushButton:hover { background-color: #2e3035; color: white; }"
        )
        self.btn_clear.clicked.connect(self.clear_context)

        self.btn_config = QPushButton("Configurar API")
        self.btn_config.setToolTip("Configurar Chave de API, Modelo e Duração")
        self.btn_config.setStyleSheet(
            "QPushButton { background-color: #202024; color: #e1e1e6; border: 1px solid #323238; border-radius: 4px; font-size: 11px; padding: 4px 10px; font-weight: 500; }"
            "QPushButton:hover { background-color: #2e3035; color: white; }"
        )
        self.btn_config.clicked.connect(self._open_config_dialog)

        toolbar.addWidget(self.btn_clear)
        toolbar.addWidget(self.btn_config)

        main_layout.addLayout(toolbar)

        # ── Área de Mensagens (ScrollArea com Balões) ───────────
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #121214;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: #121214;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(6, 10, 6, 10)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll_area, 1)

        # ── Badge de Anexo Pendente ──────────────────────────────
        self.attachment_badge = QFrame()
        self.attachment_badge.setStyleSheet("background-color: #202024; border: 1px solid #0284c7; border-radius: 6px; padding: 4px 8px;")
        att_layout = QHBoxLayout(self.attachment_badge)
        att_layout.setContentsMargins(4, 2, 4, 2)
        att_layout.setSpacing(6)

        self.lbl_att_name = QLabel("Anexo")
        self.lbl_att_name.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        
        self.btn_remove_att = QPushButton("✕")
        self.btn_remove_att.setFixedSize(18, 18)
        self.btn_remove_att.setToolTip("Remover anexo")
        self.btn_remove_att.setStyleSheet(
            "QPushButton { background: transparent; color: #ef4444; border: none; font-weight: bold; font-size: 12px; }"
            "QPushButton:hover { color: #f87171; }"
        )
        self.btn_remove_att.clicked.connect(self._remove_attachment)

        att_layout.addWidget(self.lbl_att_name, 1)
        att_layout.addWidget(self.btn_remove_att)
        self.attachment_badge.hide()
        main_layout.addWidget(self.attachment_badge)

        # ── Barra de Ações: Gravar / Anexar / Status ────────────
        self.record_bar = QFrame()
        self.record_bar.setStyleSheet("background-color: #1a1a1e; border: 1px solid #27272a; border-radius: 6px; padding: 4px;")
        rec_layout = QHBoxLayout(self.record_bar)
        rec_layout.setContentsMargins(4, 2, 4, 2)
        rec_layout.setSpacing(6)

        self.btn_record_action = QPushButton("Gravar Ação (3s)")
        self.btn_record_action.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #f87171; border: 1px solid #451a1a; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background-color: #451a1a; color: white; }"
        )
        self.btn_record_action.clicked.connect(self._prompt_and_record_action)

        self.btn_attach_file = QPushButton("Anexar Arquivo")
        self.btn_attach_file.setToolTip("Anexar arquivo de log, DBC, CSV ou notas (.md, .txt)")
        self.btn_attach_file.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #93c5fd; border: 1px solid #1e3a8a; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px; }"
            "QPushButton:hover { background-color: #1e3a8a; color: white; }"
        )
        self.btn_attach_file.clicked.connect(self._prompt_attach_file)

        self.pbar_capture = QProgressBar()
        self.pbar_capture.setRange(0, 100)
        self.pbar_capture.setValue(0)
        self.pbar_capture.setTextVisible(False)
        self.pbar_capture.setFixedHeight(6)
        self.pbar_capture.setStyleSheet("QProgressBar { background: #27272a; border: none; border-radius: 3px; } QProgressBar::chunk { background: #ef4444; border-radius: 3px; }")
        self.pbar_capture.hide()

        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("color: #a1a1aa; font-size: 11px;")

        rec_layout.addWidget(self.btn_record_action)
        rec_layout.addWidget(self.btn_attach_file)
        rec_layout.addWidget(self.pbar_capture, 1)
        rec_layout.addStretch()
        rec_layout.addWidget(self.lbl_status)

        main_layout.addWidget(self.record_bar)

        # ── Área de Input ────────────────────────────────────────
        input_box = QHBoxLayout()
        input_box.setSpacing(6)

        self.txt_input = CANCopilotInput()
        self.txt_input.setFixedHeight(50)
        self.txt_input.setPlaceholderText("Pergunte ao CAN Copilot (Enter para enviar)...")
        self.txt_input.setStyleSheet("""
            QTextEdit {
                background-color: #18181b;
                color: #ffffff;
                border: 1px solid #323238;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QTextEdit:focus {
                border: 1px solid #0284c7;
            }
        """)
        self.txt_input.send_requested.connect(self.send_message)

        self.btn_send = QPushButton("Enviar")
        self.btn_send.setFixedSize(65, 50)
        self.btn_send.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; font-size: 12px; border-radius: 8px; font-weight: bold; border: none; }"
            "QPushButton:hover { background-color: #0369a1; }"
        )
        self.btn_send.clicked.connect(self.send_message)

        input_box.addWidget(self.txt_input, 1)
        input_box.addWidget(self.btn_send)

        main_layout.addLayout(input_box)

        # Mensagem inicial de boas-vindas
        self._add_welcome_bubble()

    def _add_welcome_bubble(self):
        welcome_text = (
            "**Olá! Sou o CAN Copilot.**\n\n"
            "Estou pronto para ajudar no diagnóstico e engenharia reversa do barramento CAN.\n"
            "• **Grave ações** (ex: pisar no freio) para descobrir IDs e bytes que variam.\n"
            "• **Anexe logs/DBCs** para decodificar mensagens.\n"
            "• **Peça widgets** para serem criados diretamente no seu Dashboard!"
        )
        self._add_ai_bubble(welcome_text)

    def _populate_model_selector(self):
        """Preenche o seletor de modelos na barra do Copilot e seleciona o ativo."""
        cfg = load_ai_config()
        provider = cfg.get("provider", "google_gemini")
        current_model = cfg.get("model", "gemini-3.8-flash").strip().replace("models/", "").replace("google/", "")

        if current_model in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.0-pro-exp-02-05", "gemini-1.0-pro"]:
            current_model = "gemini-3.8-flash"

        gemini_models = [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.1-pro-preview",
            "gemini-3.1-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.5-flash-lite",
        ]
        openai_models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"]

        models = list(gemini_models) if provider == "google_gemini" else list(openai_models)

        if current_model and current_model not in models:
            models.append(current_model)

        self.cb_quick_model.blockSignals(True)
        self.cb_quick_model.clear()
        self.cb_quick_model.addItems(models)
        self.cb_quick_model.setCurrentText(current_model)
        self.cb_quick_model.blockSignals(False)

    def _on_quick_model_changed(self, new_model: str):
        """Salva a alteração de modelo feita diretamente na barra do Copilot."""
        if not new_model:
            return
        clean_model = new_model.strip().replace("models/", "").replace("google/", "")
        cfg = load_ai_config()
        cfg["model"] = clean_model
        save_ai_config(cfg)
        self._set_status("ready", f"Modelo: {clean_model}")

    def _open_config_dialog(self):
        dlg = AIConfigDialog(self)
        if dlg.exec():
            self._populate_model_selector()
            self._update_record_button_text()

    def clear_context(self):
        """Limpa o histórico e os balões da conversa."""
        self.history.clear()
        self._remove_attachment()
        
        # Remove todos os balões
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._add_welcome_bubble()
        self._set_status("ready", "Contexto Limpo")

    def _prompt_attach_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Anexar Arquivo para o CAN Copilot",
            "",
            "Arquivos Suportados (*.csv *.txt *.md *.json *.dbc *.log *.cwp);;Todos os Arquivos (*.*)"
        )
        if not file_path:
            return

        try:
            file_size_kb = os.path.getsize(file_path) / 1024.0
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(100 * 1024)
                if f.read(1):
                    content += "\n... [conteúdo truncado para os primeiros 100 KB] ..."

            base_name = os.path.basename(file_path)
            self.attached_filename = base_name
            self.pending_attachment_text = f"### Arquivo Anexado: `{base_name}` ({file_size_kb:.1f} KB)\n```\n{content}\n```"
            
            self.lbl_att_name.setText(f"{base_name} ({file_size_kb:.1f} KB)")
            self.attachment_badge.show()
            self.txt_input.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Anexar", f"Não foi possível ler o arquivo selecionado:\n{e}")

    def _remove_attachment(self):
        self.pending_attachment_text = ""
        self.attached_filename = ""
        self.attachment_badge.hide()

    def _prompt_and_record_action(self):
        if not self.can_worker or not getattr(self.can_worker, 'running', False):
            QMessageBox.warning(
                self, "Barramento Desconectado",
                "O CANweaver não está conectado a um barramento CAN ativo.\n\n"
                "Por favor, conecte-se a uma interface real (ou selecione Modo Simulado) em:\n"
                "Conexão -> Conectar ao Barramento... antes de gravar ações."
            )
            return

        cfg = load_ai_config()
        duration = float(cfg.get("capture_duration", 3.0))

        desc, ok = QInputDialog.getText(
            self, "Gravar Ação para IA",
            f"Descreva a ação física que você vai realizar nos próximos {duration:g} segundos:\n(Ex: 'Pisar no pedal de freio', 'Ligar a seta esquerda')"
        )
        if ok and desc.strip():
            self.btn_record_action.setEnabled(False)
            self.btn_record_action.setText(f"Gravando ({duration:g}s)...")
            self.pbar_capture.show()
            self._set_status("recording", f"Gravando {duration:g}s...")
            self.capture_engine.start_capture(description=desc.strip(), duration_sec=duration)

    def _on_capture_progress(self, progress: float):
        self.pbar_capture.setValue(int(progress * 100))

    def _on_capture_finished(self, report_dict: dict, formatted_md: str):
        self.pbar_capture.hide()
        self.btn_record_action.setEnabled(True)
        self._update_record_button_text()
        self._set_status("info", f"{report_dict['total_frames']} frames capturados")

        self.pending_attachment_text = formatted_md
        self.attached_filename = f"Ação: {report_dict.get('description', 'Captura')}"
        self.lbl_att_name.setText(f"Relatório de Ação ({report_dict['total_frames']} frames | {report_dict.get('description', '')})")
        self.attachment_badge.show()
        
        current_text = self.txt_input.toPlainText().strip()
        if not current_text:
            self.txt_input.setText(f"Analise o que mudou no barramento quando eu '{report_dict['description']}'.")
        self.txt_input.setFocus()

    def _add_user_bubble(self, text: str):
        bubble = UserBubbleWidget(text, self)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()

    def _add_ai_bubble(self, text: str = "") -> AIBubbleWidget:
        bubble = AIBubbleWidget(text, is_streaming=False, parent=self)
        bubble.create_widget_clicked.connect(self._trigger_create_widget)
        bubble.apply_filter_clicked.connect(self._trigger_apply_filter)
        bubble.update_doc_clicked.connect(self._trigger_update_doc)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        self._scroll_to_bottom()
        return bubble

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum()))

    def send_message(self):
        user_text = self.txt_input.toPlainText().strip()
        if not user_text and not self.pending_attachment_text:
            return

        if self.current_worker and self.current_worker.isRunning():
            return

        full_user_content = user_text
        if self.pending_attachment_text:
            full_user_content = f"{user_text}\n\n{self.pending_attachment_text}" if user_text else self.pending_attachment_text

        display_text = user_text
        if self.attached_filename:
            display_text = f"[{self.attached_filename}]\n{user_text}" if user_text else f"[{self.attached_filename}]"

        self._remove_attachment()
        self.txt_input.clear()

        # Adiciona balão do usuário na tela
        self._add_user_bubble(display_text)

        # Adiciona à história
        self.history.append({"role": "user", "content": full_user_content})

        # Prepara contexto extra (documentação atual do projeto se houver)
        extra_context = ""
        if self.annotation_manager and hasattr(self.annotation_manager, "filename"):
            try:
                if os.path.exists(self.annotation_manager.filename):
                    with open(self.annotation_manager.filename, "r", encoding="utf-8") as f:
                        extra_context = f"Anotações do Projeto Atual (.md):\n```markdown\n{f.read()}\n```"
            except Exception:
                pass

        # Cria balão de resposta da IA
        self.current_ai_bubble = self._add_ai_bubble("<i>Digitando...</i>")
        self._set_status("thinking", "Pensando...")
        self.btn_send.setEnabled(False)

        self.current_worker = AICopilotWorker(self.history, extra_context=extra_context, parent=self)
        self.current_worker.response_finished.connect(self._on_response_finished)
        self.current_worker.error_occurred.connect(self._on_error_occurred)
        self.current_worker.start()

    def _on_response_finished(self, full_response: str):
        self.history.append({"role": "model", "content": full_response})
        self.btn_send.setEnabled(True)
        self._set_status("ready", "Pronto")

        if self.current_ai_bubble:
            self.current_ai_bubble.set_content(full_response)
        self._scroll_to_bottom()

    def _on_error_occurred(self, err_msg: str):
        self.btn_send.setEnabled(True)
        self._set_status("error", "Erro na Requisição")
        if self.current_ai_bubble:
            bubble = self.current_ai_bubble
            bubble.set_error(err_msg, allow_retry=True)
            try:
                bubble.retry_clicked.disconnect()
            except Exception:
                pass
            bubble.retry_clicked.connect(lambda b=bubble: self._on_retry_message(b))
        self._scroll_to_bottom()

    def _on_retry_message(self, bubble: AIBubbleWidget):
        """Reenvia a mensagem anterior para o Copilot sem necessidade de redigitar."""
        if self.current_worker and self.current_worker.isRunning():
            return
        if not self.history:
            return

        extra_context = ""
        if self.annotation_manager and hasattr(self.annotation_manager, "filename"):
            try:
                if os.path.exists(self.annotation_manager.filename):
                    with open(self.annotation_manager.filename, "r", encoding="utf-8") as f:
                        extra_context = f"Anotações do Projeto Atual (.md):\n```markdown\n{f.read()}\n```"
            except Exception:
                pass

        self.current_ai_bubble = bubble
        self.current_ai_bubble.set_content("<i>Tentando novamente...</i>")
        self._set_status("thinking", "Tentando novamente...")
        self.btn_send.setEnabled(False)

        self.current_worker = AICopilotWorker(self.history, extra_context=extra_context, parent=self)
        self.current_worker.response_finished.connect(self._on_response_finished)
        self.current_worker.error_occurred.connect(self._on_error_occurred)
        self.current_worker.start()

    def _trigger_create_widget(self, config: dict):
        self.create_widget_requested.emit(config)
        QMessageBox.information(self, "Sucesso", f"Widget '{config.get('name', 'Novo Widget')}' inserido com sucesso no Dashboard!")

    def _trigger_apply_filter(self, filter_ids: str):
        self.apply_filter_requested.emit(filter_ids)
        QMessageBox.information(self, "Filtro Aplicado", f"Filtro '{filter_ids}' aplicado com sucesso!")

    def _trigger_update_doc(self, new_doc_content: str):
        self.update_doc_requested.emit(new_doc_content)
        QMessageBox.information(self, "Documentação Atualizada", "As anotações do projeto foram atualizadas com sucesso!")
