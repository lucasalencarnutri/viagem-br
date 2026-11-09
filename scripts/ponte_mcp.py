#!/usr/bin/env python3
"""Ponte de terminal para os servidores MCP da skill (google-flights e seats-aero).

Serve a qualquer ferramenta que rode comandos no terminal, tenha ela MCP ou não:
abre o servidor, faz o handshake, chama UMA ferramenta e imprime o resultado.
Ferramenta que já tem o servidor conectado como MCP usa o nativo.

CLI: `python3 ponte_mcp.py <servidor> --lista`
     `python3 ponte_mcp.py <servidor> <ferramenta> ['<argumentos em JSON>']`
exit 0 = resultado no stdout; 1 = erro do servidor ou da ferramenta; 2 = uso errado.

Servidores:
  google-flights  o binário `google-flights-mcp` do PATH ou a pasta do README
                  (~/mcp/google-flights-mcp/dist/index.js).
  seats-aero      o MCP oficial, https://seats.aero/mcp, sem login: a ponte não
                  autentica, então só enxerga os próximos 60 dias e não mostra a
                  Azul. Pra ver tudo, use o MCP nativo com conta Pro (README).

Outro caminho de servidor: variável VIAGEM_BR_CMD_<SERVIDOR> com o comando em
lista JSON, ex.: VIAGEM_BR_CMD_GOOGLE_FLIGHTS='["/caminho/google-flights-mcp"]'.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

SERVIDORES = ("google-flights", "seats-aero")
URL_SEATS_AERO = "https://seats.aero/mcp"
TIMEOUT_S = 90
USO = ("uso: python3 ponte_mcp.py <servidor> --lista\n"
       "     python3 ponte_mcp.py <servidor> <ferramenta> ['<argumentos em JSON>']\n"
       f"servidores: {', '.join(SERVIDORES)}")
# Só o que um servidor precisa pra rodar. Chave ou senha guardada em variável de ambiente fica de fora.
AMBIENTE_PERMITIDO = ("PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TEMP", "TMP", "TZ", "LANG", "LC_ALL",
                      "LC_CTYPE", "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
                      "http_proxy", "https_proxy", "no_proxy", "PLAYWRIGHT_BROWSERS_PATH", "SYSTEMROOT", "SystemRoot",
                      "WINDIR", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "ProgramFiles", "COMSPEC",
                      "PATHEXT")
AVISO_SEM_LOGIN = (">> ponte sem login: o seats.aero só enxerga os próximos 60 dias e não "
                   "mostra a Azul. Pra ver tudo, use o MCP nativo com conta Pro.")


def comando(servidor: str):
    """(comando, env) que abre o servidor; o comando é lista (stdio) ou URL (HTTP)."""
    if servidor not in SERVIDORES:
        raise SystemExit(f"ERRO: servidor desconhecido '{servidor}'. {USO}")
    env = {nome: os.environ[nome] for nome in AMBIENTE_PERMITIDO if nome in os.environ}
    var = "VIAGEM_BR_CMD_" + servidor.upper().replace("-", "_")
    if os.environ.get(var):
        try:
            return json.loads(os.environ[var]), env
        except ValueError:
            raise SystemExit(f"ERRO: {var} precisa ser uma lista JSON, ex.: '[\"/caminho/servidor\"]'")
    if servidor == "seats-aero":
        return URL_SEATS_AERO, env
    binario = shutil.which("google-flights-mcp", path=env.get("PATH"))
    if binario:
        return [binario], env
    instalado = Path.home() / "mcp" / "google-flights-mcp" / "dist" / "index.js"
    node = shutil.which("node", path=env.get("PATH"))
    if instalado.exists() and node:
        return [node, str(instalado)], env
    raise SystemExit("ERRO: google-flights-mcp não encontrado. A instalação está no "
                     "README.md da skill, passo do Google Flights.")


class _Sessao:
    """JSON-RPC por stdio com um servidor MCP: uma mensagem por linha."""

    def __init__(self, cmd, env, timeout):
        self.timeout = timeout
        self.respostas = {}
        self.fim = False
        self.stderr = []
        self.cond = threading.Condition()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, env=env, text=True, bufsize=1)
        threading.Thread(target=self._ler_stdout, daemon=True).start()
        self._leitor_stderr = threading.Thread(target=self._ler_stderr, daemon=True)
        self._leitor_stderr.start()

    def _ler_stdout(self):
        with self.proc.stdout:
            for linha in self.proc.stdout:
                try:
                    msg = json.loads(linha)
                except ValueError:
                    continue  # log solto no stdout não é resposta
                if isinstance(msg, dict) and "id" in msg:
                    with self.cond:
                        self.respostas[msg["id"]] = msg
                        self.cond.notify_all()
        with self.cond:
            self.fim = True
            self.cond.notify_all()

    def _ler_stderr(self):
        with self.proc.stderr:
            for linha in self.proc.stderr:
                self.stderr = (self.stderr + [linha.rstrip()])[-10:]

    def _enviar(self, msg):
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError):
            pass  # servidor caiu: pedir() relata com o fim do stderr

    def pedir(self, id_, metodo, params):
        self._enviar({"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params})
        with self.cond:
            self.cond.wait_for(lambda: id_ in self.respostas or self.fim, self.timeout)
            if id_ in self.respostas:
                return self.respostas[id_]
            encerrou = self.fim
        if encerrou:
            self._leitor_stderr.join(timeout=2)  # o motivo costuma estar no fim do stderr
        motivo = "o servidor encerrou" if encerrou else f"sem resposta em {self.timeout}s"
        detalhe = " | ".join(self.stderr) or "stderr vazio"
        raise SystemExit(f"ERRO: {motivo} em '{metodo}' ({detalhe})")

    def notificar(self, metodo):
        self._enviar({"jsonrpc": "2.0", "method": metodo})

    def fechar(self):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class _SessaoHttp:
    """JSON-RPC por HTTP com um servidor MCP remoto (Streamable HTTP), sem login."""

    def __init__(self, url, timeout):
        self.url = url
        self.timeout = timeout
        self.id_sessao = None

    def _post(self, msg, metodo):
        cabecalhos = {"Content-Type": "application/json",
                      "Accept": "application/json, text/event-stream",
                      "User-Agent": "viagem-br-ponte/1"}
        if self.id_sessao:
            cabecalhos["Mcp-Session-Id"] = self.id_sessao
        pedido = urllib.request.Request(self.url, data=json.dumps(msg).encode("utf-8"),
                                        headers=cabecalhos, method="POST")
        try:
            with urllib.request.urlopen(pedido, timeout=self.timeout) as resposta:
                self.id_sessao = resposta.headers.get("Mcp-Session-Id") or self.id_sessao
                return resposta.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as erro:
            raise SystemExit(f"ERRO: {self.url} respondeu {erro.code} em '{metodo}'")
        except (urllib.error.URLError, OSError) as erro:
            raise SystemExit(f"ERRO: sem conexão com {self.url} em '{metodo}' ({erro})")

    @staticmethod
    def _mensagens(corpo):
        """A resposta vem em JSON puro ou em eventos SSE (linhas `data:`)."""
        try:
            return [json.loads(corpo)]
        except ValueError:
            pass
        mensagens = []
        for linha in corpo.splitlines():
            if linha.startswith("data:"):
                try:
                    mensagens.append(json.loads(linha[5:].strip()))
                except ValueError:
                    continue
        return mensagens

    def pedir(self, id_, metodo, params):
        corpo = self._post({"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params}, metodo)
        for msg in self._mensagens(corpo):
            if isinstance(msg, dict) and msg.get("id") == id_:
                return msg
        raise SystemExit(f"ERRO: {self.url} não devolveu resposta válida em '{metodo}'")

    def notificar(self, metodo):
        self._post({"jsonrpc": "2.0", "method": metodo}, metodo)

    def fechar(self):
        pass


def chamar(cmd, env, metodo, params=None, timeout=TIMEOUT_S) -> dict:
    """Handshake + uma requisição; devolve o `result` ou SystemExit com o erro."""
    sessao = _SessaoHttp(cmd, timeout) if isinstance(cmd, str) else _Sessao(cmd, env, timeout)
    try:
        sessao.pedir(1, "initialize", {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "viagem-br-ponte", "version": "1"}})
        sessao.notificar("notifications/initialized")
        resp = sessao.pedir(2, metodo, params or {})
    finally:
        sessao.fechar()
    if "error" in resp:
        erro = resp["error"]
        raise SystemExit(f"ERRO do servidor: {erro.get('message', erro)}")
    return resp.get("result") or {}


def texto(result: dict) -> str:
    """Conteúdo estruturado em JSON, quando existe (traz status e truncated_by);
    senão o texto da ferramenta, com imagem e afins virando marcador."""
    if result.get("structuredContent"):
        return json.dumps(result["structuredContent"], ensure_ascii=False)
    partes = []
    for item in result.get("content") or []:
        if item.get("type") == "text":
            partes.append(item.get("text", ""))
        else:
            partes.append(f"[{item.get('type', 'conteúdo')} omitido]")
    return "\n".join(partes)


def lista(result: dict) -> str:
    linhas = []
    for f in result.get("tools") or []:
        props = ", ".join((f.get("inputSchema") or {}).get("properties", {}))
        desc = " ".join((f.get("description") or "").split())[:120]
        linhas.append(f"{f['name']}({props})\n    {desc}")
    return "\n".join(linhas)


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) not in (2, 3):
        print(USO, file=sys.stderr)
        return 2
    servidor, ferramenta = args[0], args[1]
    if ferramenta != "--lista":
        try:
            argumentos = json.loads(args[2]) if len(args) == 3 else {}
        except ValueError as erro:
            print(f"argumentos não são JSON válido: {erro}\n{USO}", file=sys.stderr)
            return 2
        if not isinstance(argumentos, dict):
            print(f"argumentos precisam ser um objeto JSON ({{...}}).\n{USO}", file=sys.stderr)
            return 2
    cmd, env = comando(servidor)
    if cmd == URL_SEATS_AERO:
        print(AVISO_SEM_LOGIN, file=sys.stderr)
    if ferramenta == "--lista":
        print(lista(chamar(cmd, env, "tools/list")))
        return 0
    result = chamar(cmd, env, "tools/call", {"name": ferramenta, "arguments": argumentos})
    if result.get("isError"):
        print(texto(result), file=sys.stderr)
        return 1
    print(texto(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
