"""
ai_config.py — Gerenciamento e armazenamento seguro de configurações de IA (chaves de API, modelos).
Salvo localmente na máquina do usuário (~/.canweaver/ai_config.json) para que nunca seja enviado ao Git.
"""

import os
import json

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".canweaver")
CONFIG_FILE = os.path.join(CONFIG_DIR, "ai_config.json")

DEFAULT_CONFIG = {
    "provider": "google_gemini",
    "api_key": "",
    "model": "gemini-1.5-flash",
    "custom_endpoint": "",
    "temperature": 0.3,
    "max_tokens": 4096
}

def load_ai_config() -> dict:
    """Carrega as configurações de IA salvas localmente com migração automática de modelos."""
    res = DEFAULT_CONFIG.copy()
    loaded_dict = None

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded_dict = json.load(f)
        except Exception:
            pass
    elif os.path.exists("ai_config.json"):
        try:
            with open("ai_config.json", "r", encoding="utf-8") as f:
                loaded_dict = json.load(f)
        except Exception:
            pass

    if loaded_dict:
        res.update(loaded_dict)

    # Limpa prefixos caso existam
    if res.get("model"):
        res["model"] = res["model"].strip().replace("models/", "")

    return res

def save_ai_config(config_data: dict) -> bool:
    """Salva as configurações de IA no diretório do usuário com segurança."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Erro ao salvar configurações de IA em {CONFIG_FILE}: {e}")
        # Fallback local
        try:
            with open("ai_config.json", "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
            return True
        except Exception as e2:
            print(f"Erro no fallback local: {e2}")
            return False
