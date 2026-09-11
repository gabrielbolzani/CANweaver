#!/usr/bin/env bash
# ==============================================================================
# CANweaver - Script de Execução e Auto-Instalador para Linux / macOS / WSL
# ==============================================================================

set -e

# Diretório base onde o script reside
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "               CANweaver v2.0 Launcher                 "
echo "========================================================"

# 1. Checagem de Python 3
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] python3 não foi encontrado no sistema!"
    echo "Por favor, instale o Python 3 antes de prosseguir:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install -y python3 python3-pip"
    echo "  Arch Linux:    sudo pacman -S python python-pip"
    exit 1
fi

# 2. Gerenciamento do Ambiente Virtual (.venv)
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Ambiente virtual não encontrado. Criando .venv..."
    if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "[AVISO] Falha ao criar venv com o módulo padrão."
        echo "Em sistemas baseados em Debian/Ubuntu, instale o pacote python3-venv:"
        echo "  sudo apt install -y python3-venv python3-pip"
        echo "Tentando prosseguir sem venv..."
    fi
fi

if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
    PYTHON_EXEC="python"
    PIP_EXEC="pip"
else
    PYTHON_EXEC="python3"
    PIP_EXEC="pip3"
fi

# 3. Verificação e Instalação Automática de Dependências
echo "[INFO] Verificando dependências..."
MISSING_DEPS=0
$PYTHON_EXEC -c "import PyQt6" 2>/dev/null || MISSING_DEPS=1
$PYTHON_EXEC -c "import can" 2>/dev/null || MISSING_DEPS=1
$PYTHON_EXEC -c "import serial" 2>/dev/null || MISSING_DEPS=1

if [ $MISSING_DEPS -ne 0 ]; then
    echo "[INFO] Dependências ausentes detectadas. Instalando automaticamente via requirements.txt..."
    $PIP_EXEC install --upgrade pip
    if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
        $PIP_EXEC install -r "$SCRIPT_DIR/requirements.txt"
    else
        $PIP_EXEC install "PyQt6>=6.4.0" "python-can>=4.2.0" "pyserial>=3.5"
    fi
    echo "[OK] Dependências instaladas com sucesso!"
else
    echo "[OK] Todas as dependências já estão instaladas."
fi

# 4. Checagem de bibliotecas de sistema comuns para PyQt6 no Linux
if [ "$(uname)" = "Linux" ]; then
    # Verifica se libxcb-cursor0 está presente caso o sistema utilize Debian/Ubuntu
    if command -v dpkg &> /dev/null; then
        if ! dpkg -s libxcb-cursor0 &> /dev/null 2>&1; then
            echo "[DICA] O pacote 'libxcb-cursor0' pode ser necessário para a interface gráfica PyQt6."
            echo "Caso a janela não abra, execute: sudo apt install -y libxcb-cursor0 libgl1 libegl1"
        fi
    fi
fi

# 5. Execução do CANweaver
echo "[INFO] Iniciando CANweaver..."
exec $PYTHON_EXEC "$SCRIPT_DIR/main.py" "$@"
