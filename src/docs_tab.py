"""
docs_tab.py — Aba de Documentação e Gerenciador de Markdown do CANweaver

Responsabilidade:
- Listar arquivos Markdown (.md) do projeto e subdiretórios (ex.: CANweaver_Projeto.md, README.md, docs/).
- Permitir criar novos arquivos .md, abrir arquivos externos, renomear e excluir.
- Visualizar arquivos com renderização rica de Markdown (QTextBrowser).
- Editar arquivos com editor de texto formatado (QPlainTextEdit) e atalho de salvamento (Ctrl+S).
- Modo Lado a Lado (Split view) com sincronização em tempo real entre editor e preview.
- Integração com AnnotationManager: sincroniza comentários e anotações do barramento CAN quando
  CANweaver_Projeto.md é salvo ou atualizado pela IA.
"""
from __future__ import annotations

import os
import subprocess
import sys
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QPlainTextEdit,
    QTextBrowser, QMessageBox, QFileDialog, QInputDialog,
    QMenu, QFrame, QButtonGroup
)
from PyQt6.QtGui import QFont, QColor, QKeySequence, QAction, QShortcut

from src.annotations import AnnotationManager


class MarkdownEditor(QPlainTextEdit):
    """Editor de texto para Markdown com suporte a tabulações e tecla de atalho."""
    save_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas, Courier New, monospace", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #16161a;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.5;
            }
            QPlainTextEdit:focus {
                border: 1px solid #3b82f6;
            }
        """)

    def keyPressEvent(self, event):
        # Permite indentar com Tab sem perder o foco
        if event.key() == Qt.Key.Key_Tab:
            self.insertPlainText("    ")
            return
        super().keyPressEvent(event)


class DocsTab(QWidget):
    """Aba principal de gerenciamento, edição e visualização de documentos Markdown."""

    def __init__(self, project_dir: str, annotation_manager: AnnotationManager, parent=None):
        super().__init__(parent)
        self.project_dir = project_dir
        self.annotation_manager = annotation_manager

        self.current_file_path: str | None = None
        self.is_modified = False
        self.tracked_files: list[str] = []

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(250)
        self._preview_timer.timeout.connect(self._update_preview)

        self._build_ui()
        self.refresh_files()

        # Seleciona o CANweaver_Projeto.md por padrão se existir
        self._select_default_doc()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Divisor principal: Painel Esquerdo (Lista de arquivos) | Painel Direito (Editor / Preview)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #27272a;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #3b82f6;
            }
        """)

        # ==============================================================
        # 1. Painel Esquerdo (Sidebar de Documentos)
        # ==============================================================
        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar.setMaximumWidth(400)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(6)

        # Cabeçalho da Sidebar
        sidebar_hdr = QWidget()
        sidebar_hdr_layout = QHBoxLayout(sidebar_hdr)
        sidebar_hdr_layout.setContentsMargins(4, 2, 4, 2)
        sidebar_hdr_layout.setSpacing(6)

        lbl_sidebar_title = QLabel("<b>Documentos (.md)</b>")
        lbl_sidebar_title.setStyleSheet("color: #93c5fd; font-size: 13px; font-weight: bold;")
        sidebar_hdr_layout.addWidget(lbl_sidebar_title)
        sidebar_hdr_layout.addStretch()

        sidebar_layout.addWidget(sidebar_hdr)

        # Barra de Ações: + Novo, Abrir... e Atualizar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(6)

        self.btn_new = QPushButton("+ Novo")
        self.btn_new.setToolTip("Criar novo arquivo Markdown (.md)")
        self.btn_new.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; border: none; border-radius: 4px; padding: 6px 10px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.btn_new.clicked.connect(self._prompt_new_doc)

        self.btn_open_ext = QPushButton("Abrir...")
        self.btn_open_ext.setToolTip("Abrir arquivo Markdown de qualquer pasta")
        self.btn_open_ext.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #e4e4e7; border: 1px solid #3f3f46; border-radius: 4px; padding: 6px 10px; font-size: 11px; font-weight: 500; }"
            "QPushButton:hover { background-color: #3f3f46; color: white; }"
        )
        self.btn_open_ext.clicked.connect(self._prompt_open_external)

        self.btn_refresh = QPushButton("Atualizar")
        self.btn_refresh.setToolTip("Recarregar lista de arquivos Markdown da pasta")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #202024; color: #a1a1aa; border: 1px solid #323238; border-radius: 4px; padding: 6px 10px; font-size: 11px; font-weight: 500; }"
            "QPushButton:hover { background-color: #2e3035; color: white; }"
        )
        self.btn_refresh.clicked.connect(self.refresh_files)

        btn_bar.addWidget(self.btn_new)
        btn_bar.addWidget(self.btn_open_ext)
        btn_bar.addWidget(self.btn_refresh)
        sidebar_layout.addLayout(btn_bar)

        # Lista de Documentos
        self.file_list = QListWidget()
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 4px;
                color: #d4d4d8;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 4px;
                margin-bottom: 2px;
            }
            QListWidget::item:hover {
                background-color: #27272a;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #1e3a8a;
                color: #ffffff;
                font-weight: bold;
            }
        """)
        self.file_list.itemClicked.connect(self._on_file_item_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_context_menu)
        sidebar_layout.addWidget(self.file_list, 1)

        self.main_splitter.addWidget(sidebar)

        # ==============================================================
        # 2. Painel Direito (Visualização e Edição)
        # ==============================================================
        content_pane = QWidget()
        content_layout = QVBoxLayout(content_pane)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        # Barra superior do documento aberto
        doc_header = QWidget()
        doc_header.setStyleSheet("background-color: #18181b; border: 1px solid #27272a; border-radius: 6px; padding: 4px;")
        doc_header_layout = QHBoxLayout(doc_header)
        doc_header_layout.setContentsMargins(8, 4, 8, 4)
        doc_header_layout.setSpacing(10)

        # Nome do documento ativo
        self.lbl_active_doc_title = QLabel("Nenhum documento selecionado")
        self.lbl_active_doc_title.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        doc_header_layout.addWidget(self.lbl_active_doc_title)

        # Indicador de alteração não salva
        self.lbl_modified_tag = QLabel("● Não salvo")
        self.lbl_modified_tag.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
        self.lbl_modified_tag.hide()
        doc_header_layout.addWidget(self.lbl_modified_tag)

        doc_header_layout.addStretch()

        # Seletor de Modo: [Visualizar] [Editar] [Lado a Lado]
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.btn_mode_preview = QPushButton("👁 Visualizar")
        self.btn_mode_preview.setCheckable(True)
        self.btn_mode_preview.setChecked(True)
        self.btn_mode_preview.setStyleSheet(self._mode_button_style())
        self.mode_group.addButton(self.btn_mode_preview)
        doc_header_layout.addWidget(self.btn_mode_preview)

        self.btn_mode_edit = QPushButton("✏️ Editar")
        self.btn_mode_edit.setCheckable(True)
        self.btn_mode_edit.setStyleSheet(self._mode_button_style())
        self.mode_group.addButton(self.btn_mode_edit)
        doc_header_layout.addWidget(self.btn_mode_edit)

        self.btn_mode_split = QPushButton("◫ Lado a Lado")
        self.btn_mode_split.setCheckable(True)
        self.btn_mode_split.setStyleSheet(self._mode_button_style())
        self.mode_group.addButton(self.btn_mode_split)
        doc_header_layout.addWidget(self.btn_mode_split)

        self.btn_mode_preview.clicked.connect(lambda: self._set_display_mode("preview"))
        self.btn_mode_edit.clicked.connect(lambda: self._set_display_mode("edit"))
        self.btn_mode_split.clicked.connect(lambda: self._set_display_mode("split"))

        # Separador vertical
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #3f3f46;")
        doc_header_layout.addWidget(sep)

        # Botão Recarregar
        self.btn_reload = QPushButton("Descartar / Recarregar")
        self.btn_reload.setToolTip("Descarta alterações não salvas e recarrega do arquivo em disco")
        self.btn_reload.setStyleSheet(
            "QPushButton { background-color: #27272a; color: #a1a1aa; border: 1px solid #3f3f46; border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: 500; }"
            "QPushButton:hover { background-color: #3f3f46; color: white; }"
        )
        self.btn_reload.clicked.connect(self._reload_current_file)
        doc_header_layout.addWidget(self.btn_reload)

        # Botão Salvar
        self.btn_save = QPushButton("💾 Salvar (Ctrl+S)")
        self.btn_save.setToolTip("Salva as alterações no arquivo atual (Ctrl+S)")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #10b981; color: white; border: none; border-radius: 4px; padding: 4px 14px; font-size: 11px; font-weight: bold; }"
            "QPushButton:hover { background-color: #059669; }"
            "QPushButton:disabled { background-color: #27272a; color: #71717a; }"
        )
        self.btn_save.clicked.connect(self.save_current_file)
        doc_header_layout.addWidget(self.btn_save)

        content_layout.addWidget(doc_header)

        # Área de Visualização / Edição (Splitter interno)
        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.editor_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #27272a;
                width: 3px;
            }
            QSplitter::handle:hover {
                background-color: #3b82f6;
            }
        """)

        # Componente 1: Editor de Texto Puro (Markdown)
        self.editor = MarkdownEditor()
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor_splitter.addWidget(self.editor)

        # Componente 2: Visualizador Markdown Renderizado
        self.previewer = QTextBrowser()
        self.previewer.setOpenExternalLinks(True)
        self._apply_preview_styling()
        self.editor_splitter.addWidget(self.previewer)

        content_layout.addWidget(self.editor_splitter, 1)

        self.main_splitter.addWidget(content_pane)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 4)

        main_layout.addWidget(self.main_splitter)

        # Atalho de teclado global na aba: Ctrl+S para salvar
        self.shortcut_save = QShortcut(QKeySequence("Ctrl+S"), self)
        self.shortcut_save.activated.connect(self.save_current_file)

        # Modo inicial
        self._set_display_mode("preview")

    def _mode_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #202024;
                color: #a1a1aa;
                border: 1px solid #323238;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2e3035;
                color: #ffffff;
            }
            QPushButton:checked {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #0284c7;
            }
        """

    def _apply_preview_styling(self):
        """Estiliza a área de visualização Markdown com suporte a cabeçalhos, código e tabelas."""
        self.previewer.setStyleSheet("""
            QTextBrowser {
                background-color: #121214;
                color: #e4e4e7;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 16px 20px;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
        """)

        doc = self.previewer.document()
        doc.setDefaultStyleSheet("""
            body {
                color: #e4e4e7;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
            h1 {
                color: #38bdf8;
                font-size: 20px;
                border-bottom: 2px solid #27272a;
                padding-bottom: 6px;
                margin-top: 10px;
                margin-bottom: 12px;
            }
            h2 {
                color: #93c5fd;
                font-size: 16px;
                border-bottom: 1px solid #27272a;
                padding-bottom: 4px;
                margin-top: 14px;
                margin-bottom: 8px;
            }
            h3 {
                color: #34d399;
                font-size: 14px;
                margin-top: 10px;
                margin-bottom: 6px;
            }
            h4, h5, h6 {
                color: #facc15;
                font-size: 13px;
            }
            p {
                margin-top: 4px;
                margin-bottom: 8px;
            }
            code {
                background-color: #1f1f23;
                color: #38bdf8;
                font-family: 'Consolas', monospace;
                padding: 2px 4px;
                border-radius: 4px;
            }
            pre {
                background-color: #18181b;
                color: #f4f4f5;
                font-family: 'Consolas', monospace;
                padding: 10px 14px;
                border: 1px solid #27272a;
                border-radius: 6px;
                margin: 8px 0;
            }
            blockquote {
                border-left: 3px solid #3b82f6;
                padding-left: 12px;
                margin-left: 0;
                color: #94a3b8;
                font-style: italic;
            }
            ul, ol {
                margin-top: 4px;
                margin-bottom: 8px;
                padding-left: 20px;
            }
            li {
                margin-bottom: 4px;
            }
            table {
                border-collapse: collapse;
                margin: 10px 0;
                width: 100%;
            }
            th {
                background-color: #202024;
                color: #38bdf8;
                padding: 6px 10px;
                border: 1px solid #27272a;
                font-weight: bold;
            }
            td {
                padding: 6px 10px;
                border: 1px solid #27272a;
            }
            a {
                color: #38bdf8;
                text-decoration: none;
            }
            hr {
                border: none;
                border-top: 1px solid #27272a;
                margin: 14px 0;
            }
        """)

    # ------------------------------------------------------------------
    # Modos de Exibição
    # ------------------------------------------------------------------
    def _set_display_mode(self, mode: str):
        if mode == "preview":
            self.editor.hide()
            self.previewer.show()
            self.btn_mode_preview.setChecked(True)
            self._update_preview()
        elif mode == "edit":
            self.previewer.hide()
            self.editor.show()
            self.btn_mode_edit.setChecked(True)
            self.editor.setFocus()
        elif mode == "split":
            self.editor.show()
            self.previewer.show()
            self.btn_mode_split.setChecked(True)
            self.editor_splitter.setSizes([self.width() // 2, self.width() // 2])
            self._update_preview()

    # ------------------------------------------------------------------
    # Gerenciamento e Varredura de Arquivos
    # ------------------------------------------------------------------
    def refresh_files(self):
        """Varre o diretório do projeto e pastas docs/ em busca de arquivos .md."""
        current_selection = self.current_file_path

        md_files = []
        
        # 1. Arquivo principal do projeto sempre primeiro
        main_project_md = os.path.join(self.project_dir, "CANweaver_Projeto.md")
        if os.path.exists(main_project_md):
            md_files.append(main_project_md)

        # 2. Outros arquivos .md na raiz
        try:
            for fname in sorted(os.listdir(self.project_dir)):
                if fname.lower().endswith(".md") and fname != "CANweaver_Projeto.md":
                    fpath = os.path.join(self.project_dir, fname)
                    if os.path.isfile(fpath) and fpath not in md_files:
                        md_files.append(fpath)
        except Exception:
            pass

        # 3. Subpasta docs/ se existir
        docs_sub = os.path.join(self.project_dir, "docs")
        if os.path.isdir(docs_sub):
            try:
                for fname in sorted(os.listdir(docs_sub)):
                    if fname.lower().endswith(".md"):
                        fpath = os.path.join(docs_sub, fname)
                        if os.path.isfile(fpath) and fpath not in md_files:
                            md_files.append(fpath)
            except Exception:
                pass

        # 4. Inclui arquivos externos abertos previamente
        for ext_file in self.tracked_files:
            if ext_file not in md_files and os.path.isfile(ext_file):
                md_files.append(ext_file)

        self.tracked_files = md_files

        # Preenche a lista na interface
        self.file_list.clear()
        selected_item = None

        for path in self.tracked_files:
            bname = os.path.basename(path)
            is_main = (bname == "CANweaver_Projeto.md")

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, path)

            if is_main:
                item.setText(f"★ {bname} (Projeto)")
                item.setForeground(QColor("#38bdf8"))
                item.setToolTip(f"Arquivo oficial de anotações do projeto:\n{path}")
            else:
                rel = os.path.relpath(path, self.project_dir)
                item.setText(f"📄 {rel}")
                item.setToolTip(path)

            self.file_list.addItem(item)
            if current_selection and os.path.abspath(path) == os.path.abspath(current_selection):
                selected_item = item

        if selected_item:
            self.file_list.setCurrentItem(selected_item)
        elif not self.current_file_path and self.file_list.count() > 0:
            self.file_list.setCurrentRow(0)
            self._on_file_item_clicked(self.file_list.item(0))

    def _select_default_doc(self):
        main_md = os.path.join(self.project_dir, "CANweaver_Projeto.md")
        if os.path.exists(main_md):
            self.open_file(main_md)
        elif self.file_list.count() > 0:
            self._on_file_item_clicked(self.file_list.item(0))

    def _on_file_item_clicked(self, item: QListWidgetItem):
        if not item:
            return
        fpath = item.data(Qt.ItemDataRole.UserRole)
        if fpath:
            self.open_file(fpath)

    # ------------------------------------------------------------------
    # Ações com Arquivos (Abrir, Salvar, Criar, Renomear, Excluir)
    # ------------------------------------------------------------------
    def open_file(self, file_path: str):
        """Carrega o conteúdo do arquivo especificado para o editor/previewer."""
        if self.is_modified and self.current_file_path:
            reply = QMessageBox.question(
                self, "Alterações Pendentes",
                f"O arquivo '{os.path.basename(self.current_file_path)}' possui alterações não salvas.\n"
                "Deseja salvar antes de trocar de documento?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_current_file()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Arquivo não encontrado", f"O arquivo não existe mais:\n{file_path}")
            self.refresh_files()
            return

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao abrir", f"Não foi possível ler o arquivo:\n{e}")
            return

        self.current_file_path = file_path
        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)

        self._set_modified(False)
        self._update_header_title()
        self._update_preview()

        if file_path not in self.tracked_files:
            self.tracked_files.append(file_path)
            self.refresh_files()

    def save_current_file(self):
        """Salva as alterações do editor no disco e sincroniza o AnnotationManager se for o projeto."""
        if not self.current_file_path:
            return

        content = self.editor.toPlainText()
        try:
            with open(self.current_file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao salvar", f"Falha ao salvar o arquivo:\n{e}")
            return

        self._set_modified(False)

        # Se for o arquivo de anotações do projeto, atualiza o AnnotationManager em tempo real!
        if os.path.basename(self.current_file_path) == "CANweaver_Projeto.md":
            if self.annotation_manager:
                self.annotation_manager.load()

        self._update_preview()

    def _reload_current_file(self):
        """Descarta modificações não salvas e recarrega do disco com confirmação obrigatória."""
        if not self.current_file_path:
            return
        fname = os.path.basename(self.current_file_path)
        reply = QMessageBox.question(
            self, "Confirmar Recarga",
            f"Deseja realmente recarregar o documento '{fname}' do disco?\n\n"
            "Quaisquer alterações não salvas serão descartadas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.is_modified = False
        self.open_file(self.current_file_path)

    def reload_file_if_open(self, target_filename: str):
        """Recarrega o documento se ele for o que está aberto na tela (usado após edições via IA)."""
        if self.current_file_path and os.path.basename(self.current_file_path) == target_filename:
            if not self.is_modified:
                try:
                    with open(self.current_file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self.editor.blockSignals(True)
                    self.editor.setPlainText(content)
                    self.editor.blockSignals(False)
                    self._update_preview()
                except Exception:
                    pass

    def _prompt_new_doc(self):
        """Diálogo para criação de um novo documento .md."""
        name, ok = QInputDialog.getText(
            self, "Novo Documento Markdown",
            "Digite o nome do arquivo (ex: notas_motor.md):"
        )
        if not ok or not name.strip():
            return

        clean_name = name.strip()
        if not clean_name.lower().endswith(".md"):
            clean_name += ".md"

        new_path = os.path.join(self.project_dir, clean_name)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Arquivo já existe", f"Já existe um arquivo chamado '{clean_name}'.")
            self.open_file(new_path)
            return

        try:
            with open(new_path, "w", encoding="utf-8") as f:
                f.write(f"# {os.path.splitext(clean_name)[0]}\n\nNovo documento criado no CANweaver.\n")
        except Exception as e:
            QMessageBox.critical(self, "Erro ao criar", f"Não foi possível criar o arquivo:\n{e}")
            return

        self.refresh_files()
        self.open_file(new_path)
        self._set_display_mode("edit")

    def _prompt_open_external(self):
        """Abre diálogo para selecionar qualquer arquivo .md no sistema."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Documento Markdown",
            self.project_dir,
            "Arquivos Markdown (*.md *.markdown *.txt);;Todos os Arquivos (*.*)"
        )
        if path:
            self.open_file(path)

    def _show_context_menu(self, pos):
        """Menu de contexto do botão direito nos itens da lista de arquivos."""
        item = self.file_list.itemAt(pos)
        if not item:
            return

        fpath = item.data(Qt.ItemDataRole.UserRole)
        if not fpath:
            return

        bname = os.path.basename(fpath)
        is_main = (bname == "CANweaver_Projeto.md")

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #202024;
                color: #ffffff;
                border: 1px solid #323238;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
            }
            QMenu::item:disabled {
                color: #52525b;
            }
        """)

        act_open = QAction("Abrir no Visualizador", self)
        act_open.triggered.connect(lambda: self.open_file(fpath))
        menu.addAction(act_open)

        act_explorer = QAction("Mostrar no Explorador de Arquivos", self)
        act_explorer.triggered.connect(lambda: self._reveal_in_explorer(fpath))
        menu.addAction(act_explorer)

        act_copy_path = QAction("Copiar Caminho Completo", self)
        act_copy_path.triggered.connect(lambda: self._copy_path_to_clipboard(fpath))
        menu.addAction(act_copy_path)

        menu.addSeparator()

        act_rename = QAction("Renomear...", self)
        act_rename.setEnabled(not is_main)
        act_rename.triggered.connect(lambda: self._rename_file(fpath))
        menu.addAction(act_rename)

        act_delete = QAction("Excluir Arquivo", self)
        act_delete.setEnabled(not is_main)
        act_delete.triggered.connect(lambda: self._delete_file(fpath))
        menu.addAction(act_delete)

        menu.exec(self.file_list.mapToGlobal(pos))

    def _rename_file(self, old_path: str):
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(
            self, "Renomear Arquivo",
            "Novo nome do arquivo:",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return

        clean_new = new_name.strip()
        if not clean_new.lower().endswith(".md"):
            clean_new += ".md"

        new_path = os.path.join(os.path.dirname(old_path), clean_new)
        if os.path.exists(new_path):
            QMessageBox.warning(self, "Arquivo já existe", f"Já existe um arquivo chamado '{clean_new}'.")
            return

        try:
            os.rename(old_path, new_path)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao renomear", f"Não foi possível renomear:\n{e}")
            return

        if self.current_file_path == old_path:
            self.current_file_path = new_path

        self.refresh_files()
        self.open_file(new_path)

    def _delete_file(self, fpath: str):
        bname = os.path.basename(fpath)
        reply = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Tem certeza que deseja apagar o arquivo '{bname}' permanentemente do disco?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            os.remove(fpath)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao excluir", f"Não foi possível excluir o arquivo:\n{e}")
            return

        if self.current_file_path == fpath:
            self.current_file_path = None
            self.editor.clear()
            self.previewer.clear()
            self.lbl_active_doc_title.setText("Nenhum documento selecionado")
            self._set_modified(False)

        self.refresh_files()

    def _reveal_in_explorer(self, fpath: str):
        if sys.platform == "win32":
            subprocess.run(["explorer", "/select,", os.path.normpath(fpath)])
        elif sys.platform == "darwin":
            subprocess.run(["open", "-R", fpath])
        else:
            subprocess.run(["xdg-open", os.path.dirname(fpath)])

    def _copy_path_to_clipboard(self, fpath: str):
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb:
            cb.setText(fpath)

    # ------------------------------------------------------------------
    # Sincronização e Edição
    # ------------------------------------------------------------------
    def _on_text_changed(self):
        if not self.is_modified:
            self._set_modified(True)
        # Se estiver em modo Split ou Preview, agenda atualização da renderização
        if self.btn_mode_split.isChecked() or self.btn_mode_preview.isChecked():
            self._preview_timer.start()

    def _set_modified(self, modified: bool):
        self.is_modified = modified
        if modified:
            self.lbl_modified_tag.show()
            self.btn_save.setEnabled(True)
        else:
            self.lbl_modified_tag.hide()
            self.btn_save.setEnabled(False)

    def _update_header_title(self):
        if not self.current_file_path:
            self.lbl_active_doc_title.setText("Nenhum documento selecionado")
            return
        bname = os.path.basename(self.current_file_path)
        is_main = (bname == "CANweaver_Projeto.md")
        badge = " [Documento Principal do Projeto]" if is_main else ""
        self.lbl_active_doc_title.setText(f"📄 {bname}{badge}")

    def _update_preview(self):
        """Renderiza o texto do editor para o componente QTextBrowser."""
        text = self.editor.toPlainText()
        self.previewer.setMarkdown(text)
