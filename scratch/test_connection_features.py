import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtWidgets import QApplication

def test_connection_features():
    app = QApplication.instance() or QApplication(sys.argv)

    print("1. Testando ConnectionDialog novos controles e adaptação SLCAN/SocketCAN...")
    from src.dialogs import ConnectionDialog, take_down_socketcan, bring_up_socketcan

    dlg = ConnectionDialog()
    assert hasattr(dlg, "btn_detect_ports"), "ConnectionDialog deve conter btn_detect_ports"
    assert hasattr(dlg, "btn_kill_can"), "ConnectionDialog deve conter btn_kill_can"
    assert hasattr(dlg, "lbl_interface_hint"), "ConnectionDialog deve conter lbl_interface_hint"

    # Testando modo socketcan
    dlg.cb_mode.setCurrentIndex(0) # Hardware Real
    dlg.cb_interface.setCurrentText("socketcan")
    dlg._on_interface_changed()
    assert not dlg.btn_manage_can.isHidden(), "btn_manage_can deve estar visível para socketcan"
    assert not dlg.btn_kill_can.isHidden(), "btn_kill_can deve estar visível para socketcan"
    assert dlg.btn_detect_ports.isHidden(), "btn_detect_ports deve estar oculto para socketcan"
    assert "SocketCAN" in dlg.lbl_interface_hint.text()

    # Testando modo slcan (Makerbase CANable)
    dlg.cb_interface.setCurrentText("slcan")
    dlg._on_interface_changed()
    assert dlg.btn_manage_can.isHidden(), "btn_manage_can deve estar oculto para slcan"
    assert dlg.btn_kill_can.isHidden(), "btn_kill_can deve estar oculto para slcan"
    assert not dlg.btn_detect_ports.isHidden(), "btn_detect_ports deve estar visível para slcan"
    assert "Makerbase CANable" in dlg.lbl_interface_hint.text()
    print("  [OK] Controles de SLCAN e SocketCAN validados com sucesso no ConnectionDialog!")

    print("2. Testando MainWindow botão de tomada e desconexão...")
    from main import MainWindow
    win = MainWindow()
    assert hasattr(win, "btn_conn_toggle"), "MainWindow deve conter btn_conn_toggle no cabeçalho"
    assert "Conectar" in win.btn_conn_toggle.text()
    assert win.is_connected is False

    # Simular conexão iniciada
    win._start_worker({"mode": "SIMULATED", "interface": "virtual", "channel": "0", "bitrate": 500000})
    assert win.is_connected is True
    assert "Conectado" in win.btn_conn_toggle.text()
    assert win.lbl_status.text() == "Simulado"

    # Simular desconexão
    win._disconnect_can(take_down_iface=False)
    assert win.is_connected is False
    assert "Conectar" in win.btn_conn_toggle.text()
    assert win.lbl_status.text() == "Desconectado"
    assert win.can_thread.mode == "IDLE"
    print("  [OK] Alternância de status de conexão, worker IDLE e botão de tomada validados com sucesso!")

    win.can_thread.stop()
    win.can_thread.wait(1000)
    print("\nTODOS OS TESTES DE CONEXÃO E TOMADA PASSARAM COM SUCESSO!")

if __name__ == "__main__":
    test_connection_features()
