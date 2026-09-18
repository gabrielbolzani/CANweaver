#!/usr/bin/env bash
# ==============================================================================
# CANweaver - Script de Execução e Auto-Instalador para Linux / macOS / WSL
# ==============================================================================

set -e

# Diretório base onde o script reside
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "                  CANweaver Launcher                    "
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

# Se o .venv já existe, valida se ele realmente usa Python 3 e se não está corrompido
if [ -d "$VENV_DIR" ]; then
    if [ ! -f "$VENV_DIR/bin/python3" ] || ! "$VENV_DIR/bin/python3" -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)" 2>/dev/null; then
        echo "[AVISO] Ambiente virtual existente em .venv é incompatível ou não é Python 3. Recriando..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Ambiente virtual não encontrado. Criando .venv com python3..."
    if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
        echo "[AVISO] Falha ao criar venv com python3 -m venv."
        echo "Em sistemas baseados em Debian/Ubuntu, instale o pacote python3-venv:"
        echo "  sudo apt install -y python3-venv python3-pip"
        rm -rf "$VENV_DIR" 2>/dev/null || true
        echo "Tentando prosseguir com python3 do sistema..."
    fi
fi

if [ -f "$VENV_DIR/bin/python3" ]; then
    PYTHON_EXEC="$VENV_DIR/bin/python3"
    PIP_EXEC="$VENV_DIR/bin/pip"
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$VENV_DIR/bin/activate"
    fi
else
    PYTHON_EXEC="$(command -v python3)"
    PIP_EXEC="python3 -m pip"
fi

# Garante que PYTHON_EXEC é realmente Python 3
PY_MAJOR=$($PYTHON_EXEC -c "import sys; print(sys.version_info[0])" 2>/dev/null || echo "0")
if [ "$PY_MAJOR" -lt 3 ]; then
    echo "[ERRO] Interpretador selecionado ($PYTHON_EXEC) não é Python 3!"
    echo "CANweaver requer Python 3.10 ou superior."
    exit 1
fi

# 3. Verificação e Instalação Automática de Dependências
echo "[INFO] Verificando dependências via $PYTHON_EXEC..."
MISSING_DEPS=0
$PYTHON_EXEC -c "import PyQt6" 2>/dev/null || MISSING_DEPS=1
$PYTHON_EXEC -c "import can" 2>/dev/null || MISSING_DEPS=1
$PYTHON_EXEC -c "import serial" 2>/dev/null || MISSING_DEPS=1

if [ $MISSING_DEPS -ne 0 ]; then
    echo "[INFO] Dependências ausentes detectadas. Instalando automaticamente..."
    $PIP_EXEC install --upgrade pip 2>/dev/null || true
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

# 5. Execução do CANweaver com Python 3 garantido
echo "[INFO] Iniciando CANweaver com $PYTHON_EXEC..."
exec "$PYTHON_EXEC" "$SCRIPT_DIR/main.py" "$@"
