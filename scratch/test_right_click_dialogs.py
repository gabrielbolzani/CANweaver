import os
import sys

# Headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication, QPushButton, QCheckBox, QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox
from PyQt6.QtCore import Qt

app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from lume_widgets.lume_steering_widget import LumeSteeringWidget
from lume_widgets.lume_pedals_widget import LumePedalsWidget
from src.widget_dialogs import CustomPythonDialog


def test_steering_widget_no_header_btn_and_config_embedded():
    widget = LumeSteeringWidget()
    
    # 1. Ensure no header button for config in widget
    btns = widget.findChildren(QPushButton)
    header_config_btns = [b for b in btns if b.text() == "⚙️" and "Volante" in b.toolTip()]
    assert len(header_config_btns) == 0, f"Found unexpected config button in steering widget: {header_config_btns}"
    assert not hasattr(widget, "btn_config"), "widget still has self.btn_config attribute!"

    # 2. Test create_config_widget
    cfg_w = widget.create_config_widget()
    assert cfg_w is not None

    # Check internal config widgets
    assert hasattr(widget, "_cfg_chk_invert_feedback")
    assert hasattr(widget, "_cfg_chk_invert_effort")
    assert hasattr(widget, "_cfg_sp_angle_mult")
    assert hasattr(widget, "_cfg_sp_max_effort")

    # Modify values in the UI controls
    widget._cfg_chk_invert_feedback.setChecked(True)
    widget._cfg_chk_invert_effort.setChecked(True)
    widget._cfg_sp_angle_mult.setValue(3.2)
    widget._cfg_sp_max_effort.setValue(180.0)

    # Apply
    widget.apply_config()
    assert widget.invert_feedback is True
    assert widget.invert_effort is True
    assert widget.angle_multiplier == 3.2
    assert widget.max_effort == 180.0

    # Reset
    widget.reset_default_config()
    assert widget._cfg_chk_invert_feedback.isChecked() is False
    assert widget._cfg_chk_invert_effort.isChecked() is False
    assert widget._cfg_sp_angle_mult.value() == 1.0
    assert widget._cfg_sp_max_effort.value() == 100.0

    # Custom config export
    cfg_data = widget.get_custom_config()
    assert "invert_feedback" in cfg_data
    assert "invert_effort" in cfg_data
    assert "angle_multiplier" in cfg_data
    assert "max_effort" in cfg_data


def test_pedals_widget_no_header_btn_and_config_embedded():
    widget = LumePedalsWidget()

    # 1. Ensure no button with ⚙️ or tooltip in header
    btns = widget.findChildren(QPushButton)
    gear_btns = [b for b in btns if "⚙️" in b.text() or "Configurações" in b.toolTip()]
    assert len(gear_btns) == 0, f"Found unexpected config button in pedals widget: {gear_btns}"
    assert not hasattr(widget, "btn_config"), "widget still has self.btn_config attribute!"

    # 2. Test create_config_widget
    cfg_w = widget.create_config_widget()
    assert cfg_w is not None

    # Check internal config widgets
    assert hasattr(widget, "_cfg_txt_speed_id")
    assert hasattr(widget, "_cfg_sp_speed_byte")
    assert hasattr(widget, "_cfg_sp_speed_bits")
    assert hasattr(widget, "_cfg_cb_speed_endian")
    assert hasattr(widget, "_cfg_sp_speed_factor")

    # Modify values
    widget._cfg_txt_speed_id.setText("0x305")
    widget._cfg_sp_speed_byte.setValue(4)
    widget._cfg_sp_speed_bits.setValue(8)
    widget._cfg_cb_speed_endian.setCurrentIndex(1)  # BE
    widget._cfg_sp_speed_factor.setValue(0.2)

    widget._cfg_txt_rpm_id.setText("0x450")
    widget._cfg_sp_rpm_byte.setValue(1)
    widget._cfg_sp_rpm_bits.setValue(16)
    widget._cfg_cb_rpm_endian.setCurrentIndex(1)  # BE
    widget._cfg_sp_rpm_factor.setValue(2.5)

    widget.apply_config()
    assert widget.speed_can_id == 0x305
    assert widget.speed_start_byte == 4
    assert widget.speed_num_bits == 8
    assert widget.speed_endian == "BE"
    assert widget.speed_factor == 0.2

    assert widget.rpm_can_id == 0x450
    assert widget.rpm_start_byte == 1
    assert widget.rpm_num_bits == 16
    assert widget.rpm_endian == "BE"
    assert widget.rpm_factor == 2.5

    # Reset
    widget.reset_default_config()
    assert widget._cfg_txt_speed_id.text() == "0x201"
    assert widget._cfg_sp_speed_byte.value() == 2
    assert widget._cfg_sp_speed_bits.value() == 16
    assert widget._cfg_cb_speed_endian.currentIndex() == 0
    assert widget._cfg_sp_speed_factor.value() == 0.05


def test_custom_python_dialog_embedding():
    # Test Steering in CustomPythonDialog
    steering_w = LumeSteeringWidget()
    cfg_initial = {"type": "custom_python", "script_path": "lume_widgets/lume_steering_widget.py", "width": 380, "height": 520}
    dlg_steering = CustomPythonDialog(config=cfg_initial, custom_widget=steering_w)

    # Verify custom config widget is embedded
    assert dlg_steering._custom_config_widget is not None

    # Change values through dialog
    steering_w._cfg_chk_invert_feedback.setChecked(True)
    steering_w._cfg_sp_max_effort.setValue(120.0)

    # Click accept
    dlg_steering.accept()

    # Verify get_config captures it
    updated_cfg = dlg_steering.get_config()
    assert "custom_config" in updated_cfg
    assert updated_cfg["custom_config"]["invert_feedback"] is True
    assert updated_cfg["custom_config"]["max_effort"] == 120.0

    # Test Pedals in CustomPythonDialog
    pedals_w = LumePedalsWidget()
    cfg_p_initial = {"type": "custom_python", "script_path": "lume_widgets/lume_pedals_widget.py", "width": 460, "height": 380}
    dlg_pedals = CustomPythonDialog(config=cfg_p_initial, custom_widget=pedals_w)

    assert dlg_pedals._custom_config_widget is not None
    pedals_w._cfg_txt_speed_id.setText("0x250")
    dlg_pedals.accept()

    updated_p_cfg = dlg_pedals.get_config()
    assert "custom_config" in updated_p_cfg
    assert updated_p_cfg["custom_config"]["speed_can_id"] in ["0x250", 0x250]


if __name__ == "__main__":
    test_steering_widget_no_header_btn_and_config_embedded()
    print("✓ Steering Widget tests passed!")
    test_pedals_widget_no_header_btn_and_config_embedded()
    print("✓ Pedals Widget tests passed!")
    test_custom_python_dialog_embedding()
    print("✓ CustomPythonDialog embedding tests passed!")
    print("ALL TESTS PASSED SUCCESSFULLY!")
