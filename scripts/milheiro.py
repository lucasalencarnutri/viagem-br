#!/usr/bin/env python3
"""Milheiro da emissão: (preço cash − taxas) ÷ milhas × 1000, contra a régua que você preencheu.

A régua mora na tabela "Sua régua" de references/regua-milheiro.md: R$ por 1.000 milhas,
valor máximo por programa. Este script lê a tabela a cada execução e não guarda valor nenhum.

  programa com valor na tabela     compara contra esse valor.
  valor seguido de "(média)"       é a média de referência que veio no pacote: compara e
                                   marca [MÉDIA DE REFERÊNCIA]. Trocou pelo seu, apague o "(média)".
  programa sem valor ou fora dela  calcula o milheiro e marca [FALTA: valor da sua régua].

Trava de atualidade: passados 90 dias da data informada na régua, ou sem data nenhuma,
a comparação sai marcada com [RECONFIRMAR].

Com --estimar, só diz quanto as milhas ficam em reais, mais ou menos, pelo preço que você
preencheu na tabela "Seu preço de referência" do mesmo arquivo. Programa sem valor marca
[FALTA: seu preço de referência]. É estimativa e não muda o veredito.

A taxa sai do lado do dinheiro: o preço cash no Brasil já vem com a taxa de embarque
embutida. Preço, taxas e milhas entram na mesma base de passageiros: o Google devolve
o total do grupo; o seats.aero, milhas e taxa por pessoa.

Exemplos:
  milheiro.py --cash 5546 --taxas 0 --milhas 50000 --programa azul
  milheiro.py --cash "R$ 5.546,50" --taxas 2913 --milhas 50000 --programa "miles&more"
  milheiro.py --cash 5546 --taxas 2913 --milhas "50.000" --programa AZUL
  milheiro.py --estimar --milhas 70000 --taxas 245 --programa smiles
"""
import argparse
import re
from collections import namedtuple
from datetime import date
from functools import partial
from pathlib import Path

ARQUIVO_REGUA = Path(__file__).resolve().parent.parent / "references" / "regua-milheiro.md"
FALTA_REGUA = "[FALTA: valor da sua régua]"
FALTA_PRECO = "[FALTA: seu preço de referência]"
VALIDADE_DIAS = 90

_TABELA_RE = r"<!-- {nome}:inicio -->(.*?)<!-- {nome}:fim -->"
_DATA_RE = re.compile(r"^Última atualização da régua \(DD/MM/AAAA\):[ \t]*(\S*)", re.MULTILINE)
_MEDIA_RE = re.compile(r"\(\s*m[eé]dia\s*\)", re.IGNORECASE)
AVISO_MEDIA = ("[MÉDIA DE REFERÊNCIA: não é o seu custo; troque pelo seu valor em "
               "references/regua-milheiro.md.]")

# valores: chave do programa → R$ por 1.000 (só o que está preenchido)
# atualizada_em: date ou None
# medias: chaves cujo valor ainda é a média de referência que veio no pacote
Regua = namedtuple("Regua", "valores atualizada_em medias", defaults=(frozenset(),))

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
    limpo = re.sub(r"[\s ]", "", txt.replace("R$", "").replace("r$", ""))
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


def _ler_tabela(texto: str, nome: str):
    """Lê uma tabela delimitada por comentários: (valores, medias).

    Valor em branco, zero ou ilegível não entra. Valor seguido de "(média)" é a média
    de referência que veio no pacote: entra nos valores e a chave vai pra `medias`."""
    valores, medias = {}, set()
    bloco = re.search(_TABELA_RE.format(nome=nome), texto, re.DOTALL)
    for linha in (bloco.group(1) if bloco else "").splitlines():
        linha = linha.strip()
        if not linha.startswith("|"):
            continue
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        if len(celulas) < 2 or celulas[0].casefold() == "programa" or not celulas[0].strip("-: "):
            continue
        bruto, marcas = _MEDIA_RE.subn("", celulas[1])
        if not bruto.strip():
            continue
        try:
            valor = numero_br(bruto)
        except argparse.ArgumentTypeError:
            ECOS.append(f"não entendi o valor de {celulas[0]} na régua: {celulas[1]!r}")
            continue
        if valor > 0:
            chave = chave_programa(celulas[0])
            valores[chave] = valor
            if marcas:
                medias.add(chave)
    return valores, frozenset(medias)


