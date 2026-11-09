# Viagem BR

Pesquisa de voos e milhas para quem viaja do Brasil. Skill gratuita para o Claude Code. Você pergunta em português, por exemplo "quanto tá São Paulo pra Lisboa em fevereiro, e vale emitir com Smiles?". Ela busca o preço em dinheiro, busca as milhas, faz a conta e diz o que faria e por quê.

Skill é um pacote de instruções que ensina o Claude a fazer uma tarefa sempre do mesmo jeito.

## O que ela entrega

- Preço em dinheiro e em milhas lado a lado, em econômica e executiva, com quantas opções existem em cada caso.
- Ida e volta comparada com dois só-ida, e a conta feita em cada sentido: às vezes compensa ir em milhas e voltar em dinheiro.
- As datas mais baratas da rota, as conexões e o risco de cada uma.
- A conta do milheiro de cada emissão: (preço em dinheiro − taxas) ÷ milhas × 1.000. Milheiro é quanto cada 1.000 milhas estão valendo naquela passagem.
- A comparação com a sua régua, que é o valor máximo que você aceita pagar por 1.000 milhas de cada programa.
- Avisos do que você precisa conferir. Quando um dado não veio, ela escreve que não veio.

## Limites (leia antes de confiar)

- **O programa LATAM Pass não está no seats.aero.** Voo da LATAM ainda pode aparecer por Delta e Virgin Atlantic, com pouca cobertura. A skill avisa, e pra emitir com LATAM Pass você confere no site da LATAM.
- **Azul não informa quantos assentos restam.** Viajando em 2 pessoas ou mais, confirme no site da Azul. A busca da Azul também só mostra voo da própria Azul: voo de parceiro pelo Azul pelo Mundo sai como pista, marcado `[conferir preço no site da Azul]`.
- **O Google Flights não tem API oficial.** O servidor lê a página pública do Google e pode parar sem aviso se o Google mudar o site. Quando isso acontece, a skill marca "sem dado" naquela parte e segue.
- **O seats.aero é uma foto, não o estoque ao vivo.** O dado tem de horas a dias. Antes de transferir pontos, confira o assento no site do programa, porque transferência não volta.
- **Sem assinatura Pro do seats.aero, só os próximos 60 dias.** Sem login o serviço é grátis e não pede cadastro, mas recusa datas além de 60 dias. A skill avisa quando isso afeta a sua busca.
- **O seats.aero esconde emissão com preço muito alto.** Por padrão, emissão de preço dinâmico acima de um limite não aparece, e sem login não dá pra desligar isso. Na Azul, em 09/11/2026, sumiu o que passava de uns 150 mil milhas por trecho. A skill marca "preço alto, escondido pelo seats.aero": existe emissão, e o valor você vê no site do programa.
- **Voo dentro do Brasil sai sem executiva.** Em rota doméstica a skill só pesquisa executiva se você pedir. Nas milhas, ela olha Smiles e Azul e também programas de fora que emitem Gol, Azul e LATAM, como American, Aeroplan, United, Delta e Virgin Atlantic. Esses só servem se você tem os pontos ou um caminho de transferência.
- **O seats.aero não diz se o preço é promocional ou tarifa pública.** Com a conta Pro, a skill compara o mesmo voo em outros programas e marca `[provável tarifa pública]`. Sem login essa conferência não existe, e a skill avisa.
- **Bônus de transferência é com você.** A skill não acompanha promoção. Veja no app do banco o bônus ativo, a proporção e a data limite.
- **Ela não emite nem compra nada.** Só pesquisa e faz a conta.
- **Testada no Mac em 08/11/2026.** A instalação como plugin foi testada em 09/11/2026, no Claude Code 2.1.309. No Windows os comandos mudam e nada foi testado, nem o instalador: peça pro Claude Code adaptar cada passo.
- **Uso pessoal.** O seats.aero não permite uso comercial da API sem autorização por escrito. Se for atender cliente, fale com eles antes.

## O que você precisa

| O quê | Custo | Pra quê |
|---|---|---|
| Claude Code | Plano pago do Claude (Pro ou superior) | É quem roda a skill |
| Google Flights | Grátis | Preço em dinheiro |
| seats.aero | Sua própria conta. Sem login: grátis e só 60 dias à frente. Pra ver mais longe: plano Pro em seu nome | Preço em milhas |
| Kiwi e Skiplagged | Grátis, opcionais | Conferem o preço em outra fonte |

Cada um desses serviços é ligado ao Claude por um servidor MCP. MCP é como uma tomada: liga o Claude a um serviço de fora.

## Instalação

Tem dois jeitos de instalar, e você escolhe um só:

