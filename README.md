# Viagem BR

Pesquisa de voos e milhas para quem viaja do Brasil. Skill gratuita para o Claude Code. Você pergunta em português, por exemplo "quanto tá São Paulo pra Lisboa em fevereiro, e vale emitir com Smiles?". Ela busca o preço em dinheiro, busca as milhas, faz a conta e diz o que faria e por quê.

Skill é um pacote de instruções que ensina o Claude a fazer uma tarefa sempre do mesmo jeito.

## O que ela entrega

- Preço em dinheiro e em milhas lado a lado, em econômica e executiva, com quantas opções existem em cada caso.
- As datas mais baratas da rota, as conexões e o risco de cada uma.
- A conta do milheiro de cada emissão: (preço em dinheiro − taxas) ÷ milhas × 1.000. Milheiro é quanto cada 1.000 milhas estão valendo naquela passagem.
- A comparação com a sua régua, que é o valor máximo que você aceita pagar por 1.000 milhas de cada programa.
- Avisos do que você precisa conferir. Quando um dado não veio, ela escreve que não veio.

## Limites (leia antes de confiar)

- **O programa LATAM Pass não está no seats.aero.** Voo da LATAM ainda pode aparecer por Delta e Virgin Atlantic, com pouca cobertura. A skill avisa, e pra emitir com LATAM Pass você confere no site da LATAM.
- **Azul não informa quantos assentos restam.** Viajando em 2 pessoas ou mais, confirme no site da Azul. A busca da Azul também só mostra voo da própria Azul: voo de parceiro pelo Azul pelo Mundo sai como pista, marcado `[conferir preço no site da Azul]`.
- **O Google Flights não tem API oficial.** O servidor lê a página pública do Google e pode parar sem aviso se o Google mudar o site. Quando isso acontece, a skill marca "sem dado" naquela parte e segue.
- **O seats.aero é uma foto, não o estoque ao vivo.** O dado tem de horas a dias. Antes de transferir pontos, confira o assento no site do programa, porque transferência não volta.
- **Sem assinatura Pro do seats.aero, só os próximos 60 dias e a Azul só em parte.** Sem login o serviço é grátis e não pede cadastro, mas recusa datas além de 60 dias e esconde parte dos voos da Azul: em 09/11/2026 ela apareceu em voo dentro do Brasil e pra Lisboa, e não apareceu pra Orlando. Smiles e Iberia aparecem normalmente. A skill avisa quando isso afeta a sua busca.
- **Voo dentro do Brasil sai sem executiva.** Em rota doméstica a skill só pesquisa executiva se você pedir. Nas milhas, ela olha Smiles e Azul e também programas de fora que emitem Gol, Azul e LATAM, como American, Aeroplan, United, Delta e Virgin Atlantic. Esses só servem se você tem os pontos ou um caminho de transferência.
- **O seats.aero não diz se o preço é promocional ou tarifa pública.** Com a conta Pro, a skill compara o mesmo voo em outros programas e marca `[provável tarifa pública]`. Sem login essa conferência não existe, e a skill avisa.
- **Bônus de transferência é com você.** A skill não acompanha promoção. Veja no app do banco o bônus ativo, a proporção e a data limite.
- **Ela não emite nem compra nada.** Só pesquisa e faz a conta.
- **Testada no Mac em 08/11/2026.** No Windows os comandos mudam e nada foi testado, nem o instalador: peça pro Claude Code adaptar cada passo.
- **Uso pessoal.** O seats.aero não permite uso comercial da API sem autorização por escrito. Se for atender cliente, fale com eles antes.

## O que você precisa

| O quê | Custo | Pra quê |
|---|---|---|
| Claude Code | Plano pago do Claude (Pro ou superior) | É quem roda a skill |
| Google Flights | Grátis | Preço em dinheiro |
| seats.aero | Sua própria conta. Sem login: grátis, 60 dias à frente e a Azul só em parte. Pra ver tudo: plano Pro em seu nome | Preço em milhas |
| Kiwi e Skiplagged | Grátis, opcionais | Conferem o preço em outra fonte |

Cada um desses serviços é ligado ao Claude por um servidor MCP. MCP é como uma tomada: liga o Claude a um serviço de fora.

## Instalação

Tudo acontece no Terminal, o aplicativo de comandos do Mac. Pra abrir: Command + Espaço, digite Terminal e aperte Enter. Copie um comando por vez, cole no Terminal e aperte Enter.

São três passos, mais o login do seats.aero pra quem tem conta Pro. Esse login é sempre você que faz, no seu navegador.

