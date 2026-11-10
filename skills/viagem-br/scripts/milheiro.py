#!/usr/bin/env python3
"""Milheiro da emissão: (preço cash − taxas) ÷ milhas × 1000, contra a sua régua.

A régua vem de dois lugares, programa por programa:

  ~/.viagem-br/regua-milheiro.md   os valores que você gravou. Fica fora da pasta da skill,
                                   então atualizar a skill não mexe neles.
  references/regua-milheiro.md     as médias de referência que vêm no pacote. Valem para o
                                   programa que você não gravou e saem marcadas
                                   [MÉDIA DE REFERÊNCIA].

Programa sem valor em nenhum dos dois: calcula o milheiro e marca [FALTA: valor da sua régua].
O script lê os arquivos a cada execução e não guarda valor nenhum.

Trava de atualidade: passados 90 dias da data do valor (a sua, pros seus; a do pacote,
pras médias), ou sem data nenhuma, a comparação sai marcada com [RECONFIRMAR].

Com --estimar, só diz quanto as milhas ficam em reais, mais ou menos, pelo preço de
referência (o seu, se gravou; senão a média). Programa sem valor marca
[FALTA: seu preço de referência]. É estimativa e não muda o veredito.

Com --equilibrio, pra emissão que veio sem número (o seats.aero escondeu o preço, não
acompanha a rota ou não cobre o programa), diz até quantos pontos ela ainda passa da régua:
(preço cash − taxas) ÷ valor da régua × 1.000. É o que você compara com o site do programa.
Com --pax, preço e taxas são do grupo inteiro e o limite sai por pessoa e no total.

Em viagem de ida e volta, o lado do dinheiro é o que a emissão evita, e não o só-ida do
sentido: emitir um sentido obriga a comprar o outro em só-ida, e isso pode custar mais que
o bilhete único. No lugar de --cash entram os três preços em dinheiro (--ida-e-volta,
--so-ida e --so-volta) e o que a emissão cobre (--sentido ida, volta ou os-dois). O script
acha a compra mais barata e desconta o sentido que continua em dinheiro. Com --equilibrio e
sem --sentido, devolve os três limites de uma vez.

Com --gravar, guarda um valor seu: `regua` é o máximo que você aceita pagar por 1.000
milhas; `preco` é o que você costuma pagar.

A taxa sai do lado do dinheiro: o preço cash no Brasil já vem com a taxa de embarque
embutida. Preço, taxas e milhas entram na mesma base de passageiros: o Google devolve
o total do grupo; o seats.aero, milhas e taxa por pessoa.

Exemplos:
  milheiro.py --cash 5546 --taxas 0 --milhas 50000 --programa azul
  milheiro.py --cash "R$ 5.546,50" --taxas 2913 --milhas 50000 --programa "miles&more"
  milheiro.py --cash 5546 --taxas 2913 --milhas "50.000" --programa AZUL
  milheiro.py --estimar --milhas 70000 --taxas 245 --programa smiles
  milheiro.py --gravar regua smiles 20,50
  milheiro.py --gravar regua smiles 20,50 --gravar preco smiles 18
  milheiro.py --cash 2173 --taxas desconhecida --milhas 96000 --programa smiles
  milheiro.py --cambio USD
  milheiro.py --equilibrio --cash 4264 --taxas 288 --programa azul
  milheiro.py --equilibrio --cash 8529 --taxas desconhecida --programa azul --pax 2
  milheiro.py --ida-e-volta 11699 --so-ida 7595 --so-volta 5781 --sentido ida --milhas 390000 --taxas 576 --programa azul
  milheiro.py --equilibrio --ida-e-volta 11699 --so-ida 7595 --so-volta 5781 --taxas desconhecida --programa azul --pax 2
"""
import argparse
import json
import math
import re
import urllib.error
import urllib.request
from collections import namedtuple
from datetime import date, timedelta
from functools import partial
from pathlib import Path

ARQUIVO_REGUA = Path(__file__).resolve().parent.parent / "references" / "regua-milheiro.md"
# A régua da pessoa mora fora da pasta da skill: atualizar a skill não mexe nela.
PASTA_DO_USUARIO = Path.home() / ".viagem-br"
ARQUIVO_USUARIO = PASTA_DO_USUARIO / "regua-milheiro.md"
FALTA_REGUA = "[FALTA: valor da sua régua]"
FALTA_PRECO = "[FALTA: seu preço de referência]"
VALIDADE_DIAS = 90

_TABELA_RE = r"<!-- {nome}:inicio -->(.*?)<!-- {nome}:fim -->"
_ROTULO_DA_DATA = "Última atualização da régua (DD/MM/AAAA):"
_DATA_RE = re.compile(r"^" + re.escape(_ROTULO_DA_DATA) + r"[ \t]*(\S*)", re.MULTILINE)
_MEDIA_RE = re.compile(r"\(\s*m[eé]dia\s*\)", re.IGNORECASE)
AVISO_MEDIA = ("[MÉDIA DE REFERÊNCIA: não é o seu custo; grave o seu valor com "
               "--gravar regua <programa> <valor>.]")
