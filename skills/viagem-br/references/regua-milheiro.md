# Régua do milheiro

Como a skill compara uma emissão em milhas com o preço em dinheiro e chega ao veredito. O cálculo roda em `scripts/milheiro.py`, que lê dois lugares: as médias de referência, nas tabelas do fim deste arquivo, e os valores da pessoa, em `~/.viagem-br/regua-milheiro.md`. O valor da pessoa vence a média, programa por programa.

## Fórmula

milheiro da emissão = (preço cash − taxas de emissão) ÷ milhas × 1.000

- Preço cash: o da mesma rota, mesma cabine, mesmas datas. No Brasil ele já vem com a taxa de embarque embutida; por isso a taxa sai do lado do dinheiro.
- Taxas de emissão: as cobradas em dinheiro pelo programa que emite. Taxa zerada vinda do seats-aero é placeholder do cache: valor real só no checkout. Nunca tratar 0 como fato: nesse caso, `--taxas desconhecida` no script, e o resultado sai marcado.
- Mesma base de passageiros: preço, taxas e milhas do grupo inteiro, ou os três por pessoa (armadilha 31).
- Taxa igual ou maior que o preço em dinheiro: o milheiro dá zero ou negativo e o veredito é pagar em dinheiro.

## Régua de veredito

Compare o milheiro da emissão com o valor da sua régua para o programa que emite:

- **Milheiro da emissão ACIMA do valor da régua:** as milhas valem mais nesta emissão do que custam para repor. Favorável a emitir com milhas que você já tem; comprar pontos para emitir também é razoável. Exemplo com números inventados: milheiro de R$ 50 contra régua de R$ 30. Neste caso, 100 mil milhas compradas por R$ 3.000, mais as taxas, cobrem um bilhete que custaria R$ 5.000 além das taxas.
- **Milheiro da emissão IGUAL ou ABAIXO do valor da régua:** comprar pontos para esta emissão custa mais do que entrega. O padrão é pagar em dinheiro e preservar as milhas. Não recomendar compra de pontos; emitir milhas existentes é exceção, só com critério declarado (ex.: preservar caixa), nunca como "economia".
- **Programa sem valor em lugar nenhum:** o script calcula o milheiro e marca `[FALTA: valor da sua régua]`. A decisão de comprar pontos fica pendente até a pessoa dizer o valor.
- **Programa que a pessoa não gravou:** vale a média de referência, e o resultado sai marcado `[MÉDIA DE REFERÊNCIA]`. Diga isso ao usar, sem apresentar como o custo real da pessoa.
- **Veredito SEMPRE em termos de milheiro** (ex.: "milheiro de R$ 38 contra régua de R$ 30"), nunca como "economia de X%": percentual esconde o custo de repor as milhas.
- **Bagagem desigual invalida a comparação:** preço listado é SEM bagagem; se a emissão inclui bagagem e o preço em dinheiro não, ajuste antes de dar o veredito (os dois lados com as mesmas regras de bagagem).

## Regra da moeda (programas não somam)

Pontos de programas diferentes **não somam nem se comparam**. Cada programa é uma moeda com custo e poder de emissão próprios: comparar o milheiro de um programa com o de outro não diz nada, porque as moedas e as entregas são diferentes. Comparação entre programas só existe numa forma: **o custo total em dinheiro da mesma viagem** (milhas × valor da régua + taxas, mesma rota/cabine/datas). Saldos de programas distintos listam-se separados; total, se precisar, em reais.

## Regra de leitura

Sempre separe a companhia que voa do programa que emite (ex.: voa Emirates, emite Smiles). O milheiro é do programa que emite; a experiência de voo é da companhia que opera. Fatos por programa que não podem errar: `references/fatos-programas.md`.

## Como achar o seu número

O valor da régua é o máximo que você aceita pagar por 1.000 milhas daquele programa. Quem compra milhas ou assina clube olha o que pagou da última vez: valor pago ÷ milhas recebidas × 1.000. As médias de referência servem pra começar; troque pelos seus valores, porque o preço muda com a promoção, com o clube e com o seu perfil.

## Onde ficam os seus valores

Em `~/.viagem-br/regua-milheiro.md`, fora da pasta da skill, pra atualização não apagar. Grava-se por comando:

- `python3 scripts/milheiro.py --gravar regua <programa> <valor>`: o máximo que a pessoa aceita pagar por 1.000 milhas.
- `python3 scripts/milheiro.py --gravar preco <programa> <valor>`: o que ela costuma pagar.

O comando cria o arquivo, troca só a linha daquele programa e, na régua, renova a data. Aceita `20`, `20,50` ou `"R$ 20,50"`. Programa que ela não gravou segue na média. Programa fora das tabelas entra com o nome que o seats.aero usa (ex.: `united`, `turkish`). Pra voltar à média, apague a linha do programa naquele arquivo. Quem preferir pode editar o arquivo num editor de texto, no mesmo formato.

## Médias de referência: régua

R$ por 1.000 milhas, valor máximo por programa. Médias de novembro de 2026. SUMA são 10 euros, a R$ 6,1317 o euro (06/11/2026).

Não edite esta tabela: a atualização da skill substitui este arquivo. O `(média)` ao lado de cada valor é o que faz o resultado sair marcado `[MÉDIA DE REFERÊNCIA]`.

<!-- regua:inicio -->
| Programa | Valor máximo (R$ por 1.000) |
|---|---|
| Azul | 14 (média) |
| Smiles | 16 (média) |
| LATAM Pass | 25 (média) |
| Avios | 56 (média) |
| Miles & Go | 35 (média) |
| Lifemiles | |
| SUMA | 61,32 (média) |
| Aeroplan | 70 (média) |
| Flying Blue | 75 (média) |
| Aegean | 68 (média) |
| JAL | 84 (média) |
| Connectmiles | |
<!-- regua:fim -->

Última atualização da régua (DD/MM/AAAA): 08/11/2026

Essa é a data das médias. Passados 90 dias dela, o resultado que usa média sai com `[RECONFIRMAR]` e pede pra ver se há versão nova da skill. O valor da pessoa segue a data do arquivo dela, com a mesma regra dos 90 dias: preço de milha muda rápido. O script entende `iberia`, `british` e `qatar` como Avios, `flyingblue` como Flying Blue, `copa` como Connectmiles e `tap` como Miles & Go.

## Médias de referência: preço

R$ por 1.000 milhas: o que se costuma pagar em cada programa. Serve só pra dizer "em milhas fica mais ou menos isso". O veredito continua na régua acima. Programa cobrado em outra moeda: converta pra reais antes de gravar.

<!-- preco:inicio -->
| Programa | Preço de referência (R$ por 1.000) |
|---|---|
| LATAM Pass | 25 (média) |
| Smiles | 16 (média) |
| Azul | 14 (média) |
| Avios | 56 (média) |
| Miles & Go | 35 (média) |
| Aegean | 68 (média) |
| Livelo | 30 (média) |
| Esfera | 35 (média) |
| Flying Blue | 75 (média) |
| Aeroplan | 70 (média) |
| JAL | 84 (média) |
| AAdvantage | 100 (média) |
| Skywards | 100 (média) |
| SUMA | 61,32 (média) |
<!-- preco:fim -->

Comando: `python3 scripts/milheiro.py --estimar --milhas N --taxas T --programa P`. Programa sem valor sai `[FALTA: seu preço de referência]`.