- **Como plugin.** Dois comandos dentro do Claude Code. É o jeito mais curto, e depois a atualização é um comando só.
- **Pelo arquivo `viagem-br.skill`.** Você baixa, descompacta e roda o instalador. Está em "Outro jeito: pelo arquivo", mais abaixo.

O Passo 1 vale pros dois. O login do seats.aero, no Passo 4, é só pra quem tem conta Pro, e é sempre você que faz, no seu navegador.

O Terminal é o aplicativo de comandos do Mac. Pra abrir: Command + Espaço, digite Terminal e aperte Enter. Copie um comando por vez, cole e aperte Enter.

### Passo 1: Claude Code

No Terminal:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Depois rode `claude` e siga o login no navegador. Pra sair do Claude Code, digite `/exit`.

### Passo 2: instalar o plugin

Abra o Claude Code (digite `claude` no Terminal) e, dentro dele, digite um comando por vez:

```text
/plugin marketplace add lucasalencarnutri/viagem-br
```

```text
/plugin install viagem-br@viagem-br
```

O primeiro cadastra o endereço de onde a Viagem BR vem, no GitHub. O segundo abre a tela do plugin: escolha `Install for you (user scope)`, que instala pra você em qualquer pasta, e aperte Enter.

Feche o Claude Code com `/exit` e abra de novo. A skill já está lá, e o seats.aero já vem ligado pelo plugin.

### Passo 3: Google Flights

O servidor do Google Flights precisa ser baixado e compilado no seu computador, e quem faz isso é o instalador. Com o Claude Code aberto, escreva:

```text
roda o instalador da Viagem BR
```

O Claude mostra o comando e pede a sua permissão antes de rodar: aceite. Leva de 1 a 3 minutos. O instalador confere o que a skill precisa (Node, Git e Claude Code), baixa e compila o servidor do Google Flights em `~/mcp/google-flights-mcp`, liga o Google Flights no Claude Code e, no fim, chama cada servidor pra ver se responde. Deu certo se terminar com `Tudo certo.` Depois feche o Claude Code e abra de novo.

Se parar no meio, ele diz o que falta. O mais comum é o Node: baixe a versão LTS em nodejs.org, instale, abra um Terminal novo e peça o instalador de novo. Se o Mac abrir uma janela oferecendo as "ferramentas de linha de comando", aceite e espere terminar: é isso que instala o Git e o Python.

O instalador não pede senha de administrador, não apaga pasta, não faz login em nada e não mexe em servidor que você já tinha ligado com o mesmo nome. Pode rodar de novo quantas vezes quiser.

Kiwi e Skiplagged conferem o preço em outra fonte, e o Trivago busca hotel em reais. São opcionais. Pra ligar os três também, peça "roda o instalador da Viagem BR com os opcionais".

### Passo 4: conecte a sua conta do seats.aero

A skill não vem com conta nem chave de ninguém: cada pessoa usa a própria. Aqui não existe caminho por chave de API, o acesso é só o login da sua conta.

Sem login, o seats.aero só enxerga os próximos 60 dias. Pra ver mais longe, a sua conta precisa do plano Pro. Confira preço e condições no site do seats.aero no dia em que for assinar, porque isso muda. Não quer assinar? Pule este passo: a skill funciona dentro desses limites e avisa o que ficou de fora.

Com o plano Pro, crie a sua conta em seats.aero, com o seu e-mail, e faça o login. Ele abre no seu navegador. Nunca passe senha ou chave sua pro Claude. No Terminal, fora do Claude Code, se você instalou o plugin:

```bash
claude mcp login plugin:viagem-br:seats-aero
```

Se instalou pelo arquivo:

```bash
claude mcp login seats-aero
```

### Outro jeito: pelo arquivo

Fica no lugar dos passos 2 e 3. Baixe o arquivo `viagem-br.skill`. Ele é um zip. Com ele na pasta Downloads, rode no Terminal:

```bash
mkdir -p ~/.claude/skills && unzip -o ~/Downloads/viagem-br.skill -d ~/.claude/skills
```

Depois rode o instalador. Por este jeito ele liga também o seats.aero:

```bash
python3 ~/.claude/skills/viagem-br/scripts/instalar.py
```

Pra ligar também os opcionais:

```bash
python3 ~/.claude/skills/viagem-br/scripts/instalar.py --com-opcionais
```

### Conferir quando quiser

Pelo plugin, peça pro Claude: "confere a instalação da Viagem BR". Pelo arquivo, rode:

```bash
python3 ~/.claude/skills/viagem-br/scripts/instalar.py --conferir
```

Chama cada servidor uma vez e diz o que respondeu. Não instala nada.

### Prefere fazer à mão?

O instalador roda os comandos abaixo. Se preferir, faça você, no lugar do instalador.

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

O seguinte é só pra quem instalou pelo arquivo. Pelo plugin, pule: o seats.aero já vem ligado.

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