TABELAS = {"regua": "valor máximo da sua régua", "preco": "seu preço de referência"}
TAXA_DESCONHECIDA = "desconhecida"
SENTIDOS = ("ida", "volta", "os-dois")
ROTULOS_DO_SENTIDO = {"ida": "só a ida em pontos", "volta": "só a volta em pontos",
                      "os-dois": "ida e volta em pontos"}
AVISO_TAXA = ("[TAXA DESCONHECIDA: calculado com taxa zero, então o milheiro real é menor que esse. "
              "Confira a taxa no checkout do programa.]")
AVISO_TAXA_EQUILIBRIO = ("[TAXA DESCONHECIDA: calculado com taxa zero, então o limite real é menor que esse. "
                         "Confira a taxa no checkout do programa.]")
PTAX_URL = ("https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
            "CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
            "?@moeda='{moeda}'&@dataInicial='{inicio}'&@dataFinalCotacao='{fim}'&$format=json"
            "&$select=cotacaoVenda,dataHoraCotacao&$filter=tipoBoletim%20eq%20'Fechamento'"
            "&$orderby=dataHoraCotacao%20desc&$top=1")

MODELO_DO_USUARIO = """# Minha régua do milheiro (Viagem BR)

Seus valores, em R$ por 1.000 milhas. Este arquivo fica fora da pasta da skill: atualizar a skill não mexe nele.

Programa que não estiver aqui usa a média de referência que vem na skill. Pra voltar à média, apague a linha do programa.

Pra gravar, diga pro Claude "preenche minha régua". Ou edite as tabelas aqui: aceita `20`, `20,50` ou `R$ 20,50`.

## Sua régua

O valor máximo que você aceita pagar por 1.000 milhas de cada programa.

<!-- regua:inicio -->
| Programa | Valor máximo (R$ por 1.000) |
|---|---|
<!-- regua:fim -->

Última atualização da régua (DD/MM/AAAA):

Passados 90 dias dessa data, o resultado pede pra reconfirmar os valores.

## Seu preço de referência

O que você costuma pagar por 1.000 milhas. Serve só pra estimar quanto a emissão fica em reais.

<!-- preco:inicio -->
| Programa | Preço de referência (R$ por 1.000) |
|---|---|
<!-- preco:fim -->
"""

# valores: chave do programa → R$ por 1.000 (só o que está preenchido)
# atualizada_em: date ou None. Com as duas camadas, é a data das médias do pacote
# medias: chaves cujo valor ainda é a média de referência que veio no pacote
# datas: chave → date dos valores que a pessoa gravou (vale no lugar de atualizada_em)
Regua = namedtuple("Regua", "valores atualizada_em medias datas", defaults=(frozenset(), None))

# nomes de exibição → chave da régua (mapa explícito, sem adivinhação:
# normalizar "LATAM Pass"→latam regra por regra criaria falsos positivos)
NOMES_DE_EXIBICAO = {
    "miles & go": "miles_go",
    "latam pass": "latam",
    "flying blue": "flying_blue",
    # códigos que o seats.aero devolve em mileage_program
    "flyingblue": "flying_blue",
    "copa": "connectmiles",
    "iberia": "avios",
    "british": "avios",
    "qatar": "avios",
    "tap": "miles_go",
    "aa": "american",
    "aadvantage": "american",
    "emirates": "skywards",
}

# ecos de ambiguidade do parse (impressos pelo main antes do resultado)
ECOS: list[str] = []


def reais_br(x: float) -> str:
    """110.93 → '110,93'; 1234.5 → '1.234,50'; -10 → '-10,00'."""
    sinal = "-" if x < 0 else ""
    inteiro, frac = f"{abs(x):.2f}".split(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    return sinal + ".".join([inteiro, *grupos]) + f",{frac}"


def numero_br(txt: str, eco_milhar: bool = False) -> float:
    """"R$ 1.234,56" → 1234.56. Vírgula é decimal e ponto é milhar quando há
    vírgula; sem vírgula, ponto seguido de exatamente 3 dígitos é milhar
    ("120.000" → 120000), o resto é decimal ("5546.5" → 5546.5). O ramo
    ambíguo do milhar registra eco quando eco_milhar (dinheiro)."""
    limpo = re.sub(r"[\s ]", "", txt.replace("R$", "").replace("r$", ""))
    if limpo.startswith("-"):
        raise argparse.ArgumentTypeError(
            f"valor negativo não faz sentido aqui: {txt!r}")
    if "," in limpo:
        inteiro, _, frac = limpo.partition(",")
        numero = f"{inteiro.replace('.', '')}.{frac.replace('.', '')}"
        numero = numero.rstrip(".")
    elif re.fullmatch(r"\d+\.\d{3}", limpo):
        numero = limpo.replace(".", "")
        if eco_milhar:
            ECOS.append(f"interpretado {txt.strip()!r} como {numero} (milhar): "
                        "se era decimal, use vírgula")
    else:
        numero = limpo
    try:
        return float(numero)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"não entendi o valor (use R$ 1.234,56 ou 1234.56): {txt!r}")


