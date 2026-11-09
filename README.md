# Viagem BR

Pesquisa de voos e milhas para quem viaja do Brasil. Plugin gratuito para o Claude Code. Você pergunta em português, por exemplo "quanto tá São Paulo pra Lisboa em fevereiro, e vale emitir com Smiles?". Ele busca o preço em dinheiro, busca as milhas, faz a conta do milheiro e diz o que faria e por quê.

Milheiro é quanto cada 1.000 milhas estão valendo naquela passagem.

## Instalar

Você precisa do Claude Code, que pede um plano pago do Claude. Abra o Claude Code e, dentro dele, digite um comando por vez:

```text
/plugin marketplace add lucasalencarnutri/viagem-br
```

```text
/plugin install viagem-br@viagem-br
```

O primeiro cadastra este repositório. O segundo abre a tela do plugin: escolha `Install for you (user scope)` e aperte Enter. Depois feche o Claude Code com `/exit` e abra de novo.

Falta só o Google Flights, que é baixado e compilado no seu computador. Com o Claude Code aberto, escreva:

```text
roda o instalador da Viagem BR
```

O Claude pede a sua permissão antes de rodar, e leva de 1 a 3 minutos. Depois é só perguntar.

O passo a passo completo, do zero, está no [guia](skills/viagem-br/README.md): como instalar o Claude Code, o que fazer quando algo dá errado e como instalar pelo arquivo `viagem-br.skill`, pra quem prefere.

## O que vem no plugin

- **A skill `viagem-br`.** O método de pesquisa, o catálogo de armadilhas das fontes, a conta do milheiro e a sua régua, que é o valor máximo que você aceita pagar por 1.000 milhas de cada programa.
- **A ligação com o seats.aero** (`https://seats.aero/mcp`), que mostra o preço em milhas. Sem login é grátis e enxerga só os próximos 60 dias. Com plano Pro em seu nome, o login é `claude mcp login plugin:viagem-br:seats-aero`, no Terminal.
- **O instalador do Google Flights**, que mostra o preço em dinheiro. Ele baixa o servidor [google-flights-mcp](https://github.com/andreacappelletti97/google-flights-mcp) numa versão fixa, compila em `~/mcp/google-flights-mcp` e liga no Claude Code. Não pede senha de administrador e não apaga pasta.

## Antes de confiar

A skill só pesquisa e faz a conta: não compra, não emite e não transfere pontos. O dado de milhas é uma foto de horas ou dias atrás, o seats.aero esconde emissão com preço muito alto, o programa LATAM Pass não está nele e o Google Flights pode parar sem aviso. Os limites estão todos no [guia](skills/viagem-br/README.md), na seção "Limites".

Testada no Mac. No Windows nada foi testado.

## Atualizar

No Terminal, fora do Claude Code:

```bash
claude plugin update viagem-br@viagem-br
```

O que mudou em cada versão está em [MUDANCAS.md](skills/viagem-br/MUDANCAS.md).

## Privacidade

O plugin não manda nada pra quem o criou. A sua régua fica só no seu computador, em `~/.viagem-br/`. As buscas vão pros serviços que você ligou: Google Flights e seats.aero, mais Kiwi, Skiplagged e Trivago se você ligar os opcionais. A consulta de câmbio vai ao Banco Central levando só a moeda e as datas, e a conversa segue as regras do Claude. Nunca passe senha, chave ou dado de cartão pro Claude.

## Crédito

A ideia de conferir o preço em mais de uma fonte e a de instalar como plugin vieram do [Travel Hacking Toolkit](https://github.com/borski/travel-hacking-toolkit), de Michael Borohovski (licença MIT). Nenhum trecho de texto ou código foi copiado de lá. O detalhe está no [guia](skills/viagem-br/README.md), na seção "Crédito".
