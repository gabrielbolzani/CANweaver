"""
ai_client.py — Cliente assíncrono de IA (QThread) com suporte a streaming de respostas para Google Gemini e OpenAI.
Sem dependências pesadas externas (usa urllib da biblioteca padrão).
"""

import json
import urllib.request
import urllib.error
import ssl
from PyQt6.QtCore import QThread, pyqtSignal

from src.ai_assistant.ai_config import load_ai_config
from src.ai_assistant.prompt_templates import SYSTEM_PROMPT


class AICopilotWorker(QThread):
    """
    Thread de execução assíncrona para requisições com a API de IA.
    Emite sinais de streaming de tokens para atualização fluida da interface.
    """
    token_received = pyqtSignal(str)       # Cada pedaço de texto gerado em streaming
    response_finished = pyqtSignal(str)    # Resposta completa consolidada
    error_occurred = pyqtSignal(str)       # Mensagem de erro

    def __init__(self, history: list[dict], extra_context: str = "", parent=None):
        super().__init__(parent)
        self.history = history.copy()
        self.extra_context = extra_context
        self.cfg = load_ai_config()

    def run(self):
        provider = self.cfg.get("provider", "google_gemini")
        api_key = self.cfg.get("api_key", "").strip()
        model = self.cfg.get("model", "gemini-2.0-flash").strip()
        temperature = float(self.cfg.get("temperature", 0.3))

        if not api_key and provider != "custom":
            self.error_occurred.emit(
                "Chave de API não configurada. Acesse o menu '🤖 CAN Copilot -> Configurar Chave de API' para inserir sua chave."
            )
            return

        try:
            if provider == "google_gemini":
                self._run_gemini(api_key, model, temperature)
            else:
                self._run_openai_compatible(api_key, model, temperature)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)
            self.error_occurred.emit(f"Erro HTTP {e.code}: {msg}")
        except (TimeoutError, urllib.error.URLError) as e:
            err_str = str(e)
            if "timed out" in err_str.lower():
                self.error_occurred.emit("Tempo limite esgotado (Timeout). O servidor de IA demorou para responder. Tente novamente ou use o modelo 'gemini-1.5-flash'.")
            else:
                self.error_occurred.emit(f"Erro de conexão com a rede: {e}")
        except Exception as e:
            self.error_occurred.emit(f"Erro na comunicação com a IA: {e}")

    def _run_gemini(self, api_key: str, model: str, temperature: float):
        clean_model = model.strip().replace("models/", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CANweaver/2.0"
        }

        # Sanitiza e mescla mensagens consecutivas com o mesmo papel (exigência da API do Gemini)
        contents = []
        full_system = SYSTEM_PROMPT
        if self.extra_context:
            full_system += f"\n\n### Contexto Adicional do Projeto Atual:\n{self.extra_context}"

        for msg in self.history:
            role = "user" if msg["role"] == "user" else "model"
            txt = msg.get("content", "").strip()
            if not txt:
                continue

            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"][0]["text"] += f"\n\n{txt}"
            else:
                contents.append({
                    "role": role,
                    "parts": [{"text": txt}]
                })

        if not contents:
            self.error_occurred.emit("Nenhuma mensagem para enviar.")
            return

        # Garante que a primeira mensagem seja do usuário
        if contents[0]["role"] != "user":
            contents.insert(0, {"role": "user", "parts": [{"text": "Olá."}]})

        body = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": full_system}]
            },
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 4096
            }
        }

        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if not candidates:
                self.error_occurred.emit("A IA não retornou nenhuma resposta.")
                return

            parts = candidates[0].get("content", {}).get("parts", [])
            full_text = "".join([p.get("text", "") for p in parts])
            
            # Emite resposta
            self.token_received.emit(full_text)
            self.response_finished.emit(full_text)

    def _run_openai_compatible(self, api_key: str, model: str, temperature: float):
        endpoint = self.cfg.get("custom_endpoint", "").strip()
        base_url = endpoint if endpoint else "https://api.openai.com/v1"
        url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        messages = []
        full_system = SYSTEM_PROMPT
        if self.extra_context:
            full_system += f"\n\n### Contexto Adicional do Projeto Atual:\n{self.extra_context}"

        messages.append({"role": "system", "content": full_system})

        for msg in self.history:
            txt = msg.get("content", "").strip()
            if txt:
                messages.append({"role": msg["role"], "content": txt})

        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096
        }

        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if not choices:
                self.error_occurred.emit("A IA não retornou nenhuma resposta.")
                return
            full_text = choices[0].get("message", {}).get("content", "")
            self.token_received.emit(full_text)
            self.response_finished.emit(full_text)