def chave_programa(programa: str) -> str:
    """"AZUL"/" Smiles " → chave em minúsculas; "LATAM Pass" etc. pelo mapa."""
    nome = programa.strip().casefold()
    return NOMES_DE_EXIBICAO.get(nome, nome)


def _data_br(txt: str):
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", txt.strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _celulas(linha: str):
    """Células de uma linha de dado da tabela; None para cabeçalho, traço e texto solto."""
    linha = linha.strip()
    if not linha.startswith("|"):
        return None
    celulas = [c.strip() for c in linha.strip("|").split("|")]
    if len(celulas) < 2 or celulas[0].casefold() == "programa" or not celulas[0].strip("-: "):
        return None
    return celulas


def _bloco(texto: str, nome: str):
    return re.search(_TABELA_RE.format(nome=nome), texto, re.DOTALL)


def _linhas_da_tabela(texto: str, nome: str) -> list:
    """Linhas de dado de uma tabela delimitada por comentários: [(programa, valor em texto)]."""
    bloco = _bloco(texto, nome)
    todas = (_celulas(linha) for linha in (bloco.group(1) if bloco else "").splitlines())
    return [(c[0], c[1]) for c in todas if c]


def _ler_tabela(texto: str, nome: str):
    """Lê uma tabela delimitada por comentários: (valores, medias).

    Valor em branco, zero ou ilegível não entra. Valor seguido de "(média)" é a média
    de referência que veio no pacote: entra nos valores e a chave vai pra `medias`."""
    valores, medias = {}, set()
    for programa, celula in _linhas_da_tabela(texto, nome):
        bruto, marcas = _MEDIA_RE.subn("", celula)
        if not bruto.strip():
            continue
        try:
            valor = numero_br(bruto)
        except argparse.ArgumentTypeError:
            ECOS.append(f"não entendi o valor de {programa} na régua: {celula!r}")
            continue
        if valor > 0:
            chave = chave_programa(programa)
            valores[chave] = valor
            if marcas:
                medias.add(chave)
    return valores, frozenset(medias)


def interpretar_regua(texto: str) -> Regua:
    """Lê a tabela da régua e a data da última atualização de um texto só."""
    data = _DATA_RE.search(texto)
    valores, medias = _ler_tabela(texto, "regua")
    return Regua(valores, _data_br(data.group(1)) if data else None, medias)


def _texto(caminho: Path, avisar: bool = True) -> str:
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError:
        if avisar:
            ECOS.append(f"não achei a régua em {caminho.name}")
        return ""


def _da_pessoa(nome: str):
    """(valores, data) que a pessoa gravou no arquivo dela, que pode não existir.

    Linha com "(média)" não é dela: quem copiou a tabela do pacote inteira não
    transforma as médias em régua própria."""
    texto = _texto(ARQUIVO_USUARIO, avisar=False)
    valores, medias = _ler_tabela(texto, nome)
    data = _DATA_RE.search(texto)
    return ({k: v for k, v in valores.items() if k not in medias},
            _data_br(data.group(1)) if data else None)


def ler_regua(caminho: Path = None) -> Regua:
    """As médias do pacote e, por cima, programa por programa, o que a pessoa gravou."""
    pacote = interpretar_regua(_texto(caminho or ARQUIVO_REGUA))
    dela, data = _da_pessoa("regua")
    if not dela:
        return pacote
    return Regua({**pacote.valores, **dela}, pacote.atualizada_em,
                 pacote.medias - set(dela), dict.fromkeys(dela, data))


def _precos(caminho: Path = None):
    """(preços, medias): os do pacote e, por cima, os que a pessoa gravou."""
    precos, medias = _ler_tabela(_texto(caminho or ARQUIVO_REGUA), "preco")
    dela, _ = _da_pessoa("preco")
    return {**precos, **dela}, medias - set(dela)


def ler_precos(caminho: Path = None) -> dict:
    """Preço de referência por programa."""
    return _precos(caminho)[0]


def taxa_br(txt: str):
    """Taxa em reais, ou "desconhecida" quando o cache não informa ("?" também vale)."""
    if txt.strip().casefold() in (TAXA_DESCONHECIDA, "?"):
        return TAXA_DESCONHECIDA
    return numero_br(txt, eco_milhar=True)


