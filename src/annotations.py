"""
annotations.py — Sistema de persistência e consulta de anotações

Responsabilidade: ler/escrever o arquivo CANweaver_Projeto.md e manter
o dicionário em memória com as anotações do usuário.

Formato do arquivo .md:
  ## [ID 0C0] - 2024-01-01 10:00:00
  Texto do comentário

  ## [ID 0C0 - Byte 2] - 2024-01-01 10:01:00
  Comentário sobre o byte

  ## [ID 0C0 - Byte 2 - Bit 7] - 2024-01-01 10:02:00
  Comentário sobre um bit específico

Uso:
  mgr = AnnotationManager(project_dir)
  mgr.load()
  comments = mgr.get_tooltip_for_byte("0C0", 2)
  mgr.add_comment("ID 0C0 - Byte 2", "Ângulo de direção")
"""
from __future__ import annotations

import os
import re
from PyQt6.QtCore import QDateTime


def normalize_can_hex(id_val: str | int) -> str:
    """Converte ID CAN (0x0C0, 0c0, C0, 192 dec, int, etc.) para hex padronizado maiúsculo."""
    s = str(id_val).strip()
    if not s:
        return ""
    try:
        val = int(s, 16) if not s.lower().startswith("0x") else int(s, 0)
    except ValueError:
        try:
            val = int(s, 10)
        except ValueError:
            return s.upper()
    if val <= 0x7FF:
        return f"{val:03X}"
    return f"{val:X}"


def normalize_target(target: str) -> str:
    """
    Normaliza a string de alvo para garantir casamento seguro independente de variações.
    Exemplos:
      'ID 0x0c0' -> 'ID 0C0'
      '0x0c0' -> 'ID 0C0'
      'ID c0' -> 'ID 0C0'
      'ID 0C0 - Byte 2' -> 'ID 0C0 - Byte 2'
      'ID 0c0 - byte 2 - bit 7' -> 'ID 0C0 - Byte 2 - Bit 7'
    """
    t = str(target).strip()
    m = re.match(r"^(?:ID\s+)?([0-9a-fA-FxX]+)(.*)$", t, re.IGNORECASE)
    if not m:
        return t
    raw_id = m.group(1)
    rest = m.group(2)
    try:
        int(raw_id, 16) if not raw_id.lower().startswith("0x") else int(raw_id, 0)
    except ValueError:
        return t

    canon_id = normalize_can_hex(raw_id)

    if rest:
        m_byte_bit = re.match(r"^\s*-\s*byte\s*(\d+)\s*-\s*bit\s*(\d+)", rest, re.IGNORECASE)
        if m_byte_bit:
            return f"ID {canon_id} - Byte {m_byte_bit.group(1)} - Bit {m_byte_bit.group(2)}"
        m_byte = re.match(r"^\s*-\s*byte\s*(\d+)", rest, re.IGNORECASE)
        if m_byte:
            return f"ID {canon_id} - Byte {m_byte.group(1)}"
    return f"ID {canon_id}"


class AnnotationManager:
    """Gerencia anotações salvas em CANweaver_Projeto.md."""

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.filename = os.path.join(project_dir, "CANweaver_Projeto.md")
        self.annotations: dict[str, list[str]] = {}

    def load(self):
        """Carrega anotações do arquivo .md para a memória."""
        self.annotations.clear()  # Sempre reseta antes de carregar
        if not os.path.exists(self.filename):
            return

        try:
            with open(self.filename, "r", encoding="utf-8-sig") as f:
                lines = f.readlines()
        except Exception:
            return

        current_target = None
        current_comment = []

        for line in lines:
            line_str = line.strip().lstrip("\ufeff")
            if re.match(r"^##\s*\[", line_str):
                if current_target and current_comment:
                    self._save_to_dict(current_target, "\n".join(current_comment).strip())
                m = re.search(r"##\s*\[(.*?)\]", line_str)
                if m:
                    current_target = m.group(1).strip()
                current_comment = []
            else:
                if current_target and line_str != "":
                    current_comment.append(line_str)

        if current_target and current_comment:
            self._save_to_dict(current_target, "\n".join(current_comment).strip())

    def clear(self):
        """Apaga todas as anotações da memória e do arquivo."""
        self.annotations.clear()
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                f.write("")
        except Exception:
            pass

    def add_comment(self, target: str, text: str):
        """Adiciona um comentário ao arquivo e ao dicionário em memória."""
        if not text:
            return
        norm_target = normalize_target(target)
        with open(self.filename, "a", encoding="utf-8") as f:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            f.write(f"\n## [{norm_target}] - {timestamp}\n")
            f.write(f"{text}\n")
        self._save_to_dict(norm_target, text)

    def append_raw_markdown(self, markdown_text: str):
        """Acrescenta texto Markdown gerado pela IA ou usuário diretamente ao arquivo de projeto."""
        if not markdown_text:
            return
        with open(self.filename, "a", encoding="utf-8") as f:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            f.write(f"\n\n<!-- Adicionado via CAN Copilot em {timestamp} -->\n")
            f.write(f"{markdown_text.strip()}\n")
        self.load()

    def _save_to_dict(self, target: str, comment: str):
        if not comment:
            return
        norm_target = normalize_target(target)
        if norm_target not in self.annotations:
            self.annotations[norm_target] = []
        self.annotations[norm_target].append(comment)

    def get_tooltip_for_id(self, hex_id: str) -> str:
        canon_id = normalize_can_hex(hex_id)
        target = f"ID {canon_id}"
        if target in self.annotations:
            return "\n---\n".join(self.annotations[target])
        return ""

    def get_tooltip_for_byte(self, hex_id: str, byte_idx: int) -> str:
        canon_id = normalize_can_hex(hex_id)
        comments = []
        base_target = f"ID {canon_id} - Byte {byte_idx}"

        if base_target in self.annotations:
            comments.extend(self.annotations[base_target])

        for target, texts in self.annotations.items():
            if target.startswith(f"{base_target} - Bit"):
                bit_str = target.split(" - ")[-1]
                for t in texts:
                    comments.append(f"[{bit_str}] {t}")

        return "\n---\n".join(comments) if comments else ""

    def get_annotation_info(self, hex_id: str, byte_idx: int):
        """
        Retorna (has_any, bitmask, has_byte):
          has_any  — bool: existe alguma anotação neste byte/bits
          bitmask  — int:  máscara com quais bits têm anotação (bit N → 1 << N)
          has_byte — bool: existe anotação no byte inteiro (não em bits específicos)
        """
        canon_id = normalize_can_hex(hex_id)
        base_target = f"ID {canon_id} - Byte {byte_idx}"
        has_byte = base_target in self.annotations
        has_any = has_byte
        mask = 0
        bit_prefix = f"{base_target} - Bit "
        for target in self.annotations.keys():
            if target.startswith(bit_prefix):
                has_any = True
                try:
                    bit_idx = int(target.replace(bit_prefix, ""))
                    mask |= (1 << bit_idx)
                except ValueError:
                    pass
        return has_any, mask, has_byte
