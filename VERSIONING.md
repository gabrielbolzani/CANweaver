# Guia de Versionamento e Releases - CANweaver

Este documento descreve as regras internas e o passo a passo de como versionar o código e publicar uma nova release do CANweaver no GitHub.

## 1. Fonte Única da Verdade (Single Source of Truth)
A versão do programa está centralizada em apenas **um** arquivo:
- `src/version.py`

Sempre que for lançada uma atualização (ex: passar de `0.1.5` para `0.2.0`), basta abrir este arquivo e alterar a variável `__version__`.

Ao alterar este único arquivo, o sistema automaticamente atualizará:
1. O título da Janela Principal.
2. O subtítulo na tela de "Sobre o CANweaver".
3. A lógica matemática do botão "Verificar Atualizações" (que usará a nova versão base para comparar com as tags do GitHub).

## 2. Regra de Versionamento Semântico (SemVer)
O projeto adota o padrão mundial de versionamento [SemVer](https://semver.org/), formatado como `MAJOR.MINOR.PATCH` (ex: `0.1.5`, `1.0.0`).

- **MAJOR (Principal):** Modificado quando ocorrem mudanças incompatíveis na API, alterações completas na arquitetura ou transição da fase Beta para Release final. (Ex: `0.x.x` -> `1.0.0` para a primeira versão Oficial Estável).
- **MINOR (Secundária):** Modificado ao adicionar funcionalidades novas de forma compatível com o que já existe (ex: criar uma aba nova, adicionar novos tipos de Widgets). (Ex: `0.1.5` -> `0.2.0`).
- **PATCH (Correção):** Modificado apenas em casos de correções de bugs, ajustes visuais ou melhorias de performance, sem lançar ferramentas novas. (Ex: `0.1.5` -> `0.1.6`).

## 3. Passo a Passo para Criar uma Release no GitHub

Quando o código estiver pronto para ser liberado para download na aba "Releases" do GitHub, os seguintes passos devem ser executados no terminal:

**Passo 1: Atualizar o arquivo de versão**
Abra `src/version.py` e altere a variável `__version__` para a nova versão desejada (ex: `"0.1.6"`).

**Passo 2: Fazer o Commit**
Adicione os arquivos e faça o commit referenciando a atualização da versão.
```bash
git add src/version.py
git commit -m "chore: Bump version to 0.1.6"
git push
```

**Passo 3: Criar a TAG no Git**
As tags servem como marcadores no tempo do repositório. O prefixo `v` é obrigatório para que o sistema de Update consiga ler corretamente da API do GitHub.
```bash
git tag v0.1.6
git push origin v0.1.6
```

**Passo 4: Publicar no GitHub**
1. Acesse a página do repositório no GitHub: `gabrielbolzani/CANweaver`
2. No menu lateral direito, clique em **Releases** e depois em **Draft a new release**.
3. No campo de "Choose a tag", selecione a tag recém-criada (`v0.1.6`).
4. Clique em **Generate release notes** (ou preencha manualmente as notas de atualização).
5. Se o código for compilado (ex: com PyInstaller gerando `CANweaver.exe`), o arquivo `.exe` ou o `.zip` deve ser anexado no campo "Attach binaries".
6. Clique em **Publish release**.

Imediatamente após a publicação, qualquer instância rodando uma versão anterior exibirá o aviso da nova versão ao clicar em "Verificar Atualizações", contendo o link direto para download.