def cambio(moeda: str, hoje=None) -> str:
    """Última cotação PTAX de venda do Banco Central. Só manda o código da moeda e as datas.

    A janela volta 7 dias porque fim de semana e feriado não têm boletim."""
    codigo = moeda.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", codigo):
        raise ValueError(f"código de moeda inválido: {moeda!r} (use, por exemplo, USD, EUR ou CAD)")
    fim = hoje or date.today()
    url = PTAX_URL.format(moeda=codigo, inicio=f"{fim - timedelta(days=7):%m-%d-%Y}", fim=f"{fim:%m-%d-%Y}")
    pedido = urllib.request.Request(url, headers={"User-Agent": "viagem-br/1"})
    falta = (f"[FALTA: câmbio de {codigo}] O Banco Central não devolveu cotação agora. Sem câmbio, "
             "não calcule o milheiro de taxa cobrada nessa moeda.")
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            valores = json.loads(resposta.read().decode("utf-8")).get("value") or []
    except (urllib.error.URLError, OSError, ValueError):
        return falta
    if not valores:
        return falta
    valor = f"{valores[0]['cotacaoVenda']:.4f}".replace(".", ",")
    quando = date.fromisoformat(valores[0]["dataHoraCotacao"][:10])
    return f"{codigo}: R$ {valor} (PTAX de venda do Banco Central, fechamento de {quando:%d/%m/%Y})"


def milheiro(preco_cash: float, taxas: float, milhas: int) -> float:
    return (preco_cash - taxas) / milhas * 1000


def estimar(milhas: float, programa: str, taxas: float = None, precos: dict = None,
            medias=None) -> str:
    """Quanto a emissão fica em reais, mais ou menos, pelo preço de referência.

    `medias`: chaves cujo preço ainda é a média que veio no pacote."""
    if precos is None:
        precos, medias = _precos()
    nome = programa.strip()
    chave = chave_programa(programa)
    if chave not in precos:
        return (f"{nome}: {FALTA_PRECO} Pergunte quanto a pessoa costuma pagar e grave com "
                f"--gravar preco \"{nome}\" <valor>.")
    preco = precos[chave]
    pontos = milhas / 1000 * preco
    origem = ("estimativa pela média de referência, não pelo seu preço"
              if chave in (medias or ()) else "estimativa")
    base = (f"{nome}: as milhas ficam mais ou menos R$ {reais_br(pontos)} "
            f"(R$ {reais_br(preco)} o milheiro, {origem})")
    if taxas is None:
        return base + " [FALTA: taxas]"
    return (base + f"; com R$ {reais_br(taxas)} de taxas, mais ou menos "
            f"R$ {reais_br(pontos + taxas)} no total.")


def gravar(tabela: str, programa: str, valor: float, hoje=None) -> str:
    """Grava um valor da pessoa no arquivo dela, fora da pasta da skill, e devolve a confirmação.

    `regua` é o máximo que ela aceita pagar por 1.000 milhas e renova a data da régua;
    `preco` é o que ela costuma pagar. Cria o arquivo e a pasta se não existirem."""
    if tabela not in TABELAS:
        raise ValueError(f"tabela desconhecida: {tabela!r} (use regua ou preco)")
    if not valor > 0:
        raise ValueError("o valor precisa ser maior que zero. Pra voltar à média, apague a "
                         f"linha do programa em {ARQUIVO_USUARIO}")
    nome = programa.strip()
    chave = chave_programa(nome)
    texto = _texto(ARQUIVO_USUARIO, avisar=False) or MODELO_DO_USUARIO
    bloco = _bloco(texto, tabela)
    if bloco is None:
        raise ValueError(f"{ARQUIVO_USUARIO} está sem os marcadores da tabela '{tabela}'. "
                         "Guarde uma cópia, apague o arquivo e grave de novo.")
    linhas, gravada = [], False
    for linha in bloco.group(1).strip("\n").splitlines():
        celulas = _celulas(linha)
        if celulas and chave_programa(celulas[0]) == chave:
            if not gravada:
                nome = celulas[0]  # mantém o nome que já estava na linha
                linhas.append(f"| {nome} | {reais_br(valor)} |")
            gravada = True
        else:
            linhas.append(linha)
    if not gravada:
        linhas.append(f"| {nome} | {reais_br(valor)} |")
    novo = texto[:bloco.start(1)] + "\n" + "\n".join(linhas) + "\n" + texto[bloco.end(1):]
    if tabela == "regua":
        data = f"{_ROTULO_DA_DATA} {(hoje or date.today()):%d/%m/%Y}"
        novo, trocas = _DATA_RE.subn(data, novo, count=1)
        if not trocas:
            novo = novo.rstrip("\n") + f"\n\n{data}\n"
    ARQUIVO_USUARIO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_USUARIO.write_text(novo, encoding="utf-8")

    confirmacao = (f"Gravado em {ARQUIVO_USUARIO}: {nome}, R$ {reais_br(valor)} por 1.000 milhas "
                   f"({TABELAS[tabela]}). Atualizar a skill não mexe nesse arquivo.")
    pacote = _texto(ARQUIVO_REGUA, avisar=False)
    conhecidos = {chave_programa(p) for t in TABELAS for p, _ in _linhas_da_tabela(pacote, t)}
    if chave not in conhecidos:
        confirmacao += (f" '{nome}' não está nas tabelas do pacote: confira o nome. "
                        "Vale o código que o seats.aero usa, como united ou turkish.")
    return confirmacao


