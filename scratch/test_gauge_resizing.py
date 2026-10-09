import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QPixmap, QPainter
from src.widgets_tab import GaugeWidget
from src.widget_dialogs import GaugeDialog

def run_tests():
    app = QApplication.instance() or QApplication(sys.argv)

    print("=== TEST 1: Default dimensions per style ===")
    styles_defaults = [
        ("Barra Horizontal", 240, 60),
        ("Barra Vertical", 70, 220),
        ("Arco", 160, 190),
        ("Texto Apenas", 160, 60),
    ]
    for style, exp_w, exp_h in styles_defaults:
        cfg = {"type": "gauge", "name": f"Test {style}", "style": style}
        gw = GaugeWidget(None, cfg)
        print(f"  Style '{style}': {gw.width()}x{gw.height()} (expected {exp_w}x{exp_h})")
        assert gw.width() == exp_w, f"Expected width {exp_w}, got {gw.width()}"
        assert gw.height() == exp_h, f"Expected height {exp_h}, got {gw.height()}"

    print("=== TEST 2: Preserves explicit width & height in config ===")
    cfg_custom = {
        "type": "gauge",
        "name": "Custom Dim",
        "style": "Barra Vertical",
        "width": 80,
        "height": 350
    }
    gw_custom = GaugeWidget(None, cfg_custom)
    assert gw_custom.width() == 80
    assert gw_custom.height() == 350
    assert gw_custom.config["width"] == 80
    assert gw_custom.config["height"] == 350
    print("  ✓ Custom width/height preserved on init!")

    print("=== TEST 3: Resizing (apply_resized_geometry) for Horizontal and Vertical Bars ===")
    # Horizontal Bar resizing
    cfg_hbar = {"type": "gauge", "name": "HBar", "style": "Barra Horizontal"}
    gw_hbar = GaugeWidget(None, cfg_hbar)
    
    test_sizes_hbar = [(400, 80), (300, 45), (180, 30), (500, 120)]
    for tw, th in test_sizes_hbar:
        gw_hbar.apply_resized_geometry(QRect(10, 10, tw, th))
        assert gw_hbar.width() == tw
        assert gw_hbar.height() == th
        assert gw_hbar.config["width"] == tw
        assert gw_hbar.config["height"] == th
        # Render to QPixmap to ensure paintEvent doesn't crash and paints cleanly
        pix = QPixmap(gw_hbar.size())
        pix.fill()
        gw_hbar.render(pix)
        print(f"  ✓ HBar resized and rendered cleanly at {tw}x{th}")

    # Vertical Bar resizing
    cfg_vbar = {"type": "gauge", "name": "VBar", "style": "Barra Vertical"}
    gw_vbar = GaugeWidget(None, cfg_vbar)

    test_sizes_vbar = [(60, 320), (80, 400), (45, 180), (120, 250), (50, 50)]
    for tw, th in test_sizes_vbar:
        gw_vbar.apply_resized_geometry(QRect(10, 10, tw, th))
        assert gw_vbar.width() == tw
        assert gw_vbar.height() == th
        assert gw_vbar.config["width"] == tw
        assert gw_vbar.config["height"] == th
        pix = QPixmap(gw_vbar.size())
        pix.fill()
        gw_vbar.render(pix)
        print(f"  ✓ VBar resized and rendered cleanly at {tw}x{th}")

    print("=== TEST 4: snap_to_grid preserves independent width and height ===")
    cfg_snap = {
        "type": "gauge",
        "name": "Snap Test",
        "style": "Barra Vertical",
        "width": 68,
        "height": 295,
        "snap_size": True
    }
    gw_snap = GaugeWidget(None, cfg_snap)
    gw_snap.snap_to_grid(grid_size=20)
    # 68 snaps to 60 or 80, 295 snaps to 300
    assert gw_snap.width() == 60 or gw_snap.width() == 80
    assert gw_snap.height() == 300
    assert gw_snap.width() != gw_snap.height(), "Vertical bar should NOT be squashed into square!"
    print(f"  ✓ Vertical bar snapped to: {gw_snap.width()}x{gw_snap.height()}")

    print("=== TEST 5: GaugeDialog dimensions and style switching ===")
    dlg = GaugeDialog(None)
    # By default Arco: 160x190
    cfg_dlg = dlg.get_config()
    assert cfg_dlg["width"] == 160
    assert cfg_dlg["height"] == 190

    # Switch to Barra Horizontal
    dlg.cb_style.setCurrentText("Barra Horizontal")
    cfg_dlg_h = dlg.get_config()
    assert cfg_dlg_h["width"] == 240
    assert cfg_dlg_h["height"] == 60
    print("  ✓ GaugeDialog switched to Barra Horizontal with 240x60 defaults")

    # Switch to Barra Vertical
    dlg.cb_style.setCurrentText("Barra Vertical")
    cfg_dlg_v = dlg.get_config()
    assert cfg_dlg_v["width"] == 70
    assert cfg_dlg_v["height"] == 220
    print("  ✓ GaugeDialog switched to Barra Vertical with 70x220 defaults")

    print("\n🎉 ALL RESIZING TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
