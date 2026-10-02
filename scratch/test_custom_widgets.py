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

def test_template_widget_lifecycle():
    print("[5] Testando ciclo de vida do widget de exemplo (widget_template.py)...")
    custom_dir = get_custom_widgets_directory()
    tmpl_path = os.path.join(custom_dir, "widget_template.py")

    worker = CANWorker()
    worker.mode = "SIMULATED"
    tab = WidgetsTab(worker)

    cfg = {"type": "custom_python", "script_path": tmpl_path}
    w = CustomPythonDashboardWidget(tab.canvas, cfg, worker)
    tab._place_widget(w, tab.canvas.pos())

    assert w.custom_widget is not None, "TemplateCustomWidget não foi instanciado!"
    assert w._error_msg is None, f"Erro inesperado no template: {w._error_msg}"
    print(f"    Widget instanciado: {w.custom_widget.WIDGET_NAME}")

    # Simula clique do botão Disparar 0x100
    w.custom_widget.on_click_send_a()
    assert "Tx Enviado" in w.custom_widget.lbl_status.text()
    print("    [OK] Transmissão acionada pelo botão do template")

    # Injeta frame CAN 0x100 com byte 0 = 128 (50% no progress bar)
    tab._broadcast_can_frame(0x100, 10.0, [128, 0, 0, 0, 0, 0, 0, 0])
    assert w.custom_widget.progress_bar.value() == 50
    assert "0x100" in w.custom_widget.lbl_status.text()
    print("    [OK] Recepção CAN recebida e refletida na barra de progresso (50%)")

    # Testa persistência de configuração
    w.custom_widget.btn_toggle.setChecked(True)
    custom_cfg = w.custom_widget.get_custom_config()
    assert custom_cfg.get("ciclo_ativo") is True
    w.custom_widget.on_close()
    print("    [OK] Ciclo de vida e persistência do template testados com sucesso!")

def test_cross_platform_path_resolution():
    print("[6] Testando compatibilidade de caminhos entre Windows e Linux...")
    from src.custom_widget_api import resolve_custom_widget_path

    # 1. Simula caminho absoluto do Windows
    win_abs_path = r"C:\Users\User\CANweaver\custom_widgets\widget_template.py"
    resolved = resolve_custom_widget_path(win_abs_path)
    assert os.path.isfile(resolved), f"Falha ao resolver caminho do Windows: {resolved}"
    print(f"    [OK] Caminho absoluto do Windows resolvido para: {resolved}")

    # 2. Simula caminho relativo com barras do Windows
    win_rel_path = r"custom_widgets\obd2_widget.py"
    resolved = resolve_custom_widget_path(win_rel_path)
    assert os.path.isfile(resolved), f"Falha ao resolver caminho relativo do Windows: {resolved}"
    print(f"    [OK] Caminho relativo com barras invertidas resolvido para: {resolved}")

def test_python38_subscriptable_fallback():
    print("[7] Testando fallback automático para scripts sem 'from __future__ import annotations' no Python 3.8...")
    # Cria script temporário com tipagem sem import __future__
    script_content = '''
from src.custom_widget_api import CustomWidgetBase

class ScriptSemFutureWidget(CustomWidgetBase):
    WIDGET_NAME = "Widget Legado Sem Future"

    def on_can_frame(self, can_id: int, freq: float, payload: list[int]):
        pass
'''
    scratch_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_script_fallback.py")
    try:
        with open(scratch_file, "w", encoding="utf-8") as f:
            f.write(script_content)

        cls, err = load_custom_widget_class_from_file(scratch_file)
        assert cls is not None, f"Falha no fallback de carregamento: {err}"
        assert cls.WIDGET_NAME == "Widget Legado Sem Future"
        print("    [OK] Fallback automático para Python 3.8 compilou e carregou o widget perfeitamente!")
    finally:
        if os.path.exists(scratch_file):
            os.remove(scratch_file)

