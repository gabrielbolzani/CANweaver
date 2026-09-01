"""
ai_dialogs.py — Diálogo de configuração de chaves de API e modelos para o CAN Copilot.
"""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QMessageBox, QFrame, QFormLayout,
    QDoubleSpinBox
)
from PyQt6.QtGui import QDesktopServices

from src.ai_assistant.ai_config import load_ai_config, save_ai_config


class AIConfigDialog(QDialog):
    """Diálogo modal para configurar Chave de API, Provedor e Modelo do CAN Copilot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar CAN Copilot (Inteligência Artificial)")
        self.resize(500, 380)

        self.cfg = load_ai_config()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Cabeçalho explicativo
        hdr = QLabel("🤖 <b>CAN Copilot — Configuração de IA</b>")
        hdr.setStyleSheet("font-size: 14px; color: #38bdf8;")
        
        info = QLabel(
            "Configure sua chave de API para habilitar assistência inteligente em tempo real, "
            "análise de deltas de sinal, sugestão de widgets e documentação de engenharia reversa.<br>"
            "<i>Nota: Sua chave é salva exclusivamente na sua máquina e nunca é enviada ao Git.</i>"
        )
        info.setStyleSheet("color: #a1a1aa; font-size: 11px;")
        info.setWordWrap(True)

        layout.addWidget(hdr)
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #323238;")
        layout.addWidget(sep)

        # Formulário
        form = QFormLayout()
        form.setSpacing(8)

        # Provedor
        self.cb_provider = QComboBox()
        self.cb_provider.addItem("Google Gemini (Recomendado - Gratuito/Ultra Rápido)", "google_gemini")
        self.cb_provider.addItem("OpenAI (GPT-4o, GPT-4o-mini)", "openai")
        self.cb_provider.addItem("Endpoint Customizado / Local (Compatível com OpenAI)", "custom")

        cur_provider = self.cfg.get("provider", "google_gemini")
        idx = self.cb_provider.findData(cur_provider)
        if idx >= 0:
            self.cb_provider.setCurrentIndex(idx)
        self.cb_provider.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provedor de IA:", self.cb_provider)

        # Chave de API com botão de visualização
        key_layout = QHBoxLayout()
        self.txt_api_key = QLineEdit(self.cfg.get("api_key", ""))
        self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_api_key.setPlaceholderText("Cole sua Chave de API aqui...")

        self.btn_toggle_echo = QPushButton("👁️")
        self.btn_toggle_echo.setFixedWidth(36)
        self.btn_toggle_echo.setToolTip("Exibir/Ocultar chave")
        self.btn_toggle_echo.clicked.connect(self._toggle_echo)

        key_layout.addWidget(self.txt_api_key, 1)
        key_layout.addWidget(self.btn_toggle_echo)
        form.addRow("Chave de API (Key):", key_layout)

        # Link para obter chave
        link_layout = QHBoxLayout()
        self.btn_get_key = QPushButton("🔗 Obter Chave Gratuita do Google AI Studio")
        self.btn_get_key.setStyleSheet(
            "QPushButton { background: transparent; color: #60a5fa; text-decoration: underline; border: none; text-align: left; }"
            "QPushButton:hover { color: #93c5fd; }"
        )
        self.btn_get_key.clicked.connect(self._open_key_url)
        link_layout.addWidget(self.btn_get_key)
        link_layout.addStretch()
        form.addRow("", link_layout)

        # Modelo
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        form.addRow("Modelo:", self.cb_model)

        # Endpoint Customizado (visível se custom/openai)
        self.txt_custom_endpoint = QLineEdit(self.cfg.get("custom_endpoint", ""))
        self.txt_custom_endpoint.setPlaceholderText("Ex: http://localhost:11434/v1 ou https://api.openai.com/v1")
        form.addRow("Endpoint URL:", self.txt_custom_endpoint)

        # Temperatura (Criatividade)
        self.sp_temp = QDoubleSpinBox()
        self.sp_temp.setRange(0.0, 1.0)
        self.sp_temp.setSingleStep(0.1)
        self.sp_temp.setValue(float(self.cfg.get("temperature", 0.3)))
        form.addRow("Temperatura (0=Determinístico, 1=Criativo):", self.sp_temp)

        layout.addLayout(form)

        # Atualiza lista de modelos para o provedor selecionado
        self._on_provider_changed()

        layout.addStretch()

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #323238;")
        layout.addWidget(sep2)

        # Botões de Ação
        btn_row = QHBoxLayout()
        self.btn_test = QPushButton("⚡ Testar Conexão")
        self.btn_test.setStyleSheet(
            "QPushButton { background-color: #1e3a5f; color: #93c5fd; padding: 6px 14px; border: 1px solid #1d4ed8; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1d4ed8; color: white; }"
        )
        self.btn_test.clicked.connect(self._test_connection)

        btn_save = QPushButton("Salvar Configurações")
        btn_save.setStyleSheet(
            "QPushButton { background-color: #10b981; color: white; padding: 6px 14px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #059669; }"
        )
        btn_save.clicked.connect(self._save_and_accept)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(self.btn_test)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_cancel)

        layout.addLayout(btn_row)

    def _toggle_echo(self):
        if self.txt_api_key.echoMode() == QLineEdit.EchoMode.Password:
            self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.txt_api_key.setEchoMode(QLineEdit.EchoMode.Password)

    def _open_key_url(self):
        provider = self.cb_provider.currentData()
        if provider == "google_gemini":
            QDesktopServices.openUrl(QUrl("https://aistudio.google.com/app/apikey"))
        else:
            QDesktopServices.openUrl(QUrl("https://platform.openai.com/api-keys"))

    def _on_provider_changed(self):
        provider = self.cb_provider.currentData()
        self.cb_model.clear()

        if provider == "google_gemini":
            models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3.6-flash"]
            self.cb_model.addItems(models)
            self.btn_get_key.setText("🔗 Obter Chave Gratuita do Google AI Studio (Gemini)")
            self.txt_custom_endpoint.setEnabled(False)
            self.txt_custom_endpoint.setPlaceholderText("Padrão: Google AI Studio API Endpoint")
        elif provider == "openai":
            models = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o3-mini"]
            self.cb_model.addItems(models)
            self.btn_get_key.setText("🔗 Obter Chave no OpenAI Platform")
            self.txt_custom_endpoint.setEnabled(False)
            self.txt_custom_endpoint.setPlaceholderText("Padrão: https://api.openai.com/v1")
        else:
            models = ["llama-3.3-70b", "deepseek-r1", "mistral-large", "qwen-2.5-coder", "custom-model"]
            self.cb_model.addItems(models)
            self.btn_get_key.setText("🔗 Ver documentação do endpoint customizado")
            self.txt_custom_endpoint.setEnabled(True)
            self.txt_custom_endpoint.setPlaceholderText("Ex: http://localhost:11434/v1")

        saved_model = self.cfg.get("model", "")
        if saved_model:
            self.cb_model.setCurrentText(saved_model.replace("models/", ""))

    def _test_connection(self):
        api_key = self.txt_api_key.text().strip()
        provider = self.cb_provider.currentData()
        model = self.cb_model.currentText().strip().replace("models/", "")
        endpoint = self.txt_custom_endpoint.text().strip()

        if not api_key and provider != "custom":
            QMessageBox.warning(self, "Aviso", "Por favor, insira uma Chave de API para testar.")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("⏳ Testando...")

        # Teste rápido assíncrono / direto usando urllib
        try:
            import urllib.request
            import json

            if provider == "google_gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json", "User-Agent": "CANweaver/2.0"}
                body = {
                    "contents": [{"parts": [{"text": "Responda apenas: OK"}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                }
                req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    QMessageBox.information(self, "Sucesso", f"Conexão com Google Gemini ({model}) validada com sucesso!\nResposta: {text}")
            else:
                base_url = endpoint if endpoint else "https://api.openai.com/v1"
                url = f"{base_url.rstrip('/')}/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                body = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Responda apenas: OK"}],
                    "max_tokens": 10
                }
                req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["choices"][0]["message"]["content"].strip()
                    QMessageBox.information(self, "Sucesso", f"Conexão com {provider} ({model}) validada com sucesso!\nResposta: {text}")
        except Exception as e:
            QMessageBox.critical(self, "Erro de Conexão", f"Falha ao conectar com o serviço de IA:\n{e}")
        finally:
            self.btn_test.setEnabled(True)
            self.btn_test.setText("⚡ Testar Conexão")

    def _save_and_accept(self):
        data = {
            "provider": self.cb_provider.currentData(),
            "api_key": self.txt_api_key.text().strip(),
            "model": self.cb_model.currentText().strip(),
            "custom_endpoint": self.txt_custom_endpoint.text().strip(),
            "temperature": self.sp_temp.value(),
            "max_tokens": 4096
        }
        if save_ai_config(data):
            self.accept()
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível salvar as configurações de IA.")
