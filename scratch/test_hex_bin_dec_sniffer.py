import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Ensure src can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.worker import CANWorker
from src.analysis_tab import AnalysisTab
from src.annotations import AnnotationManager

def test_payload_format_detection_and_parsing():
    print("Testing payload format detection and parsing...")

    # Sample rows from user's CSV
    rows_dec = [
        ["1790881754.2136257", "CF00400", "8", "240", "255", "140", "124", "28", "255", "255", "255"],
        ["1790881754.2158866", "4EF0005", "8", "100", "21", "29", "5", "0", "0", "88", "27"],
        ["1790881754.219302", "18FEF147", "8", "255", "0", "0", "255", "255", "255", "255", "255"],
        ["1790881754.8051372", "CF00300", "8", "255", "255", "9", "255", "255", "255", "255", "255"],
        ["1790881754.8254545", "CF00300", "8", "255", "255", "10", "255", "255", "255", "255", "255"],
        ["1790881754.8432896", "CF00300", "8", "255", "255", "11", "255", "255", "255", "255", "255"],
        ["1790881757.1200333", "18FEF147", "8", "255", "11", "1", "255", "255", "255", "255", "255"],
    ]

    detected = CANWorker._detect_csv_payload_format(rows_dec)
    assert detected == "DEC", f"Expected DEC, got {detected}"
    print("✓ Auto-detection correctly recognized user's decimal CSV as 'DEC'")

    # Test parse with DEC
    row_cf00400 = rows_dec[0][3:]
    payload = CANWorker._parse_playback_payload(row_cf00400, "DEC")
    assert payload == [240, 255, 140, 124, 28, 255, 255, 255], f"Unexpected payload: {payload}"
    assert payload[4] == 28, f"Expected byte B4 to be decimal 28, got {payload[4]}"
    print("✓ CF00400 B4 parsed as decimal 28 (0x1C)")

    # Test 18FEF147 row with B1=11
    row_147 = rows_dec[6][3:]
    payload_147 = CANWorker._parse_playback_payload(row_147, "DEC")
    assert payload_147[1] == 11, f"Expected B1=11, got {payload_147[1]}"
    print("✓ 18FEF147 B1 parsed as decimal 11 (0x0B)")

    # Test HEX CSV detection
    rows_hex = [
        ["100.0", "123", "8", "0A", "1B", "FF", "00", "1C", "2D", "3E", "4F"]
    ]
    detected_hex = CANWorker._detect_csv_payload_format(rows_hex)
    assert detected_hex == "HEX", f"Expected HEX, got {detected_hex}"
    payload_hex = CANWorker._parse_playback_payload(rows_hex[0][3:], "HEX")
    assert payload_hex == [0x0A, 0x1B, 0xFF, 0x00, 0x1C, 0x2D, 0x3E, 0x4F]
    print("✓ Hex CSV correctly detected and parsed as 'HEX'")


def test_analysis_tab_display_modes():
    print("Testing AnalysisTab display modes (HEX, BIN, DEC)...")
    app = QApplication.instance() or QApplication(sys.argv)

    annot_mgr = AnnotationManager("/tmp")
    tab = AnalysisTab(annot_mgr, None)

    # Check cb_format widget exists and has items
    assert hasattr(tab, "cb_format"), "AnalysisTab should have cb_format"
    items = [tab.cb_format.itemText(i) for i in range(tab.cb_format.count())]
    assert items == ["HEX", "BIN", "DEC"], f"Expected ['HEX', 'BIN', 'DEC'], got {items}"
    assert tab.cb_format.currentText() == "HEX"
    assert tab.display_format == "HEX"
    print("✓ cb_format properly initialized with ['HEX', 'BIN', 'DEC']")

    # Process a CAN frame with payload containing byte 28 (0x1C), 240 (0xF0), 0
    can_id = 0xCF00400
    payload = [240, 255, 140, 124, 28, 255, 0, 11]
    tab.process_can_frame(can_id, 10.0, payload)

    row_info = tab.can_database.get("CF00400")
    assert row_info is not None, "CF00400 should be in database"
    row_idx = row_info["row_index"]

    # In HEX mode:
    # B0=240 -> "F0", B4=28 -> "1C", B6=0 -> "00", B7=11 -> "0B"
    assert tab.table_model.item(row_idx, 2).text() == "F0"
    assert tab.table_model.item(row_idx, 6).text() == "1C"
    assert tab.table_model.item(row_idx, 8).text() == "00"
    assert tab.table_model.item(row_idx, 9).text() == "0B"
    print("✓ HEX mode displays bytes as two-digit hexadecimal ('F0', '1C', '00', '0B')")

    # Switch to DEC mode via cb_format
    tab.cb_format.setCurrentText("DEC")
    assert tab.display_format == "DEC"
    assert tab.table_model.item(row_idx, 2).text() == "240"
    assert tab.table_model.item(row_idx, 6).text() == "28"
    assert tab.table_model.item(row_idx, 8).text() == "0"
    assert tab.table_model.item(row_idx, 9).text() == "11"
    print("✓ DEC mode dynamically updates all table cells to decimal ('240', '28', '0', '11')")

    # Switch to BIN mode via cb_format
    tab.cb_format.setCurrentText("BIN")
    assert tab.display_format == "BIN"
    assert tab.table_model.item(row_idx, 2).text() == "11110000"
    assert tab.table_model.item(row_idx, 6).text() == "00011100"
    assert tab.table_model.item(row_idx, 8).text() == "00000000"
    assert tab.table_model.item(row_idx, 9).text() == "00001011"
    print("✓ BIN mode dynamically updates all table cells to 8-bit binary ('11110000', '00011100', etc)")

    # Test new incoming frame while in DEC mode
    tab.cb_format.setCurrentText("DEC")
    new_payload = [240, 255, 140, 124, 27, 255, 0, 12]
    tab.process_can_frame(can_id, 10.0, new_payload)
    assert tab.table_model.item(row_idx, 6).text() == "27"
    assert tab.table_model.item(row_idx, 9).text() == "12"
    print("✓ New frames processed while in DEC mode format directly as decimal ('27', '12')")

    # Test toggle_display_format cycling
    tab.cb_format.setCurrentText("HEX")
    tab.toggle_display_format()
    assert tab.display_format == "BIN"
    assert tab.cb_format.currentText() == "BIN"
    tab.toggle_display_format()
    assert tab.display_format == "DEC"
    assert tab.cb_format.currentText() == "DEC"
    tab.toggle_display_format()
    assert tab.display_format == "HEX"
    assert tab.cb_format.currentText() == "HEX"
    print("✓ toggle_display_format cycles HEX -> BIN -> DEC -> HEX and synchronizes cb_format")


if __name__ == "__main__":
    test_payload_format_detection_and_parsing()
    test_analysis_tab_display_modes()
    print("\nALL SNIFFER DISPLAY AND PLAYBACK TESTS PASSED SUCCESSFULLY!")
