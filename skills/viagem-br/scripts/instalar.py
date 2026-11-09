#!/usr/bin/env python3
"""Instalador da Viagem BR: prepara o que a skill precisa e confere se responde.

  python3 instalar.py                  instala o servidor do Google Flights e liga, no Claude
                                       Code, os dois servidores de que a skill precisa.
  python3 instalar.py --com-opcionais  liga também Kiwi, Skiplagged e Trivago.
  python3 instalar.py --conferir       só confere se está tudo respondendo. Não instala nada.

O que ele faz, nesta ordem:
  1. confere Node 22.12 ou mais novo, npm, Git e Claude Code. Faltou algum, para e diz o
     que instalar;
  2. baixa o servidor do Google Flights em ~/mcp/google-flights-mcp, no commit fixado, e compila;
  3. liga google-flights e seats-aero no Claude Code (claude mcp add --scope user). Com a
     Viagem BR instalada como plugin, o plugin já liga o seats-aero, e aqui entra só o
     google-flights;
  4. chama cada servidor uma vez e diz o que respondeu.

Funciona de qualquer pasta: a do plugin ou ~/.claude/skills/viagem-br, pra quem instalou
pelo arquivo .skill.

O que ele nunca faz: instalar o Node, pedir senha de administrador, apagar pasta, fazer o
login do seats.aero ou mexer num servidor que você já tinha ligado com o mesmo nome.
Pode rodar de novo: o que já está pronto ele pula.

exit 0 = tudo certo; 1 = faltou alguma coisa, e o texto diz o quê.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import ponte_mcp

REPO_GF = "https://github.com/andreacappelletti97/google-flights-mcp.git"
# Versão 1.1.0 do servidor. O npm seguia na 1.0.3, que parou quando o Google fechou o
# endpoint antigo. Trocar o commit é decisão consciente (SKILL.md, Pré-requisito).
COMMIT_GF = "9e261981b5d2893594fb0f22a21a255d1e52a884"
NODE_MINIMO = (22, 12)
URL_SEATS = "https://seats.aero/mcp"
OPCIONAIS = {"kiwi": "https://mcp.kiwi.com", "skiplagged": "https://mcp.skiplagged.com/mcp",
             "trivago": "https://mcp.trivago.com/mcp"}
PASTA_GF = Path.home() / "mcp" / "google-flights-mcp"
# Instalada como plugin do Claude Code, é o plugin que liga estes servidores (.mcp.json na
# raiz dele). O google-flights fica de fora: precisa ser compilado no computador da pessoa.
PLUGIN = "viagem-br"
SERVIDORES_DO_PLUGIN = ("seats-aero",)
COMO_INSTALAR = {
    "node": "Node 22.12 ou mais novo: baixe a versão LTS em nodejs.org e instale.",
    "npm": "npm: vem junto com o Node (nodejs.org).",
    "git": "Git: no Mac, rode `xcode-select --install` e aceite a instalação. No Windows, git-scm.com.",
    "claude": "Claude Code: faça o passo 1 do README.md da skill.",
}
RODE_O_INSTALADOR = "Rode `python3 scripts/instalar.py`, de dentro da pasta da skill."


class Parar(Exception):
    """Não dá pra seguir. A mensagem diz o que a pessoa precisa fazer."""


def _rodar(cmd, cwd=None):
    """Roda um comando sem terminal e sem perguntar nada: (código de saída, texto)."""
    try:
        feito = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, errors="replace",
                               env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except OSError as erro:
        return 1, str(erro)
    return feito.returncode, feito.stdout or ""


def _fim(texto: str, linhas: int = 15) -> str:
    """O fim da saída de um comando que falhou, que é onde o motivo costuma estar."""
    return "\n".join(f"    {linha}" for linha in texto.strip().splitlines()[-linhas:])


def _sem_git(url: str) -> str:
    url = url.strip().rstrip("/").casefold()
    return url[:-len(".git")] if url.endswith(".git") else url


def nome_no_plugin(nome: str) -> str:
    """Nome com que o Claude Code mostra um servidor que vem do plugin."""
    return f"plugin:{PLUGIN}:{nome}"


class Instalador:
    def __init__(self, rodar=None, achar=None, chamar=None, pasta_gf=None, dizer=print):
        self.rodar = rodar or _rodar
        self.achar = achar or shutil.which
        self.chamar = chamar or ponte_mcp.chamar
        self.pasta_gf = Path(pasta_gf or PASTA_GF)
        self.dizer = dizer
        self.nome_do_seats = "seats-aero"  # nome que vale no login; conferir() troca se vier do plugin

    # ---- instalar ----

    def instalar(self, opcionais: bool = False) -> int:
        try:
            self.dizer("[1/4] Conferindo Node, npm, Git e Claude Code ...")
            self._ferramentas()
            self.dizer("[2/4] Servidor do Google Flights ...")
            self._google_flights()
            self.dizer("[3/4] Ligando os servidores no Claude Code ...")
            self._ligar("google-flights", ["--scope", "user", "google-flights", "--", "node",
                                           str(self.pasta_gf / "dist" / "index.js")])
            self._ligar("seats-aero", ["--transport", "http", "--scope", "user", "seats-aero", URL_SEATS])
            if opcionais:
                for nome, url in OPCIONAIS.items():
                    self._ligar(nome, ["--transport", "http", "--scope", "user", nome, url])
        except Parar as motivo:
            self.dizer(f"\nPAROU: {motivo}")
            return 1
        self.dizer("[4/4] Conferindo se respondem ...")
        codigo = self.conferir()
        if codigo == 0:
            self.dizer("\nPróximos passos:\n"
                       "  - Tem assinatura Pro do seats.aero? Faça o login no Terminal, que abre no seu navegador:\n"
                       f"      claude mcp login {self.nome_do_seats}\n"
                       "    Sem login a skill funciona, só com os próximos 60 dias.\n"
                       "  - O Claude Code estava aberto? Feche e abra de novo: ele só enxerga servidor\n"
                       "    novo quando abre.\n"
                       "  - Pra usar: digite claude no Terminal e peça, por exemplo,\n"
                       "    \"pesquisa voo de São Paulo pra Lisboa em fevereiro, econômica, 2 adultos\".")
        return codigo

    def _exigir(self, cmd, o_que: str, cwd=None) -> str:
        codigo, saida = self.rodar(cmd, cwd)
        if codigo != 0:
            raise Parar(f"{o_que} não deu certo. O fim do que o comando respondeu:\n{_fim(saida)}")
        return saida

    def _ferramentas(self) -> None:
        faltas = [como for nome, como in COMO_INSTALAR.items() if not self.achar(nome)]
        node = self.achar("node")
        if node:
            _, saida = self.rodar([node, "--version"])
            versao = re.search(r"v?(\d+)\.(\d+)", saida)
            if not versao or (int(versao.group(1)), int(versao.group(2))) < NODE_MINIMO:
                faltas.insert(0, f"O seu Node é o {saida.strip() or 'de versão desconhecida'}, e o "
                                 "servidor do Google Flights precisa do 22.12 ou mais novo: baixe a "
                                 "versão LTS em nodejs.org e instale.")
        if faltas:
            raise Parar("falta instalar antes de continuar:\n"
                        + "\n".join(f"  - {falta}" for falta in faltas)
                        + "\nDepois abra um Terminal novo e rode este instalador de novo.")

    def _google_flights(self) -> None:
        git, npm, pasta = self.achar("git"), self.achar("npm"), self.pasta_gf
        indice = pasta / "dist" / "index.js"
        mudou = False
        if not pasta.exists():
            self.dizer(f"  Baixando em {pasta} ...")
            pasta.parent.mkdir(parents=True, exist_ok=True)
            self._exigir([git, "clone", "--quiet", REPO_GF, str(pasta)], "Baixar o servidor do Google Flights")
            mudou = True
        else:
            codigo, remoto = self.rodar([git, "-C", str(pasta), "remote", "get-url", "origin"])
            if codigo != 0 or _sem_git(remoto) != _sem_git(REPO_GF):
                raise Parar(f"a pasta {pasta} já existe e não é o servidor do Google Flights desta "
                            "skill. Não mexi nela. Mude o nome dela ou apague, e rode o instalador de novo.")
        atual = self._exigir([git, "-C", str(pasta), "rev-parse", "HEAD"], "Ler a versão do servidor").strip()
        if atual != COMMIT_GF:
            codigo, _ = self.rodar([git, "-C", str(pasta), "checkout", "--quiet", COMMIT_GF])
            if codigo != 0:  # clone antigo, de antes desse commit existir
                self._exigir([git, "-C", str(pasta), "fetch", "--quiet", "origin"],
                             "Buscar a versão fixada do servidor")
                self._exigir([git, "-C", str(pasta), "checkout", "--quiet", COMMIT_GF],
                             "Voltar o servidor pra versão fixada")
            mudou = True
        if not mudou and indice.exists():
            self.dizer("  Já estava pronto: não baixei nem compilei de novo.")
            return
        self.dizer("  Compilando. Leva de 1 a 3 minutos ...")
        self._exigir([npm, "ci"], "Instalar as dependências do servidor (npm ci)", cwd=pasta)
        self._exigir([npm, "run", "build"], "Compilar o servidor (npm run build)", cwd=pasta)
        if not indice.exists():
            raise Parar(f"a compilação terminou sem criar {indice}. Rode o instalador de novo; se "
                        "repetir, siga o passo a passo manual do README.md.")
        self.dizer("  Pronto.")

    def _ligado(self, nome: str):
        """(nome que vale no Claude Code, o que ele respondeu), ou (None, "") se não está ligado.

        Servidor que a pessoa ligou vem antes: quando ela e o plugin apontam pro mesmo endereço,
        o Claude Code usa o dela e esconde o do plugin (visto na versão 2.1.309).
        """
        claude = self.achar("claude")
        nomes = [nome] + ([nome_no_plugin(nome)] if nome in SERVIDORES_DO_PLUGIN else [])
        for candidato in nomes:
            codigo, saida = self.rodar([claude, "mcp", "get", candidato])
            if codigo == 0:
                return candidato, saida
        return None, ""

    def _ligar(self, nome: str, argumentos: list) -> None:
        ligado, _ = self._ligado(nome)
        if ligado == nome:
            self.dizer(f"  {nome}: já estava ligado no Claude Code, não mexi.")
        elif ligado:  # ligar de novo passaria por cima do plugin e do login feito nele
            self.dizer(f"  {nome}: o plugin da Viagem BR já liga, não liguei de novo.")
        else:
            self._exigir([self.achar("claude"), "mcp", "add", *argumentos], f"Ligar o {nome} no Claude Code")
            self.dizer(f"  {nome}: ligado.")

    # ---- conferir ----

    def conferir(self) -> int:
        """Chama cada servidor uma vez e olha como o Claude Code os enxerga. Não instala nada."""
        tudo_certo = True
        node, indice = self.achar("node"), self.pasta_gf / "dist" / "index.js"
        if not node or not indice.exists():
            tudo_certo = False
            self.dizer(f"  ✘ Google Flights: o servidor não está instalado em {self.pasta_gf}. {RODE_O_INSTALADOR}")
        else:
            erro = self._perguntar([node, str(indice)], "lookup_airport", {"query": "Lisbon"})
            if erro:
                tudo_certo = False
                self.dizer(f"  ✘ Google Flights: o servidor não respondeu ({erro}). {RODE_O_INSTALADOR}")
            else:
                self.dizer("  ✔ Google Flights: o servidor abriu e respondeu. A busca de preço "
                           "ainda depende de o Google não bloquear no dia.")
        erro = self._perguntar(URL_SEATS, "get_capabilities", {})
        if erro:
            tudo_certo = False
            self.dizer(f"  ✘ seats.aero: {URL_SEATS} não respondeu ({erro}). Confira a internet e tente de novo.")
        else:
            self.dizer("  ✔ seats.aero: respondeu. Este teste é sem login; com conta Pro, o login "
                       "é pelo Claude Code.")
        claude = self.achar("claude")
        for nome in ("google-flights", "seats-aero"):
            if not claude:
                tudo_certo = False
                self.dizer(f"  ✘ {nome} no Claude Code: não achei o Claude Code. {COMO_INSTALAR['claude']}")
                continue
            ligado, saida = self._ligado(nome)
            if not ligado:
                tudo_certo = False
                self.dizer(f"  ✘ {nome} no Claude Code: não está ligado. {RODE_O_INSTALADOR}")
                continue
            if nome == "seats-aero":
                self.nome_do_seats = ligado
            como = "ligado" if ligado == nome else "ligado pelo plugin"
            estado = re.search(r"Status:\s*(.+)", saida)
            estado = estado.group(1).strip() if estado else "sem estado informado"
            if "Failed" in estado or "✘" in estado:
                tudo_certo = False
                self.dizer(f"  ✘ {nome} no Claude Code: {como}, mas sem conexão ({estado}).")
            elif "Connected" in estado:
                self.dizer(f"  ✔ {nome} no Claude Code: {como} e conectado.")
            else:
                self.dizer(f"  ! {nome} no Claude Code: {como}, estado \"{estado}\". Confira com `claude mcp list`.")
        self.dizer("\nTudo certo." if tudo_certo else "\nFalta resolver o que está marcado com ✘.")
        return 0 if tudo_certo else 1

    def _perguntar(self, cmd, ferramenta: str, argumentos: dict) -> str:
        """Uma chamada de ferramenta direto ao servidor. Devolve o erro, ou vazio se respondeu."""
        env = None
        if isinstance(cmd, list):  # servidor aberto aqui na máquina recebe só o ambiente de que precisa
            env = {nome: os.environ[nome] for nome in ponte_mcp.AMBIENTE_PERMITIDO if nome in os.environ}
        try:
            resposta = self.chamar(cmd, env, "tools/call", {"name": ferramenta, "arguments": argumentos},
                                   timeout=60)
        except SystemExit as erro:
            return str(erro) or "sem resposta"
        if resposta.get("isError"):
            return ponte_mcp.texto(resposta)[:300] or "a ferramenta devolveu erro"
        return ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--com-opcionais", action="store_true",
                   help="liga também Kiwi, Skiplagged e Trivago (conferência de preço e hotel)")
    p.add_argument("--conferir", action="store_true",
                   help="só confere se os servidores respondem; não instala nada")
    a = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # terminal que não conhece ✔ e ✘ troca o símbolo e segue
        sys.stdout.reconfigure(errors="replace")
    instalador = Instalador()
    return instalador.conferir() if a.conferir else instalador.instalar(opcionais=a.com_opcionais)


if __name__ == "__main__":
    raise SystemExit(main())
