# Hotel pelo Trivago

Usa o MCP `trivago` quando ele estiver conectado. Sem ele, avise e siga sem preço de hotel. Testado em 2026-11-08 (Recife, Boa Viagem, 05 a 11/12/2026, casal).

## Como buscar

- `trivago-accommodation-radius-search` para cidade, bairro ou ponto de referência, com latitude e longitude do lugar onde a pessoa quer ficar. `trivago-accommodation-search` só para um hotel pelo nome ou região grande.
- Sempre `country: BR`, `currency: BRL` e `language: PT_BR`, além de `adults` e `rooms` da viagem. Trocar o país não é estratégia de economia: sem conferir imposto, a diferença entre mercados não prova nada.
- Filtre por nota e estrelas (`review_rating`, `hotel_rating`) quando a pessoa disser o padrão.

## Como ler

- `price_per_stay` é o total da estadia; use esse número no custo da viagem.
- A primeira oferta do hotel não é a mais barata. No teste, o mesmo hotel veio primeiro a R$ 2.733 e tinha oferta a R$ 2.073. Compare todas.
- Compare condições iguais. A oferta mais barata costuma ser sem café e sem reembolso; o mesmo hotel a R$ 2.302 vinha com café e cancelamento grátis. Diga sempre a condição junto do preço (`price_attributes`).
- O mesmo hotel pode vir duas vezes com códigos diferentes (mesma latitude e longitude, nomes parecidos). Trate como um só e avise.
- O link é o `deal_url` da oferta citada, sem editar.

## O que nunca dizer

- Preço de hotel como garantido: é o preço da consulta, e imposto ou taxa local só se confirmam no site de reserva. Traga a data da consulta.
- Que a oferta é a melhor do mercado: o Trivago compara os sites parceiros dele.
