"""
worker.py — Thread de captura/envio CAN (CANWorker)

Responsabilidade: toda comunicação com o barramento CAN.
Suporta três modos: SIMULATED, HARDWARE (via python-can), PLAYBACK (CSV).

Sinais emitidos:
  - frame_received(can_id: int, freq: float, payload: list[int])
  - error_occurred(msg: str)

Uso:
  worker = CANWorker()
  worker.mode = "SIMULATED"
  worker.frame_received.connect(handler)
  worker.start()
  ...
  worker.stop()
"""
from __future__ import annotations

import time
import random
import csv
import can
from PyQt6.QtCore import QThread, pyqtSignal
from src.simulator import CANSimulator


class CANWorker(QThread):
    """
    Thread de CAN Bus que suporta Simulação, Hardware Real (python-can) e Playback.
    """
    frame_received = pyqtSignal(int, float, list)
    error_occurred = pyqtSignal(str)
    playback_progress = pyqtSignal(int, int)
    error_frame_received = pyqtSignal(int, str, str)  # can_id, error_type, description

    def __init__(self):
        super().__init__()
        self.running = False
        self.mode = "SIMULATED"
        self.bus = None
        self.playback_file = ""
        self.playback_transmit = False
        self.playback_loop = False
        self.playback_paused = False
        self.playback_speed = 1.0
        self.seek_requested = None
        self.playback_rows = []
        self.playback_total = 0
        self.playback_index = 0
        self.last_timestamps = {}
        self.counters = {0x0C0: 0, 0x180: 0, 0x3F0: 0}
        self.toggle_111 = False

    def run(self):
        self.running = True

        if self.mode == "HARDWARE" and self.bus:
            self._run_hardware()
        elif self.mode == "PLAYBACK" and self.playback_file:
            self._run_playback()
        elif self.mode == "SIMULATED":
            self._run_simulated()
        else:
            while self.running:
                time.sleep(0.5)

    def _run_hardware(self):
        try:
            while self.running:
                msg = self.bus.recv(timeout=0.1)
                if msg and msg.arbitration_id is not None:
                    current_time = time.time()
                    can_id = msg.arbitration_id

                    # Separar error frames — não poluir a aba de Análise
                    if msg.is_error_frame:
                        err_type, err_desc = self._decode_error_frame(can_id, msg)
                        self.error_frame_received.emit(can_id, err_type, err_desc)
                        continue

                    if can_id in self.last_timestamps:
                        period = current_time - self.last_timestamps[can_id]
                        freq = 1.0 / period if period > 0 else 0.0
                    else:
                        freq = 0.0

                    self.last_timestamps[can_id] = current_time
                    self.frame_received.emit(can_id, freq, list(msg.data))
        except Exception as e:
            self.error_occurred.emit(f"Erro no barramento CAN: {e}")
            self.running = False

    @staticmethod
    def _decode_error_frame(can_id: int, msg) -> tuple:
        """Decodifica um error frame do SocketCAN e retorna (tipo, descrição)."""
        # Os bits do arbitration_id em error frames carregam flags de erro
        arb = can_id

        if arb & 0x0001:  # CAN_ERR_TX_TIMEOUT
            return "TX Timeout", "Frame de transmissão expirou sem ACK"
        if arb & 0x0004:  # CAN_ERR_LOSTARB
            return "Lost Arbitration", "Perda de arbitragem no barramento"
        if arb & 0x0008:  # CAN_ERR_CRTL
            return "Controller Error", "Erro interno do controlador CAN"
        if arb & 0x0010:  # CAN_ERR_PROT
            return "Protocol Violation", "Violação de protocolo CAN detectada"
        if arb & 0x0020:  # CAN_ERR_TRX
            return "Transceiver Error", "Erro no transceiver / hardware físico"
        if arb & 0x0040:  # CAN_ERR_ACK
            return "No ACK", "Nenhum nó reconheceu o frame (sem ACK)"
        if arb & 0x0080:  # CAN_ERR_BUSOFF
            return "Bus-Off", "Controlador entrou em estado Bus-Off"
        if arb & 0x0100:  # CAN_ERR_BUSERROR
            return "Bus Error", "Erro detectado no barramento CAN"
        if arb & 0x0200:  # CAN_ERR_RESTARTED
            return "Bus Restarted", "Controlador reiniciado após Bus-Off"

        # Sem flag específica reconhecida
        data_hex = " ".join(f"{b:02X}" for b in msg.data) if msg.data else ""
        return "Error Frame", f"Frame de erro genérico (ID={can_id:#05x}, data={data_hex})"

    def _run_playback(self):
        try:
            with open(self.playback_file, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                self.playback_rows = [row for row in reader if len(row) >= 4]

            self.playback_total = len(self.playback_rows)
            self.playback_index = 0
            self.playback_paused = False

            while self.running:
                last_msg_time = None

                while self.playback_index < self.playback_total and self.running:
                    # Se estiver pausado, aguarda comandos mantendo a UI responsiva ao seek
                    while self.playback_paused and self.running:
                        if self.seek_requested is not None:
                            self.playback_index = max(0, min(self.seek_requested, self.playback_total - 1))
                            self.seek_requested = None
                            last_msg_time = None
                            if 0 <= self.playback_index < self.playback_total:
                                row = self.playback_rows[self.playback_index]
                                try:
                                    can_id = int(row[1], 16)
                                    payload = [int(x, 16) for x in row[3:]]
                                    self.frame_received.emit(can_id, 0.0, payload)
                                    self.playback_progress.emit(self.playback_index, self.playback_total)
                                except Exception:
                                    pass
                        time.sleep(0.04)

                    if not self.running:
                        break

                    if self.seek_requested is not None:
                        self.playback_index = max(0, min(self.seek_requested, self.playback_total - 1))
                        self.seek_requested = None
                        last_msg_time = None
                        
                    if self.playback_index >= self.playback_total:
                        break

                    row = self.playback_rows[self.playback_index]

                    timestamp = float(row[0])
                    can_id = int(row[1], 16)
                    payload = [int(x, 16) for x in row[3:]]

                    if last_msg_time is not None:
                        delay = timestamp - last_msg_time
                        if delay > 0:
                            effective_delay = delay / max(0.1, self.playback_speed)
                            # Fatias pequenas de sleep para responder instantaneamente a pause/seek/stop
                            while effective_delay > 0.04 and self.running and not self.playback_paused and self.seek_requested is None:
                                time.sleep(0.04)
                                effective_delay -= 0.04
                            if effective_delay > 0 and self.running and not self.playback_paused and self.seek_requested is None:
                                time.sleep(effective_delay)

                    if self.seek_requested is not None or self.playback_paused:
                        continue

                    last_msg_time = timestamp

                    if self.playback_transmit and self.bus:
                        try:
                            msg = can.Message(arbitration_id=can_id, data=payload, is_extended_id=False)
                            self.bus.send(msg)
                        except Exception:
                            pass

                    current_time = time.time()
                    if can_id in self.last_timestamps:
                        period = current_time - self.last_timestamps[can_id]
                        freq = 1.0 / period if period > 0 else 0.0
                    else:
                        freq = 0.0

                    self.last_timestamps[can_id] = current_time
                    self.frame_received.emit(can_id, freq, payload)
                    self.playback_progress.emit(self.playback_index, self.playback_total)
                    
                    self.playback_index += 1

                if not self.running or not self.playback_loop:
                    break
                
                self.playback_index = 0 # loop reseta

            if self.running:
                self.error_occurred.emit("Reprodução concluída com sucesso.")

        except Exception as e:
            self.error_occurred.emit(f"Erro no playback: {e}")

        self.running = False

    def _run_simulated(self):
        simulator = CANSimulator(self._emit_simulated_frame)
        while self.running:
            simulator.step()

    def _emit_simulated_frame(self, can_id: int, payload: list):
        """Callback chamado pelo CANSimulator: calcula frequência e emite o sinal Qt."""
        current_time = time.time()
        if can_id in self.last_timestamps:
            period = current_time - self.last_timestamps[can_id]
            freq = 1.0 / period if period > 0 else 0.0
        else:
            freq = 0.0
        self.last_timestamps[can_id] = current_time
        self.frame_received.emit(can_id, freq, payload)

    def stop(self):
        self.running = False

    def pause_playback(self):
        self.playback_paused = True

    def resume_playback(self):
        self.playback_paused = False

    def toggle_pause_playback(self) -> bool:
        self.playback_paused = not self.playback_paused
        return self.playback_paused

    def stop_playback(self):
        self.playback_paused = True
        if hasattr(self, "playback_total") and self.playback_total > 0:
            self.seek_requested = 0

    def seek_playback(self, val_permille: int | float):
        """Muda a posição para um percentual de 0 a 1000 (para maior resolução)."""
        if self.mode == "PLAYBACK" and hasattr(self, "playback_total") and self.playback_total > 0:
            target = int((float(val_permille) / 1000.0) * self.playback_total)
            self.seek_requested = max(0, min(target, self.playback_total - 1))

    def set_playback_speed(self, speed: float):
        self.playback_speed = max(0.1, float(speed))

    def set_playback_loop(self, loop: bool):
        self.playback_loop = bool(loop)

    def send_message(self, can_id, data):
        """Injeta um frame no barramento. Em modo simulado, re-emite o sinal."""
        if self.mode == "SIMULATED":
            current_time = time.time()
            if can_id in self.last_timestamps:
                period = current_time - self.last_timestamps[can_id]
                freq = 1.0 / period if period > 0 else 0.0
            else:
                freq = 0.0
            self.last_timestamps[can_id] = current_time
            self.frame_received.emit(can_id, freq, data)
        elif self.mode == "HARDWARE" and self.bus:
            try:
                msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
                self.bus.send(msg)
                
                # Loopback local para atualizar a interface (indicadores)
                current_time = time.time()
                if can_id in self.last_timestamps:
                    period = current_time - self.last_timestamps[can_id]
                    freq = 1.0 / period if period > 0 else 0.0
                else:
                    freq = 0.0
                self.last_timestamps[can_id] = current_time
                self.frame_received.emit(can_id, freq, data)
            except Exception as e:
                print(f"Erro de Tx no Barramento: {e}")