def test_lume_widgets_and_grouped_sections():
    print("[8] Testando seções agrupadas e pasta privada lume_widgets...")
    from src.custom_widget_api import list_available_custom_widgets_grouped, get_lume_widgets_directory
    grouped = list_available_custom_widgets_grouped()
    assert "custom_widgets" in grouped, "Seção custom_widgets raiz ausente!"
    assert "lume_widgets" in grouped, "Seção lume_widgets privada ausente!"

    lume_sec = grouped["lume_widgets"]
    assert lume_sec["is_lume"] is True
    lume_widget_names = [w["name"] for w in lume_sec["widgets"]]
    print(f"    Widgets na pasta lume_widgets: {lume_widget_names}")
    assert any("Lume" in n for n in lume_widget_names), "Widget Lume Starter não encontrado em lume_widgets!"
    print("    [OK] Seções agrupadas e pasta lume_widgets funcionando!")

def test_external_folder_linking():
    print("[9] Testando vinculação e desvinculação de pasta externa de widgets...")
    from src.custom_widget_api import (
        add_custom_widget_directory,
        remove_custom_widget_directory,
        list_available_custom_widgets_grouped
    )
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix="canweaver_test_widgets_")
    try:
        # Cria um widget dentro da pasta temporária
        test_py = os.path.join(temp_dir, "meu_widget_externo.py")
        with open(test_py, "w", encoding="utf-8") as f:
            f.write('''
from src.custom_widget_api import CustomWidgetBase

class WidgetExternoTeste(CustomWidgetBase):
    WIDGET_NAME = "Widget Externo Teste"
''')
        # Vincula a pasta
        ok = add_custom_widget_directory(temp_dir)
        assert ok is True, "Falha ao adicionar pasta externa de widgets"

        grouped = list_available_custom_widgets_grouped()
        sec_key = f"user_{temp_dir}"
        assert sec_key in grouped, f"Seção externa {sec_key} não encontrada no menu agrupado!"
        sec_data = grouped[sec_key]
        assert sec_data["is_user"] is True
        assert len(sec_data["widgets"]) == 1
        assert sec_data["widgets"][0]["name"] == "Widget Externo Teste"
        print(f"    [OK] Pasta vinculada com sucesso: subseção '{sec_data['name']}' com widget '{sec_data['widgets'][0]['name']}'")

        # Desvincula a pasta
        removed = remove_custom_widget_directory(temp_dir)
        assert removed is True, "Falha ao remover pasta externa de widgets"
        grouped_after = list_available_custom_widgets_grouped()
        assert sec_key not in grouped_after, "Pasta externa ainda presente após desvinculação!"
        print("    [OK] Pasta desvinculada com sucesso do menu!")
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

def test_lume_steering_widget_lifecycle():
    print("[10] Testando execução do Lume Steering Widget...")
    from src.custom_widget_api import get_lume_widgets_directory
    lume_path = os.path.join(get_lume_widgets_directory(), "lume_steering_widget.py")

    worker = CANWorker()
    worker.mode = "SIMULATED"
    tab = WidgetsTab(worker)

    cfg = {"type": "custom_python", "script_path": lume_path}
    w = CustomPythonDashboardWidget(tab.canvas, cfg, worker)
    tab._place_widget(w, tab.canvas.pos())

    assert w.custom_widget is not None, "LumeSteeringWidget não foi instanciado!"
    assert w._error_msg is None, f"Erro inesperado no widget Lume: {w._error_msg}"
    assert w.custom_widget.max_effort == 100.0, "Esforço máximo padrão deve ser 100 Nm!"
    print(f"    Widget instanciado: {w.custom_widget.WIDGET_NAME} (Max effort: {w.custom_widget.max_effort})")

    # Injeta frame CAN de ângulo
    import struct
    payload_enc = list(struct.pack("<i", 507000)) + [0, 0, 0, 0]
    tab._broadcast_can_frame(0x02A, 10.0, payload_enc)
    assert round(w.custom_widget.current_angle_deg, 1) == 40.1
    print("    [OK] Recepção CAN refletida no ângulo do volante Lume")
    w.custom_widget.on_close()

if __name__ == "__main__":
    test_discovery()
    test_obd2_extended_sensors_and_flow()
    test_signal_finder_correlation()
    test_documentation_dialog()
    test_template_widget_lifecycle()
    test_cross_platform_path_resolution()
    test_python38_subscriptable_fallback()
    test_lume_widgets_and_grouped_sections()
    test_external_folder_linking()
    test_lume_steering_widget_lifecycle()
    print("\nTODOS OS TESTES DAS NOVAS FUNCIONALIDADES PASSARAM COM 100% DE SUCESSO!")
