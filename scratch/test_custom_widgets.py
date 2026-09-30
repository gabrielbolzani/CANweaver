import sys
import os

# Adiciona raiz do projeto ao sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from src.custom_widget_api import (
    list_available_custom_widgets,
    load_custom_widget_class_from_file,
    get_custom_widgets_directory
)
from src.widgets_tab import WidgetsTab, CustomPythonDashboardWidget
from src.worker import CANWorker

def test_discovery():
    print("[1] Testando descoberta de widgets customizados...")
    widgets = list_available_custom_widgets()
    assert len(widgets) >= 2, f"Esperado >= 2 widgets, encontrado {len(widgets)}"
    names = [w["name"] for w in widgets]
    print(f"    Widgets encontrados: {names}")
    assert any("OBD" in n or "Scanner" in n for n in names), "Scanner OBD-II não encontrado"
    assert any("Modelo" in n or "Template" in n for n in names), "Widget Template não encontrado"
    print("    [OK] Descoberta funcionando!")

def test_obd2_extended_sensors_and_flow():
    print("[2] Testando sensores expandidos OBD-II (RPM, Bateria, Combustível, MAF, Consumo)...")
    custom_dir = get_custom_widgets_directory()
    obd2_path = os.path.join(custom_dir, "obd2_widget.py")

    worker = CANWorker()
    worker.mode = "SIMULATED"
    tab = WidgetsTab(worker)

    cfg = {
        "type": "custom_python",
        "script_path": obd2_path,
        "width": 460,
        "height": 420
    }
    w = CustomPythonDashboardWidget(tab.canvas, cfg, worker)
    tab._place_widget(w, tab.canvas.pos())

    assert w.custom_widget is not None, "custom_widget não foi instanciado!"
    assert w._error_msg is None, f"Erro inesperado: {w._error_msg}"
    print(f"    Widget instanciado: {w.custom_widget.WIDGET_NAME}")

    # 1. RPM = 2500 -> raw = 10000 -> 0x2710 -> A=0x27, B=0x10
    tab._broadcast_can_frame(0x7E8, 10.0, [0x04, 0x41, 0x0C, 0x27, 0x10, 0, 0, 0])
    rpm_txt = w.custom_widget.lbl_val_rpm.text()
    assert "2,500" in rpm_txt or "2500" in rpm_txt, f"Erro no RPM: {rpm_txt}"
    print(f"    [OK] RPM decodificado: {rpm_txt}")

    # 2. Tensão Bateria = 14.2V (PID 0x42) -> raw = 14200 -> 0x3778 -> A=0x37, B=0x78
    tab._broadcast_can_frame(0x7E8, 2.0, [0x04, 0x41, 0x42, 0x37, 0x78, 0, 0, 0])
    bat_txt = w.custom_widget.lbl_val_bat.text()
    assert "14.2" in bat_txt, f"Erro na Bateria: {bat_txt}"
    print(f"    [OK] Tensão Bateria decodificada: {bat_txt}")

    # 3. Nível de Combustível = 80% (PID 0x2F) -> A = 204
    tab._broadcast_can_frame(0x7E8, 1.0, [0x03, 0x41, 0x2F, 204, 0, 0, 0, 0])
    fuel_txt = w.custom_widget.lbl_val_fuel.text()
    assert "80.0" in fuel_txt, f"Erro no Combustível: {fuel_txt}"
    print(f"    [OK] Nível de Combustível decodificado: {fuel_txt}")

    # 4. Velocidade = 80 km/h (PID 0x0D) e MAF = 20.0 g/s (PID 0x10) -> raw = 2000 -> 0x07D0
    tab._broadcast_can_frame(0x7E8, 10.0, [0x03, 0x41, 0x0D, 80, 0, 0, 0, 0])
    tab._broadcast_can_frame(0x7E8, 5.0, [0x04, 0x41, 0x10, 0x07, 0xD0, 0, 0, 0])
    cons_txt = w.custom_widget.lbl_val_cons.text()
    print(f"    [OK] Consumo calculado a 80 km/h com MAF 20 g/s: {cons_txt}")
    assert "km/L" in cons_txt

def test_signal_finder_correlation():
    print("[3] Testando Motor de Engenharia Reversa (CAN Signal Finder)...")
    custom_dir = get_custom_widgets_directory()
    obd2_path = os.path.join(custom_dir, "obd2_widget.py")

    worker = CANWorker()
    tab = WidgetsTab(worker)

    cfg = {"type": "custom_python", "script_path": obd2_path}
    w = CustomPythonDashboardWidget(tab.canvas, cfg, worker)
    tab._place_widget(w, tab.canvas.pos())

    # Ativa o Signal Finder buscando Velocidade
    w.custom_widget.cb_reference_signal.setCurrentIndex(0)  # speed
    w.custom_widget.toggle_signal_finder(True)

    # Injeta 25 frames simulando subida e descida de velocidade
    # O sinal OBD dá a velocidade de 0 a 100 km/h
    # Simultaneamente, injeta ID proprietário 0x280 com a velocidade multiplicada por 100 nos bytes 2-3 (Big Endian)
    for speed_val in range(20, 45):
        # 1. OBD-II ground truth
        w.custom_widget.on_can_frame(0x7E8, 10.0, [0x03, 0x41, 0x0D, speed_val, 0, 0, 0, 0])
        # 2. Tráfego proprietário 0x280 (Velocidade * 100)
        raw_val = speed_val * 100
        sp_h, sp_l = (raw_val >> 8) & 0xFF, raw_val & 0xFF
        w.custom_widget.on_can_frame(0x280, 20.0, [0x01, 0x02, sp_h, sp_l, 0x55, 0xAA, 0, 0])
        # 3. Tráfego de ruído aleatório
        w.custom_widget.on_can_frame(0x350, 10.0, [10, 20, 30, 40, 50, 60, 70, 80])

    # Força cálculo de correlação
    w.custom_widget._calculate_correlation_candidates()
    table = w.custom_widget.table_candidates
    assert table.rowCount() > 0, "Nenhum candidato encontrado pelo Signal Finder!"

    best_id = table.item(0, 0).text()
    best_loc = table.item(0, 1).text()
    best_corr = table.item(0, 3).text()
    print(f"    [OK] Melhor candidato descoberto: ID {best_id}, {best_loc}, Correlação {best_corr}")
    assert "0x280" in best_id, f"Esperado ID 0x280, obteve {best_id}"
    assert "Bytes 2-3" in best_loc, f"Esperado Bytes 2-3, obteve {best_loc}"

def test_documentation_dialog():
    print("[4] Testando abertura do Guia Técnico de Documentação...")
    from custom_widgets.obd2_widget import OBD2DocumentationDialog
    dlg = OBD2DocumentationDialog()
    assert dlg.windowTitle().startswith("Guia Técnico")
    print("    [OK] Janela de documentação instanciada perfeitamente!")

if __name__ == "__main__":
    test_discovery()
    test_obd2_extended_sensors_and_flow()
    test_signal_finder_correlation()
    test_documentation_dialog()
    print("\nTODOS OS TESTES DAS NOVAS FUNCIONALIDADES PASSARAM COM 100% DE SUCESSO!")