def _aviso_validade(regua: Regua, chave: str, hoje=None) -> str:
    """Trava de atualidade: sem data ou vencido, o resultado sai marcado.

    Valor que a pessoa gravou segue a data dela; média segue a data do pacote."""
    dela = regua.datas is not None and chave in regua.datas
    data = regua.datas[chave] if dela else regua.atualizada_em
    if chave in regua.medias:
        if data is None:
            return " [RECONFIRMAR: as médias de referência estão sem data.]"
        if ((hoje or date.today()) - data).days <= VALIDADE_DIAS:
            return ""
        return (f" [RECONFIRMAR: as médias de referência são de {data:%d/%m/%Y}, mais de "
                f"{VALIDADE_DIAS} dias atrás; veja se há versão nova da skill.]")
    if data is None:
        return (" [RECONFIRMAR: sua régua está sem data de atualização; "
                "confirme se o valor ainda vale.]")
    if ((hoje or date.today()) - data).days <= VALIDADE_DIAS:
        return ""
    return (f" [RECONFIRMAR: sua régua é de {data:%d/%m/%Y}, mais de "
            f"{VALIDADE_DIAS} dias atrás; confirme se o valor ainda vale.]")


def comparar(milheiro_calc: float, programa: str, regua: Regua = None, hoje=None) -> str:
    if milheiro_calc <= 0:
        return (f"R$ {reais_br(milheiro_calc)}/milheiro: as taxas igualam ou passam o preço "
                "em dinheiro. Pagar em dinheiro, as milhas não geram valor nesta emissão.")
    regua = ler_regua() if regua is None else regua
    chave = chave_programa(programa)
    nome = programa.strip()
    if chave not in regua.valores:
        return (f"R$ {reais_br(milheiro_calc)}/milheiro: {FALTA_REGUA} Sem esse valor para "
                f"{nome}, a decisão de comprar pontos fica pendente. Pergunte o valor e grave "
                f"com --gravar regua \"{nome}\" <valor>.")
    valor = regua.valores[chave]
    dif = round(milheiro_calc - valor, 2)
    pos = "igual" if dif == 0 else ("abaixo" if dif < 0 else "acima")
    if chave in regua.medias:
        ref = ("igual à" if dif == 0 else f"{pos} da") + " média de referência"
        aviso = " " + AVISO_MEDIA
    else:
        ref = ("igual ao" if dif == 0 else f"{pos} do") + " valor da sua régua"
        aviso = ""
    return (f"R$ {reais_br(milheiro_calc)}/milheiro: {ref} para {nome} "
            f"(R$ {reais_br(valor)}), diferença de R$ {reais_br(abs(dif))} por milheiro."
            f"{aviso}{_aviso_validade(regua, chave, hoje)}")


def pontos_de_equilibrio(preco_cash: float, taxas: float, valor_regua: float, pax: int = 1) -> int:
    """Até quantos pontos a emissão ainda passa da régua.

    É a conta do milheiro virada: (preço cash − taxas) ÷ valor da régua × 1.000.
    Abaixo desse número o milheiro fica acima da régua; nele ou acima, não.
    Com `pax`, preço e taxas são do grupo e o número sai por pessoa."""
    return math.floor(round((preco_cash - taxas) / valor_regua * 1000 / pax, 6))


def _milhar_br(n: int) -> str:
    return reais_br(n).split(",")[0]


def equilibrio(preco_cash: float, taxas: float, programa: str, regua: Regua = None, hoje=None,
               pax: int = 1) -> str:
    """Pra emissão sem número (preço escondido, rota não monitorada, programa fora do seats.aero):
    o que a pessoa compara com a quantidade de pontos que o site do programa pedir.

    `taxas` None = taxa desconhecida: a conta sai com zero, e o texto avisa que o limite real é menor.
    `pax` acima de 1: preço e taxas são do grupo, e o limite sai por pessoa e no total, porque o
    Google devolve o total do grupo e o site do programa pode mostrar os pontos de cada passageiro."""
    if pax < 1:
        raise ValueError("--pax precisa ser 1 ou mais")
    nome = programa.strip()
    sem_taxa = taxas is None
    taxas = 0.0 if sem_taxa else taxas
    if preco_cash - taxas <= 0:
        return (f"{nome}: as taxas (R$ {reais_br(taxas)}) igualam ou passam o preço em dinheiro "
                f"(R$ {reais_br(preco_cash)}). Pagar em dinheiro, com qualquer quantidade de pontos.")
    regua = ler_regua() if regua is None else regua
    chave = chave_programa(programa)
    if chave not in regua.valores:
        return (f"{nome}: {FALTA_REGUA} Sem esse valor não dá pra dizer até quantos pontos a emissão "
                f"compensa. Pergunte o valor e grave com --gravar regua \"{nome}\" <valor>.")
    valor = regua.valores[chave]
    total = _milhar_br(pontos_de_equilibrio(preco_cash, taxas, valor))
    if pax > 1:
        cada = _milhar_br(pontos_de_equilibrio(preco_cash, taxas, valor, pax))
        limite, corte = f"menos de {cada} pontos por pessoa ({total} no total)", f"{cada} por pessoa"
        base = f" (valores dos {pax} passageiros juntos)"
    else:
        limite, corte, base = f"menos de {total} pontos", total, ""
    if chave in regua.medias:
        ref, aviso = "da média de referência", " " + AVISO_MEDIA
    else:
        ref, aviso = "do valor da sua régua", ""
    das_taxas = ", sem contar as taxas" if sem_taxa else f" e R$ {reais_br(taxas)} de taxas"
    if sem_taxa:
        aviso += " " + AVISO_TAXA_EQUILIBRIO
    return (f"{nome}: a emissão passa {ref} (R$ {reais_br(valor)}) se pedir {limite}, "
            f"pra um preço em dinheiro de R$ {reais_br(preco_cash)}{das_taxas}{base}. "
            f"Com {corte} ou mais, o padrão é pagar em dinheiro."
            f"{aviso}{_aviso_validade(regua, chave, hoje)}")


