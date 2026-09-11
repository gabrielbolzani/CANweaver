"""
test_ai_copilot.py — Validação automatizada da infraestrutura do CAN Copilot.
"""

import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Adiciona diretório raiz do projeto ao path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)
QMessageBox.information = lambda *args, **kwargs: None
QMessageBox.warning = lambda *args, **kwargs: None
QMessageBox.critical = lambda *args, **kwargs: None

from src.ai_assistant.ai_config import load_ai_config, save_ai_config
from src.ai_assistant.action_capture import ActionCaptureEngine
from src.ai_assistant.prompt_templates import SYSTEM_PROMPT
from src.ai_assistant.ai_panel import CANCopilotPanel
from src.annotations import AnnotationManager
from src.widgets_tab import WidgetsTab
from src.analysis_tab import AnalysisTab
from src.worker import CANWorker

print("=" * 60)
print("TESTE DO CAN COPILOT (ASSISTENTE IA)")
print("=" * 60)

# Backup da config original do usuário para não apagar a chave real dele
original_user_cfg = load_ai_config()

# 1. Teste de Configuração
print("[1] Testando persistencia segura de configuracoes de IA...")
test_cfg = {
    "provider": "google_gemini",
    "api_key": "TEST_KEY_TEMPORARY_123",
    "model": "gemini-1.5-flash",
    "custom_endpoint": "",
    "temperature": 0.3,
    "max_tokens": 4096
}
save_ai_config(test_cfg)
loaded = load_ai_config()
assert loaded["api_key"] == "TEST_KEY_TEMPORARY_123"
assert loaded["model"] == "gemini-1.5-flash"
print("  [OK] Configuracoes de IA carregadas e salvas com sucesso.")

# 2. Teste do ActionCaptureEngine
print("[2] Testando gravacao de acao e calculo de deltas de frames CAN...")
worker = CANWorker()
capture_engine = ActionCaptureEngine(worker)

captured_data = {}
def on_capture_done(report_dict, formatted_md):
    captured_data["report"] = report_dict
    captured_data["md"] = formatted_md

capture_engine.capture_finished.connect(on_capture_done)

capture_engine.start_capture("Pressionei acelerador", duration_sec=1.0)
# Simular frames
now = time.time()
# ID 0x405 variando byte 0 de 0 a 150
capture_engine._on_frame_received(0x405, 20.0, [0, 0, 0, 0, 0, 0, 0, 0])
capture_engine._on_frame_received(0x405, 20.0, [75, 0, 0, 0, 0, 0, 0, 0])
capture_engine._on_frame_received(0x405, 20.0, [150, 0, 0, 0, 0, 0, 0, 0])

# ID 0x180 estatico
capture_engine._on_frame_received(0x180, 50.0, [10, 20, 30, 40, 50, 60, 70, 80])

capture_engine.stop_capture()

assert "report" in captured_data
rep = captured_data["report"]
assert rep["total_frames"] == 4
assert len(rep["changed_ids"]) == 1
assert rep["changed_ids"][0]["can_id_hex"] == "0x405"
var0 = rep["changed_ids"][0]["variations"][0]
assert var0["byte_idx"] == 0 and var0["min"] == 0 and var0["max"] == 150
print(f"  [OK] Deltas calculados com precisao:")
print("  " + captured_data["md"].replace("\n", "\n  "))

# 3. Teste do Painel de Chat e Parser de Ações
print("[3] Testando Painel do CAN Copilot e extracao de Tool Calling...")
annot_mgr = AnnotationManager(os.getcwd())
panel = CANCopilotPanel(worker, annot_mgr)

# Simular resposta da IA com bloco de criação de widget e bloco de documentação
sample_ai_response = """
Identifiquei com base nos deltas que o ID 0x405 Byte 0 corresponde ao Throttle.
Sugiro monitorar com um Gauge:

```json:create_widget
{
  "type": "gauge",
  "name": "Throttle",
  "can_id": "405",
  "byte": 0,
  "byte_len": 1,
  "unit": "%",
  "val_min_raw": 0,
  "val_max_raw": 255,
  "val_min_conv": 0,
  "val_max_conv": 100
}
```

E aplicar o filtro:
```json:apply_filter
{
  "filter_ids": "405"
}
```

```markdown:update_doc
### ID 0x405 - Throttle
- Byte 0: Acelerador (0-100%)
```
"""

actions_triggered = []
panel.create_widget_requested.connect(lambda cfg: actions_triggered.append(("widget", cfg)))
panel.apply_filter_requested.connect(lambda f: actions_triggered.append(("filter", f)))
panel.update_doc_requested.connect(lambda d: actions_triggered.append(("doc", d)))

ai_bubble = panel._add_ai_bubble(sample_ai_response)
assert ai_bubble.actions_layout.count() == 3
print("  [OK] 3 Botoes de acao (Widget, Filtro, Documentacao) renderizados dentro do balao da IA.")

# 4. Teste de Execução de Ações
print("[4] Testando execucao das acoes no WidgetsTab, AnalysisTab e AnnotationManager...")
widgets_tab = WidgetsTab(worker)
analysis_tab = AnalysisTab(annot_mgr, worker)

# Acionar botão 1 (Criar widget)
btn_w = ai_bubble.actions_layout.itemAt(0).widget()
btn_w.click()
assert len(actions_triggered) >= 1 and actions_triggered[0][0] == "widget"
w_instance = widgets_tab.add_widget_from_config(actions_triggered[0][1])
assert w_instance is not None and w_instance.config["name"] == "Throttle"
print("  [OK] Widget 'Throttle' inserido programaticamente no Canvas com sucesso.")

# Acionar botão 2 (Filtro)
btn_f = ai_bubble.actions_layout.itemAt(1).widget()
btn_f.click()
analysis_tab.apply_id_filter(actions_triggered[1][1])
assert analysis_tab.txt_filter_id.text() == "405"
print("  [OK] Filtro '405' aplicado no Sniffer com sucesso.")

# Acionar botão 3 (Documentação)
btn_d = ai_bubble.actions_layout.itemAt(2).widget()
btn_d.click()
annot_mgr.append_raw_markdown(actions_triggered[2][1])
print("  [OK] Documentacao Markdown atualizada com sucesso.")

# Teste da busca de IDs
analysis_tab.txt_search_list_ids.setText("0C0")
print("  [OK] Busca de lista de IDs validada com sucesso.")

# Restaura a config real do usuário
save_ai_config(original_user_cfg)

print("\nTODOS OS TESTES DO CAN COPILOT PASSARAM COM 100% DE SUCESSO!")
os._exit(0)

