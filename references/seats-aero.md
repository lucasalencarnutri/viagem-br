# seats.aero: como o servidor funciona

O servidor é o MCP oficial, `https://seats.aero/mcp`, e cada pessoa usa a própria conta. Medido em 2026-11-01; login, recorte por banco e `max_fees` revistos em 2026-11-07; limites de conta e lista de programas conferidos em 2026-11-08. Mudou o servidor: re-testar e atualizar com data.

| Item | Como funciona |
|---|---|
| Sem login | De graça e sem cadastro: só voos dos próximos 60 dias, sem a Azul, sem busca ao vivo e sem alerta, limite de 1.000 requisições por IP por dia. Data fora dos 60 dias dá erro (armadilha 24) |
| Com login | Só com assinatura Pro do seats.aero: calendário inteiro, busca ao vivo, alertas e mais ferramentas. Login: `claude mcp login seats-aero` (a pessoa faz no navegador dela) |
| Busca | `get_flights` com `origins` e `destinations` em lista, `cabin` com um valor só (uma chamada por cabine), `start_date` e `end_date` (até 60 dias por chamada), `max_results` (teto 50), `programs`, `operating_carriers` (companhia que voa, ex.: `G3`, `AD`), `max_stops` (padrão 0 = só direto, armadilha 15), `min_seats` (nem todo programa aceita), `max_fees` em centavos de dólar (armadilha 26). A resposta traz `status` (`results`, `filtered` ou `no_availability`), `truncated_by` (quantos resultados ficaram fora do corte) e `search_url` (a mesma busca no site) |
| Frescor | `minutes_old` (7 dias ≈ 10 mil minutos) |
| Programas | 33 em `programs`, com `smiles`, `azul`, `iberia`, `british`, `qatar`, `lifemiles`, `livelo`, `jal` e `asiamiles`. LATAM Pass fora |
| Detalhe do voo | `get_flight_details` (por `flight_ref`) |
| Busca ao vivo | `live_search`, só com login, com cota da conta e um programa por chamada (tem `smiles`, não tem `azul`). Gasta a cota: usar só perto da emissão ou quando o cache estiver velho |
| Preço de clube | Opções salvas na conta (`get_pricing_options`), só com login; não conferido se o Clube Smiles está lá |
| Reserva | Não faz (`get_capabilities` devolve `booking: false`) |

A resposta é cortada em 50 e ordenada por milhas: com programas definidos, filtre por eles na primeira chamada (armadilha 20).

Pela ponte de terminal (`scripts/ponte_mcp.py seats-aero ...`) a sessão é sempre anônima, porque a ponte não faz login. Sem login existem 8 ferramentas: `get_capabilities`, `get_flights`, `get_flight_details`, `search_airports`, `list_routes`, `list_transfer_partners`, `list_transfer_program_mileage_programs` e `search_help_docs`.

## Recorte por banco

**`transfer_partners`** no `get_flights` (tem `livelo` e `esfera`): recorta pelos programas que o seats.aero acha que cada banco alcança, e esse mapa é incompleto. Em 2026-11-07, a Livelo saiu sem Iberia e sem Qatar (armadilha 25). Use depois da busca por programa, como conferência; ausência nesse recorte não prova que o banco não transfere. A lista do seats.aero por banco sai em `list_transfer_program_mileage_programs`. Caminho, proporção e bônus valem pelo app do banco: conferir antes de transferir.

## Só com login

- **`get_booking_options(flight_ref, seats)`**: outros programas que emitem o mesmo voo, com preço confirmado ou estimativa da tabela. Estimativa não é disponibilidade; preço confirmado (`estimate: false`) do mesmo programa vence a estimativa. `taxCost` vem em centésimos de `taxCurrency` (1250 = US$ 12,50), e ausente ou zero é taxa desconhecida. Uso no Passo 7A e na armadilha 34.
- **`find_deals`**: amostra de achados pra inspiração. Nunca vira opção sem `get_flights` na rota e na data.
- **`create_alert`, `list_active_alerts`, `expire_alert`**: alerta de disponibilidade com filtro por voo, cabine e classe; o contínuo é só por e-mail. Criar só quando a pessoa pedir, conferindo `list_active_alerts` antes pra não duplicar.

## Avisos por resultado

`unknown_seat_count` (armadilha 16), `unknown_taxes` (armadilha 17) e `mixed_cabin` quando `min_cabin_pct` fica abaixo de 100 (trecho em cabine inferior: avisar a pessoa).
