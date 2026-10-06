import sys
import os
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Ensure src can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import can
from src.dialogs import (
    SocketCANConfigDialog, ConnectionDialog,
    get_available_can_interfaces, get_can_interface_status,
    build_socketcan_shell_command, bring_up_socketcan
)
from src.worker import CANWorker


def test_socketcan_config_dialog_and_helpers():
    print("Testando SocketCANConfigDialog e funções de controle...")
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Test build_socketcan_shell_command
    cmd = build_socketcan_shell_command("can0", 500000, restart_ms=100)
    assert "sudo ip link set can0 down" in cmd
    assert "sudo ip link set can0 up type can bitrate 500000 restart-ms 100" in cmd
    print("  [OK] Comando básico gerado corretamente:", cmd)

    cmd_opts = build_socketcan_shell_command("can1", 250000, listen_only=True, loopback=True, sample_point=0.875)
    assert "can1" in cmd_opts
    assert "bitrate 250000" in cmd_opts
    assert "listen-only on" in cmd_opts
    assert "loopback on" in cmd_opts
    assert "sample-point 0.875" in cmd_opts
    print("  [OK] Comando com opções avançadas gerado corretamente:", cmd_opts)

    # 2. Test get_available_can_interfaces
    ifaces = get_available_can_interfaces()
    assert isinstance(ifaces, list)
    assert len(ifaces) > 0
    print("  [OK] Interfaces detectadas:", ifaces)

    # 3. Test get_can_interface_status
    status = get_can_interface_status("can0")
    assert "state" in status
    assert "details" in status
    print("  [OK] Status de can0:", status["state"], "bitrate:", status.get("bitrate"))

    # 4. Test SocketCANConfigDialog UI
    dlg = SocketCANConfigDialog(initial_channel="can0", initial_bitrate=500000)
    assert hasattr(dlg, "cb_iface")
    assert hasattr(dlg, "cb_bitrate")
    assert hasattr(dlg, "btn_up")
    assert hasattr(dlg, "btn_down")
    assert hasattr(dlg, "btn_copy_cmd")
    assert hasattr(dlg, "txt_cmd_preview")

    assert "can0" in dlg.txt_cmd_preview.text()

    # Explicitly set bitrate to 500000 and verify preview
    dlg.cb_bitrate.setCurrentText("500000")
    assert "500000" in dlg.txt_cmd_preview.text()

    # Changing interface updates command preview
    dlg.cb_iface.setCurrentText("can1")
    assert "can1" in dlg.txt_cmd_preview.text()

    # Changing bitrate updates command preview
    dlg.cb_bitrate.setCurrentText("250000")
    assert "250000" in dlg.txt_cmd_preview.text()

    cfg = dlg.get_config()
    assert cfg["channel"] == "can1"
    assert cfg["bitrate"] == 250000
    print("  [OK] SocketCANConfigDialog parâmetros e reatividade validados com sucesso!")


def test_connection_dialog_integration():
    print("Testando integração do botão de gerenciamento no ConnectionDialog...")
    app = QApplication.instance() or QApplication(sys.argv)

    conn_dlg = ConnectionDialog()
    assert hasattr(conn_dlg, "btn_manage_can"), "ConnectionDialog deve conter btn_manage_can"

    # No modo Hardware Real com socketcan
    conn_dlg.cb_mode.setCurrentIndex(0)
    conn_dlg.cb_interface.setCurrentText("socketcan")
    conn_dlg._on_interface_changed()
    assert not conn_dlg.btn_manage_can.isHidden(), "btn_manage_can deve estar visível para socketcan"

    # Mudando para slcan -> deve ocultar
    conn_dlg.cb_interface.setCurrentText("slcan")
    conn_dlg._on_interface_changed()
    assert conn_dlg.btn_manage_can.isHidden(), "btn_manage_can deve estar oculto para slcan"

    # Mudando para Playback sem Tx -> deve ocultar
    conn_dlg.cb_mode.setCurrentIndex(2)
    conn_dlg.chk_transmit.setChecked(False)
    conn_dlg.on_mode_change(2)
    assert conn_dlg.btn_manage_can.isHidden()

    # Playback com Tx e socketcan -> deve exibir
    conn_dlg.cb_interface.setCurrentText("socketcan")
    conn_dlg.chk_transmit.setChecked(True)
    conn_dlg.on_mode_change(2)
    assert not conn_dlg.btn_manage_can.isHidden()
    print("  [OK] Visibilidade condicional de btn_manage_can funcionando perfeitamente!")


def test_playback_transmit_extended_id():
    print("Testando transmissão de frames no Playback com suporte a Extended IDs...")

    worker = CANWorker()
    worker.mode = "PLAYBACK"
    worker.playback_transmit = True

    mock_bus = MagicMock()
    worker.bus = mock_bus

    # Mock rows with extended ID 0xCF00400 (217056256 > 0x7FF) and standard ID 0x123
    worker.playback_rows = [
        ["100.0", "CF00400", "8", "240", "255", "140", "124", "28", "255", "255", "255"],
        ["100.1", "123", "4", "01", "02", "03", "04"]
    ]
    worker.playback_total = len(worker.playback_rows)
    worker.running = True
    worker.playback_speed = 100.0
    worker.playback_loop = False
    worker.playback_byte_format = "DEC"

    # Test send_message
    worker.send_message(0xCF00400, [0xF0, 0xFF])
    assert mock_bus.send.called
    sent_msg = mock_bus.send.call_args[0][0]
    assert sent_msg.arbitration_id == 0xCF00400
    assert sent_msg.is_extended_id == True, "ID 0xCF00400 deve ter is_extended_id=True!"
    print("  [OK] send_message identificou corretamente is_extended_id=True para 0xCF00400!")

    # Test standard ID
    worker.send_message(0x123, [0x01, 0x02])
    sent_msg2 = mock_bus.send.call_args[0][0]
    assert sent_msg2.arbitration_id == 0x123
    assert sent_msg2.is_extended_id == False, "ID 0x123 deve ter is_extended_id=False!"
    print("  [OK] send_message identificou corretamente is_extended_id=False para 0x123!")

    # Test stop cleans up bus
    worker.stop()
    assert worker.bus is None
    assert mock_bus.shutdown.called
    print("  [OK] stop() encerrou e liberou o barramento de hardware com sucesso!")


if __name__ == "__main__":
    test_socketcan_config_dialog_and_helpers()
    test_connection_dialog_integration()
    test_playback_transmit_extended_id()
    print("\nTODOS OS TESTES DE SOCKETCAN E PLAYBACK TX PASSARAM COM SUCESSO!")
