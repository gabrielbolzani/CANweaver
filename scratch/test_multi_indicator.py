import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from src.widget_dialogs import MultiIndicatorDialog
from src.widgets_tab import MultiIndicatorWidget

def test_multi_indicator_dialog_and_widget():
    print("Testando MultiIndicatorDialog e MultiIndicatorWidget...")

    # 1. Testar criação do diálogo sem crash e com área de estados funcional
    dlg = MultiIndicatorDialog(config=None, grid_size=20)
    assert hasattr(dlg, "states_area"), "MultiIndicatorDialog deve possuir states_area inicializada!"
    assert len(dlg._state_rows) == 2, f"Deve iniciar com 2 estados padrão, encontrado {len(dlg._state_rows)}"

    # 2. Testar adição de novo estado
    dlg._add_state_row("Estado 2", "#ef4444", [2] + [None]*7, "Erro Crítico")
    assert len(dlg._state_rows) == 3, "Adicionar novo estado deve aumentar a lista para 3"

    # Atualiza textos auxiliares
    dlg._state_rows[0].txt_aux.setText("Modo Neutro")
    dlg._state_rows[1].txt_aux.setText("Operação Normal")
    dlg.txt_default_aux.setText("Desconhecido")

    cfg = dlg.get_config()
    assert cfg["type"] == "multi_indicator"
    assert len(cfg["states"]) == 3
    assert cfg["states"][0]["label"] == "Estado 0"
    assert cfg["states"][0]["aux_text"] == "Modo Neutro"
    assert cfg["states"][1]["label"] == "Estado 1"
    assert cfg["states"][1]["aux_text"] == "Operação Normal"
    assert cfg["states"][2]["label"] == "Estado 2"
    assert cfg["states"][2]["aux_text"] == "Erro Crítico"
    assert cfg["default_aux_text"] == "Desconhecido"
    print("  [OK] Diálogo permite adicionar novos estados e suporta texto auxiliar com sucesso!")

    # 3. Testar Widget no Modo Texto
    cfg["visual_type"] = "Texto"
    widget_text = MultiIndicatorWidget(None, cfg)
    widget_text.show()
    
    # Estado inicial (default)
    assert widget_text.lbl_display.text() == "??"
    assert widget_text.lbl_aux.text() == "Desconhecido"
    assert not widget_text.lbl_aux.isHidden()

    # Recebe frame para Estado 0 (payload[0] == 0)
    widget_text.process_can_frame(0x100, 10.0, [0, 0, 0, 0, 0, 0, 0, 0])
    assert widget_text.lbl_display.text() == "Estado 0"
    assert widget_text.lbl_aux.text() == "Modo Neutro"
    assert not widget_text.lbl_aux.isHidden()

    # Recebe frame para Estado 2 (payload[0] == 2)
    widget_text.process_can_frame(0x100, 10.0, [2, 0, 0, 0, 0, 0, 0, 0])
    assert widget_text.lbl_display.text() == "Estado 2"
    assert widget_text.lbl_aux.text() == "Erro Crítico"
    assert not widget_text.lbl_aux.isHidden()
    print("  [OK] MultiIndicatorWidget no modo Texto exibe label e texto auxiliar perfeitamente!")

    # 4. Testar Widget no Modo LED
    cfg["visual_type"] = "LED"
    widget_led = MultiIndicatorWidget(None, cfg)
    widget_led.show()
    
    # Inicial
    assert widget_led.lbl_display.text() == "●"
    assert widget_led.lbl_aux.text() == "?? — Desconhecido"
    
    # Frame para Estado 1
    widget_led.process_can_frame(0x100, 10.0, [1, 0, 0, 0, 0, 0, 0, 0])
    assert widget_led.lbl_display.text() == "●"
    assert widget_led.lbl_aux.text() == "Estado 1 — Operação Normal"
    assert "color: #10b981" in widget_led.lbl_display.styleSheet()
    print("  [OK] MultiIndicatorWidget no modo LED exibe círculo colorido e label/auxiliar!")

if __name__ == "__main__":
    test_multi_indicator_dialog_and_widget()
    print("\nTodos os testes do MultiIndicator passaram!")
