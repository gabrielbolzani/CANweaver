## 🚀 O que há de novo no CANweaver v2.5.0

Esta versão traz melhorias substanciais para a aba de **Painel & Widgets (Dashboard)**, com foco em ergonomia visual, camadas, novas formas geométricas livres e ajuste dimensional totalmente responsivo para gauges analógicos e barras.

---

### 📊 Gauges Responsivos com Ajuste Dinâmico (Barra Horizontal e Barra Vertical)
- **Ajuste Proporcional ao Espaço Delimitado:** Os mostradores de barra horizontal e vertical agora adaptam 100% de seus elementos (título, trilho, valor numérico e preenchimento) ao tamanho delimitado da caixa ($W \times H$), eliminando qualquer corte de texto ou transbordamento fora da tela.
- **Barra Horizontal Adaptativa:**
  - Em alturas padrão ($H \ge 42\text{ px}$), distribui de forma elegante o nome do widget à esquerda, valor numérico à direita e o trilho de progresso abaixo.
  - Em alturas compactas ($H < 42\text{ px}$ - Modo Slim), o texto é integrado diretamente no interior da barra com alto contraste.
- **Barra Vertical Dinâmica:**
  - O trilho vertical aproveita toda a extensão de altura útil entre o nome (topo) e o valor (base), com largura auto-ajustada proporcionalmente a $X$.
  - Suporta qualquer proporção (ex: $60 \times 320\text{ px}$ ou $80 \times 400\text{ px}$) sem distorção e sem deixar áreas vazias.
- **Diálogo de Configuração com Dimensões Independentes:** Campo de **Largura** e **Altura** dedicados no diálogo de configuração, sugerindo automaticamente as dimensões ideais ao alternar o estilo visual.
- **Snap de Grade Independente:** O alinhamento à grade mantém as proporções personalizadas de largura e altura sem achatar barras verticais.

---

### 🎨 Camadas e Z-Order no Dashboard ("Trazer para Frente" / "Enviar para Trás")
- **Controle de Camadas:** Clique com o botão direito em qualquer widget para enviá-lo para trás ou trazê-lo para frente, permitindo sobreposições elegantes (ex: molduras atrás de instrumentos, botões sobrepostos a painéis).
- **Ações em Lote:** Suporte a mudança de camada simultânea para múltiplos widgets selecionados.
- **Persistência Completa:** A ordem das camadas é preservada fielmente ao salvar e carregar arquivos de projeto (`.cwp`).

---

### 📐 Formas Livres Expandidas (ShapeWidget)
- **Nova Forma Retângulo / Quadrado Arredondado:** Adicionada a opção de cantos arredondados configuráveis (`rounded_rectangle`).
- **Controle Independente de Cores:** Ajuste separado para a **cor da borda/linha** (`stroke_color`) e a **cor do centro/preenchimento** (`fill_color`), com suporte a centro transparente ("Sem preenchimento").
- **Pré-visualização em Tempo Real:** Live Preview instantâneo no diálogo de configuração de formas geométricas.

---

### 🏎️ Widgets Customizados Cockpit & Lume
- **AutoFit de Texto em Botões:** Implementado redimensionamento dinâmico de texto nos botões dos widgets de volante, segurança e cockpit, garantindo que rótulos nunca sumam ou fiquem cortados ao redimensionar.
- **Botões de Decremento no Cockpit:** Adicionada linha de botões de decremento percentual (`[-5]`, `[-10]`, `[-20]`, `[0%]`) no widget de pedais e tração, espelhando a linha de incremento.
- **Persistência de Posição:** Correção no carregamento e salvamento de projetos para evitar deslocamento indesejado de widgets customizados.

---

### 📦 Instalação e Execução:
```bash
# Clone ou atualize o repositório
git clone https://github.com/gabrielbolzani/CANweaver.git
cd CANweaver

# No Linux / macOS:
chmod +x run.sh
./run.sh

# No Windows:
run.bat
```
