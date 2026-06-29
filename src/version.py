"""
Arquivo central de versionamento do CANweaver.
Altere a versão aqui para que ela reflita automaticamente em:
- Título da janela principal
- Menu Sobre
- Sistema de verificação de atualizações (Releases do GitHub)

====================================================================
REGRA DE VERSIONAMENTO SEMÂNTICO (SemVer) - MAJOR.MINOR.PATCH
====================================================================
Adotamos o padrão mundial de versionamento (ex: 0.1.0, 1.2.3)

[MAJOR] (Primeiro número)
- Altere quando fizer mudanças incompatíveis na API, mudar
  completamente a arquitetura ou sair de fase Beta para Release final.
  Ex: 0.x.x (Fase Beta) -> 1.0.0 (Primeira versão Oficial Estável).

[MINOR] (Segundo número)
- Altere quando adicionar novas funcionalidades de forma
  compatível com o que já existe (ex: criar uma aba nova, adicionar 
  novos tipos de Widgets). 
  Ex: 0.1.0 -> 0.2.0

[PATCH] (Terceiro número)
- Altere quando fizer apenas correções de bugs, ajustes visuais ou
  melhorias de performance, sem lançar grandes ferramentas novas.
  Ex: 0.2.0 -> 0.2.1

====================================================================
COMO LANÇAR UMA RELEASE NO GITHUB
====================================================================
O GitHub NÃO lê este arquivo automaticamente para criar a Release. 
Você precisa dizer a ele qual é a versão. Siga o passo a passo:

1. Atualize a variável __version__ abaixo (ex: "0.1.0").
2. Faça o commit da sua alteração e suba (push) para o GitHub.
3. No terminal, crie uma "Tag" no Git com o MESMO número:
   git tag v0.1.0
   git push origin v0.1.0
4. Vá no GitHub > Releases > Draft a new release. Selecione a 
   tag "v0.1.0" que você acabou de enviar, anexe o arquivo .exe 
   (se tiver) e publique!
"""

__version__ = "0.1.5"
