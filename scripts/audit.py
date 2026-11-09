#!/usr/bin/env python3
"""Auditoria mecânica da SAÍDA de uma pesquisa completa (skill viagem-br).

Checa: seções na ordem AVISOS → TABELA → VEREDITO → MILHAS → PRÓXIMOS PASSOS;
linha `>>` nos AVISOS; as 4 células da matriz (dinheiro/milhas × econômica/executiva)
com piso · densidade ou marcador de vazio; `[FALTA:` do cabeçalho casado com os AVISOS;
chave de API exposta (pro_...).
Com --recorte (só um pedaço do método), exige AVISOS e VEREDITO e confere só as células que aparecem.
Confere formato, não se o número está certo.
CLI: `python3 audit.py [--recorte] <arquivo.md>`. Exit 0 libera; exit 1 lista uma violação por linha.
"""
import re
import sys

SECOES = ["AVISOS", "TABELA", "VEREDITO", "MILHAS", "PRÓXIMOS PASSOS"]
_SECAO_RE = {n: re.compile(rf"^##\s+{n}\b", re.MULTILINE) for n in SECOES}
_PROXIMO_HEADER_RE = re.compile(r"^##\s", re.MULTILINE)

CELULAS = ["dinheiro × econômica", "dinheiro × executiva",
           "milhas × econômica", "milhas × executiva"]
_PISO_DINHEIRO_RE = re.compile(r"R\$\s*[\d.,]+\s*·\s*\d+")
_PISO_MILHAS_RE = re.compile(r"[\d.,]+\s*(?:k|mil)\s+(?:milhas|pontos|avios)[^\n]*·\s*\d+", re.IGNORECASE)
_MARCADOR_VAZIO = ("sem estoque no cache", "sem voo", "sem dado: ferramenta bloqueada",
                   "sem dado: seats.aero sem login", "não pesquisada: rota doméstica",
                   "sem dado: programa fora do seats.aero", "preço alto, escondido pelo seats.aero",
                   "sem dado: rota não monitorada pelo seats.aero")
_FALTA_RE = re.compile(r"\[FALTA:[^\]]+\]")
_CHAVE_RE = re.compile(r"pro_[A-Za-z0-9]{20,}")


def _secao(texto: str, nome: str) -> str:
    """Texto da seção `nome`: do título até o próximo título de nível 2 (ou o fim)."""
    ini = _SECAO_RE[nome].search(texto)
    if ini is None:
        return ""
    fim = _PROXIMO_HEADER_RE.search(texto, ini.end())
    return texto[ini.start():fim.start() if fim else len(texto)]


def _celula_re(rotulo: str) -> re.Pattern:
    a, b = rotulo.split("×")
    return re.compile(re.escape(a.strip()) + r"\s*×\s*" + re.escape(b.strip()))


def auditar(texto: str, recorte: bool = False) -> list[str]:
    """Devolve a lista de violações (vazia = SAÍDA conforme o formato da skill)."""
    viol = []

    # (1) seções presentes e na ordem AVISOS → TABELA → VEREDITO → MILHAS → PRÓXIMOS PASSOS
    pos = {}
    for nome in SECOES:
        m = _SECAO_RE[nome].search(texto)
        if m is None:
            if not recorte or nome in ("AVISOS", "VEREDITO"):
                viol.append(f"seção {nome} ausente")
        else:
            pos[nome] = m.start()
    esperadas = [n for n in SECOES if n in pos]
    observadas = sorted(pos, key=pos.get)
    if observadas != esperadas:
        for esp, vista in zip(esperadas, observadas):
            if esp != vista:
                viol.append(f"ordem das seções violada: {vista} aparece antes de {esp} "
                            f"(ordem correta: {' → '.join(SECOES)})")
                break

    # (2) AVISOS com pelo menos uma linha ">>"
    avisos = _secao(texto, "AVISOS") if "AVISOS" in pos else None
    if avisos is not None and not any(
            l.lstrip().startswith(">>") for l in avisos.splitlines()):
        viol.append("AVISOS sem linha '>>'")

    # (3)+(4)+(5) as 4 células da TABELA, cada uma com piso · densidade ou marcador de vazio
    if "TABELA" in pos:
        linhas = _secao(texto, "TABELA").splitlines()
        for rotulo in CELULAS:
            rx = _celula_re(rotulo)
            da_celula = [l for l in linhas if rx.search(l)]
            if not da_celula:
                if not recorte:
                    viol.append(f"célula ausente na TABELA: {rotulo} "
                                "(a matriz completa exige as 4 células)")
            elif not any(_PISO_DINHEIRO_RE.search(l) or _PISO_MILHAS_RE.search(l)
                         or any(marc in l for marc in _MARCADOR_VAZIO)
                         for l in da_celula):
                viol.append(f"célula '{rotulo}' sem piso · densidade "
                            "(exige 'R$ N · N', 'Nk milhas · N' ou marcador de vazio)")

    # (6) [FALTA: declarado no cabeçalho precisa de linha correspondente nos AVISOS
    primeiro_header = _PROXIMO_HEADER_RE.search(texto)
    header = texto[:primeiro_header.start()] if primeiro_header else texto
    if avisos is not None:
        for falta in dict.fromkeys(_FALTA_RE.findall(header)):
            if falta not in avisos:
                viol.append(f"cabeçalho declara {falta} sem linha correspondente nos AVISOS")

    # (7) chave de API exposta: nunca entra em arquivo nem em resposta
    if _CHAVE_RE.search(texto):
        viol.append("chave de API exposta (padrão pro_...): remova do texto")

    return viol


def main() -> None:
    args = sys.argv[1:]
    recorte = "--recorte" in args
    args = [a for a in args if a != "--recorte"]
    if len(args) != 1:
        print("uso: python3 audit.py [--recorte] <arquivo.md>", file=sys.stderr)
        raise SystemExit(2)
    try:
        with open(args[0], encoding="utf-8") as f:
            texto = f.read()
    except OSError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        raise SystemExit(2)
    viol = auditar(texto, recorte=recorte)
    for v in viol:
        print(v)
    raise SystemExit(1 if viol else 0)


if __name__ == "__main__":
    main()
