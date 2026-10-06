import os
import sys
import csv

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from src.analysis_tab import AnalysisTab
from src.annotations import AnnotationManager
from src.worker import CANWorker

def test_id_counts_and_export():
    print("Testando contagem de IDs únicos e exportação CSV...")

    annot_mgr = AnnotationManager("/tmp/test_annot_export")
    worker = CANWorker()
    tab = AnalysisTab(annot_mgr, worker)

    # 1. Estado Inicial
    assert tab.lbl_filtered_count.text() == "Total: 0 IDs"
    assert tab.lbl_id_filter.text() == "Visibilidade de IDs (0)"

    # 2. Injetando frames (incluindo repetidos)
    tab.process_can_frame(0x0C0, 10.0, [0x01, 0x02])
    tab.process_can_frame(0x180, 20.0, [0xAA, 0xBB])
    tab.process_can_frame(0x200, 15.0, [0x11, 0x22])
    tab.process_can_frame(0x0C0, 12.0, [0x03, 0x04])  # Repetido! Deve manter 3 IDs únicos
    tab.process_can_frame(0x180, 21.0, [0xAA, 0xCC])  # Repetido!

    assert len(tab.can_database) == 3
    assert tab.lbl_filtered_count.text() == "Total: 3 IDs"
    assert tab.lbl_id_filter.text() == "Visibilidade de IDs (3)"
    print("  [OK] Contagem de IDs únicos no barramento funciona corretamente (3 IDs)!")

    # 3. Testando filtro de ID
    tab.txt_filter_id.setText("0C")
    assert tab.lbl_filtered_count.text() == "Exibindo: 1 de 3 IDs"
    assert tab.lbl_id_filter.text() == "Visibilidade de IDs (3)"
    print("  [OK] Filtro dinâmico e atualização de contagem exibindo '1 de 3 IDs'!")

    # 4. Limpar filtro
    tab.txt_filter_id.setText("")
    assert tab.lbl_filtered_count.text() == "Total: 3 IDs"

    # 5. Testando Exportação CSV
    csv_out = "/tmp/test_exported_ids.csv"
    if os.path.exists(csv_out):
        os.remove(csv_out)

    exported_path = tab.export_unique_ids_csv(destination_path=csv_out)
    assert exported_path == csv_out
    assert os.path.exists(csv_out)

    with open(csv_out, "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    print("  Conteúdo do CSV gerado:")
    for row in reader:
        print("   ", row)

    # Verifica formato: cabeçalho "ID", depois cada ID único em sua linha
    assert reader[0] == ["ID"]
    id_rows = [r[0] for r in reader[1:]]
    assert id_rows == ["0C0", "180", "200"]
    assert len(id_rows) == len(set(id_rows))  # Cada ID aparece exatamente uma vez!
    print("  [OK] CSV gerado com sucesso: cada ID aparece uma vez e pulando linha!")

    # 6. Testando Reset ao limpar dados
    tab.clear_data()
    assert len(tab.can_database) == 0
    assert tab.lbl_filtered_count.text() == "Total: 0 IDs"
    assert tab.lbl_id_filter.text() == "Visibilidade de IDs (0)"
    print("  [OK] Reset limpo ao reiniciar dados!")

if __name__ == "__main__":
    test_id_counts_and_export()
    print("\nTodos os testes passaram com sucesso!")
