"""
action_capture.py — Motor de captura de janelas de tráfego CAN e cálculo de deltas de sinais para a IA.
Permite ao usuário gravar uma ação física no veículo/barramento e compilar um resumo estatístico para o CAN Copilot.
"""

import time
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class ActionCaptureEngine(QObject):
    """
    Grava frames CAN por um período de tempo determinado (ex: 2.5 a 3 segundos)
    e calcula os deltas de bytes, variações de bits e contadores para análise pela IA.
    """
    capture_progress = pyqtSignal(float)   # Progresso 0.0 a 1.0
    capture_finished = pyqtSignal(dict, str) # report_dict, formatted_markdown

    def __init__(self, can_worker_ref=None, parent=None):
        super().__init__(parent)
        self.can_worker = can_worker_ref
        self.is_capturing = False
        self.user_description = ""
        self.duration_sec = 3.0
        self.start_time = 0.0
        
        self.recorded_frames: list[tuple[float, int, float, list[int]]] = []
        
        self.timer_tick = QTimer(self)
        self.timer_tick.setInterval(50)
        self.timer_tick.timeout.connect(self._on_tick)

    def start_capture(self, description: str = "", duration_sec: float = 3.0):
        """Inicia a captura de uma janela de ação no barramento."""
        if self.is_capturing:
            return
        
        self.user_description = description.strip()
        self.duration_sec = max(1.0, min(10.0, duration_sec))
        self.recorded_frames.clear()
        self.start_time = time.time()
        self.is_capturing = True

        if self.can_worker:
            self.can_worker.frame_received.connect(self._on_frame_received)

        self.timer_tick.start()

    def _on_frame_received(self, can_id: int, freq: float, payload: list):
        if not self.is_capturing:
            return
        now = time.time()
        self.recorded_frames.append((now, can_id, freq, list(payload)))

    def _on_tick(self):
        if not self.is_capturing:
            return
        elapsed = time.time() - self.start_time
        progress = min(1.0, elapsed / self.duration_sec)
        self.capture_progress.emit(progress)

        if elapsed >= self.duration_sec:
            self.stop_capture()

    def stop_capture(self):
        """Finaliza a captura e compila o relatório estatístico."""
        if not self.is_capturing:
            return
        self.is_capturing = False
        self.timer_tick.stop()

        if self.can_worker:
            try:
                self.can_worker.frame_received.disconnect(self._on_frame_received)
            except Exception:
                pass

        report_dict, formatted_md = self._compile_report()
        self.capture_finished.emit(report_dict, formatted_md)

    def _compile_report(self) -> tuple[dict, str]:
        total_frames = len(self.recorded_frames)
        by_id: dict[int, dict] = {}

        for t, can_id, freq, payload in self.recorded_frames:
            if can_id not in by_id:
                by_id[can_id] = {
                    "count": 0,
                    "last_freq": freq,
                    "first_payload": list(payload),
                    "last_payload": list(payload),
                    "min_bytes": list(payload),
                    "max_bytes": list(payload),
                    "bit_flips": [0] * len(payload),
                    "previous_payload": list(payload)
                }
            
            entry = by_id[can_id]
            entry["count"] += 1
            entry["last_freq"] = freq
            entry["last_payload"] = list(payload)

            # Ajusta tamanho caso payload mude
            while len(entry["min_bytes"]) < len(payload):
                entry["min_bytes"].append(255)
                entry["max_bytes"].append(0)
                entry["bit_flips"].append(0)
                entry["previous_payload"].append(0)

            for b_idx, val in enumerate(payload):
                if val < entry["min_bytes"][b_idx]:
                    entry["min_bytes"][b_idx] = val
                if val > entry["max_bytes"][b_idx]:
                    entry["max_bytes"][b_idx] = val
                
                # Bit flips
                xor_diff = val ^ entry["previous_payload"][b_idx]
                entry["bit_flips"][b_idx] |= xor_diff
                entry["previous_payload"][b_idx] = val

        # Identifica IDs com variação
        changed_ids = []
        for can_id, info in by_id.items():
            variations = []
            for b_idx in range(len(info["min_bytes"])):
                min_v = info["min_bytes"][b_idx]
                max_v = info["max_bytes"][b_idx]
                first_v = info["first_payload"][b_idx] if b_idx < len(info["first_payload"]) else 0
                last_v = info["last_payload"][b_idx] if b_idx < len(info["last_payload"]) else 0
                flips = info["bit_flips"][b_idx]

                if min_v != max_v or flips != 0:
                    variations.append({
                        "byte_idx": b_idx,
                        "min": min_v,
                        "max": max_v,
                        "first": first_v,
                        "last": last_v,
                        "delta": last_v - first_v,
                        "bit_flips_hex": f"0x{flips:02X}"
                    })
            if variations:
                changed_ids.append({
                    "can_id": can_id,
                    "can_id_hex": f"0x{can_id:03X}" if can_id <= 0x7FF else f"0x{can_id:08X}",
                    "count": info["count"],
                    "freq": info["last_freq"],
                    "variations": variations
                })

        report_dict = {
            "description": self.user_description,
            "duration": round(time.time() - self.start_time, 2),
            "total_frames": total_frames,
            "total_ids": len(by_id),
            "changed_ids": changed_ids,
            "all_active_ids": [f"0x{cid:03X}" if cid <= 0x7FF else f"0x{cid:08X}" for cid in sorted(by_id.keys())]
        }

        # Formata em Markdown legível
        md = []
        md.append(f"### 📊 Relatório de Ação Capturada ({report_dict['duration']}s | {total_frames} frames)")
        if self.user_description:
            md.append(f"**Ação relatada pelo usuário:** *\"{self.user_description}\"*")
        
        md.append(f"**IDs Ativos no Barramento ({len(by_id)}):** `{'`, `'.join(report_dict['all_active_ids'])}`\n")

        if changed_ids:
            md.append("#### 🎯 IDs que Apresentaram Variação durante a Ação:")
            for item in changed_ids:
                md.append(f"- **ID `{item['can_id_hex']}`** ({item['count']} frames | ~{item['freq']:.1f} Hz):")
                for var in item["variations"]:
                    md.append(
                        f"  - **Byte {var['byte_idx']}**: Variou de `0x{var['min']:02X}` ({var['min']}) até `0x{var['max']:02X}` ({var['max']}) "
                        f"[Primeiro: `0x{var['first']:02X}`, Último: `0x{var['last']:02X}`, Delta: `{var['delta']:+d}`, Bits alternados: `{var['bit_flips_hex']}`]"
                    )
        else:
            md.append("ℹ️ *Nenhum byte apresentou variação significativa durante a janela de captura.*")

        formatted_md = "\n".join(md)
        return report_dict, formatted_md
