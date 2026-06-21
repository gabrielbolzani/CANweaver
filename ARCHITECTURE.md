# CANweaver — Arquitetura do Projeto

> **Para IAs e colaboradores:** leia este arquivo ANTES de editar qualquer código.
> Ele foi criado especificamente para guiar edições focadas, economizando tokens e evitando regressões.

---

## Visão Geral

O CANweaver é uma ferramenta de análise e engenharia reversa de redes CAN (Controller Area Network) com interface gráfica PyQt6. O projeto está estruturado em módulos coesos, cada um com responsabilidade única.

```
CANweaver/
│
├── main.py                  ← Ponto de entrada (~200 linhas)
│
├── src/                     ← Módulos de lógica e UI
│   ├── __init__.py
│   ├── worker.py            ← Thread de captura/envio CAN
│   ├── delegate.py          ← Renderizador de células da tabela
│   ├── dialogs.py           ← Diálogos (ConnectionDialog, CommentDialog)
│   ├── annotations.py       ← Sistema de anotações (leitura/escrita .md)
│   ├── analysis_tab.py      ← Aba de Análise (sniffer ao vivo)
│   ├── transmit_tab.py      ← Aba de Transmissão (single-shot e cíclico)
│   └── widgets_tab.py       ← Aba de Painéis/Gauges (em desenvolvimento)
│
├── assets/                  ← Recursos estáticos
│   ├── ico.ico
│   ├── style.qss            ← Folha de estilos global (dark theme)
│   └── recursos/            ← Imagens auxiliares
│
├── CANweaver_Projeto.md     ← Anotações do usuário (gerado em runtime)
├── README.md                ← Documentação pública do projeto
└── ARCHITECTURE.md          ← Este arquivo
```

---

## Módulos — Responsabilidade e Contexto

### `main.py` — Ponto de Entrada
- Cria a `MainWindow` (QMainWindow)
- Monta a **Toolbar Global** (botões Conectar e Gravar — aparecem em TODAS as abas)
- Instancia os 3 widgets de aba e os conecta ao `CANWorker`
- Gerencia o ciclo de vida da gravação (CSV)
- **Edite aqui** se precisar mudar: toolbar, ciclo de gravação, inicialização da aplicação

### `src/worker.py` — `CANWorker(QThread)`
- Toda comunicação com o barramento CAN
- Três modos: `SIMULATED` (gerador interno), `HARDWARE` (via python-can), `PLAYBACK` (CSV)
- Emite `frame_received(can_id, freq, payload)` e `error_occurred(msg)`
- Método `send_message(can_id, data)` para injeção de frames (usado pela aba Transmitir)
- **Edite aqui** se precisar mudar: simulação, suporte a novo hardware, lógica de envio

### `src/delegate.py` — `CANItemDelegate(QStyledItemDelegate)`
- Renderizador customizado de células da tabela CAN
- **Modo HEX:** célula com texto + borda amarela se anotada
- **Modo BIN:** desenha 8 quadradinhos por byte, label "76543210", fade por cor de fundo, borda amarela por bit específico
- Roles dos QStandardItem:
  - `UserRole` → string binária anterior (para detectar mudanças)
  - `UserRole+1` → bool: tem anotação
  - `UserRole+3` → int bitmask: quais bits têm anotação
  - `UserRole+4` → bool: o byte inteiro tem anotação
- **Edite aqui** se precisar mudar: visual dos bits, cores, animações de mudança

### `src/dialogs.py` — Diálogos
- `ConnectionDialog`: seleção de modo (Simulado/Hardware/Playback), interface, canal, bitrate e arquivo
- `CommentDialog`: caixa de texto com Enter = salvar, Shift+Enter = nova linha
- **Edite aqui** se precisar mudar: campos de conexão, comportamento dos modais