### Passo 1: Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Depois rode `claude` e siga o login no navegador. Pra sair do Claude Code, digite `/exit`.

### Passo 2: colocar a skill na pasta certa

Baixe o arquivo `viagem-br.skill`. Ele é um zip. Com ele na pasta Downloads, rode:

```bash
mkdir -p ~/.claude/skills && unzip -o ~/Downloads/viagem-br.skill -d ~/.claude/skills
```

### Passo 3: rodar o instalador

```bash
python3 ~/.claude/skills/viagem-br/scripts/instalar.py
```

Leva de 1 a 3 minutos. Ele confere o que a skill precisa (Node, Git e Claude Code), baixa e compila o servidor do Google Flights em `~/mcp/google-flights-mcp`, liga o Google Flights e o seats.aero no Claude Code e, no fim, chama cada um pra ver se responde. Deu certo se terminar com `Tudo certo.`

Se parar no meio, ele diz o que falta. O mais comum é o Node: baixe a versão LTS em nodejs.org, instale, abra um Terminal novo e rode o instalador de novo. Se o Mac abrir uma janela oferecendo as "ferramentas de linha de comando", aceite e espere terminar: é isso que instala o Git e o Python.

O instalador não pede senha de administrador, não apaga pasta, não faz login em nada e não mexe em servidor que você já tinha ligado com o mesmo nome. Pode rodar de novo quantas vezes quiser.

Kiwi e Skiplagged conferem o preço em outra fonte, e o Trivago busca hotel em reais. São opcionais. Pra ligar os três também:

```bash
python3 ~/.claude/skills/viagem-br/scripts/instalar.py --com-opcionais
```

### Passo 4: conecte a sua conta do seats.aero

A skill não vem com conta nem chave de ninguém: cada pessoa usa a própria. Aqui não existe caminho por chave de API, o acesso é só o login da sua conta.

Sem login, o seats.aero só enxerga os próximos 60 dias e mostra a Azul só em parte. Pra ver mais longe e a Azul inteira, a sua conta precisa do plano Pro. Confira preço e condições no site do seats.aero no dia em que for assinar, porque isso muda. Não quer assinar? Pule este passo: a skill funciona dentro desses limites e avisa o que ficou de fora.

Com o plano Pro, crie a sua conta em seats.aero, com o seu e-mail, e faça o login. Ele abre no seu navegador. Nunca passe senha ou chave sua pro Claude:

```bash
claude mcp login seats-aero
```

### Conferir quando quiser

```bash
python3 ~/.claude/skills/viagem-br/scripts/instalar.py --conferir
```

Chama cada servidor uma vez e diz o que respondeu. Não instala nada.

### Prefere fazer à mão?

O instalador roda os comandos abaixo. Se preferir, faça você, no lugar do passo 3.

Confira o Node (22.12 ou mais novo), o Git e o Python, um por vez:

```bash
node --version
```

```bash
git --version
```

```bash
python3 --version
```

Baixe e compile o servidor do Google Flights. O pacote do npm ainda entrega a versão 1.0.3, que parou de funcionar quando o Google mudou o site. A versão que funciona está no GitHub, e o comando abaixo fixa exatamente ela (conferido em 08/11/2026):

```bash
mkdir -p ~/mcp && cd ~/mcp && git clone https://github.com/andreacappelletti97/google-flights-mcp.git && cd google-flights-mcp && git checkout 9e261981b5d2893594fb0f22a21a255d1e52a884 && npm ci && npm run build
```

Deu certo se o final mostrar `Build success`. Agora ligue os dois servidores no Claude Code:

```bash
claude mcp add --scope user google-flights -- node ~/mcp/google-flights-mcp/dist/index.js
```

```bash
claude mcp add --transport http --scope user seats-aero https://seats.aero/mcp
```

Os opcionais, se quiser:

```bash
claude mcp add --transport http --scope user kiwi https://mcp.kiwi.com
```

```bash
claude mcp add --transport http --scope user skiplagged https://mcp.skiplagged.com/mcp
```

```bash
claude mcp add --transport http --scope user trivago https://mcp.trivago.com/mcp
```

E confira. Cada servidor precisa aparecer com `✔ Connected`:

```bash
claude mcp list
```

## Ajuste a sua régua

A skill já vem com médias de referência de novembro de 2026, então funciona de cara. Troque pelos seus valores, porque esse número depende de como você compra milhas. Enquanto valer a média, o resultado sai marcado `[MÉDIA DE REFERÊNCIA]`. Programa sem valor nenhum sai `[FALTA: valor da sua régua]` no lugar da comparação.

