#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PyQt6.QtWidgets import QApplication
from src.widget_dialogs import extract_can_signal, parse_factor_str, GaugeDialog
from src.widgets_tab import GaugeWidget

def test_factor_parsing():
    print("Testing parse_factor_str...")
    assert parse_factor_str("0.125") == 0.125
    assert parse_factor_str("0,125") == 0.125
    assert parse_factor_str("x0.125") == 0.125
    assert parse_factor_str("X0.125") == 0.125
    assert parse_factor_str("· 0.125") == 0.125
    assert parse_factor_str("1/256") == 1.0 / 256.0
    assert parse_factor_str("/256") == 1.0 / 256.0
    assert parse_factor_str("1") == 1.0
    assert parse_factor_str("-0.5") == -0.5
    assert parse_factor_str(0.125) == 0.125
    print("  ✓ parse_factor_str passed all cases!")

def test_signal_extraction_john_deere():
    print("Testing extract_can_signal with John Deere 7195J signals...")

    # 1. RPM do motor: ID 0CF00400, B3-B4, Little-Endian
    # Exemplo: B3=0x20, B4=0x1C -> 0x1C20 = 7200 * 0.125 = 900 rpm
    payload_rpm = [0x00, 0x00, 0x00, 0x20, 0x1C, 0x00, 0x00, 0x00]
    raw_rpm = extract_can_signal(payload_rpm, start_byte=3, start_bit=0, bit_len=16, endianness="little")
    assert raw_rpm == 7200, f"Expected 7200, got {raw_rpm}"
    rpm_val = raw_rpm * 0.125
    assert rpm_val == 900.0, f"Expected 900.0 rpm, got {rpm_val}"
    print(f"  ✓ RPM: raw={raw_rpm} -> {rpm_val} rpm")

    # 2. Torque real: ID 0CF00400, B2, 8 bits. B2 - 125
    payload_torque = [0x00, 0x00, 228, 0x20, 0x1C, 0x00, 0x00, 0x00]
    raw_torque = extract_can_signal(payload_torque, start_byte=2, start_bit=0, bit_len=8, endianness="little")
    assert raw_torque == 228
    torque_val = raw_torque - 125
    assert torque_val == 103.0
    print(f"  ✓ Torque: raw={raw_torque} -> {torque_val} %")

    # 3. Velocidade: ID 18FEF147, B1-B2, Little-Endian. / 256
    # Exemplo: B1=0x00, B2=0x04 -> 0x0400 = 1024 / 256 = 4.00 km/h
    payload_speed = [0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]
    raw_speed = extract_can_signal(payload_speed, start_byte=1, start_bit=0, bit_len=16, endianness="little")
    assert raw_speed == 1024, f"Expected 1024, got {raw_speed}"
    speed_val = raw_speed / 256.0
    assert speed_val == 4.0, f"Expected 4.0 km/h, got {speed_val}"
    print(f"  ✓ Velocidade: raw={raw_speed} -> {speed_val} km/h")

    # 4. Temperatura da água: ID 18FEEE00, B0. B0 - 40 °C
    # Leitura ~75 °C -> B0 = 115
    payload_temp = [115, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
    raw_temp = extract_can_signal(payload_temp, start_byte=0, start_bit=0, bit_len=8, endianness="little")
    assert raw_temp == 115
    temp_val = raw_temp - 40
    assert temp_val == 75.0
    print(f"  ✓ Temp Água: raw={raw_temp} -> {temp_val} °C")

    # 5. Big-endian multi-byte check
    payload_be = [0x12, 0x34, 0x56, 0x78, 0x00, 0x00, 0x00, 0x00]
    raw_be = extract_can_signal(payload_be, start_byte=0, start_bit=0, bit_len=16, endianness="big")
    assert raw_be == 0x1234, f"Expected 0x1234, got {hex(raw_be)}"
    print(f"  ✓ Big-Endian: raw={hex(raw_be)}")

    # 6. Signed check (8-bit signed: 0xFE = -2)
    payload_signed = [0xFE]
    raw_signed = extract_can_signal(payload_signed, start_byte=0, start_bit=0, bit_len=8, signed=True)
    assert raw_signed == -2, f"Expected -2, got {raw_signed}"
    print(f"  ✓ Signed: raw={raw_signed}")

def test_gauge_widget_lifecycle(app):
    print("Testing GaugeWidget processing and display...")

    # Configuração RPM estilo John Deere
    rpm_cfg = {
        "type": "gauge",
        "name": "RPM Motor",
        "style": "Arco",
        "can_id": "0CF00400",
        "unit": "rpm",
        "conversion_mode": "factor_offset",
        "endianness": "little",
        "start_byte": 3,
        "start_bit": 0,
        "bit_length": 16,
        "factor": 0.125,
        "offset": 0.0,
        "display_min": 0.0,
        "display_max": 3000.0,
        "show_float": False,
        "gauge_size": 160
    }

    w_rpm = GaugeWidget(None, rpm_cfg)
    assert w_rpm.target_can_id == 0x0CF00400
    assert w_rpm._get_conv_value() == 0.0

    # Processa frame com 900 rpm (0x1C20 = 7200)
    w_rpm.process_can_frame(0x0CF00400, 10.0, [0x00, 0x00, 0x00, 0x20, 0x1C, 0x00, 0x00, 0x00])
    assert w_rpm._raw_value == 7200
    assert w_rpm._get_conv_value() == 900.0
    print(f"  ✓ GaugeWidget RPM: {w_rpm._get_conv_value()} rpm")

    # Configuração Velocidade (/ 256)
    speed_cfg = {
        "type": "gauge",
        "name": "Velocidade",
        "style": "Barra Horizontal",
        "can_id": "18FEF147",
        "unit": "km/h",
        "conversion_mode": "factor_offset",
        "endianness": "little",
        "start_byte": 1,
        "start_bit": 0,
        "bit_length": 16,
        "factor": 1.0 / 256.0,
        "offset": 0.0,
        "display_min": 0.0,
        "display_max": 30.0,
        "show_float": True,
        "gauge_size": 180
    }
    w_speed = GaugeWidget(None, speed_cfg)
    assert w_speed.target_can_id == 0x18FEF147
    w_speed.process_can_frame(0x18FEF147, 50.0, [0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00])
    assert w_speed._raw_value == 1024
    assert abs(w_speed._get_conv_value() - 4.0) < 1e-4
    print(f"  ✓ GaugeWidget Speed: {w_speed._get_conv_value()} km/h")

    # Configuração Legada (2 Pontos) para testar retrocompatibilidade
    legacy_cfg = {
        "type": "gauge",
        "name": "Sensor Legado",
        "can_id": "123",
        "byte": 0,
        "byte_len": 1,
        "val_min_raw": 0.0,
        "val_max_raw": 200.0,
        "val_min_conv": 10.0,
        "val_max_conv": 50.0,
        "conversion_mode": "two_point"
    }
    w_legacy = GaugeWidget(None, legacy_cfg)
    assert w_legacy.target_can_id == 0x123
    w_legacy.process_can_frame(0x123, 10.0, [100, 0, 0, 0, 0, 0, 0, 0])
    # 100 raw -> 50% between 10 e 50 = 30.0
    assert w_legacy._get_conv_value() == 30.0
    print(f"  ✓ GaugeWidget Legacy 2-Point: {w_legacy._get_conv_value()}")

def test_gauge_dialog(app):
    print("Testing GaugeDialog...")
    dlg = GaugeDialog(None)
    # Default is direct formula mode
    cfg = dlg.get_config()
    assert cfg["conversion_mode"] == "factor_offset"
    assert "start_byte" in cfg
    assert "bit_length" in cfg
    assert "endianness" in cfg
    assert "display_min" in cfg
    assert "display_max" in cfg
    print("  ✓ GaugeDialog default config valid!")

    # Test loading existing advanced config
    adv_input = {
        "type": "gauge",
        "name": "RPM Teste",
        "can_id": "0CF00400",
        "conversion_mode": "factor_offset",
        "endianness": "little",
        "start_byte": 3,
        "start_bit": 0,
        "bit_length": 16,
        "factor": 0.125,
        "offset": 0.0,
        "display_min": 0.0,
        "display_max": 3000.0
    }
    dlg2 = GaugeDialog(None, config=adv_input)
    cfg2 = dlg2.get_config()
    assert cfg2["conversion_mode"] == "factor_offset"
    assert cfg2["endianness"] == "little"
    assert cfg2["start_byte"] == 3
    assert cfg2["bit_length"] == 16
    assert cfg2["factor"] == 0.125
    assert cfg2["display_max"] == 3000.0
    print("  ✓ GaugeDialog correctly populated from advanced config!")

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    test_factor_parsing()
    test_signal_extraction_john_deere()
    test_gauge_widget_lifecycle(app)
    test_gauge_dialog(app)
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
