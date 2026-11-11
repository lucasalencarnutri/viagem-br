# Mudanças da Viagem BR

A versão mais nova fica no topo. A versão disponível pra baixar aparece no começo do guia de instalação.

## 1.6.2 (11/11/2026)

- Correção no jeito de atualizar pelo plugin: são dois comandos no Terminal, `claude plugin marketplace update viagem-br` e depois `claude plugin update viagem-br@viagem-br`. O segundo sozinho, que era o que as versões 1.6.0 e 1.6.1 ensinavam, responde que você já está na última versão e não atualiza.
- Em viagem de ida e volta, a conta de um sentido só trazia sempre o aviso de refazer a conta caso o outro sentido também fosse em milhas. Agora o aviso aparece só quando a conta muda de fato. Com dois só-ida já sendo a compra mais barata ela é a mesma, e o aviso não aparece mais.

## 1.6.1 (10/11/2026)

- Correção na conta de ida e volta. Quando o bilhete de ida e volta em dinheiro sai mais barato que dois só-ida, comparar cada sentido com o só-ida dele fazia a emissão parecer melhor do que é. A conta passa a usar o dinheiro que a emissão evita de verdade.
- Quando o preço em milhas não aparece (escondido pelo seats.aero, rota que ele não acompanha ou programa que ele não cobre), a skill passa a dizer até quantos pontos por pessoa a emissão ainda compensa: só a ida, só a volta e a viagem inteira. Você compara com o que o site do programa pedir.

## 1.6.0 (09/11/2026)

- Instalação como plugin do Claude Code, com dois comandos digitados dentro dele. O passo a passo está no README.
- Pelo plugin, o seats.aero já vem ligado. O Google Flights continua com o instalador, que o Claude roda quando você pede.
- O instalador reconhece o seats.aero ligado pelo plugin e não liga de novo. O login indicado no fim leva o nome certo pra cada jeito de instalar.
- Atualizar pelo plugin é um comando: `claude plugin update viagem-br@viagem-br`.
- Instalar pelo arquivo `viagem-br.skill` continua funcionando do mesmo jeito.

## 1.5.0 (09/11/2026)

- Ida e volta passa a ser comparada com dois só-ida, e a conta do milheiro é feita em cada sentido. O veredito pode sair misto: um sentido em milhas, o outro em dinheiro.
- Antes de buscar milhas, a skill consulta quais programas o seats.aero acompanha na rota. Programa que ele não acompanha sai marcado, em vez de parecer sem assento.
- Correção: o que some no seats.aero não é a Azul de quem não tem login. É emissão com preço muito alto, que ele esconde por padrão. A célula passa a sair "preço alto, escondido pelo seats.aero".

## 1.4.0 (09/11/2026)

- Cidade com mais de um aeroporto: São Paulo, Rio e Belo Horizonte entram inteiras numa busca só.
- A busca de voo passa a trazer 20 opções, e a contagem de voos fica mais fiel.
- Câmbio do dia pelo Banco Central, pra converter taxa cobrada em dólar ou euro.
- Taxa que o seats.aero não informa sai marcada, em vez de entrar como zero.
- Milhas aparecem em uma linha por programa.
- O registro de preço no histórico só é criado se você pedir pra monitorar.
- Pergunta rápida e pesquisa completa têm critério claro, e o objetivo que faltar é deduzido e dito no começo.

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
