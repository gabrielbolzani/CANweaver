"""
simulator.py — Gerador de frames CAN simulados (CANSimulator)

Responsabilidade: gerar frames CAN com dados realistas para testes
sem necessidade de hardware físico.

Canais simulados:
  - 0x100: RPM (bytes 0-1, senoidal 800~6000 rpm) e Velocidade (byte 2, dente-de-serra 0~180 km/h)
  - 0x200: Temperatura do motor (byte 0, sobe até 90°C) e Nível de combustível (byte 1, desce de 100 a 0)
  - 0x300: Indicadores de painel (byte 0, bits: 0=pisca esq, 1=pisca dir, 2=farol alto, 3=freio de mão)

Uso:
  sim = CANSimulator(callback)
  while running:
      sim.step()  # bloqueia ~50ms por iteração
"""

import time
import math


class CANSimulator:
    """Gerador de frames CAN com sinais realistas para modo simulado."""

    def __init__(self, emit_callback):
        """
        Args:
            emit_callback: callable(can_id: int, payload: list[int])
                           Chamado a cada frame gerado.
        """
        self.emit_callback = emit_callback
        self.start_time = time.time()
        self.blinker_state = False
        self.last_blinker_toggle = time.time()

    def step(self):
        """Gera um ciclo de frames e dorme ~50ms."""
        t = time.time() - self.start_time
        current_time = time.time()

        # ── 0x100 — Motor / Velocidade ─────────────────────────────────────
        # RPM: onda senoidal entre 800 e 6000 rpm (ciclo de 10 s)
        rpm = int(3400 + 2600 * math.sin(t * 2 * math.pi / 10))
        # Velocidade: 0 a 180 km/h (dente-de-serra, 20 km/h por segundo)
        speed = int((t * 20) % 180)

        payload_100 = [
            (rpm >> 8) & 0xFF,
            rpm & 0xFF,
            speed,
            0x00, 0x00, 0x00, 0x00, 0x00,
        ]
        self.emit_callback(0x100, payload_100)

        # ── 0x200 — Temperaturas e Níveis ──────────────────────────────────
        # Temp do motor: sobe 2°C/s até 90°C e estabiliza
        temp = min(90, int(t * 2))
        # Combustível: desce de 100 a 0 (1 unidade a cada 2 s)
        fuel = max(0, 100 - int(t / 2))

        payload_200 = [
            temp,
            fuel,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ]
        self.emit_callback(0x200, payload_200)

        # ── 0x300 — Indicadores de painel ──────────────────────────────────
        # Pisca-pisca: alterna a cada 0,5 s
        if current_time - self.last_blinker_toggle > 0.5:
            self.blinker_state = not self.blinker_state
            self.last_blinker_toggle = current_time

        pisca_esq = 1 if self.blinker_state else 0
        pisca_dir = 0 if self.blinker_state else 1
        # Farol alto: liga nos segundos 5-9 de cada ciclo de 10 s
        farol = 1 if (int(t) % 10) > 5 else 0
        # Freio de mão: ligado nos primeiros 10 s
        freio = 1 if t < 10 else 0

        led_byte = (freio << 3) | (farol << 2) | (pisca_dir << 1) | pisca_esq

        payload_300 = [
            led_byte, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        ]
        self.emit_callback(0x300, payload_300)

        # Sleep curto para ~20 Hz de atualização
        time.sleep(0.05)