def interpretar_regua(texto: str) -> Regua:
    """Lê a tabela "Sua régua" e a data da última atualização."""
    data = _DATA_RE.search(texto)
    valores, medias = _ler_tabela(texto, "regua")
    return Regua(valores, _data_br(data.group(1)) if data else None, medias)


def _texto_da_regua(caminho: Path = None) -> str:
    caminho = caminho or ARQUIVO_REGUA
    try:
        return caminho.read_text(encoding="utf-8")
    except OSError:
        ECOS.append(f"não achei a régua em {caminho.name}")
        return ""


def ler_regua(caminho: Path = None) -> Regua:
    return interpretar_regua(_texto_da_regua(caminho))


def ler_precos(caminho: Path = None) -> dict:
    """Lê a tabela "Seu preço de referência"."""
    return _ler_tabela(_texto_da_regua(caminho), "preco")[0]


def milheiro(preco_cash: float, taxas: float, milhas: int) -> float:
    return (preco_cash - taxas) / milhas * 1000


def estimar(milhas: float, programa: str, taxas: float = None, precos: dict = None,
            medias=None) -> str:
    """Quanto a emissão fica em reais, mais ou menos, pelo preço da tabela.

    `medias`: chaves cujo preço ainda é a média que veio no pacote."""
    if precos is None:
        precos, medias = _ler_tabela(_texto_da_regua(), "preco")
    nome = programa.strip()
    chave = chave_programa(programa)
    if chave not in precos:
        return (f"{nome}: {FALTA_PRECO} Preencha a tabela \"Seu preço de referência\" em "
                "references/regua-milheiro.md.")
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


def _aviso_validade(regua: Regua, hoje=None) -> str:
    """Trava de atualidade da régua: sem data ou vencida, o resultado sai marcado."""
    if regua.atualizada_em is None:
        return (" [RECONFIRMAR: sua régua está sem data de atualização; "
                "confirme se o valor ainda vale.]")
    if ((hoje or date.today()) - regua.atualizada_em).days <= VALIDADE_DIAS:
        return ""
    return (f" [RECONFIRMAR: sua régua é de {regua.atualizada_em:%d/%m/%Y}, mais de "
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
                f"{nome}, a decisão de comprar pontos fica pendente. Preencha a tabela em "
                "references/regua-milheiro.md.")
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
            f"{aviso}{_aviso_validade(regua, hoje)}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cash", type=partial(numero_br, eco_milhar=True),
                   help="preço em dinheiro da mesma rota/cabine/datas, na mesma base de "
                        "passageiros de --milhas e --taxas (aceita R$ 1.234,56)")
    p.add_argument("--taxas", type=partial(numero_br, eco_milhar=True),
                   help="taxas de emissão em R$ (aceita R$ 1.234,56)")
    p.add_argument("--milhas", type=numero_br, required=True,
                   help="milhas exigidas na emissão (50.000 → 50000)")
    p.add_argument("--programa", required=True,
                   help="programa que emite (o valor vem de references/regua-milheiro.md)")
    p.add_argument("--estimar", action="store_true",
                   help="só diz quanto as milhas ficam em reais, pelo seu preço de referência")
    a = p.parse_args()
    if a.estimar:
        resultado = estimar(a.milhas, a.programa, a.taxas)
    else:
        if a.cash is None or a.taxas is None:
            p.error("--cash e --taxas são obrigatórios fora do modo --estimar")
        if a.milhas == 0:
            p.error("--milhas 0 não divide: conferir o valor")
        resultado = comparar(milheiro(a.cash, a.taxas, a.milhas), a.programa)
    for eco in ECOS:
        print(eco)
    print(resultado)


if __name__ == "__main__":
    main()
