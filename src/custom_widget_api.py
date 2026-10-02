"""
custom_widget_api.py — API e Gerenciador de Widgets Customizados em Python para CANweaver.

Permite que usuários criem seus próprios widgets em arquivos Python externos,
com interface PyQt6 e acesso direto ao barramento CAN (envio e recepção de frames).
"""
from __future__ import annotations

import os
import sys
import json
import inspect
import importlib.util
import traceback
from typing import Type
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt


class CustomWidgetBase(QWidget):
    """
    Classe base para widgets criados pelo usuário em Python.
    
    Atributos de classe opcionais para personalização:
        WIDGET_NAME (str): Nome exibido nos menus.
        WIDGET_DESC (str): Descrição do widget.
        DEFAULT_SIZE (tuple[int, int]): Dimensões iniciais (largura, altura). Ex: (280, 200).
    """
    WIDGET_NAME: str = "Widget Python"
    WIDGET_DESC: str = "Widget customizado em Python"
    DEFAULT_SIZE: tuple[int, int] = (260, 180)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._dashboard_wrapper = None
        self.init_ui()

    def set_wrapper(self, wrapper):
        """Conecta o wrapper do CANweaver ao widget customizado."""
        self._dashboard_wrapper = wrapper

    def init_ui(self):
        """
        Sobrescreva este método na sua subclasse para montar os elementos visuais
        (ex: QPushButton, QLabel, QProgressBar, QSlider, etc.).
        """
        pass

    def send_can(self, can_id: int, payload: list[int] | bytes) -> bool:
        """
        Envia um frame no barramento CAN.

        Args:
            can_id (int): Identificador CAN (11-bit ou 29-bit), ex: 0x7DF ou 0x123.
            payload (list[int] ou bytes): Até 8 bytes (ex: [0x02, 0x01, 0x0C, 0, 0, 0, 0, 0]).

        Returns:
            bool: True se a mensagem foi enviada ao worker CAN.
        """
        if self._dashboard_wrapper and hasattr(self._dashboard_wrapper, "send_can_from_child"):
            return self._dashboard_wrapper.send_can_from_child(can_id, payload)
        return False

    def on_can_frame(self, can_id: int, freq: float, payload: list[int]):
        """
        Chamado automaticamente quando um frame CAN chega do barramento.

        Args:
            can_id (int): ID CAN da mensagem recebida.
            freq (float): Frequência aproximada em Hz do ID.
            payload (list[int]): Lista de inteiros com os bytes da mensagem (0 a 8 bytes).
        """
        pass

    def get_custom_config(self) -> dict:
        """
        Sobrescreva para retornar quaisquer parâmetros que você deseja salvar no projeto (.cwp).
        Ex: return {"selected_pid": 12, "auto_poll": True}
        """
        return {}

    def set_custom_config(self, config: dict):
        """
        Sobrescreva para restaurar parâmetros salvos no arquivo de projeto (.cwp).
        """
        pass

    def create_config_widget(self, parent: QWidget | None = None) -> QWidget | None:
        """
        Sobrescreva para retornar um QWidget com campos de configuração específicos
        para exibição embutida no diálogo de edição acessado com o botão direito.
        """
        return None

    def apply_config(self):
        """
        Chamado ao confirmar (Aplicar) o diálogo de configuração do widget.
        """
        pass

    def reset_default_config(self):
        """
        Sobrescreva para restaurar as configurações padrão de fábrica do widget.
        """
        pass

    def contextMenuEvent(self, event):
        """Propaga o clique do botão direito para o menu de contexto do CANweaver."""
        if self._dashboard_wrapper and hasattr(self._dashboard_wrapper, "show_context_menu"):
            try:
                from src.widgets_tab import get_event_global_pos
                self._dashboard_wrapper.show_context_menu(get_event_global_pos(event))
                event.accept()
                return
            except Exception:
                pass
        super().contextMenuEvent(event)

    def on_close(self):
        """
        Chamado quando o widget está sendo excluído ou fechado.
        Use para parar QTimers internos, threads auxiliares ou sockets.
        """
        pass



