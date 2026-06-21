"""
delegate.py — Renderizador customizado de células da tabela (CANItemDelegate)

Responsabilidade: pintar os bytes da grelha CAN.
  - Modo HEX: exibe o valor em hexadecimal com borda amarela se anotado.
  - Modo BIN: desenha 8 quadradinhos por byte com a label "76543210",
              destaca bits alterados em verde, bits anotados com borda amarela,
              e aplica fade baseado na cor de fundo da célula.

Roles usados nos QStandardItem:
  UserRole      → string binária do valor ANTERIOR (para detectar mudança)
  UserRole+1    → bool: célula/byte tem alguma anotação
  UserRole+3    → int bitmask: quais bits específicos têm anotação
  UserRole+4    → bool: o BYTE inteiro (não só bits) tem anotação
"""

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtGui import QPainter, QColor, QFont, QPen


class CANItemDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        is_annotated = index.data(Qt.ItemDataRole.UserRole + 1)
        annotated_mask = index.data(Qt.ItemDataRole.UserRole + 3) or 0
        has_byte_annot = index.data(Qt.ItemDataRole.UserRole + 4)
        if has_byte_annot is None:
            has_byte_annot = is_annotated

        text = index.data(Qt.ItemDataRole.DisplayRole)
        is_binary = text and len(text) == 8 and all(c in '01' for c in text) and index.column() >= 2

        if is_binary:
            painter.save()

            bg_brush = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg_brush:
                painter.fillRect(option.rect, bg_brush)
            else:
                if option.state & QStyle.StateFlag.State_Selected:
                    painter.fillRect(option.rect, option.palette.highlight())

            old_bin = index.data(Qt.ItemDataRole.UserRole)
            if not old_bin or len(old_bin) != 8:
                old_bin = text

            rect = option.rect
            header_str = "76543210"

            painter.setPen(QColor("#69697a"))
            header_font = QFont("Courier New", 7)
            painter.setFont(header_font)
            painter.drawText(rect.adjusted(0, 2, 0, 0),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, header_str)

            margin_x = 4
            available_width = rect.width() - (margin_x * 2)
            square_size = min(available_width // 8, rect.height() - 16)
            if square_size > 14:
                square_size = 14

            spacing = (available_width - (square_size * 8)) / 7 if available_width > (square_size * 8) else 1
            if spacing > 4:
                spacing = 4

            total_draw_width = (square_size * 8) + (spacing * 7)
            start_x = rect.x() + (rect.width() - total_draw_width) // 2
            start_y = rect.y() + 14

            for i in range(8):
                bit_rect = QRect(int(start_x + i * (square_size + spacing)),
                                 int(start_y), int(square_size), int(square_size))

                bit_val = text[i]
                changed = (bit_val != old_bin[i])

                bg_color_name = bg_brush.color().name() if bg_brush else ""

                if changed:
                    fill_color = QColor("#04d361")
                    pen_color = QColor("#04d361")
                else:
                    if bg_color_name == "#1a1a1e":
                        fill_color = QColor("#202024") if bit_val == '1' else QColor("#1a1a1e")
                        pen_color = QColor("#29292e") if bit_val == '1' else QColor("#202024")
                    elif bg_color_name == "#1f2937":
                        fill_color = QColor("#323238") if bit_val == '1' else QColor("#1f2937")
                        pen_color = QColor("#404040") if bit_val == '1' else QColor("#29292e")
                    else:
                        fill_color = QColor("#000000") if bit_val == '1' else QColor("#ffffff")
                        pen_color = QColor("#000000") if bit_val == '1' else QColor("#323238")

                painter.setBrush(fill_color)

                bit_annotated = (annotated_mask & (1 << (7 - i))) != 0
                if bit_annotated:
                    painter.setPen(QPen(QColor("#facc15"), 2))
                else:
                    painter.setPen(pen_color)

                painter.drawRect(bit_rect)

            if has_byte_annot:
                pen = QPen(QColor("#facc15"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(option.rect.adjusted(1, 1, -2, -2))

            painter.restore()
        else:
            super().paint(painter, option, index)
            if is_annotated:
                painter.save()
                pen = QPen(QColor("#facc15"))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawRect(option.rect.adjusted(1, 1, -2, -2))
                painter.restore()
