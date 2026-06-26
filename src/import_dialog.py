import re
import csv
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QFileDialog, QMessageBox, QFormLayout, QCheckBox, QWidget
)

class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar Logs (Candump / Audit)")
        self.resize(450, 250)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Arquivo de Origem
        self.btn_file = QPushButton("Selecionar Arquivo...")
        self.btn_file.clicked.connect(self.select_file)
        self.lbl_file = QLabel("Nenhum arquivo selecionado")
        self.input_filepath = ""

        # Formato
        self.cb_format = QComboBox()
        self.cb_format.addItems(["Candump", "Audit"])
        self.cb_format.currentIndexChanged.connect(self.update_options)

        # ====== Opções de Audit ======
        self.widget_audit = QWidget()
        layout_audit = QFormLayout(self.widget_audit)
        layout_audit.setContentsMargins(0, 0, 0, 0)
        self.cb_channel = QComboBox()
        self.cb_channel.addItems(["Ambos (CAN2 e CAN3)", "Somente CAN2", "Somente CAN3"])
        layout_audit.addRow("Filtrar Canal:", self.cb_channel)

        # ====== Opções de Candump ======
        self.widget_candump = QWidget()
        layout_candump = QFormLayout(self.widget_candump)
        layout_candump.setContentsMargins(0, 0, 0, 0)
        
        self.chk_fixed_freq = QCheckBox("Simular tempo fixo entre as mensagens")
        self.chk_fixed_freq.setChecked(False)
        self.chk_fixed_freq.stateChanged.connect(self.update_candump_options)
        
        self.txt_freq = QLineEdit("100")
        self.txt_freq.setToolTip("Frequência em Hz.")
        self.txt_freq.setEnabled(False)
        
        layout_candump.addRow("", self.chk_fixed_freq)
        layout_candump.addRow("Frequência (Hz):", self.txt_freq)

        form.addRow("Arquivo de Origem:", self.btn_file)
        form.addRow("", self.lbl_file)
        form.addRow("Formato:", self.cb_format)
        form.addRow(self.widget_audit)
        form.addRow(self.widget_candump)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.btn_import = QPushButton("Importar e Salvar CSV...")
        self.btn_import.setStyleSheet("background-color: #3b82f6; color: white; padding: 6px; border-radius: 4px;")
        self.btn_import.clicked.connect(self.process_import)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_import)
        btn_layout.addWidget(self.btn_cancel)

        layout.addStretch()
        layout.addLayout(btn_layout)

        self.update_options()

    def select_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo de Log", "", "Text Files (*.txt *.log);;All Files (*)"
        )
        if file_name:
            self.input_filepath = file_name
            self.lbl_file.setText(os.path.basename(file_name))
            self.auto_detect_format()

    def auto_detect_format(self):
        if not self.input_filepath: return
        try:
            with open(self.input_filepath, 'r', encoding='utf-8') as f:
                for _ in range(20):
                    line = f.readline()
                    if not line: break
                    if "CAN_MESSAGE" in line:
                        self.cb_format.setCurrentText("Audit")
                        return
                    if "can" in line.lower() and "[" in line and "]" in line:
                        self.cb_format.setCurrentText("Candump")
                        return
        except:
            pass

    def update_options(self):
        fmt = self.cb_format.currentText()
        if fmt == "Audit":
            self.widget_audit.setVisible(True)
            self.widget_candump.setVisible(False)
        else:
            self.widget_audit.setVisible(False)
            self.widget_candump.setVisible(True)

    def update_candump_options(self):
        self.txt_freq.setEnabled(self.chk_fixed_freq.isChecked())

    def process_import(self):
        if not self.input_filepath:
            QMessageBox.warning(self, "Aviso", "Selecione um arquivo primeiro.")
            return

        fmt = self.cb_format.currentText()

        try:
            freq = float(self.txt_freq.text().strip())
            if freq <= 0: freq = 100.0
        except:
            freq = 100.0

        cb_channel_txt = self.cb_channel.currentText()

        out_name, _ = QFileDialog.getSaveFileName(
            self, "Salvar CSV como...", "", "CSV Files (*.csv)"
        )
        if not out_name:
            return

        try:
            with open(self.input_filepath, 'r', encoding='utf-8') as fin, \
                 open(out_name, 'w', newline='', encoding='utf-8') as fout:
                
                writer = csv.writer(fout)
                writer.writerow(["Timestamp", "ID", "DLC", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7"])

                t_simulated = 0.0
                dt = 1.0 / freq

                for line in fin:
                    line = line.strip()
                    if not line: continue

                    if fmt == "Audit":
                        if cb_channel_txt == "Somente CAN2":
                            valid_prefix = ("CAN_MESSAGE2 2 ",)
                        elif cb_channel_txt == "Somente CAN3":
                            valid_prefix = ("CAN_MESSAGE3 3 ",)
                        else:
                            valid_prefix = ("CAN_MESSAGE2 2 ", "CAN_MESSAGE3 3 ")
                            
                        if not line.startswith(valid_prefix):
                            continue
                            
                        parts = line.split()
                        if len(parts) < 14:
                            continue

                        can_id = parts[2]
                        try:
                            dlc = int(parts[3])
                        except:
                            dlc = 8

                        payload = parts[4:4+dlc]

                        try:
                            ts = float(parts[12])
                        except:
                            ts = t_simulated
                            t_simulated += dt
                        
                        writer.writerow([ts, can_id, dlc] + payload)

                    elif fmt == "Candump":
                        ts = None
                        m_ts = re.match(r'^\(([\d\.]+)\)', line)
                        if m_ts:
                            ts = float(m_ts.group(1))
                            line = line[m_ts.end():].strip()

                        m_msg = re.match(r'^\S+\s+([0-9A-Fa-f]+)\s+\[(\d+)\]\s*(.*)$', line)
                        if m_msg:
                            can_id = m_msg.group(1)
                            dlc = int(m_msg.group(2))
                            data_str = m_msg.group(3)
                            payload = data_str.split()[:dlc]

                        if self.chk_fixed_freq.isChecked() or ts is None:
                            # Ignora o 'ts' lido se o checkbox estiver marcado
                            ts_final = t_simulated
                            t_simulated += dt
                        else:
                            ts_final = ts

                        writer.writerow([ts_final, can_id, dlc] + payload)

            self.output_csv = out_name
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro na importação:\n{e}")

