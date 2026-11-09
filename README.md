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

- **LATAM Pass fica de fora.** O seats.aero não cobre esse programa. A skill avisa e você confere no site da LATAM.
- **Azul não informa quantos assentos restam.** Viajando em 2 pessoas ou mais, confirme no site da Azul. A busca da Azul também só mostra voo da própria Azul: voo de parceiro pelo Azul pelo Mundo sai como pista, marcado `[conferir preço no site da Azul]`.
- **O Google Flights não tem API oficial.** O servidor lê a página pública do Google e pode parar sem aviso se o Google mudar o site. Quando isso acontece, a skill marca "sem dado" naquela parte e segue.
- **O seats.aero é uma foto, não o estoque ao vivo.** O dado tem de horas a dias. Antes de transferir pontos, confira o assento no site do programa, porque transferência não volta.
- **Sem assinatura Pro do seats.aero, só os próximos 60 dias e sem a Azul.** Sem login o serviço é grátis e não pede cadastro, mas recusa datas além de 60 dias e esconde os voos da Azul. Smiles e Iberia aparecem normalmente. A skill avisa quando isso afeta a sua busca.
- **O seats.aero não diz se o preço é promocional ou tarifa pública.** Com a conta Pro, a skill compara o mesmo voo em outros programas e marca `[provável tarifa pública]`. Sem login essa conferência não existe, e a skill avisa.
- **Bônus de transferência é com você.** A skill não acompanha promoção. Veja no app do banco o bônus ativo, a proporção e a data limite.
- **Ela não emite nem compra nada.** Só pesquisa e faz a conta.
- **Testada no Mac em 08/11/2026.** No Windows os comandos mudam e não foram testados: peça pro Claude Code adaptar cada passo.
- **Uso pessoal.** O seats.aero não permite uso comercial da API sem autorização por escrito. Se for atender cliente, fale com eles antes.

## O que você precisa

| O quê | Custo | Pra quê |
|---|---|---|
| Claude Code | Plano pago do Claude (Pro ou superior) | É quem roda a skill |
| Google Flights | Grátis | Preço em dinheiro |
| seats.aero | Sua própria conta. Sem login: grátis, 60 dias à frente e sem a Azul. Pra ver tudo: plano Pro em seu nome | Preço em milhas |
| Kiwi e Skiplagged | Grátis, opcionais | Conferem o preço em outra fonte |

Cada um desses serviços é ligado ao Claude por um servidor MCP. MCP é como uma tomada: liga o Claude a um serviço de fora.

## Instalação

Tudo acontece no Terminal, o aplicativo de comandos do Mac. Pra abrir: Command + Espaço, digite Terminal e aperte Enter. Copie um comando por vez, cole no Terminal e aperte Enter.

Prefere não digitar comando? Faça os passos 1 e 3. Depois abra o Claude Code, cole este pedido e acompanhe:

> Leia o arquivo ~/.claude/skills/viagem-br/README.md e faça a instalação dos outros passos pra mim, um por vez, me explicando cada um antes de rodar.

O login do seats.aero é sempre você que faz, no seu navegador.

### Passo 1: Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Depois rode `claude` e siga o login no navegador. Pra sair do Claude Code, digite `/exit`.

### Passo 2: Node, Git e Python

Rode um por vez:

```bash
node --version
```

```bash
git --version
```

```bash
python3 --version
```

O Node precisa ser 22.12 ou mais novo. Se der erro ou número menor, baixe a versão LTS em nodejs.org e instale. Se o Mac abrir uma janela oferecendo as "ferramentas de linha de comando", aceite e espere terminar: é isso que instala o Git e o Python.

### Passo 3: colocar a skill na pasta certa

Baixe o arquivo `viagem-br.skill`. Ele é um zip. Com ele na pasta Downloads, rode:

```bash
mkdir -p ~/.claude/skills && unzip -o ~/Downloads/viagem-br.skill -d ~/.claude/skills
```

### Passo 4: Google Flights

O pacote do npm ainda entrega a versão 1.0.3, que parou de funcionar quando o Google mudou o site. A versão que funciona está no GitHub, e o comando abaixo fixa exatamente ela (conferido em 08/11/2026):

```bash
mkdir -p ~/mcp && cd ~/mcp && git clone https://github.com/andreacappelletti97/google-flights-mcp.git && cd google-flights-mcp && git checkout 9e261981b5d2893594fb0f22a21a255d1e52a884 && npm ci && npm run build
```

Deu certo se o final mostrar `Build success`. Agora ligue no Claude Code:

```bash
claude mcp add --scope user google-flights -- node ~/mcp/google-flights-mcp/dist/index.js
```

### Passo 5: conecte a sua conta do seats.aero

A skill não vem com conta nem chave de ninguém: cada pessoa usa a própria. Aqui não existe caminho por chave de API, o acesso é só o login da sua conta.