def dinheiro_evitado(ida_e_volta: float, so_ida: float, so_volta: float, sentido: str) -> float:
    """Em ida e volta, o que a emissão tira da compra em dinheiro mais barata da viagem.

    Emitir os dois sentidos evita a compra inteira: o menor entre o bilhete único e a soma dos
    dois só-ida. Emitir um sentido só evita essa compra menos o só-ida do outro sentido, que
    continua sendo comprado. Com dois só-ida mais baratos, isso dá o próprio só-ida do sentido."""
    if sentido not in SENTIDOS:
        raise ValueError(f"sentido desconhecido: {sentido!r} (use ida, volta ou os-dois)")
    compra = min(ida_e_volta, so_ida + so_volta)
    if sentido == "os-dois":
        return compra
    return compra - (so_volta if sentido == "ida" else so_ida)


def _compra_mais_barata(ida_e_volta: float, so_ida: float, so_volta: float) -> str:
    soma = so_ida + so_volta
    if ida_e_volta < soma:
        return (f"é o ida e volta num bilhete só, R$ {reais_br(ida_e_volta)} "
                f"(os dois só-ida somam R$ {reais_br(soma)})")
    return (f"são os dois só-ida, R$ {reais_br(soma)} "
            f"(o ida e volta num bilhete só sai R$ {reais_br(ida_e_volta)})")


def _outro_sentido(sentido: str, so_ida: float, so_volta: float):
    return ("volta", so_volta) if sentido == "ida" else ("ida", so_ida)


def _nunca_compensa(sentido: str, ida_e_volta: float, so_ida: float, so_volta: float) -> str:
    outro, preco = _outro_sentido(sentido, so_ida, so_volta)
    compra = min(ida_e_volta, so_ida + so_volta)
    return (f"não compensa com nenhuma quantidade de pontos (a {outro} em só-ida, R$ {reais_br(preco)}, "
            f"custa o mesmo ou mais que a viagem inteira em dinheiro, R$ {reais_br(compra)})")


def _nota_da_viagem(ida_e_volta: float, so_ida: float, so_volta: float, sentido: str) -> str:
    """Diz de onde saiu o lado do dinheiro, pra conta poder ser refeita."""
    compra = _compra_mais_barata(ida_e_volta, so_ida, so_volta)
    if sentido == "os-dois":
        evitado = dinheiro_evitado(ida_e_volta, so_ida, so_volta, sentido)
        return (f"[IDA E VOLTA: a compra em dinheiro mais barata {compra}. Emitindo os dois sentidos, a "
                f"emissão evita os R$ {reais_br(evitado)} inteiros; milhas e taxas são a soma dos dois sentidos.]")
    outro, preco = _outro_sentido(sentido, so_ida, so_volta)
    evitado = dinheiro_evitado(ida_e_volta, so_ida, so_volta, sentido)
    proprio = so_ida if sentido == "ida" else so_volta
    return (f"[IDA E VOLTA: a compra em dinheiro mais barata {compra}. Emitindo só a {sentido}, a {outro} "
            f"continua em dinheiro, em só-ida (R$ {reais_br(preco)}): a emissão evita R$ {reais_br(evitado)}. "
            f"Se a {outro} também for em milhas, a conta desta {sentido} muda: refaça contra o só-ida dela, "
            f"com --cash {reais_br(proprio)}.]")


