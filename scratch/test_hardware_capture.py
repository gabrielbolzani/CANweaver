"""
scratch/test_hardware_capture.py — Validação do fluxo de troca de worker e configuração de gravação.
"""

import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from src.ai_assistant.ai_config import load_ai_config, save_ai_config, DEFAULT_CONFIG
from src.ai_assistant.action_capture import ActionCaptureEngine
from src.ai_assistant.ai_panel import CANCopilotPanel
from src.worker import CANWorker

print("=" * 60)
print("TESTE: Troca de Worker (CANable/Hardware) e Configuração de Duração")
print("=" * 60)

# 1. Testar configuração de capture_duration
print("[1] Testando configuração de capture_duration...")
cfg = load_ai_config()
cfg["capture_duration"] = 5.5
save_ai_config(cfg)
loaded = load_ai_config()
assert loaded["capture_duration"] == 5.5, f"Esperado 5.5, obtido {loaded.get('capture_duration')}"
print("  [OK] capture_duration persistido com sucesso (5.5s)")

# 2. Testar troca de worker dinâmico (Simulando conexão CANable)
print("[2] Testando propagação de worker para CANCopilotPanel...")
initial_worker = CANWorker()
initial_worker.mode = "IDLE"

panel = CANCopilotPanel(initial_worker)
assert panel.can_worker is initial_worker
assert panel.capture_engine.can_worker is initial_worker

# Agora simula o que o main.py faz ao conectar com CANable:
new_hardware_worker = CANWorker()
new_hardware_worker.mode = "HARDWARE"
panel.set_worker(new_hardware_worker)

assert panel.can_worker is new_hardware_worker, "Painel não atualizou o can_worker!"
assert panel.capture_engine.can_worker is new_hardware_worker, "Capture engine não recebeu o novo worker!"
print("  [OK] set_worker propagou o novo worker para o painel e o engine de captura!")

# 3. Testar captura através do novo worker
print("[3] Testando captura com o novo worker...")
captured = {}
def on_done(report, md):
    captured["report"] = report
    captured["md"] = md

panel.capture_engine.capture_finished.connect(on_done)
panel.capture_engine.start_capture("Teste de freio", duration_sec=1.0)

# Emite frame do NOVO worker (hardware)
new_hardware_worker.frame_received.emit(0x120, 50.0, [1, 2, 3, 4, 5, 6, 7, 8])
new_hardware_worker.frame_received.emit(0x120, 50.0, [1, 2, 3, 4, 5, 6, 7, 9]) # byte 7 variou
panel.capture_engine.stop_capture()

assert "report" in captured
assert captured["report"]["total_frames"] == 2
assert len(captured["report"]["changed_ids"]) == 1
print("  [OK] Frames recebidos pelo novo worker capturados com sucesso! Total:", captured["report"]["total_frames"])

# 4. Testar tratamento de 0 frames (quando barramento está mudo)
print("[4] Testando diagnóstico para 0 frames...")
captured_empty = {}
def on_empty_done(report, md):
    captured_empty["report"] = report
    captured_empty["md"] = md

panel.capture_engine.capture_finished.disconnect()
panel.capture_engine.capture_finished.connect(on_empty_done)
panel.capture_engine.start_capture("Tentativa vazia", duration_sec=1.0)
panel.capture_engine.stop_capture()

assert captured_empty["report"]["total_frames"] == 0
assert "Nenhum frame CAN foi recebido" in captured_empty["md"]
print("  [OK] Mensagem clara de diagnóstico gerada quando 0 frames são capturados:")
print("  " + captured_empty["md"].replace("\n", "\n  "))

print("=" * 60)
print("TODOS OS TESTES PASSARAM COM SUCESSO!")
print("=" * 60)
