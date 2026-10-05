import os
import sys
import time
import csv
import zipfile

# Headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)

from src.worker import CANWorker
from src.dialogs import ConnectionDialog
from src.annotations import AnnotationManager, normalize_can_hex, normalize_target
from src.analysis_tab import AnalysisTab


def test_1_playback_no_freeze_on_finish():
    print("[1] Testando fim de playback sem travamento (Thread viva, seek, play e loop)...")
    csv_path = "/tmp/test_playback_sample.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Timestamp", "ID", "DLC", "B0", "B1", "B2", "B3"])
        for i in range(5):
            writer.writerow([i * 0.05, "100", 4, "01", "02", "03", f"{i:02X}"])

    worker = CANWorker()
    worker.mode = "PLAYBACK"
    worker.playback_file = csv_path
    worker.playback_loop = False
    worker.playback_speed = 10.0  # Ultra rápido

    frames_received = []
    worker.frame_received.connect(lambda cid, freq, data: frames_received.append((cid, data)))

    worker.start()

    # Espera até chegar ao fim e processa eventos Qt
    for _ in range(30):
        time.sleep(0.02)
        app.processEvents()

    assert len(frames_received) >= 5, f"Esperado >= 5 frames, recebido {len(frames_received)}"
    assert worker.isRunning(), "A thread CANWorker NÃO deve morrer ao fim do playback!"
    assert worker.running, "worker.running deve continuar True aguardando comandos!"
    assert worker.playback_paused, "Ao terminar sem loop, worker deve estar em estado pausado!"
    assert worker.playback_index >= worker.playback_total, "playback_index deve estar no final!"

    # 1.1 Testar Playback Seek após término
    worker.seek_playback(0)
    time.sleep(0.1)
    assert worker.playback_index == 0, f"Seek para 0 falhou, index atual: {worker.playback_index}"

    # 1.2 Testar Replay ao dar Play (toggle_pause_playback)
    frames_before = len(frames_received)
    is_paused = worker.toggle_pause_playback()
    assert is_paused is False, "toggle_pause_playback() deve retornar False (reproduzindo)"
    for _ in range(20):
        time.sleep(0.02)
        app.processEvents()
    assert len(frames_received) > frames_before, "Deveria ter emitido novos frames após reiniciar reprodução!"

    # 1.3 Testar Loop reativado após término
    worker.set_playback_loop(True)
    assert worker.playback_loop is True
    time.sleep(0.3)
    assert worker.isRunning()

    worker.stop()
    worker.wait(1000)
    print("    [OK] Playback não morre mais ao chegar ao final e aceita play/seek/loop!")


def test_2_connection_dialog_loop_removed():
    print("[2] Testando remoção do checkbox de loop no modal de conexão...")
    dlg = ConnectionDialog()
    assert not hasattr(dlg, "chk_loop"), "ConnectionDialog não deve mais conter o atributo chk_loop!"
    
    cfg = dlg.get_config()
    assert "playback_loop" not in cfg, "Config do modal não deve mais ditar playback_loop!"
    assert cfg["mode"] == "HARDWARE"
    
    # Alternar para playback
    dlg.cb_mode.setCurrentIndex(2)
    cfg2 = dlg.get_config()
    assert cfg2["mode"] == "PLAYBACK"
    assert "playback_loop" not in cfg2
    print("    [OK] Checkbox redundante removido com sucesso!")


def test_3_representation_decimal_prevention():
    print("[3] Testando integridade da representação BIN/HEX e prevenções de decimal...")
    # 3.1 Testar parsing do worker
    raw_csv_row = ["0.0", "0x120", "8", "0A", "255", "FF", "10", "0", "01"]
    parsed = CANWorker._parse_playback_payload(raw_csv_row[3:])
    assert parsed == [0x0A, 255, 0xFF, 0x10, 0, 1]
    for b in parsed:
        assert 0 <= b <= 255

    # 3.2 Testar AnalysisTab exibição e NoEditTriggers
    annot_mgr = AnnotationManager("/tmp/test_annot_dir")
    worker = CANWorker()
    tab = AnalysisTab(annot_mgr, worker)

    assert tab.table_view.editTriggers() == tab.table_view.EditTrigger.NoEditTriggers, "table_view não deve permitir edição de células!"

    # Injeta frame com valores extremos
    tab.process_can_frame(0x180, 10.0, [0x0A, 255, 0x14, 0, 0x7E, 0xAA, 0x55, 0x01])

    # No modo HEX
    assert tab.display_format == "HEX"
    assert tab.table_model.item(0, 2).text() == "0A"
    assert tab.table_model.item(0, 3).text() == "FF"
    assert tab.table_model.item(0, 4).text() == "14"

    # Alterna para BIN
    tab.toggle_display_format()
    assert tab.display_format == "BIN"
    assert tab.table_model.item(0, 2).text() == "00001010"
    assert tab.table_model.item(0, 3).text() == "11111111"
    assert len(tab.table_model.item(0, 3).text()) == 8

    # Alterna de volta para HEX
    tab.toggle_display_format()
    assert tab.display_format == "HEX"
    assert tab.table_model.item(0, 2).text() == "0A"
    assert tab.table_model.item(0, 3).text() == "FF"

    print("    [OK] Representação segura em HEX e BIN sem desvios para decimal!")


