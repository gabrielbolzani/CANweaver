#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QModelIndex, QRect
from PyQt6.QtGui import QPainter, QImage, QColor, QStandardItemModel, QStandardItem
from src.analysis_tab import AnalysisTab
from src.delegate import CANItemDelegate

def test_highlight_changes():
    app = QApplication.instance() or QApplication(sys.argv)
    from src.annotations import AnnotationManager
    mgr = AnnotationManager(".")
    tab = AnalysisTab(mgr, None)

    # 1. Checkbox exists, is checked by default and has correct text
    assert hasattr(tab, "chk_highlight_changes"), "chk_highlight_changes attribute missing"
    assert tab.chk_highlight_changes.text() == "Destacar Mudanças"
    assert tab.chk_highlight_changes.isChecked() is True
    assert tab.item_delegate.highlight_changes is True
    print("  ✓ Checkbox 'Destacar Mudanças' criado e ativado por padrão!")

    # 2. Test receiving packet with changes while highlight_changes is True
    # Simulate packet arrival
    tab.process_can_frame(0x100, 10.0, [0x01, 0x02, 0x03, 0x04])
    item_b0 = tab.table_model.item(0, 2)
    assert item_b0 is not None

    # First packet doesn't trigger change because it's initial
    # Now send changed packet
    tab.process_can_frame(0x100, 10.0, [0xFF, 0x02, 0x03, 0x04])
    assert item_b0.background().color().name() == "#1e3a8a", f"Expected #1e3a8a, got {item_b0.background().color().name()}"
    print("  ✓ Com 'Destacar Mudanças' ativado, byte alterado recebe destaque (#1e3a8a)!")

    # 3. Test delegate painting in BIN mode with highlight_changes True vs False
    tab.display_format = "BIN"
    item_b0.setText("11111111")
    item_b0.setData("00000000", Qt.ItemDataRole.UserRole)  # Old was all zeros, new is all ones (all changed!)

    # Paint with highlight_changes = True
    img_true = QImage(120, 40, QImage.Format.Format_ARGB32)
    img_true.fill(Qt.GlobalColor.black)
    p_true = QPainter(img_true)
    from PyQt6.QtWidgets import QStyleOptionViewItem
    opt = QStyleOptionViewItem()
    opt.rect = QRect(0, 0, 120, 40)
    idx = tab.table_model.index(0, 2)
    tab.item_delegate.paint(p_true, opt, idx)
    p_true.end()

    # Search for the green color (#04d361 -> RGB 4, 211, 97)
    found_green_true = False
    for y in range(40):
        for x in range(120):
            pixel = QColor(img_true.pixel(x, y))
            if pixel.name() == "#04d361":
                found_green_true = True
                break
        if found_green_true:
            break
    assert found_green_true, "Expected green bit squares when highlight_changes is True"
    print("  ✓ Delegate pintou quadradinhos verdes (#04d361) para bits alterados!")

    # 4. Now uncheck 'Destacar Mudanças'
    tab.chk_highlight_changes.setChecked(False)
    assert tab.item_delegate.highlight_changes is False
    # Check that previous active blue background was cleared
    assert item_b0.background().color().isValid() is False or item_b0.data(Qt.ItemDataRole.BackgroundRole) is None
    print("  ✓ Desmarcar 'Destacar Mudanças' limpou imediatamente o fundo azul de alteração!")

    # Paint with highlight_changes = False
    img_false = QImage(120, 40, QImage.Format.Format_ARGB32)
    img_false.fill(Qt.GlobalColor.black)
    p_false = QPainter(img_false)
    tab.item_delegate.paint(p_false, opt, idx)
    p_false.end()

    found_green_false = False
    for y in range(40):
        for x in range(120):
            pixel = QColor(img_false.pixel(x, y))
            if pixel.name() == "#04d361":
                found_green_false = True
                break
        if found_green_false:
            break
    assert not found_green_false, "Did not expect green bit squares when highlight_changes is False"
    print("  ✓ Com 'Destacar Mudanças' desativado, NENHUM quadradinho verde foi pintado!")

    # 5. Send another change while highlight_changes is False: should not set #1e3a8a
    tab.process_can_frame(0x100, 10.0, [0xAA, 0x02, 0x03, 0x04])
    assert item_b0.data(Qt.ItemDataRole.BackgroundRole) is None
    print("  ✓ Novos pacotes com alteração não ativam fundo azul quando desmarcado!")

    # 6. Re-enable 'Destacar Mudanças'
    tab.chk_highlight_changes.setChecked(True)
    assert tab.item_delegate.highlight_changes is True
    print("  ✓ Reativação funciona perfeitamente!")

if __name__ == "__main__":
    test_highlight_changes()
    print("\n🎉 ALL HIGHLIGHT CHANGES TESTS PASSED!")