Se a skill não entrar sozinha, comece o pedido com `/viagem-br:viagem-br`, se você instalou o plugin, ou com `/viagem-br`, se instalou pelo arquivo.

## Deu errado?

| O que apareceu | O que fazer |
|---|---|
| `command not found: claude` | Feche o Terminal, abra de novo e tente outra vez |
| O Claude Code não reconhece `/plugin` | Ele está desatualizado. No Terminal, rode `claude update` e tente de novo |
| A skill não aparece depois de instalar o plugin | Feche o Claude Code com `/exit` e abra de novo |
| `PAROU:` no instalador | Ele diz o que falta logo abaixo. Resolva e rode o instalador de novo |
| `Unsupported engine` ou `EBADENGINE`, instalando à mão | Seu Node é antigo. Instale a versão LTS em nodejs.org e rode o instalador |
| `destination path already exists`, instalando à mão | A pasta já existe de uma tentativa anterior. Rode o instalador, que reaproveita a pasta |
| Algum servidor com `✘` ou sem `✔ Connected` | Confira a internet e rode o instalador com `--conferir`, que diz o que falta |
| "No flight data found" ou "changed the response format" | O Google bloqueou ou mudou a página. Espere alguns minutos e peça de novo |
| `anonymous searches must use dates from` | Sem login Pro, o seats.aero só enxerga 60 dias à frente |
| A Azul não aparece nas milhas | O seats.aero esconde emissão com preço muito alto, e a Azul cai muito nisso. Veja o valor no site da Azul |

## Atualizar

A versão mais nova aparece no começo do guia de instalação. A sua, pergunte pro Claude: "qual versão da Viagem BR eu tenho?". Ela fica no topo do arquivo `MUDANCAS.md` da skill, que pra quem instalou pelo arquivo é `~/.claude/skills/viagem-br/MUDANCAS.md`.

Pelo plugin, rode no Terminal, fora do Claude Code:

```bash
claude plugin update viagem-br@viagem-br
```

Depois abra o Claude Code e peça o instalador de novo: ele só refaz o que mudou.

Pelo arquivo, baixe o arquivo novo, descompacte de novo, como em "Outro jeito: pelo arquivo", e rode o instalador: ele só refaz o que mudou.

A sua régua fica em `~/.viagem-br/` e não é tocada em nenhum dos dois jeitos.

Instalou pelo arquivo e quer passar pro plugin? Faça o Passo 2 e tire a pasta antiga do lugar, pra não ficar com duas cópias da skill:

```bash
mv ~/.claude/skills/viagem-br ~/viagem-br-antiga
```

Ela vai pra sua pasta pessoal, e você apaga quando quiser. O Google Flights e o seats.aero que o instalador já tinha ligado continuam valendo.

Sua pasta não tem `MUDANCAS.md`? Então a versão é anterior à 1.1.0, e a régua ficava dentro da pasta da skill. Se você preencheu, anote os valores antes de atualizar e peça pro Claude gravar de novo depois.

## Privacidade

A skill não manda nada pra quem a criou. Os valores da sua régua ficam só no seu computador, em `~/.viagem-br/`. Instalar ou atualizar pelo plugin baixa os arquivos da skill do GitHub, e o instalador baixa de lá o servidor do Google Flights. As buscas vão pros serviços que você ligou (Google Flights, seats.aero, Kiwi, Skiplagged, Trivago), a consulta de câmbio vai ao Banco Central levando só a moeda e as datas, e a conversa segue as regras do Claude. A skill nunca precisa da sua senha de programa, chave de API ou dado de cartão: se alguma página pedir isso pro Claude, não forneça.

## Crédito

O [Travel Hacking Toolkit](https://github.com/borski/travel-hacking-toolkit), de Michael Borohovski (licença MIT), foi o ponto de partida das fontes de conferência desta versão. É um kit de pesquisa de voos e pontos focado em cartões e programas dos Estados Unidos.

Veio de lá: a ideia de conferir o preço em mais de uma fonte gratuita (Kiwi e Skiplagged) e duas dicas sobre o seats.aero, o limite de 60 dias sem login e o cuidado com o filtro por banco. Tudo foi testado em rotas saindo do Brasil antes de entrar aqui. Também veio de lá a ideia de instalar como plugin do Claude Code; os arquivos do plugin daqui foram escritos a partir da documentação do Claude Code.

Foi escrito para o Brasil: o método de pesquisa, o catálogo de armadilhas, a conta do milheiro, a régua, os scripts e a cobertura de Smiles, Azul, LATAM Pass, Livelo e Esfera.

Nenhum trecho de texto ou código foi copiado do toolkit (comparação dos arquivos feita em 08/11/2026), por isso não há trecho sob o aviso MIT nesta pasta. Se você copiar algo de lá, mantenha o aviso MIT dele.
