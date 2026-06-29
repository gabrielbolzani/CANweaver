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

import time
import random
import csv
import can
from PyQt6.QtCore import QThread, pyqtSignal


class CANWorker(QThread):
    """
    Thread de CAN Bus que suporta Simulação, Hardware Real (python-can) e Playback.
    """
    frame_received = pyqtSignal(int, float, list)
    error_occurred = pyqtSignal(str)
    playback_progress = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.running = False
        self.mode = "SIMULATED"
        self.bus = None
        self.playback_file = ""
        self.playback_transmit = False
        self.playback_loop = False
        self.seek_requested = None
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

    def _run_playback(self):
        try:
            with open(self.playback_file, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                self.playback_rows = [row for row in reader if len(row) >= 4]

            self.playback_total = len(self.playback_rows)
            self.playback_index = 0

            while self.running:
                last_msg_time = None

                while self.playback_index < self.playback_total and self.running:
                    if self.seek_requested is not None:
                        self.playback_index = self.seek_requested
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
                            time.sleep(delay)

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
        target_ids = [0x0C0, 0x180, 0x3F0, 0x111]
        while self.running:
            time.sleep(random.choice([0.01, 0.05, 0.1]))
            can_id = random.choice(target_ids)
            current_time = time.time()

            if can_id in self.last_timestamps:
                period = current_time - self.last_timestamps[can_id]
                freq = 1.0 / period if period > 0 else 0.0
            else:
                freq = random.uniform(10.0, 80.0)

            self.last_timestamps[can_id] = current_time

            if can_id == 0x0C0:
                self.counters[0x0C0] = (self.counters[0x0C0] + 1) % 16
                payload = [0x01, random.randint(0x00, 0xFF), random.randint(0x00, 0x02),
                           0x00, 0x00, 0x00, 0x00, self.counters[0x0C0]]
            elif can_id == 0x180:
                payload = [0x20, 0x00, random.choice([0x00, 0x01]), 0x00, 0x00, 0x00, 0x00, 0x00]
            elif can_id == 0x111:
                self.toggle_111 = not self.toggle_111
                # Alterna o bit 1 do byte 0 (0x02 = 00000010)
                val = 0x02 if self.toggle_111 else 0x00
                payload = [val, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
            else:
                payload = [random.randint(0x08, 0x0F), random.randint(0x00, 0xFF),
                           0x55, 0xAA, 0x00, 0x00, 0x00, 0x00]

            self.frame_received.emit(can_id, freq, payload)

    def stop(self):
        self.running = False

    def seek_playback(self, index_pct: int):
        """Muda a posição para um percentual ou posição."""
        if self.mode == "PLAYBACK":
            self.seek_requested = int((index_pct / 100.0) * self.playback_total)

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