Pra ajustar, diga pro Claude "preenche minha régua do milheiro" e informe os valores. Ele grava em `~/.viagem-br/regua-milheiro.md`, um arquivo seu que fica fora da pasta da skill: atualizar a skill não mexe nele. Você pode preencher só os programas que usa, e os outros seguem na média. Quem preferir pode abrir esse arquivo num editor de texto depois que ele existir.

Dá pra gravar também o seu preço de referência, que é o que você costuma pagar por 1.000 milhas. Com ele, a skill diz quanto a emissão fica em reais, mais ou menos. O veredito não muda.

Como achar o seu número: olhe sua última compra de milhas ou seu clube e faça valor pago ÷ milhas recebidas × 1.000. Exemplo com números inventados: R$ 600 por 20.000 milhas dá R$ 30 por 1.000.

## Como usar

No Terminal, digite `claude`, aperte Enter e escreva como falaria com alguém:

- Pesquisa voo de São Paulo pra Lisboa em fevereiro de 2027, econômica, 2 adultos. Tenho Smiles e pontos na Livelo.
- Qual a data mais barata pra ir de Recife a Miami em março?
- Vale pagar executiva de Guarulhos pra Madri em abril?

Se a skill não entrar sozinha, comece o pedido com `/viagem-br`.

## Deu errado?

| O que apareceu | O que fazer |
|---|---|
| `command not found: claude` | Feche o Terminal, abra de novo e tente outra vez |
| `PAROU:` no instalador | Ele diz o que falta logo abaixo. Resolva e rode o instalador de novo |
| `Unsupported engine` ou `EBADENGINE`, instalando à mão | Seu Node é antigo. Instale a versão LTS em nodejs.org e rode o instalador |
| `destination path already exists`, instalando à mão | A pasta já existe de uma tentativa anterior. Rode o instalador, que reaproveita a pasta |
| Algum servidor com `✘` ou sem `✔ Connected` | Confira a internet e rode o instalador com `--conferir`, que diz o que falta |
| "No flight data found" ou "changed the response format" | O Google bloqueou ou mudou a página. Espere alguns minutos e peça de novo |
| `anonymous searches must use dates from` | Sem login Pro, o seats.aero só enxerga 60 dias à frente |
| A Azul não aparece nas milhas | Sem login Pro, o seats.aero esconde parte dos voos da Azul |

## Atualizar

A sua versão está no topo do arquivo `~/.claude/skills/viagem-br/MUDANCAS.md`, e a mais nova, no começo do guia de instalação. Se preferir, pergunte pro Claude "qual versão da Viagem BR eu tenho?".

Pra atualizar, baixe o arquivo novo, repita o passo 2 e rode o instalador de novo: ele só refaz o que mudou. A sua régua fica em `~/.viagem-br/` e não é tocada.

Sua pasta não tem `MUDANCAS.md`? Então a versão é anterior à 1.1.0, e a régua ficava dentro da pasta da skill. Se você preencheu, anote os valores antes de atualizar e peça pro Claude gravar de novo depois.

## Privacidade

A skill não manda nada pra quem a criou. Os valores da sua régua ficam só no seu computador, em `~/.viagem-br/`. As buscas vão pros serviços que você ligou (Google Flights, seats.aero, Kiwi, Skiplagged), e a conversa segue as regras do Claude. A skill nunca precisa da sua senha de programa, chave de API ou dado de cartão: se alguma página pedir isso pro Claude, não forneça.

## Crédito

O [Travel Hacking Toolkit](https://github.com/borski/travel-hacking-toolkit), de Michael Borohovski (licença MIT), foi o ponto de partida das fontes de conferência desta versão. É um kit de pesquisa de voos e pontos focado em cartões e programas dos Estados Unidos.

Veio de lá: a ideia de conferir o preço em mais de uma fonte gratuita (Kiwi e Skiplagged) e duas dicas sobre o seats.aero, o limite de 60 dias sem login e o cuidado com o filtro por banco. Tudo foi testado em rotas saindo do Brasil antes de entrar aqui.

Foi escrito para o Brasil: o método de pesquisa, o catálogo de armadilhas, a conta do milheiro, a régua, os scripts e a cobertura de Smiles, Azul, LATAM Pass, Livelo e Esfera.

Nenhum trecho de texto ou código foi copiado do toolkit (comparação dos arquivos feita em 08/11/2026), por isso não há trecho sob o aviso MIT nesta pasta. Se você copiar algo de lá, mantenha o aviso MIT dele.