def equilibrio_ida_e_volta(ida_e_volta: float, so_ida: float, so_volta: float, programa: str,
                           regua: Regua = None, hoje=None, pax: int = 1, sentido: str = None,
                           taxas: float = None) -> str:
    """Ponto de equilíbrio da viagem de ida e volta: até quantos pontos cada construção em milhas
    ainda ganha da compra em dinheiro mais barata.

    Sem `sentido`, devolve os três limites (só a ida, só a volta, os dois juntos).
    `taxas` só entra com um `sentido`; None = desconhecida, e o texto avisa que o limite real é menor."""
    if pax < 1:
        raise ValueError("--pax precisa ser 1 ou mais")
    if sentido is None and taxas is not None:
        raise ValueError("sem --sentido o equilíbrio devolve os três limites e não sabe de qual sentido é a "
                         "taxa: passe --taxas desconhecida, ou rode um sentido por vez com a taxa dele")
    nome = programa.strip()
    regua = ler_regua() if regua is None else regua
    chave = chave_programa(programa)
    if chave not in regua.valores:
        return (f"{nome}: {FALTA_REGUA} Sem esse valor não dá pra dizer até quantos pontos a emissão "
                f"compensa. Pergunte o valor e grave com --gravar regua \"{nome}\" <valor>.")
    valor = regua.valores[chave]
    if chave in regua.medias:
        ref, aviso = "da média de referência", " " + AVISO_MEDIA
    else:
        ref, aviso = "do valor da sua régua", ""
    sem_taxa = taxas is None
    desconto = 0.0 if sem_taxa else taxas
    linhas = []
    for s in (SENTIDOS if sentido is None else (sentido,)):
        rotulo = ROTULOS_DO_SENTIDO[s]
        evitado = dinheiro_evitado(ida_e_volta, so_ida, so_volta, s)
        if evitado <= 0:
            linhas.append(f"- {rotulo}: {_nunca_compensa(s, ida_e_volta, so_ida, so_volta)}")
            continue
        if evitado - desconto <= 0:
            linhas.append(f"- {rotulo}: as taxas (R$ {reais_br(desconto)}) igualam ou passam o que a emissão "
                          f"evita (R$ {reais_br(evitado)}): pagar em dinheiro")
            continue
        quanto = f"{_milhar_br(pontos_de_equilibrio(evitado, desconto, valor))} pontos"
        if pax > 1:
            cada = _milhar_br(pontos_de_equilibrio(evitado, desconto, valor, pax))
            quanto = f"{cada} pontos por pessoa ({quanto.split()[0]} no total)"
        if s == "os-dois":
            linhas.append(f"- {rotulo}: a soma dos dois sentidos menor que {quanto}")
        else:
            outro, preco = _outro_sentido(s, so_ida, so_volta)
            linhas.append(f"- {rotulo} (a {outro} continua em dinheiro, R$ {reais_br(preco)} em só-ida): "
                          f"menos de {quanto}")
    das_taxas = "sem as taxas" if sem_taxa else f"com R$ {reais_br(taxas)} de taxas"
    if pax > 1:
        das_taxas = f"com os preços em dinheiro dos {pax} passageiros juntos, {das_taxas}"
    if sem_taxa:
        aviso += " " + AVISO_TAXA_EQUILIBRIO
    return (f"{nome}, ida e volta: a compra em dinheiro mais barata "
            f"{_compra_mais_barata(ida_e_volta, so_ida, so_volta)}. "
            f"A emissão passa {ref} (R$ {reais_br(valor)}) se pedir:\n" + "\n".join(linhas)
            + f"\nNesses números ou acima, o padrão é pagar em dinheiro. Conta feita {das_taxas}."
            f"{aviso}{_aviso_validade(regua, chave, hoje)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cash", type=partial(numero_br, eco_milhar=True),
                   help="preço em dinheiro da mesma rota/cabine/datas, na mesma base de "
                        "passageiros de --milhas e --taxas (aceita R$ 1.234,56)")
    p.add_argument("--taxas", type=taxa_br,
                   help="taxas de emissão em R$ (aceita R$ 1.234,56), ou a palavra desconhecida "
                        "quando o cache não informa")
    p.add_argument("--milhas", type=numero_br,
                   help="milhas exigidas na emissão (50.000 → 50000)")
    p.add_argument("--programa",
                   help="programa que emite (seu valor, se gravou; senão a média do pacote)")
    p.add_argument("--estimar", action="store_true",
                   help="só diz quanto as milhas ficam em reais, pelo preço de referência")
    p.add_argument("--gravar", nargs=3, action="append", metavar=("TABELA", "PROGRAMA", "VALOR"),
                   help="guarda um valor seu em ~/.viagem-br/regua-milheiro.md. TABELA é regua "
                        "(máximo que aceita pagar) ou preco (o que costuma pagar). Pode repetir")
    p.add_argument("--equilibrio", action="store_true",
                   help="pra emissão sem número: diz até quantos pontos ela ainda passa da régua "
                        "(pede --cash, --taxas e --programa; não usa --milhas)")
    p.add_argument("--pax", type=int,
                   help="só com --equilibrio: quantos passageiros o --cash e o --taxas cobrem; "
                        "o limite sai por pessoa e no total")
    preco_br = partial(numero_br, eco_milhar=True)
    p.add_argument("--ida-e-volta", type=preco_br, metavar="R$",
                   help="viagem de ida e volta: preço em dinheiro do bilhete de ida e volta. Vai com "
                        "--so-ida e --so-volta, no lugar de --cash")
    p.add_argument("--so-ida", type=preco_br, metavar="R$",
                   help="viagem de ida e volta: só-ida em dinheiro da ida")
    p.add_argument("--so-volta", type=preco_br, metavar="R$",
                   help="viagem de ida e volta: só-ida em dinheiro da volta")
    p.add_argument("--sentido", choices=SENTIDOS,
                   help="viagem de ida e volta: o que a emissão cobre. Em os-dois, milhas e taxas "
                        "são a soma dos dois sentidos")
    p.add_argument("--cambio", metavar="MOEDA",
                   help="última cotação PTAX do Banco Central da moeda (USD, EUR, CAD...)")
    a = p.parse_args()
    if a.pax is not None and not a.equilibrio:
        p.error("--pax só vale com --equilibrio. No cálculo do milheiro, --cash, --taxas e --milhas "
                "já entram na mesma base de passageiros")
    viagem = (a.ida_e_volta, a.so_ida, a.so_volta)
    tem_viagem = any(preco is not None for preco in viagem)
    if tem_viagem:
        if None in viagem:
            p.error("--ida-e-volta, --so-ida e --so-volta andam juntos: são os três preços em dinheiro "
                    "da viagem")
        if a.cash is not None:
            p.error("com os três preços da viagem não passe --cash: o script acha a compra mais barata e "
                    "desconta o sentido que continua em dinheiro")
        if min(viagem) <= 0:
            p.error("os três preços da viagem precisam ser maiores que zero")
        if a.estimar or a.gravar or a.cambio:
            p.error("--ida-e-volta, --so-ida e --so-volta só valem no cálculo do milheiro e no --equilibrio")
    elif a.sentido:
        p.error("--sentido pede --ida-e-volta, --so-ida e --so-volta")
    if a.cambio:
        try:
            print(cambio(a.cambio))
        except ValueError as erro:
            p.error(str(erro))
        return
    if a.gravar:
        for tabela, programa, valor in a.gravar:
            try:
                print(gravar(tabela, programa, numero_br(valor)))
            except (ValueError, argparse.ArgumentTypeError) as erro:
                p.error(str(erro))
            except OSError as erro:
                p.error(f"não consegui gravar em {ARQUIVO_USUARIO}: {erro}")
        return
    if a.equilibrio:
        if a.taxas is None or a.programa is None or (a.cash is None and not tem_viagem):
            p.error("--equilibrio pede --cash, --taxas e --programa "
                    "(em ida e volta, os três preços da viagem no lugar de --cash)")
        taxas = None if a.taxas == TAXA_DESCONHECIDA else a.taxas
        pax = 1 if a.pax is None else a.pax
        try:
            if tem_viagem:
                resultado = equilibrio_ida_e_volta(*viagem, a.programa, pax=pax, sentido=a.sentido, taxas=taxas)
            else:
                resultado = equilibrio(a.cash, taxas, a.programa, pax=pax)
        except ValueError as erro:
            p.error(str(erro))
        for eco in ECOS:
            print(eco)
        print(resultado)
        return
    if a.milhas is None or a.programa is None:
        p.error("--milhas e --programa são obrigatórios (ou use --gravar, --equilibrio ou --cambio)")
    desconhecida = a.taxas == TAXA_DESCONHECIDA
    if a.estimar:
        resultado = estimar(a.milhas, a.programa, None if desconhecida else a.taxas)
    else:
        if a.taxas is None or (a.cash is None and not tem_viagem):
            p.error("--cash e --taxas são obrigatórios fora do modo --estimar "
                    "(em ida e volta, os três preços da viagem no lugar de --cash)")
        if a.milhas == 0:
            p.error("--milhas 0 não divide: conferir o valor")
        taxas = 0.0 if desconhecida else a.taxas
        if tem_viagem:
            if a.sentido is None:
                p.error("em ida e volta diga o que a emissão cobre: --sentido ida, volta ou os-dois")
            evitado = dinheiro_evitado(*viagem, a.sentido)
            if evitado <= 0:
                resultado = f"Emitir só a {a.sentido} {_nunca_compensa(a.sentido, *viagem)}. Pagar em dinheiro."
                desconhecida = False
            else:
                resultado = (comparar(milheiro(evitado, taxas, a.milhas), a.programa)
                             + " " + _nota_da_viagem(*viagem, a.sentido))
        else:
            resultado = comparar(milheiro(a.cash, taxas, a.milhas), a.programa)
        if desconhecida:
            resultado += " " + AVISO_TAXA
    for eco in ECOS:
        print(eco)
    print(resultado)


if __name__ == "__main__":
    main()
