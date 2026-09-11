@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM  CANweaver - Launcher e Auto-Instalador para Windows
REM ==============================================================================

cd /d "%~dp0"
title CANweaver Launcher

echo ========================================================
echo                CANweaver v2.0 Launcher                 
echo ========================================================

REM 1. Checagem do Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERRO] Python nao foi encontrado no sistema!
        echo Por favor, instale o Python 3.10 ou superior do site oficial python.org
        echo Lembre-se de marcar a opcao "Add Python to PATH" durante a instalacao.
        pause
        exit /b 1
    ) else (
        set "PY_CMD=py -3"
    )
) else (
    set "PY_CMD=python"
)

REM 2. Criacao e ativacao de ambiente virtual (.venv)
if not exist ".venv" (
    echo [INFO] Criando ambiente virtual em .venv...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [AVISO] Falha ao criar ambiente virtual. Tentando prosseguir com Python global...
        set "PYTHON_EXEC=%PY_CMD%"
        set "PIP_EXEC=%PY_CMD% -m pip"
    ) else (
        set "PYTHON_EXEC=.venv\Scripts\python.exe"
        set "PIP_EXEC=.venv\Scripts\pip.exe"
    )
) else (
    set "PYTHON_EXEC=.venv\Scripts\python.exe"
    set "PIP_EXEC=.venv\Scripts\pip.exe"
)

REM 3. Verificacao de dependencias
echo [INFO] Verificando dependencias...
set "MISSING=0"
"%PYTHON_EXEC%" -c "import PyQt6" >nul 2>nul || set "MISSING=1"
"%PYTHON_EXEC%" -c "import can" >nul 2>nul || set "MISSING=1"
"%PYTHON_EXEC%" -c "import serial" >nul 2>nul || set "MISSING=1"

if "%MISSING%"=="1" (
    echo [INFO] Dependencias ausentes detectadas. Instalando automaticamente...
    "%PIP_EXEC%" install --upgrade pip >nul 2>nul
    if exist "requirements.txt" (
        "%PIP_EXEC%" install -r requirements.txt
    ) else (
        "%PIP_EXEC%" install PyQt6>=6.4.0 python-can>=4.2.0 pyserial>=3.5
    )
    if %errorlevel% neq 0 (
        echo [ERRO] Falha ao instalar dependencias necessarias.
        pause
        exit /b 1
    )
    echo [OK] Dependencias instaladas com sucesso!
) else (
    echo [OK] Todas as dependencias estao prontas.
)

REM 4. Execucao da aplicacao
echo [INFO] Iniciando CANweaver...
"%PYTHON_EXEC%" main.py %*
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] A aplicacao encerrou com codigo de erro %errorlevel%.
    pause
)
