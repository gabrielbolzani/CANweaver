<div align="center">
  <img src="ico.ico" alt="CANweaver Logo" width="120" />

  # CANweaver v2.0
  **AI Assisted CAN Reverse Engineering**
</div>

---

O **CANweaver** é uma ferramenta gráfica avançada desenvolvida em Python e PyQt6 para análise, simulação e injeção de pacotes em redes CAN (Controller Area Network). Projetado com foco em hacking automotivo, engenharia reversa e telemetria, ele transforma a leitura do caos hexadecimal em uma interface elegante, escura e dinâmica.

## 🚀 Principais Funcionalidades

### 🔍 Análise Visual Avançada (Sniffer)
- **Grid Dinâmico e Colorido:** As mensagens capturadas são alinhadas em uma tabela de alta performance. Quando um byte muda de valor em tempo real, a célula pisca em Azul escuro!
- **Modo Dark Premium:** Construído com tokens de design profissionais, garantindo uma interface `Glassmorphism` amigável para horas de trabalho noturno no carro.
- **Fade em Inativos:** Se um frame (ID) para de sofrer alterações, a linha sofre um fade out e fica apagada, dando destaque visual apenas ao que está acontecendo fisicamente no seu hardware!
- **Ocultar Estáticos:** Oculte com 1 clique todo o ruído passivo da rede (módulos dormindo).
- **Busload em Tempo Real:** Fique de olho na saúde e gargalo do barramento com indicadores de % de carga diretamente no painel.

### 📝 Documentação Integrada (Anotações)
- **Sistema de Comentários Interno:** Pare o mouse em qualquer bit, byte ou ID para inserir comentários multilinhas (`Shift+Enter`).
- **Marcação Visual Ouro:** Células documentadas ganham bordas e estilos amarelos cintilantes, servindo de trilha de migalhas para você não se perder no que já hackeou.
- Tudo é salvo e agregado nativamente no arquivo `CANweaver_Projeto.md`.

### 🥷 Injeção Ofensiva (Aba Transmitir)
- **Single-Shot Pulse:** Dispare frames customizados instantaneamente (ID e Dados) suportando digitação tanto em formato HEX quanto BINÁRIO puro!
- **Transmissão Cíclica Multitarefa:** Organize playlists de pacotes e mande o sistema bombardeá-los na rede em uma frequência customizada (`Hz` exato, ex: 10 Hz para manter uma injeção de 100ms viva no painel).
- **Pausa Cirúrgica:** Ative ou silencie timers específicos sem destruir o andamento de toda a orquestra.

### 📼 Gestão de Gravação de Sessões (Playback)
- Capture o tráfego do carro pressionando `Gravar`. A gravação é mascarada em um cache fantasma.
- Ao parar, um assistente inteligente pedirá que você rebatize o nome do CSV, mantendo a sua pasta de trabalho extremamente limpa.
- Recarregue os logs depois no modo `Playback` para assistir à ação gravada em Loop como um DVR!

---

## 🛠️ Tecnologias e Bibliotecas

- **[Python 3.10+]**
- **[PyQt6]** - O coração gráfico da arquitetura.
- **[python-can]** - Para comunicação física robusta via adaptadores USB (suporta SocketCAN, SLCAN, Vector, Kvaser, etc).
- **[pyserial]** - Escaneamento automático de interfaces COM/ttyUSB.

## ⚙️ Como Iniciar

1. Clone o repositório:
   ```bash
   git clone https://github.com/gabrielbolzani/CANweaver.git
   ```
2. Instale as dependências:
   ```bash
   pip install PyQt6 python-can pyserial
   ```
3. Execute o programa:
   ```bash
   python main.py
   ```

> **Aviso de Simulação:** Se você não tiver um CANable ou adaptador conectado, o CANweaver inicializará vazio em modo `IDLE`. Vá até `Conectar...`, mude o seletor para **Simulado** e clique em **OK** para que a Engine crie pacotes fantasmas matematicamente perfeitos para teste da UI!

## 📜 Licença e Contribuição
Este é um projeto para entusiastas e pesquisadores de Cyber Segurança Veicular. Hackeie com responsabilidade e mantenha o cinto de segurança apertado.

Desenvolvido com ☕ e IA.