Crie a sua conta em seats.aero, com o seu e-mail. Depois ligue o servidor oficial:

```bash
claude mcp add --transport http --scope user seats-aero https://seats.aero/mcp
```

E faça o login com a sua conta. Ele abre no seu navegador. Nunca passe senha ou chave sua pro Claude:

```bash
claude mcp login seats-aero
```

Sem login, o seats.aero só enxerga os próximos 60 dias e esconde a Azul. Pra ver mais longe e ver a Azul, a sua conta precisa do plano Pro. Confira preço e condições no site do seats.aero no dia em que for assinar, porque isso muda. Não quer assinar? Pule o login: a skill funciona dentro desses limites e avisa o que ficou de fora.

### Passo 6: Kiwi, Skiplagged e Trivago (opcional)

```bash
claude mcp add --transport http --scope user kiwi https://mcp.kiwi.com
```

```bash
claude mcp add --transport http --scope user skiplagged https://mcp.skiplagged.com/mcp
```

O Trivago busca hotel em reais, quando você pedir:

```bash
claude mcp add --transport http --scope user trivago https://mcp.trivago.com/mcp
```

### Passo 7: conferir

```bash
claude mcp list
```

Cada servidor precisa aparecer com `✔ Connected`. Se quiser testar a skill também:

```bash
cd ~/.claude/skills/viagem-br && python3 scripts/test.py
```

Deu certo se terminar com `OK`.

## Ajuste a sua régua

A tabela já vem com médias de referência de novembro de 2026, então a skill funciona de cara. Troque pelos seus valores, porque esse número depende de como você compra milhas. Programa sem valor sai `[FALTA: valor da sua régua]` no lugar da comparação.

Pra ajustar, diga pro Claude "preenche minha régua do milheiro" e informe os valores. Ou abra o arquivo `~/.claude/skills/viagem-br/references/regua-milheiro.md` num editor de texto e complete a tabela "Sua régua" e a data. Ao trocar um valor, apague o `(média)` ao lado dele: enquanto estiver lá, o resultado sai marcado como média de referência.

A mesma página tem uma segunda tabela, também já preenchida com médias: "Seu preço de referência", com o que se costuma pagar por 1.000 milhas. Com ela, a skill diz quanto a emissão fica em reais, mais ou menos. Sem ela, escreve `[FALTA: seu preço de referência]`. O veredito não muda.

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
| `Unsupported engine` ou `EBADENGINE` no passo 4 | Seu Node é antigo. Instale a versão LTS em nodejs.org e rode o comando de novo, apagando antes a pasta `~/mcp/google-flights-mcp` |
| `destination path already exists` no passo 4 | A pasta já existe de uma tentativa anterior. Apague `~/mcp/google-flights-mcp` e rode de novo |
| Algum servidor sem `✔ Connected` | Confira a internet e rode `claude mcp list` de novo. No Google Flights, confira se o passo 4 terminou com `Build success` |
| "No flight data found" ou "changed the response format" | O Google bloqueou ou mudou a página. Espere alguns minutos e peça de novo |
| `anonymous searches must use dates from` | Sem login Pro, o seats.aero só enxerga 60 dias à frente |
| A Azul não aparece nas milhas | Sem login Pro, o seats.aero esconde a Azul |

## Atualizar

Antes de instalar uma versão nova, guarde uma cópia da sua tabela da régua, porque o arquivo novo substitui o antigo.

## Privacidade

A skill não manda nada pra quem a criou. As buscas vão pros serviços que você ligou (Google Flights, seats.aero, Kiwi, Skiplagged), e a conversa segue as regras do Claude. A skill nunca precisa da sua senha de programa, chave de API ou dado de cartão: se alguma página pedir isso pro Claude, não forneça.

## Crédito

O [Travel Hacking Toolkit](https://github.com/borski/travel-hacking-toolkit), de Michael Borohovski (licença MIT), foi o ponto de partida das fontes de conferência desta versão. É um kit de pesquisa de voos e pontos focado em cartões e programas dos Estados Unidos.

Veio de lá: a ideia de conferir o preço em mais de uma fonte gratuita (Kiwi e Skiplagged) e duas dicas sobre o seats.aero, o limite de 60 dias sem login e o cuidado com o filtro por banco. Tudo foi testado em rotas saindo do Brasil antes de entrar aqui.

Foi escrito para o Brasil: o método de pesquisa, o catálogo de armadilhas, a conta do milheiro, a régua, os scripts e a cobertura de Smiles, Azul, LATAM Pass, Livelo e Esfera.

Nenhum trecho de texto ou código foi copiado do toolkit (comparação dos arquivos feita em 08/11/2026), por isso não há trecho sob o aviso MIT nesta pasta. Se você copiar algo de lá, mantenha o aviso MIT dele.