USER_WIDGET_DIRS_FILE = os.path.join(os.path.expanduser("~"), ".canweaver", "custom_widget_folders.json")


def get_custom_widgets_directory() -> str:
    """Retorna o caminho absoluto do diretório custom_widgets na raiz do CANweaver."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    custom_dir = os.path.join(root_dir, "custom_widgets")
    if not os.path.exists(custom_dir):
        try:
            os.makedirs(custom_dir, exist_ok=True)
        except Exception:
            pass
    return custom_dir


def get_lume_widgets_directory() -> str:
    """Retorna o caminho da pasta lume_widgets na raiz do projeto (privada / no .gitignore)."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lume_dir = os.path.join(root_dir, "lume_widgets")
    if not os.path.exists(lume_dir):
        try:
            os.makedirs(lume_dir, exist_ok=True)
        except Exception:
            pass
    return lume_dir


def get_user_custom_widget_directories() -> list[str]:
    """Retorna a lista de pastas de widgets registradas pelo usuário em ~/.canweaver/custom_widget_folders.json."""
    if not os.path.isfile(USER_WIDGET_DIRS_FILE):
        return []
    try:
        with open(USER_WIDGET_DIRS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [os.path.abspath(d) for d in data if os.path.isdir(d)]
    except Exception:
        pass
    return []


def add_custom_widget_directory(dir_path: str) -> bool:
    """Adiciona uma pasta personalizada à lista de pastas salvas do usuário."""
    if not dir_path or not os.path.isdir(dir_path):
        return False
    abs_path = os.path.abspath(dir_path)
    dirs = get_user_custom_widget_directories()
    if abs_path not in dirs:
        dirs.append(abs_path)
        try:
            os.makedirs(os.path.dirname(USER_WIDGET_DIRS_FILE), exist_ok=True)
            with open(USER_WIDGET_DIRS_FILE, "w", encoding="utf-8") as f:
                json.dump(dirs, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    return True


def remove_custom_widget_directory(dir_path: str) -> bool:
    """Remove uma pasta personalizada da lista de pastas do usuário."""
    if not dir_path:
        return False
    abs_path = os.path.abspath(dir_path)
    dirs = get_user_custom_widget_directories()
    if abs_path in dirs:
        dirs.remove(abs_path)
        try:
            os.makedirs(os.path.dirname(USER_WIDGET_DIRS_FILE), exist_ok=True)
            with open(USER_WIDGET_DIRS_FILE, "w", encoding="utf-8") as f:
                json.dump(dirs, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    return False


def resolve_custom_widget_path(file_path: str) -> str:
    """
    Resolve caminhos de scripts de widgets de forma compatível entre Windows e Linux.
    Se o caminho original não existir diretamente (ex: salvo com barras invertidas do Windows
    ou caminho absoluto de outra máquina), tenta localizar nos diretórios de widgets registrados.
    """
    if not file_path:
        return ""
    if os.path.isfile(file_path):
        return os.path.abspath(file_path)

    # 1. Normaliza separadores de barra (Windows -> Linux)
    norm = file_path.replace("\\", "/")
    if os.path.isfile(norm):
        return os.path.abspath(norm)

    # 2. Busca pelo nome do arquivo em todas as pastas conhecidas
    base_name = os.path.basename(norm)
    dirs_to_check = [
        get_custom_widgets_directory(),
        get_lume_widgets_directory(),
    ] + get_user_custom_widget_directories()

    for d in dirs_to_check:
        in_d = os.path.join(d, base_name)
        if os.path.isfile(in_d):
            return os.path.abspath(in_d)

    # 3. Busca recursiva em subpastas de primeiro nível de custom_widgets
    root_custom = get_custom_widgets_directory()
    if os.path.isdir(root_custom):
        try:
            for sub in os.listdir(root_custom):
                sub_p = os.path.join(root_custom, sub)
                if os.path.isdir(sub_p):
                    candidate = os.path.join(sub_p, base_name)
                    if os.path.isfile(candidate):
                        return os.path.abspath(candidate)
        except Exception:
            pass

    # 4. Busca relativa à raiz do projeto
    root_dir = os.path.dirname(root_custom)
    in_root = os.path.join(root_dir, norm)
    if os.path.isfile(in_root):
        return os.path.abspath(in_root)

    return file_path


def open_path_in_system(path: str) -> bool:
    """
    Abre um arquivo ou pasta no aplicativo padrão do sistema operacional (Windows, Linux, macOS).
    Usa QDesktopServices do Qt com fallback para utilitários do sistema.
    """
    if not path:
        return False

    resolved = resolve_custom_widget_path(path) if not os.path.exists(path) else path
    if not os.path.exists(resolved):
        return False

    abs_path = os.path.abspath(resolved)
    try:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        if QDesktopServices.openUrl(QUrl.fromLocalFile(abs_path)):
            return True
    except Exception:
        pass

    try:
        import subprocess
        if sys.platform.startswith("win") and hasattr(os, "startfile"):
            os.startfile(abs_path)
            return True
        elif sys.platform.startswith("darwin"):
            subprocess.Popen(["open", abs_path])
            return True
        else:
            subprocess.Popen(["xdg-open", abs_path])
            return True
    except Exception:
        pass

    return False


def load_custom_widget_class_from_file(file_path: str) -> tuple[Type[CustomWidgetBase] | None, str | None]:
    """
    Carrega dinamicamente um arquivo Python (.py) e procura por uma classe que herde de CustomWidgetBase.
    
    Retorna:
        (Classe, None) em caso de sucesso.
        (None, mensagem_de_erro) se ocorrer erro de sintaxe, importação ou classe não encontrada.
    """
    resolved_path = resolve_custom_widget_path(file_path)
    if not os.path.isfile(resolved_path):
        return None, f"Arquivo não encontrado: {file_path}"
    file_path = resolved_path

    module_name = f"canweaver_custom_{os.path.splitext(os.path.basename(file_path))[0]}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None, f"Não foi possível carregar a especificação do arquivo: {file_path}"

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except TypeError as te:
            # Compatibilidade com Python 3.8: se o script do usuário utilizar list[int],
            # dict[k, v] ou sintaxe de union sem 'from __future__ import annotations'
            err_str = str(te)
            if "not subscriptable" in err_str or "unsupported operand type" in err_str:
                with open(file_path, "r", encoding="utf-8") as f:
                    code_src = f.read()
                code_compiled = compile("from __future__ import annotations\n" + code_src, file_path, "exec")
                exec(code_compiled, module.__dict__)
            else:
                raise

        # Procura classe derivada de CustomWidgetBase
        found_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                inspect.isclass(attr)
                and issubclass(attr, CustomWidgetBase)
                and attr is not CustomWidgetBase
            ):
                found_class = attr
                break

        if found_class is None:
            return None, (
                f"Nenhuma classe que herde de 'CustomWidgetBase' foi encontrada em:\n{file_path}\n\n"
                f"Certifique-se de herdar de CustomWidgetBase:\n"
                f"  from src.custom_widget_api import CustomWidgetBase\n"
                f"  class MeuWidget(CustomWidgetBase): ..."
            )

        return found_class, None

    except Exception:
        err_msg = traceback.format_exc()
        return None, f"Erro ao executar script do widget:\n{err_msg}"



def _scan_directory_widgets(dir_path: str, section_name: str) -> list[dict]:
    """Varre um diretório por arquivos .py de widgets customizados."""
    results = []
    if not os.path.isdir(dir_path):
        return results

    try:
        entries = sorted(os.listdir(dir_path))
    except Exception:
        return results

    for fname in entries:
        if fname.endswith(".py") and not fname.startswith("__"):
            full_path = os.path.join(dir_path, fname)
            widget_cls, err = load_custom_widget_class_from_file(full_path)
            if widget_cls:
                results.append({
                    "file_name": fname,
                    "file_path": full_path,
                    "class": widget_cls,
                    "name": getattr(widget_cls, "WIDGET_NAME", fname),
                    "desc": getattr(widget_cls, "WIDGET_DESC", ""),
                    "default_size": getattr(widget_cls, "DEFAULT_SIZE", (260, 180)),
                    "section": section_name,
                })
            else:
                results.append({
                    "file_name": fname,
                    "file_path": full_path,
                    "class": None,
                    "name": fname,
                    "desc": f"Erro: {err}",
                    "default_size": (260, 180),
                    "error": err,
                    "section": section_name,
                })
    return results


def list_available_custom_widgets_grouped() -> dict[str, dict]:
    """
    Varre os diretórios registrados de widgets customizados e retorna um dicionário organizado em seções:
    - "custom_widgets": pasta padrão custom_widgets/ na raiz
    - Subpastas em custom_widgets/ (ex: custom_widgets/sensores/)
    - "lume_widgets": pasta privada lume_widgets/ (no .gitignore)
    - Pastas personalizadas adicionadas pelo usuário

    Retorna:
        dict[section_id, {
            "name": str,            # Nome legível da seção
            "path": str,            # Caminho absoluto da pasta
            "is_root": bool,        # True se for a pasta custom_widgets/ raiz
            "is_lume": bool,        # True se for a pasta lume_widgets/
            "is_user": bool,        # True se for pasta externa carregada pelo usuário
            "widgets": list[dict]   # Lista de widgets encontrados
        }]
    """
    sections = {}

    # 1. Pasta custom_widgets/ raiz
    root_custom = get_custom_widgets_directory()
    sections["custom_widgets"] = {
        "name": "Padrão",
        "path": root_custom,
        "is_root": True,
        "is_lume": False,
        "is_user": False,
        "widgets": _scan_directory_widgets(root_custom, "Padrão")
    }

    # 2. Subpastas dentro de custom_widgets/
    if os.path.isdir(root_custom):
        try:
            for item in sorted(os.listdir(root_custom)):
                sub_path = os.path.join(root_custom, item)
                if os.path.isdir(sub_path) and not item.startswith(".") and item != "__pycache__":
                    w_list = _scan_directory_widgets(sub_path, item)
                    if w_list:
                        sections[f"sub_{item}"] = {
                            "name": item,
                            "path": sub_path,
                            "is_root": False,
                            "is_lume": False,
                            "is_user": False,
                            "widgets": w_list
                        }
        except Exception:
            pass

    # 3. Pasta lume_widgets/ (privada / local no .gitignore)
    lume_dir = get_lume_widgets_directory()
    if os.path.isdir(lume_dir):
        lume_widgets = _scan_directory_widgets(lume_dir, "Lume Widgets")
        sections["lume_widgets"] = {
            "name": "Lume Widgets",
            "path": lume_dir,
            "is_root": False,
            "is_lume": True,
            "is_user": False,
            "widgets": lume_widgets
        }

    # 4. Pastas personalizadas vinculadas pelo usuário
    user_dirs = get_user_custom_widget_directories()
    for udir in user_dirs:
        if os.path.isdir(udir) and udir != root_custom and udir != lume_dir:
            bname = os.path.basename(udir)
            sec_id = f"user_{udir}"
            sections[sec_id] = {
                "name": bname,
                "path": udir,
                "is_root": False,
                "is_lume": False,
                "is_user": True,
                "widgets": _scan_directory_widgets(udir, bname)
            }

    return sections


def list_available_custom_widgets() -> list[dict]:
    """Retorna lista plana de todos os widgets disponíveis em todas as pastas registradas."""
    grouped = list_available_custom_widgets_grouped()
    all_widgets = []
    for sec_data in grouped.values():
        all_widgets.extend(sec_data.get("widgets", []))
    return all_widgets