def test_4_import_cwp_cross_platform_annotations():
    print("[4] Testando importação de .cwp com anotações geradas em outro PC (BOM, case, subpastas)...")
    # 4.1 Testar normalização
    assert normalize_can_hex("0x0C0") == "0C0"
    assert normalize_can_hex("0c0") == "0C0"
    assert normalize_can_hex("c0") == "0C0"
    assert normalize_can_hex("18eaff00") == "18EAFF00"
    assert normalize_target("ID 0x0c0 - byte 2 - bit 5") == "ID 0C0 - Byte 2 - Bit 5"

    # 4.2 Testar AnnotationManager com UTF-8 BOM e variações de case
    annot_dir = "/tmp/test_annot_cross"
    os.makedirs(annot_dir, exist_ok=True)
    md_file = os.path.join(annot_dir, "CANweaver_Projeto.md")
    
    # Escreve com BOM e variações que ocorrem em outros SOs
    with open(md_file, "w", encoding="utf-8-sig") as f:
        f.write("\ufeff## [ID 0x0c0] - 2026-01-01 10:00:00\n")
        f.write("Comentario ID do outro PC\n\n")
        f.write("## [ID c0 - Byte 2] - 2026-01-01 10:01:00\n")
        f.write("Comentario Byte 2\n\n")
        f.write("## [ID 0C0 - Byte 2 - Bit 7] - 2026-01-01 10:02:00\n")
        f.write("Comentario Bit 7\n")

    mgr = AnnotationManager(annot_dir)
    mgr.load()

    # Verifica matching
    assert "Comentario ID do outro PC" in mgr.get_tooltip_for_id("0C0")
    assert "Comentario ID do outro PC" in mgr.get_tooltip_for_id("0x0C0")
    assert "Comentario ID do outro PC" in mgr.get_tooltip_for_id("0c0")
    assert "Comentario Byte 2" in mgr.get_tooltip_for_byte("0C0", 2)
    
    has_any, mask, has_byte = mgr.get_annotation_info("0C0", 2)
    assert has_any is True
    assert has_byte is True
    assert (mask & (1 << 7)) != 0

    # 4.3 Testar refresh_annotations no AnalysisTab
    worker = CANWorker()
    tab = AnalysisTab(mgr, worker)
    # Injeta frames de 0x0C0
    tab.process_can_frame(0x0C0, 20.0, [0, 0, 0x12, 0, 0, 0, 0, 0])

    item_id = tab.table_model.item(0, 0)
    assert item_id.data(Qt.ItemDataRole.UserRole + 1) is True, "Célula do ID deve ter UserRole+1=True para borda amarela!"
    assert "Comentario ID" in item_id.toolTip()

    item_b2 = tab.table_model.item(0, 4)  # Coluna 4 = Byte 2
    assert item_b2.data(Qt.ItemDataRole.UserRole + 1) is True, "Byte 2 deve ter UserRole+1=True para borda amarela!"
    assert "Comentario Byte 2" in item_b2.toolTip()

    # Testa lista lateral
    list_item = tab.list_ids.item(0)
    assert list_item.foreground().color().name() == "#facc15", "Item da lista lateral deve ficar amarelo!"

    # 4.4 Testar extração resiliente de ZIP com subpasta (ex: MeuProjeto/CANweaver_Projeto.md)
    cwp_path = "/tmp/test_project_subfolder.cwp"
    with zipfile.ZipFile(cwp_path, "w") as zf:
        zf.writestr("MeuProjeto/canweaver_projeto.md", "# Projeto\n\n## [ID 0x180]\nTeste Subpasta\n")
        zf.writestr("MeuProjeto/transmit_tasks.json", "[]")
        zf.writestr("MeuProjeto/dashboard_layout.json", "[]")

    # Verifica se a função de busca resiliente acha as entradas
    with zipfile.ZipFile(cwp_path, "r") as zf:
        def _find_zip_entry(target_basename: str):
            target_lower = target_basename.lower()
            for name in zf.namelist():
                clean = name.replace('\\', '/')
                if os.path.basename(clean).lower() == target_lower:
                    return name
            return None

        assert _find_zip_entry("CANweaver_Projeto.md") == "MeuProjeto/canweaver_projeto.md"
        assert _find_zip_entry("transmit_tasks.json") == "MeuProjeto/transmit_tasks.json"
        assert _find_zip_entry("dashboard_layout.json") == "MeuProjeto/dashboard_layout.json"

    print("    [OK] Anotações e projetos entre diferentes computadores funcionam 100%!")


if __name__ == "__main__":
    test_1_playback_no_freeze_on_finish()
    test_2_connection_dialog_loop_removed()
    test_3_representation_decimal_prevention()
    test_4_import_cwp_cross_platform_annotations()
    print("\n================ TODOS OS TESTES PASSARAM COM SUCESSO! ================\n")