### `src/annotations.py` — `AnnotationManager`
- Lê e escreve o arquivo `CANweaver_Projeto.md`
- Mantém dicionário em memória: `{ "ID 0C0 - Byte 2": ["comentário..."] }`
- Métodos principais:
  - `load()` → carrega o .md para memória
  - `add_comment(target, text)` → salva no .md e na memória
  - `get_tooltip_for_id(hex_id)` → texto para tooltip do ID
  - `get_tooltip_for_byte(hex_id, byte_idx)` → texto agregado (byte + bits)
  - `get_annotation_info(hex_id, byte_idx)` → `(has_any, bitmask, has_byte)`
- **Edite aqui** se precisar mudar: formato de armazenamento, sistema de tags

### `src/analysis_tab.py` — `AnalysisTab(QWidget)`
- Toda a UI e lógica da aba "Análise (Sniffer)"
- Grelha CAN (`QTableView` + `QStandardItemModel`)
- Fade visual dos bytes inativos via `QTimer` (100ms)
- Cálculo de Busload via `QTimer` (1s) — usa `self.current_bitrate`
- Filtros por ID (texto) e Frequência (operador + valor)
- Lista de IDs com checkboxes para visibilidade
- Context menu (botão direito) → `CommentDialog` → salva anotação
- **Edite aqui** se precisar mudar: tabela, filtros, fade, busload, anotações visuais

### `src/transmit_tab.py` — `TransmitTab(QWidget)`
- UI e lógica da aba "Transmitir"
- **Single Shot:** digita ID + dados (HEX ou BIN) → dispara um frame
- **Periódico:** lista de tarefas com QTimer individual por linha
  - Frequência em Hz (convertida para ms internamente: `1000 / hz`)
  - Botão Pausar/Retomar por linha (muda cor e texto)
  - Botão Excluir por linha
  - Botões globais: Iniciar Cíclicos / Parar Todos
- **Edite aqui** se precisar mudar: transmissão, periodicidade, UI da aba Transmitir

### `src/widgets_tab.py` — `WidgetsTab(QWidget)`
- Esqueleto para a aba "Widgets" (em desenvolvimento)
- Recebe `can_thread_ref` para futura conexão com dados ao vivo
- **Edite aqui** para adicionar gauges, velocímetros, painéis

---

## Fluxo de Dados

```
CANWorker.frame_received
        │
        ▼
AnalysisTab.process_can_frame()   ← atualiza tabela + fade + busload
        │
        ├── AnnotationManager     ← consulta tooltips e bitmasks
        └── CANItemDelegate       ← renderiza cada célula (via paint())

Usuário → click direito → CommentDialog → AnnotationManager.add_comment()
                                        → atualiza célula com bitmask/tooltip

TransmitTab → QTimer → CANWorker.send_message()
                              │
                              └── (modo SIMULATED) → frame_received.emit()
                                                          │
                                                          ▼
                                                  AnalysisTab (loop)
```

---

## Convenções

- Novos módulos: criar em `src/`, importar em `main.py`
- Assets: colocar em `assets/`
- Testes rápidos: `python -m py_compile main.py` para checar sintaxe
- Rodar: `python main.py`
- Dependências: `pip install PyQt6 python-can pyserial`

---

## Status das Funcionalidades

| Funcionalidade | Status | Arquivo |
|---|---|---|
| Sniffer ao vivo (HEX/BIN) | ✅ Completo | `src/analysis_tab.py` |
| Fade de inativos | ✅ Completo | `src/analysis_tab.py` |
| Busload % | ✅ Completo | `src/analysis_tab.py` |
| Filtros por ID e Frequência | ✅ Completo | `src/analysis_tab.py` |
| Anotações por ID/Byte/Bit | ✅ Completo | `src/annotations.py` |
| Borda amarela por bit | ✅ Completo | `src/delegate.py` |
| Gravação CSV | ✅ Completo | `main.py` |
| Playback CSV | ✅ Completo | `src/worker.py` |
| Transmissão single-shot | ✅ Completo | `src/transmit_tab.py` |
| Transmissão cíclica | ✅ Completo | `src/transmit_tab.py` |
| Assistente IA | 🚧 Em Desenvolvimento | `src/analysis_tab.py` |
| Gauges / Widgets visuais | 🚧 Em Desenvolvimento | `src/widgets_tab.py` |
