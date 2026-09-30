"""
custom_widget_api.py — API e Gerenciador de Widgets Customizados em Python para CANweaver.

Permite que usuários criem seus próprios widgets em arquivos Python externos,
com interface PyQt6 e acesso direto ao barramento CAN (envio e recepção de frames).
"""
from __future__ import annotations

import os
import sys
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

    def on_close(self):
        """
        Chamado quando o widget está sendo excluído ou fechado.
        Use para parar QTimers internos, threads auxiliares ou sockets.
        """
        pass


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


def load_custom_widget_class_from_file(file_path: str) -> tuple[Type[CustomWidgetBase] | None, str | None]:
    """
    Carrega dinamicamente um arquivo Python (.py) e procura por uma classe que herde de CustomWidgetBase.
    
    Retorna:
        (Classe, None) em caso de sucesso.
        (None, mensagem_de_erro) se ocorrer erro de sintaxe, importação ou classe não encontrada.
    """
    if not os.path.isfile(file_path):
        return None, f"Arquivo não encontrado: {file_path}"

    module_name = f"canweaver_custom_{os.path.splitext(os.path.basename(file_path))[0]}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None, f"Não foi possível carregar a especificação do arquivo: {file_path}"

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

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


def list_available_custom_widgets() -> list[dict]:
    """
    Varre o diretório custom_widgets/ procurando por arquivos .py válidos.
    Retorna lista de dicionários com metadados de cada widget disponível.
    """
    widgets_dir = get_custom_widgets_directory()
    results = []

    if not os.path.exists(widgets_dir):
        return results

    for fname in os.listdir(widgets_dir):
        if fname.endswith(".py") and not fname.startswith("__"):
            full_path = os.path.join(widgets_dir, fname)
            widget_cls, err = load_custom_widget_class_from_file(full_path)
            if widget_cls:
                results.append({
                    "file_name": fname,
                    "file_path": full_path,
                    "class": widget_cls,
                    "name": getattr(widget_cls, "WIDGET_NAME", fname),
                    "desc": getattr(widget_cls, "WIDGET_DESC", ""),
                    "default_size": getattr(widget_cls, "DEFAULT_SIZE", (260, 180)),
                })
            else:
                results.append({
                    "file_name": fname,
                    "file_path": full_path,
                    "class": None,
                    "name": fname,
                    "desc": f"Erro: {err}",
                    "default_size": (260, 180),
                    "error": err
                })

    return results
