# Mudanças da Viagem BR

A versão mais nova fica no topo. A versão disponível pra baixar aparece no começo do guia de instalação.

## 1.3.0 (09/11/2026)

- Voo dentro do Brasil: a executiva só é pesquisada se você pedir, e as duas células saem "não pesquisada: rota doméstica".
- Em rota doméstica, as milhas olham Smiles e Azul e também programas de fora que emitem Gol, Azul e LATAM: American, Aeroplan, United, Livelo, Delta e Virgin Atlantic.
- Correção: sem login, o seats.aero mostra a Azul em parte. As versões anteriores diziam que ele escondia a Azul inteira.
- Correção: o que está fora do seats.aero é o programa LATAM Pass. Voo da LATAM pode aparecer por Delta e Virgin Atlantic. A célula da LATAM Pass passa a sair "sem dado: programa fora do seats.aero", e não mais "sem estoque".

## 1.2.0 (09/11/2026)

- Instalador único: `python3 ~/.claude/skills/viagem-br/scripts/instalar.py` confere o que falta, baixa e compila o servidor do Google Flights e liga os servidores no Claude Code.
- `--conferir` chama cada servidor uma vez e diz o que respondeu, sem instalar nada.
- Kiwi, Skiplagged e Trivago passam a ser ligados só com `--com-opcionais`.
- O passo a passo manual continua no README, pra quem prefere.

## 1.1.0 (09/11/2026)

- Sua régua passa a morar em `~/.viagem-br/regua-milheiro.md`, fora da pasta da skill. Atualizar a skill não apaga mais os seus valores.
- O Claude grava os seus valores por comando, sem editar tabela à mão.
- Programa que você não gravou continua usando a média de referência, e a média nova chega junto com a atualização.
- O pacote ganha número de versão e esta lista.
- Vindo de versão anterior com régua preenchida dentro da pasta da skill: anote os valores antes de atualizar e grave de novo depois.

## 1.0.2 (09/11/2026)

- A JetBlue entra como filtro pelo próprio seats.aero conectado, sem precisar ir ao site, pra achar assento de parceiro da Azul pelo Mundo.
- O resultado avisa quando o valor usado é média de referência e não a sua régua.

## 1.0.1 (09/11/2026)

- Regra explícita: a skill só pesquisa e faz a conta. Nunca compra, emite, reserva ou transfere pontos.
- A ponte de terminal entrega ao servidor só as variáveis de ambiente de que ele precisa.

## 1.0.0 (08/11/2026)

- Primeira versão pública: pesquisa de voo em dinheiro e em milhas, conta do milheiro, régua com médias de referência e busca de hotel pelo Trivago.
