# 2026-08-20 GRU-NRT: REFERENCIA P/ MILHAS (EXEMPLO)

> **EXEMPLO / NÚMEROS FICTÍCIOS.** Mostra o formato da SAÍDA da skill e serve de
> teste do `scripts/audit.py`. Rota, voos, preços, milhas e régua abaixo são
> inventados; não citar este arquivo como fonte. Data e hora fictícias das
> chamadas: 2026-08-20 09:12 BRT · google-flights + seats-aero.

ENTRADA (exemplo): OBJETIVO REFERENCIA P/ MILHAS · ORIGEM GRU · DESTINO NRT ·
JANELA 14–28 out 2026 · CABINE economy (executiva como variável) · RESTRICOES
máx. 1 conexão · [FALTA: PAX] (assumido 1 adulto).

## AVISOS

>> [FALTA: PAX]: a ENTRADA não trouxe; buscas rodadas com 1 adulto.
>> Milhas: sem LATAM Pass no seats-aero. Célula do programa marcada
   "sem dado: programa fora do seats.aero".

## TABELA

Matriz completa, cada célula com PISO · DENSIDADE (sujeito a disponibilidade):

| célula | piso · densidade |
|---|---|
| dinheiro × econômica | R$ 7.431 · 11 diretas/semana |
| dinheiro × executiva | R$ 14.980 · 4 opções/dia |
| milhas × econômica | 128k milhas + R$ 380 · 2 programas (Azul, Smiles) |
| milhas × executiva | 390k milhas + R$ 350 · 2 programas (Azul, Smiles) |
| milhas × executiva (LATAM Pass) | sem dado: programa fora do seats.aero [FALTA: busca manual no programa] |

Finalistas em dinheiro: companhia que voa | rota e conexões | duração total |
horários-chave | preço | posição vs faixa típica:

- Air Canada (AC 63 + AC 5): GRU–YYZ–NRT · 27h55 · sai 23:55, chega 09:50+2 ·
  R$ 7.431 · piso da faixa típica.
- ANA (NH 84 + NH 85): GRU–FRA–HND · 26h10 · sai 23:35, chega 08:00+2 ·
  R$ 7.890 · dentro da faixa típica.
- Executiva mais barata em dinheiro: Air Canada business, conexão em YYZ de 2h05
  (confortável), R$ 14.980.

## VEREDITO

Executiva pela Azul a 390k milhas + R$ 350 é a compra razoável: o milheiro
implícito de R$ 37,51 fica acima do valor da régua do programa (R$ 30,00, régua
fictícia deste exemplo), critério do Passo 7B. Em dinheiro, nenhum finalista está
abaixo da faixa típica: mexa nas datas antes de aceitar o preço.

## MILHAS

Milheiro implícito por emissão (`scripts/milheiro.py`; preço em dinheiro = piso
da mesma rota/cabine/datas):

- Azul, executiva: (14.980 − 350) ÷ 390.000 × 1.000 = R$ 37,51/milheiro,
  acima da régua (azul, R$ 30,00): emissão razoável.
- Smiles, econômica: (7.431 − 380) ÷ 128.000 × 1.000 = R$ 55,09/milheiro,
  acima da régua (smiles, R$ 30,00): emissão razoável.

## PRÓXIMOS PASSOS

- Baseline de track criado (fictício): GRU–NRT, ida 2026-10-15, 1ª observação
  hoje; tendência só a partir da 2ª rodada.
- URL de evidência do preço em dinheiro (fictícia):
  https://www.google.com/travel/flights?q=GRU-NRT-2026-10-15-economy&curr=BRL
- Na próxima rodada: repetir o passo 7A (get_flights) e comparar `minutes_old` e
  assentos por programa.
