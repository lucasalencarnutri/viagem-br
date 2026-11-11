"""Testes da skill. Rode de dentro da pasta da skill: python3 scripts/test.py

Não precisam de rede, chave, conta ou servidor instalado.
"""
import argparse
import contextlib
import http.server
import io
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import audit
import instalar
import milheiro as modulo_milheiro
import ponte_mcp
from milheiro import (ECOS, FALTA_PRECO, FALTA_REGUA, Regua, comparar, estimar, gravar, interpretar_regua,
                      ler_precos, ler_regua, milheiro, numero_br, reais_br)

PASTA = Path(__file__).resolve().parent.parent
EXEMPLO = PASTA / "exemplo" / "pesquisa-exemplo.md"

# Dentro do plugin, esta pasta é <raiz do plugin>/skills/viagem-br. Instalada pelo arquivo
# .skill, não há plugin em volta, e os testes que olham os arquivos do plugin são pulados.
RAIZ_DO_PLUGIN = PASTA.parent.parent
MANIFESTO_DO_PLUGIN = RAIZ_DO_PLUGIN / ".claude-plugin" / "plugin.json"
TEM_PLUGIN = PASTA.parent.name == "skills" and MANIFESTO_DO_PLUGIN.exists()

# Régua inventada, só pra exercitar a comparação nos testes.
HOJE = date(2026, 11, 8)
REGUA_TESTE = Regua({"azul": 20.0, "smiles": 25.0, "latam": 30.0, "avios": 40.0, "miles_go": 42.0,
                     "flying_blue": 50.0, "connectmiles": 55.0}, HOJE)

# Os testes nunca leem nem gravam a régua real de quem roda: o arquivo da pessoa
# aponta pra um lugar que não existe, e só TestReguaDaPessoa troca por uma pasta temporária.
_SEM_REGUA_PROPRIA = mock.patch.object(
    modulo_milheiro, "ARQUIVO_USUARIO",
    Path(tempfile.gettempdir()) / "viagem-br-teste-sem-regua" / "regua-milheiro.md")


def setUpModule():
    _SEM_REGUA_PROPRIA.start()


def tearDownModule():
    _SEM_REGUA_PROPRIA.stop()


# Servidor MCP falso (stdio): sem node, sem rede e sem chave.
SERVIDOR_FALSO = r'''
import json, sys
for linha in sys.stdin:
    msg = json.loads(linha)
    if "id" not in msg:
        continue
    metodo = msg["method"]
    if metodo == "initialize":
        res = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
               "serverInfo": {"name": "falso", "version": "0"}}
    elif metodo == "tools/list":
        res = {"tools": [{"name": "eco", "description": "Devolve o texto.",
                          "inputSchema": {"type": "object",
                                          "properties": {"texto": {"type": "string"}}}}]}
    elif metodo == "tools/call" and msg["params"]["name"] == "eco":
        print("log solto no stdout")
        res = {"content": [{"type": "text", "text": msg["params"]["arguments"]["texto"]},
                           {"type": "image", "data": "x"}]}
    elif metodo == "tools/call":
        res = {"content": [{"type": "text", "text": "ferramenta falhou"}], "isError": True}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                          "error": {"code": -32601, "message": "método desconhecido"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": res}), flush=True)
'''


class TestMilheiro(unittest.TestCase):
    def test_calculo_com_taxa(self):
        # a taxa sai do lado do dinheiro: (8900 - 350) / 148000 * 1000
        self.assertAlmostEqual(milheiro(8900, 350, 148000), 57.77027027, places=5)

    def test_taxa_maior_piora_o_milheiro(self):
        # mesma tarifa e mesmas milhas: quanto mais taxa, menos a emissão entrega
        self.assertLess(milheiro(8000, 2000, 100000), milheiro(8000, 200, 100000))

    def test_somar_a_taxa_inverteria_o_veredito(self):
        # (8057 − 1929,16) ÷ 125.000 × 1.000 = 49,02, abaixo de uma régua de 60.
        # Somando a taxa daria 79,89 e o veredito sairia invertido.
        calc = milheiro(8057, 1929.16, 125000)
        self.assertAlmostEqual(calc, 49.02, places=2)
        regua = Regua({"avios": 60.0}, HOJE)
        self.assertIn("abaixo", comparar(calc, "avios", regua, HOJE))

    def test_taxa_igual_ou_maior_que_o_preco(self):
        for calc in (milheiro(1000, 1500, 50000), milheiro(1000, 1000, 50000)):
            with self.subTest(calc=calc):
                self.assertLessEqual(calc, 0)
                self.assertIn("Pagar em dinheiro", comparar(calc, "azul", REGUA_TESTE, HOJE))
                self.assertIn("Pagar em dinheiro", comparar(calc, "miles&more", REGUA_TESTE, HOJE))

    def test_calculo_sem_taxa(self):
        self.assertAlmostEqual(milheiro(743, 0, 12000), 61.91666666, places=5)

    def test_milhas_zero_erro(self):
        with self.assertRaises(ZeroDivisionError):
            milheiro(100, 10, 0)

    def test_comparar_abaixo(self):
        self.assertIn("abaixo", comparar(10.0, "azul", REGUA_TESTE, HOJE))

    def test_comparar_acima(self):
        self.assertIn("acima", comparar(70.0, "smiles", REGUA_TESTE, HOJE))

    def test_comparar_igual_nao_sai_acima(self):
        # a régua trata IGUAL como ABAIXO: comprar pontos não compensa
        res = comparar(20.0, "azul", REGUA_TESTE, HOJE)
        self.assertIn("igual ao", res)
        self.assertNotIn("acima", res)

    def test_programa_sem_valor_marca_falta(self):
        self.assertEqual(FALTA_REGUA, "[FALTA: valor da sua régua]")
        res = comparar(50.0, "miles&more", REGUA_TESTE, HOJE)
        self.assertIn(FALTA_REGUA, res)
        self.assertIn("R$ 50,00/milheiro", res)

    def test_regua_em_branco_marca_falta_em_todo_programa(self):
        vazia = Regua({}, None)
        for programa in ("azul", "smiles", "LATAM Pass", "avios"):
            with self.subTest(programa=programa):
                self.assertIn(FALTA_REGUA, comparar(30.0, programa, vazia, HOJE))


class TestLeituraDaRegua(unittest.TestCase):
    MODELO = ("<!-- regua:inicio -->\n| Programa | Valor |\n|---|---|\n{linhas}\n<!-- regua:fim -->\n\n"
              "Última atualização da régua (DD/MM/AAAA): {data}\n")

    def regua(self, linhas, data=""):
        return interpretar_regua(self.MODELO.format(linhas=linhas, data=data))

    def test_le_valor_com_e_sem_prefixo(self):
        r = self.regua("| Azul | 20 |\n| Smiles | R$ 25,50 |\n| Avios | 40.5 |")
        self.assertEqual(r.valores, {"azul": 20.0, "smiles": 25.5, "avios": 40.5})

    def test_linha_em_branco_fica_de_fora(self):
        self.assertEqual(self.regua("| Azul | |\n| Smiles | 25 |").valores, {"smiles": 25.0})

    def test_zero_fica_de_fora(self):
        self.assertEqual(self.regua("| Azul | 0 |").valores, {})

    def test_valor_ilegivel_fica_de_fora_e_avisa(self):
        ECOS.clear()
        self.assertEqual(self.regua("| Azul | quinze |").valores, {})
        self.assertTrue(any("Azul" in e for e in ECOS))
        ECOS.clear()

    def test_nome_de_exibicao_vira_chave(self):
        r = self.regua("| LATAM Pass | 30 |\n| Miles & Go | 42 |\n| Flying Blue | 50 |")
        self.assertEqual(sorted(r.valores), ["flying_blue", "latam", "miles_go"])

    def test_linha_nova_com_programa_fora_da_lista(self):
        r = self.regua("| United | 60 |")
        self.assertNotIn(FALTA_REGUA, comparar(90.0, "united", r, HOJE))

    def test_data_da_regua(self):
        self.assertEqual(self.regua("| Azul | 20 |", "28/08/2026").atualizada_em, date(2026, 8, 28))

    def test_data_em_branco_ou_invalida(self):
        self.assertIsNone(self.regua("| Azul | 20 |").atualizada_em)
        self.assertIsNone(self.regua("| Azul | 20 |", "31/02/2026").atualizada_em)

    def test_arquivo_ausente_nao_derruba(self):
        ECOS.clear()
        self.assertEqual(ler_regua(PASTA / "nao-existe.md"), Regua({}, None))
        ECOS.clear()

    def test_regua_vem_com_medias_de_referencia(self):
        v = ler_regua().valores
        esperado = {"azul": 14, "smiles": 16, "latam": 25, "avios": 56, "miles_go": 35,
                    "suma": 61.32, "aeroplan": 70, "flying_blue": 75, "aegean": 68, "jal": 84}
        self.assertEqual(v, esperado)  # Lifemiles e Connectmiles ficam sem valor

    def test_data_das_medias(self):
        self.assertEqual(ler_regua().atualizada_em, date(2026, 11, 8))

    def test_valor_com_media_entra_e_fica_marcado(self):
        r = self.regua("| Smiles | 16 (média) |\n| Azul | R$ 20,50 |")
        self.assertEqual(r.valores, {"smiles": 16.0, "azul": 20.5})
        self.assertEqual(set(r.medias), {"smiles"})

    def test_regua_de_fabrica_vem_toda_marcada_como_media(self):
        r = ler_regua()
        self.assertEqual(set(r.medias), set(r.valores))


class TestMediaDeReferencia(unittest.TestCase):
    # smiles ainda é média de fábrica; azul já é valor da pessoa
    REGUA = Regua({"smiles": 16.0, "azul": 20.0, "avios": 56.0}, HOJE, frozenset({"smiles", "avios"}))

    def test_media_nao_sai_como_sua_regua(self):
        res = comparar(55.6, "smiles", self.REGUA, HOJE)
        self.assertIn("acima da média de referência para smiles (R$ 16,00)", res)
        self.assertIn("[MÉDIA DE REFERÊNCIA", res)
        self.assertNotIn("sua régua", res)

    def test_valor_proprio_segue_como_sua_regua(self):
        res = comparar(25.0, "azul", self.REGUA, HOJE)
        self.assertIn("acima do valor da sua régua para azul (R$ 20,00)", res)
        self.assertNotIn("MÉDIA DE REFERÊNCIA", res)

    def test_codigo_do_seats_aero_herda_a_marca(self):
        self.assertIn("[MÉDIA DE REFERÊNCIA", comparar(78.0, "iberia", self.REGUA, HOJE))

    def test_estimativa_com_media_avisa(self):
        res = estimar(70000, "smiles", 380, {"smiles": 16.0}, {"smiles"})
        self.assertIn("média de referência", res)
        self.assertIn("R$ 1.500,00", res)

    def test_estimativa_com_preco_proprio_nao_avisa(self):
        self.assertNotIn("média de referência", estimar(70000, "smiles", 380, {"smiles": 16.0}))


class TestReguaDaPessoa(unittest.TestCase):
    """A régua da pessoa mora fora da pasta da skill e vale por cima das médias do pacote."""

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.arq = Path(td.name) / "ainda-nao-existe" / "regua-milheiro.md"
        troca_arquivo = mock.patch.object(modulo_milheiro, "ARQUIVO_USUARIO", self.arq)
        troca_arquivo.start()
        self.addCleanup(troca_arquivo.stop)
        ECOS.clear()
        self.addCleanup(ECOS.clear)

    def escrever(self, linhas_regua="", data="", linhas_preco=""):
        self.arq.parent.mkdir(parents=True, exist_ok=True)
        self.arq.write_text(
            f"<!-- regua:inicio -->\n| Programa | Valor |\n|---|---|\n{linhas_regua}\n<!-- regua:fim -->\n\n"
            f"Última atualização da régua (DD/MM/AAAA): {data}\n\n"
            f"<!-- preco:inicio -->\n| Programa | Preço |\n|---|---|\n{linhas_preco}\n<!-- preco:fim -->\n",
            encoding="utf-8")

    def test_lugar_padrao_fica_fora_da_pasta_da_skill(self):
        self.assertEqual(modulo_milheiro.PASTA_DO_USUARIO, Path.home() / ".viagem-br")
        self.assertNotIn(PASTA, modulo_milheiro.PASTA_DO_USUARIO.parents)

    def test_sem_arquivo_da_pessoa_valem_as_medias(self):
        r = ler_regua()
        self.assertEqual(r.valores["smiles"], 16)
        self.assertIn("smiles", r.medias)

    def test_gravar_cria_o_arquivo_e_a_pasta(self):
        gravar("regua", "smiles", 20.5, hoje=HOJE)
        self.assertTrue(self.arq.exists())

    def test_valor_da_pessoa_vence_a_media_so_naquele_programa(self):
        gravar("regua", "smiles", 20.5, hoje=HOJE)
        r = ler_regua()
        self.assertEqual(r.valores["smiles"], 20.5)
        self.assertNotIn("smiles", r.medias)
        self.assertEqual(r.valores["azul"], 14)
        self.assertIn("azul", r.medias)

    def test_resultado_chama_de_sua_regua_so_o_que_e_dela(self):
        gravar("regua", "smiles", 20.5, hoje=HOJE)
        dela = comparar(55.6, "smiles", hoje=HOJE)
        self.assertIn("acima do valor da sua régua para smiles (R$ 20,50)", dela)
        self.assertNotIn("MÉDIA DE REFERÊNCIA", dela)
        self.assertIn("[MÉDIA DE REFERÊNCIA", comparar(55.6, "azul", hoje=HOJE))

    def test_gravar_de_novo_troca_o_valor_sem_duplicar_a_linha(self):
        gravar("regua", "smiles", 20.5, hoje=HOJE)
        gravar("regua", "Smiles", 22, hoje=HOJE)
        self.assertEqual(ler_regua().valores["smiles"], 22)
        self.assertEqual(self.arq.read_text(encoding="utf-8").casefold().count("| smiles |"), 1)

    def test_codigo_do_seats_aero_cai_na_linha_do_programa(self):
        gravar("regua", "Avios", 50, hoje=HOJE)
        gravar("regua", "iberia", 52, hoje=HOJE)
        texto = self.arq.read_text(encoding="utf-8")
        self.assertEqual(ler_regua().valores["avios"], 52)
        self.assertIn("| Avios | 52,00 |", texto)
        self.assertNotIn("iberia", texto.casefold())

    def test_validade_segue_a_data_de_quem_deu_o_valor(self):
        # valor dela com 100 dias: vencido. Média do pacote, de 08/11/2026: no prazo.
        gravar("regua", "smiles", 20.5, hoje=HOJE - timedelta(days=100))
        self.assertIn("[RECONFIRMAR", comparar(55.6, "smiles", hoje=HOJE))
        self.assertNotIn("[RECONFIRMAR", comparar(55.6, "azul", hoje=HOJE))

    def test_valor_novo_da_pessoa_nao_herda_o_vencimento_das_medias(self):
        depois = HOJE + timedelta(days=200)
        gravar("regua", "smiles", 20.5, hoje=depois)
        self.assertNotIn("[RECONFIRMAR", comparar(55.6, "smiles", hoje=depois))
        self.assertIn("[RECONFIRMAR", comparar(55.6, "azul", hoje=depois))

    def test_gravar_preco_vale_na_estimativa(self):
        gravar("preco", "smiles", 18, hoje=HOJE)
        self.assertEqual(ler_precos()["smiles"], 18)
        dela = estimar(70000, "smiles", 380)
        self.assertIn("R$ 18,00 o milheiro", dela)
        self.assertNotIn("média de referência", dela)
        self.assertIn("média de referência", estimar(70000, "azul", 380))

    def test_gravar_preco_nao_mexe_na_regua(self):
        gravar("preco", "smiles", 18, hoje=HOJE)
        r = ler_regua()
        self.assertEqual(r.valores["smiles"], 16)
        self.assertIn("smiles", r.medias)

    def test_gravar_recusa_zero(self):
        with self.assertRaises(ValueError):
            gravar("regua", "smiles", 0, hoje=HOJE)
        self.assertFalse(self.arq.exists())

    def test_gravar_recusa_tabela_desconhecida(self):
        with self.assertRaises(ValueError):
            gravar("milhas", "smiles", 20, hoje=HOJE)

    def test_programa_fora_das_tabelas_grava_e_pede_conferencia(self):
        aviso = gravar("regua", "smlies", 20, hoje=HOJE)
        self.assertIn("confira o nome", aviso)
        self.assertEqual(ler_regua().valores["smlies"], 20)

    def test_programa_conhecido_grava_sem_pedir_conferencia(self):
        self.assertNotIn("confira o nome", gravar("regua", "iberia", 50, hoje=HOJE))

    def test_arquivo_editado_a_mao_vale(self):
        self.escrever("| Smiles | R$ 22,50 |", HOJE.strftime("%d/%m/%Y"), "| Azul | 12 |")
        self.assertEqual(ler_regua().valores["smiles"], 22.5)
        self.assertEqual(ler_precos()["azul"], 12)

    def test_linha_com_media_no_arquivo_da_pessoa_nao_vira_valor_dela(self):
        # quem copiou a tabela do pacote inteira não transforma as médias em régua própria
        self.escrever("| Smiles | 99 (média) |\n| Azul | 15 |", HOJE.strftime("%d/%m/%Y"))
        r = ler_regua()
        self.assertEqual(r.valores["smiles"], 16)
        self.assertIn("smiles", r.medias)
        self.assertEqual(r.valores["azul"], 15)

    def test_cli_grava_e_depois_compara_com_o_valor_dela(self):
        def rodar(*args):
            saida = io.StringIO()
            with mock.patch.object(sys, "argv", ["milheiro.py", *args]), contextlib.redirect_stdout(saida):
                modulo_milheiro.main()
            return saida.getvalue()
        gravou = rodar("--gravar", "regua", "smiles", "R$ 20,50")
        self.assertIn("smiles", gravou.casefold())
        self.assertIn("20,50", gravou)
        self.assertIn(str(self.arq), gravou)
        self.assertIn("valor da sua régua",
                      rodar("--cash", "4272", "--taxas", "380", "--milhas", "70000", "--programa", "smiles"))

    def test_cli_sem_gravar_continua_exigindo_milhas_e_programa(self):
        with mock.patch.object(sys, "argv", ["milheiro.py", "--cash", "100", "--taxas", "10"]), \
                self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            modulo_milheiro.main()


class TestPontoDeEquilibrio(unittest.TestCase):
    """Emissão sem número (preço escondido, rota não monitorada): até quantos pontos ela ainda passa da régua."""
    REGUA = Regua({"azul": 14.0, "smiles": 20.0}, HOJE, frozenset({"azul"}))

    def test_conta(self):
        # (4.264 − 288) ÷ 14 × 1.000 = 284.000
        self.assertEqual(modulo_milheiro.pontos_de_equilibrio(4264, 288, 14.0), 284000)

    def test_um_ponto_abaixo_passa_da_regua_e_um_acima_nao(self):
        for cash, taxas, valor in ((4264, 288, 14.0), (8529, 0, 14.0), (5488, 375.89, 16.0), (867, 62.14, 20.5)):
            with self.subTest(cash=cash, valor=valor):
                pontos = modulo_milheiro.pontos_de_equilibrio(cash, taxas, valor)
                self.assertGreater(milheiro(cash, taxas, pontos - 1), valor)
                self.assertLess(milheiro(cash, taxas, pontos + 1), valor)

    def test_texto_com_valor_da_pessoa(self):
        res = modulo_milheiro.equilibrio(5000, 1000, "smiles", self.REGUA, HOJE)
        self.assertIn("menos de 200.000", res)
        self.assertIn("valor da sua régua (R$ 20,00)", res)
        self.assertIn("pagar em dinheiro", res)
        self.assertNotIn("MÉDIA DE REFERÊNCIA", res)

    def test_texto_com_media_avisa(self):
        res = modulo_milheiro.equilibrio(4264, 288, "azul", self.REGUA, HOJE)
        self.assertIn("menos de 284.000", res)
        self.assertIn("média de referência (R$ 14,00)", res)
        self.assertIn("[MÉDIA DE REFERÊNCIA", res)
        self.assertNotIn("sua régua", res)

    def test_programa_sem_regua_marca_falta(self):
        self.assertIn(FALTA_REGUA, modulo_milheiro.equilibrio(4264, 288, "delta", self.REGUA, HOJE))

    def test_taxa_que_come_o_preco_manda_pagar_em_dinheiro(self):
        for cash, taxas in ((1000, 1000), (1000, 1500)):
            with self.subTest(taxas=taxas):
                res = modulo_milheiro.equilibrio(cash, taxas, "smiles", self.REGUA, HOJE)
                self.assertIn("Pagar em dinheiro", res)
                self.assertNotIn("menos de", res)

    def test_regua_vencida_pede_reconfirmar(self):
        velha = Regua({"smiles": 20.0}, HOJE - timedelta(days=91))
        self.assertIn("[RECONFIRMAR", modulo_milheiro.equilibrio(5000, 1000, "smiles", velha, HOJE))

    def rodar(self, *args):
        saida = io.StringIO()
        with mock.patch.object(sys, "argv", ["milheiro.py", *args]), contextlib.redirect_stdout(saida):
            modulo_milheiro.main()
        return saida.getvalue()

    def test_linha_de_comando_nao_exige_milhas(self):
        # régua de fábrica: Azul a R$ 14 (média)
        saida = self.rodar("--equilibrio", "--cash", "4.264", "--taxas", "288", "--programa", "azul")
        self.assertIn("menos de 284.000", saida)
        self.assertIn("[MÉDIA DE REFERÊNCIA", saida)

    def test_linha_de_comando_com_taxa_desconhecida(self):
        saida = self.rodar("--equilibrio", "--cash", "8529", "--taxas", "desconhecida", "--programa", "azul")
        self.assertIn("menos de 609.214", saida)
        self.assertIn("[TAXA DESCONHECIDA", saida)
        self.assertIn("o limite real é menor", saida)
        self.assertNotIn("R$ 0,00 de taxas", saida)  # taxa que ninguém sabe não vira zero no texto
        self.assertIn("sem contar as taxas", saida)

    def test_taxa_desconhecida_na_funcao(self):
        res = modulo_milheiro.equilibrio(8529, None, "azul", self.REGUA, HOJE)
        self.assertIn("menos de 609.214", res)
        self.assertIn("[TAXA DESCONHECIDA", res)

    def test_linha_de_comando_exige_dinheiro_e_taxas(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.rodar("--equilibrio", "--programa", "azul")

    def test_com_pax_o_limite_sai_por_pessoa_e_no_total(self):
        # o Google devolve o total do grupo e o site do programa mostra pontos por pessoa:
        # limite sem a base dita faz comparar 320 mil por pessoa com 609 mil dos dois
        res = modulo_milheiro.equilibrio(8529, None, "azul", self.REGUA, HOJE, pax=2)
        self.assertIn("menos de 304.607 pontos por pessoa", res)
        self.assertIn("609.214 no total", res)
        self.assertIn("2 passageiros", res)
        self.assertIn("Com 304.607 por pessoa ou mais", res)

    def test_limite_por_pessoa_fecha_com_a_conta_do_milheiro(self):
        for cash, taxas, valor, pax in ((8529, 0, 14.0, 2), (12020, 576.36, 14.0, 2),
                                        (20000, 1500, 16.0, 4), (867, 62.14, 20.5, 3)):
            with self.subTest(cash=cash, pax=pax):
                cada = modulo_milheiro.pontos_de_equilibrio(cash, taxas, valor, pax)
                self.assertGreater(milheiro(cash, taxas, (cada - 1) * pax), valor)
                self.assertLess(milheiro(cash, taxas, (cada + 1) * pax), valor)

    def test_um_passageiro_nao_fala_em_por_pessoa(self):
        res = modulo_milheiro.equilibrio(5000, 1000, "smiles", self.REGUA, HOJE)
        self.assertNotIn("por pessoa", res)
        self.assertNotIn("passageiros", res)

    def test_linha_de_comando_com_pax(self):
        saida = self.rodar("--equilibrio", "--cash", "8529", "--taxas", "desconhecida",
                           "--programa", "azul", "--pax", "2")
        self.assertIn("menos de 304.607 pontos por pessoa", saida)
        self.assertIn("609.214 no total", saida)

    def test_pax_zero_e_erro(self):
        erro = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(erro):
            self.rodar("--equilibrio", "--cash", "8529", "--taxas", "0", "--programa", "azul", "--pax", "0")
        self.assertIn("--pax precisa ser 1 ou mais", erro.getvalue())

    def test_pax_fora_do_equilibrio_e_erro(self):
        # no cálculo normal quem multiplica pelo PAX é quem chama: aceitar --pax calado dobraria o milheiro
        erro = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(erro):
            self.rodar("--cash", "8529", "--taxas", "0", "--milhas", "195000", "--programa", "azul", "--pax", "2")
        self.assertIn("--pax só vale com --equilibrio", erro.getvalue())



class TestIdaEVolta(unittest.TestCase):
    """Ida e volta: o lado do dinheiro é o que a emissão evita, não o só-ida do sentido.

    Emitir um sentido obriga a comprar o outro em só-ida. Quando o bilhete único sai mais barato
    que dois só-ida, comparar cada emissão com o só-ida do seu sentido superestima as milhas."""
    ORLANDO = (11699, 7595, 5781)  # VCP⇄MCO, 2 adultos, 2026-11-09: bilhete único mais barato
    LISBOA = (5488, 2154, 3230)    # SAO⇄LIS, 1 adulto, 2026-11-09: dois só-ida mais baratos
    RECIFE = (867, 410, 497)       # CGH⇄REC, 1 adulto, 2026-11-09: bilhete único um pouco mais barato
    REGUA = Regua({"azul": 14.0, "smiles": 20.0}, HOJE, frozenset({"azul"}))
    VIAGEM = ("--ida-e-volta", "11.699", "--so-ida", "7.595", "--so-volta", "5.781")

    def test_dinheiro_evitado_com_bilhete_unico_mais_barato(self):
        evitado = modulo_milheiro.dinheiro_evitado
        self.assertEqual(evitado(*self.ORLANDO, "os-dois"), 11699)
        self.assertEqual(evitado(*self.ORLANDO, "ida"), 11699 - 5781)
        self.assertEqual(evitado(*self.ORLANDO, "volta"), 11699 - 7595)

    def test_com_dois_so_ida_mais_baratos_nada_muda(self):
        evitado = modulo_milheiro.dinheiro_evitado
        self.assertEqual(evitado(*self.LISBOA, "ida"), 2154)
        self.assertEqual(evitado(*self.LISBOA, "volta"), 3230)
        self.assertEqual(evitado(*self.LISBOA, "os-dois"), 2154 + 3230)

    @staticmethod
    def _custos(viagem, pontos_ida, pontos_volta, valor):
        """Custo de cada construção, com os pontos valendo a régua."""
        ida_e_volta, so_ida, so_volta = viagem
        ida, volta = pontos_ida / 1000 * valor, pontos_volta / 1000 * valor
        return {"dinheiro": min(ida_e_volta, so_ida + so_volta), "ida": ida + so_volta,
                "volta": so_ida + volta, "os-dois": ida + volta}

    @staticmethod
    def _grade(viagem, valor):
        teto = int(1.5 * min(viagem[0], viagem[1] + viagem[2]) / valor * 1000)
        return range(teto // 45, teto, teto // 45)

    def test_por_que_o_so_ida_do_sentido_engana(self):
        # Orlando, ida a 230 mil pontos por pessoa (460 mil os dois), ponto a R$ 14
        self.assertGreater(milheiro(7595, 0, 460000), 14.0)  # contra o só-ida da ida, mandava emitir
        custos = self._custos(self.ORLANDO, 460000, 10**9, 14.0)
        self.assertGreater(custos["ida"], custos["dinheiro"])  # e a viagem saía mais cara que tudo em dinheiro
        self.assertLess(milheiro(modulo_milheiro.dinheiro_evitado(*self.ORLANDO, "ida"), 0, 460000), 14.0)

    def test_os_tres_limites_dizem_quando_os_pontos_ganham_do_dinheiro(self):
        valor = 14.0
        for viagem in (self.ORLANDO, self.LISBOA, self.RECIFE):
            limite = {s: modulo_milheiro.dinheiro_evitado(*viagem, s) / valor * 1000
                      for s in ("ida", "volta", "os-dois")}
            for pontos_ida in self._grade(viagem, valor):
                for pontos_volta in self._grade(viagem, valor):
                    custos = self._custos(viagem, pontos_ida, pontos_volta, valor)
                    ganha = min(custos["ida"], custos["volta"], custos["os-dois"]) < custos["dinheiro"]
                    diz = (pontos_ida < limite["ida"] or pontos_volta < limite["volta"]
                           or pontos_ida + pontos_volta < limite["os-dois"])
                    self.assertEqual(ganha, diz, (viagem, pontos_ida, pontos_volta))

    @staticmethod
    def _ordem_das_contas(viagem, pontos_ida, pontos_volta, valor):
        """A ordem que o SKILL.md manda: cada sentido sozinho; com um sentido já em milhas,
        o outro contra o próprio só-ida; nenhum passou sozinho, os dois juntos."""
        _, so_ida, so_volta = viagem
        evitado = modulo_milheiro.dinheiro_evitado
        ida = milheiro(evitado(*viagem, "ida"), 0, pontos_ida) > valor
        volta = milheiro(evitado(*viagem, "volta"), 0, pontos_volta) > valor
        if ida:
            return "os-dois" if milheiro(so_volta, 0, pontos_volta) > valor else "ida"
        if volta:
            return "os-dois" if milheiro(so_ida, 0, pontos_ida) > valor else "volta"
        if milheiro(evitado(*viagem, "os-dois"), 0, pontos_ida + pontos_volta) > valor:
            return "os-dois"
        return "dinheiro"

    def test_a_ordem_das_contas_acha_a_construcao_mais_barata(self):
        valor = 14.0
        for viagem in (self.ORLANDO, self.LISBOA, self.RECIFE):
            for pontos_ida in self._grade(viagem, valor):
                for pontos_volta in self._grade(viagem, valor):
                    custos = self._custos(viagem, pontos_ida, pontos_volta, valor)
                    escolha = self._ordem_das_contas(viagem, pontos_ida, pontos_volta, valor)
                    self.assertAlmostEqual(custos[escolha], min(custos.values()), places=6,
                                           msg=(viagem, pontos_ida, pontos_volta, escolha))

    def rodar(self, *args):
        saida = io.StringIO()
        with mock.patch.object(sys, "argv", ["milheiro.py", *args]), contextlib.redirect_stdout(saida):
            modulo_milheiro.main()
        return saida.getvalue()

    def erro(self, *args):
        saida = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(saida):
            self.rodar(*args)
        return saida.getvalue()

    def test_milheiro_de_um_sentido_usa_o_dinheiro_evitado(self):
        saida = self.rodar(*self.VIAGEM, "--sentido", "ida", "--milhas", "460000",
                           "--taxas", "desconhecida", "--programa", "azul")
        for trecho in ("R$ 12,87/milheiro", "abaixo da média de referência", "[IDA E VOLTA",
                       "ida e volta num bilhete só, R$ 11.699,00", "os dois só-ida somam R$ 13.376,00",
                       "Emitindo só a ida", "R$ 5.781,00", "evita R$ 5.918,00", "[TAXA DESCONHECIDA",
                       # a conta de um sentido sozinho muda se o outro também for em milhas: a saída avisa
                       "Se a volta também for em milhas", "--cash 7.595,00"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, saida)

    def test_milheiro_dos_dois_sentidos(self):
        saida = self.rodar(*self.VIAGEM, "--sentido", "os-dois", "--milhas", "850000", "--taxas", "0",
                           "--programa", "azul")
        self.assertIn("R$ 13,76/milheiro", saida)  # 11.699 ÷ 850.000 × 1.000
        self.assertIn("soma dos dois sentidos", saida)
        self.assertIn("evita os R$ 11.699,00 inteiros", saida)  # o valor dito, sem "esse valor"
        self.assertNotIn("também for em milhas", saida)

    def test_dois_so_ida_mais_baratos_diz_isso(self):
        saida = self.rodar("--ida-e-volta", "5488", "--so-ida", "2154", "--so-volta", "3230",
                           "--sentido", "ida", "--milhas", "100000", "--taxas", "0", "--programa", "azul")
        self.assertIn("R$ 21,54/milheiro", saida)
        self.assertIn("os dois só-ida, R$ 5.384,00", saida)
        self.assertIn("evita R$ 2.154,00", saida)

    def test_aviso_de_refazer_a_conta_so_sai_quando_ela_muda(self):
        # com dois só-ida mais baratos (ou empatados com o bilhete único), o que a emissão de um
        # sentido evita já é o só-ida dele: mandar refazer com o mesmo número seria ruído
        for viagem, sentido in (((5488, 2154, 3230), "ida"), ((5384, 2154, 3230), "volta")):
            with self.subTest(viagem=viagem, sentido=sentido):
                ida_e_volta, so_ida, so_volta = (str(v) for v in viagem)
                saida = self.rodar("--ida-e-volta", ida_e_volta, "--so-ida", so_ida, "--so-volta", so_volta,
                                   "--sentido", sentido, "--milhas", "100000", "--taxas", "0",
                                   "--programa", "azul")
                self.assertIn(f"Emitindo só a {sentido}", saida)
                self.assertNotIn("também for em milhas", saida)
                self.assertNotIn("--cash", saida)

    def test_bilhete_unico_mais_barato_que_o_outro_so_ida(self):
        # ida e volta a R$ 1.000 com a volta em só-ida a R$ 1.200: emitir só a ida nunca compensa
        saida = self.rodar("--ida-e-volta", "1000", "--so-ida", "900", "--so-volta", "1200",
                           "--sentido", "ida", "--milhas", "10000", "--taxas", "0", "--programa", "azul")
        self.assertIn("não compensa com nenhuma quantidade de pontos", saida)
        self.assertNotIn("/milheiro", saida)

    def test_equilibrio_devolve_os_tres_limites(self):
        saida = self.rodar("--equilibrio", *self.VIAGEM, "--taxas", "desconhecida", "--programa", "azul",
                           "--pax", "2")
        for trecho in ("só a ida em pontos", "menos de 211.357 pontos por pessoa (422.714 no total)",
                       "só a volta em pontos", "menos de 146.571 pontos por pessoa (293.142 no total)",
                       "ida e volta em pontos", "menor que 417.821 pontos por pessoa (835.642 no total)",
                       "ida e volta num bilhete só, R$ 11.699,00", "média de referência (R$ 14,00)",
                       "[MÉDIA DE REFERÊNCIA", "[TAXA DESCONHECIDA", "2 passageiros", "pagar em dinheiro"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, saida)

    def test_equilibrio_de_um_recorte_so(self):
        # contra o voo direto da companhia do programa: só o limite da viagem inteira
        saida = self.rodar("--equilibrio", "--ida-e-volta", "21329", "--so-ida", "8529", "--so-volta", "12020",
                           "--sentido", "os-dois", "--taxas", "desconhecida", "--programa", "azul", "--pax", "2")
        self.assertIn("menor que 733.892 pontos por pessoa", saida)
        self.assertIn("os dois só-ida, R$ 20.549,00", saida)
        self.assertNotIn("só a ida em pontos", saida)
        self.assertNotIn("só a volta em pontos", saida)

    def test_equilibrio_com_dois_so_ida_mais_baratos_bate_com_o_so_ida(self):
        res = modulo_milheiro.equilibrio_ida_e_volta(*self.LISBOA, "azul", self.REGUA, HOJE)
        self.assertIn("menos de 153.857 pontos", res)   # 2.154 ÷ 14 × 1.000
        self.assertIn("menos de 230.714 pontos", res)   # 3.230 ÷ 14 × 1.000
        self.assertIn("menor que 384.571 pontos", res)  # 5.384 ÷ 14 × 1.000
        self.assertNotIn("por pessoa", res)

    def test_equilibrio_sem_dinheiro_evitado_num_sentido(self):
        res = modulo_milheiro.equilibrio_ida_e_volta(1000, 900, 1200, "azul", self.REGUA, HOJE)
        self.assertIn("só a ida em pontos: não compensa com nenhuma quantidade de pontos", res)
        self.assertIn("menos de 7.142 pontos", res)  # só a volta: (1.000 − 900) ÷ 14 × 1.000

    def test_equilibrio_programa_sem_regua(self):
        res = modulo_milheiro.equilibrio_ida_e_volta(*self.ORLANDO, "delta", self.REGUA, HOJE)
        self.assertIn(FALTA_REGUA, res)
        self.assertNotIn("menos de", res)

    def test_equilibrio_com_valor_da_pessoa_nao_fala_em_media(self):
        res = modulo_milheiro.equilibrio_ida_e_volta(*self.ORLANDO, "smiles", self.REGUA, HOJE)
        self.assertIn("valor da sua régua (R$ 20,00)", res)
        self.assertNotIn("MÉDIA DE REFERÊNCIA", res)

    def test_equilibrio_de_um_sentido_aceita_taxa(self):
        saida = self.rodar("--equilibrio", *self.VIAGEM, "--sentido", "ida", "--taxas", "576,36",
                           "--programa", "azul", "--pax", "2")
        self.assertIn("menos de 190.772 pontos por pessoa", saida)  # (5.918 − 576,36) ÷ 14 × 1.000 ÷ 2
        self.assertIn("R$ 576,36 de taxas", saida)
        self.assertNotIn("[TAXA DESCONHECIDA", saida)

    def test_os_tres_precos_andam_juntos(self):
        self.assertIn("andam juntos", self.erro("--ida-e-volta", "11699", "--so-ida", "7595", "--sentido", "ida",
                                                "--milhas", "460000", "--taxas", "0", "--programa", "azul"))

    def test_com_os_tres_precos_nao_vai_cash(self):
        self.assertIn("não passe --cash", self.erro(*self.VIAGEM, "--cash", "7595", "--sentido", "ida",
                                                    "--milhas", "460000", "--taxas", "0", "--programa", "azul"))

    def test_milheiro_de_ida_e_volta_exige_o_sentido(self):
        self.assertIn("--sentido ida, volta ou os-dois",
                      self.erro(*self.VIAGEM, "--milhas", "460000", "--taxas", "0", "--programa", "azul"))

    def test_sentido_sem_os_tres_precos_e_erro(self):
        self.assertIn("--sentido pede", self.erro("--cash", "7595", "--sentido", "ida", "--milhas", "460000",
                                                  "--taxas", "0", "--programa", "azul"))

    def test_tres_limites_so_com_taxa_desconhecida(self):
        self.assertIn("um sentido por vez",
                      self.erro("--equilibrio", *self.VIAGEM, "--taxas", "576", "--programa", "azul"))

    def test_preco_zerado_e_erro(self):
        self.assertIn("maiores que zero", self.erro("--ida-e-volta", "0", "--so-ida", "7595", "--so-volta", "5781",
                                                    "--sentido", "ida", "--milhas", "460000", "--taxas", "0",
                                                    "--programa", "azul"))

class TestCambio(unittest.TestCase):
    """Cotação PTAX do Banco Central. Nenhum teste toca a rede."""
    HOJE = date(2026, 11, 9)

    def resposta(self, valores):
        corpo = json.dumps({"value": valores}).encode("utf-8")
        resp = mock.MagicMock()
        resp.read.return_value = corpo
        resp.__enter__.return_value = resp
        return resp

    def test_devolve_valor_data_e_fonte(self):
        dado = [{"cotacaoVenda": 5.5146, "dataHoraCotacao": "2026-11-09 13:11:19.041465"}]
        with mock.patch.object(modulo_milheiro.urllib.request, "urlopen", return_value=self.resposta(dado)) as abrir:
            texto = modulo_milheiro.cambio("usd", hoje=self.HOJE)
        self.assertIn("R$ 5,5146", texto)
        self.assertIn("09/11/2026", texto)
        self.assertIn("PTAX", texto)
        url = abrir.call_args[0][0]
        url = getattr(url, "full_url", url)
        self.assertIn("olinda.bcb.gov.br", url)
        self.assertIn("USD", url)
        self.assertIn("11-09-2026", url)  # a janela termina hoje
        self.assertIn("11-02-2026", url)  # e volta 7 dias, por causa de fim de semana e feriado

    def test_sem_cotacao_na_janela(self):
        with mock.patch.object(modulo_milheiro.urllib.request, "urlopen", return_value=self.resposta([])):
            self.assertIn("[FALTA: câmbio", modulo_milheiro.cambio("USD", hoje=self.HOJE))

    def test_sem_rede_nao_derruba(self):
        with mock.patch.object(modulo_milheiro.urllib.request, "urlopen",
                               side_effect=modulo_milheiro.urllib.error.URLError("sem rede")):
            self.assertIn("[FALTA: câmbio", modulo_milheiro.cambio("USD", hoje=self.HOJE))

    def test_codigo_invalido_nem_consulta(self):
        with mock.patch.object(modulo_milheiro.urllib.request, "urlopen") as abrir, \
                self.assertRaises(ValueError):
            modulo_milheiro.cambio("dolar", hoje=self.HOJE)
        abrir.assert_not_called()

    def test_linha_de_comando_nao_exige_milhas(self):
        saida = io.StringIO()
        with mock.patch.object(sys, "argv", ["milheiro.py", "--cambio", "CAD"]), \
                mock.patch.object(modulo_milheiro, "cambio", return_value="CAD: ok"), \
                contextlib.redirect_stdout(saida):
            modulo_milheiro.main()
        self.assertIn("CAD: ok", saida.getvalue())


class TestEstimativaEmReais(unittest.TestCase):
    # preços inventados, só pra exercitar a conta
    PRECOS = {"smiles": 10.0, "flying_blue": 20.0, "avios": 30.0, "miles_go": 40.0,
              "american": 50.0, "skywards": 60.0}

    def test_milhas_mais_taxas(self):
        res = estimar(70800, "smiles", 245.36, self.PRECOS)
        self.assertIn("R$ 708,00", res)
        self.assertIn("R$ 10,00 o milheiro", res)
        self.assertIn("R$ 953,36", res)

    def test_sem_taxa_informada_nao_finge_zero(self):
        self.assertIn("[FALTA: taxas]", estimar(70800, "smiles", None, self.PRECOS))

    def test_codigos_e_apelidos_dos_programas(self):
        pares = (("flyingblue", "R$ 200,00"), ("iberia", "R$ 300,00"), ("tap", "R$ 400,00"),
                 ("aa", "R$ 500,00"), ("AAdvantage", "R$ 500,00"), ("emirates", "R$ 600,00"))
        for codigo, esperado in pares:
            with self.subTest(codigo=codigo):
                self.assertIn(esperado, estimar(10000, codigo, 0, self.PRECOS))

    def test_programa_sem_valor_marca_falta(self):
        self.assertEqual(FALTA_PRECO, "[FALTA: seu preço de referência]")
        self.assertIn(FALTA_PRECO, estimar(10000, "miles&more", 0, self.PRECOS))

    def test_tap_na_regua_cai_em_miles_go(self):
        self.assertNotIn(FALTA_REGUA, comparar(90.0, "tap", REGUA_TESTE, HOJE))

    def test_le_a_tabela_de_precos(self):
        with tempfile.TemporaryDirectory() as td:
            arq = Path(td) / "regua.md"
            arq.write_text("<!-- preco:inicio -->\n| Programa | Preço |\n|---|---|\n| Smiles | R$ 11,00 |\n"
                           "| Azul | |\n<!-- preco:fim -->\n", encoding="utf-8")
            self.assertEqual(ler_precos(arq), {"smiles": 11.0})

    def test_tabela_de_precos_vem_preenchida(self):
        p = ler_precos()
        self.assertEqual(p["smiles"], 16)
        self.assertEqual(p["livelo"], 30)
        self.assertEqual(p["american"], 100)
        self.assertEqual(p["suma"], 61.32)
        self.assertEqual(len(p), 14)


class TestTravaDeAtualidade(unittest.TestCase):
    def test_no_prazo_nao_avisa(self):
        regua = Regua({"azul": 20.0}, HOJE - timedelta(days=90))
        self.assertNotIn("[RECONFIRMAR", comparar(25.0, "azul", regua, HOJE))

    def test_vencida_avisa(self):
        regua = Regua({"azul": 20.0}, HOJE - timedelta(days=91))
        self.assertIn("[RECONFIRMAR", comparar(25.0, "azul", regua, HOJE))

    def test_sem_data_avisa(self):
        self.assertIn("[RECONFIRMAR", comparar(25.0, "azul", Regua({"azul": 20.0}, None), HOJE))


class TestNumeroBr(unittest.TestCase):
    def test_br_com_prefixo(self):
        self.assertEqual(numero_br("R$ 1.234,56"), 1234.56)

    def test_br_sem_prefixo(self):
        self.assertEqual(numero_br("12528,00"), 12528.0)

    def test_ponto_milhar_sem_virgula(self):
        self.assertEqual(numero_br("120.000"), 120000.0)

    def test_ponto_decimal_sem_virgula(self):
        self.assertEqual(numero_br("5546.5"), 5546.5)

    def test_inteiro_puro(self):
        self.assertEqual(numero_br("5546"), 5546.0)

    def test_negativo_erro_claro(self):
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            numero_br("-R$ 100")
        self.assertIn("negativo", str(ctx.exception))

    def test_lixo_erro_claro(self):
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            numero_br("carne")
        self.assertIn("não entendi", str(ctx.exception))


class TestNomesDosProgramas(unittest.TestCase):
    def test_maiusculas(self):
        self.assertIn("abaixo", comparar(10.0, "AZUL", REGUA_TESTE, HOJE))

    def test_espaco_e_maiuscula(self):
        self.assertIn("acima", comparar(70.0, " Smiles ", REGUA_TESTE, HOJE))

    def test_latam_pass(self):
        self.assertIn("abaixo", comparar(10.0, "LATAM Pass", REGUA_TESTE, HOJE))

    def test_miles_e_go(self):
        self.assertIn("acima", comparar(50.0, "Miles & Go", REGUA_TESTE, HOJE))

    def test_flying_blue(self):
        self.assertIn("acima", comparar(80.0, "Flying Blue", REGUA_TESTE, HOJE))

    def test_miles_and_more_nao_e_miles_and_go(self):
        self.assertIn(FALTA_REGUA, comparar(50.0, "Miles & More", REGUA_TESTE, HOJE))

    def test_codigos_do_seats_aero_caem_na_regua(self):
        for codigo in ("flyingblue", "iberia", "british", "qatar", "copa"):
            with self.subTest(codigo=codigo):
                self.assertNotIn(FALTA_REGUA, comparar(90.0, codigo, REGUA_TESTE, HOJE))


class TestEcoMilhar(unittest.TestCase):
    def test_eco_quando_milhar_ambiguo(self):
        ECOS.clear()
        numero_br("1.234", eco_milhar=True)
        self.assertTrue(any("milhar" in e for e in ECOS))
        ECOS.clear()

    def test_sem_eco_quando_virgula(self):
        ECOS.clear()
        numero_br("1.234,00", eco_milhar=True)
        self.assertEqual(ECOS, [])


class TestReaisBr(unittest.TestCase):
    def test_simples(self):
        self.assertEqual(reais_br(110.93), "110,93")

    def test_milhar(self):
        self.assertEqual(reais_br(1234.5), "1.234,50")

    def test_negativo(self):
        self.assertEqual(reais_br(-123.45), "-123,45")
        self.assertEqual(reais_br(-1234.5), "-1.234,50")


class TestCliMilheiro(unittest.TestCase):
    def rodar(self, *args):
        saida = io.StringIO()
        with mock.patch.object(sys, "argv", ["milheiro.py", *args]), contextlib.redirect_stdout(saida):
            modulo_milheiro.main()
        return saida.getvalue()

    def test_sem_regua_preenchida(self):
        saida = self.rodar("--cash", "R$ 5.546,50", "--taxas", "546,50", "--milhas", "50.000", "--programa", "lifemiles")
        self.assertIn("R$ 100,00/milheiro", saida)
        self.assertIn(FALTA_REGUA, saida)

    def test_com_regua_preenchida(self):
        with tempfile.TemporaryDirectory() as td:
            arq = Path(td) / "regua.md"
            arq.write_text(TestLeituraDaRegua.MODELO.format(linhas="| Smiles | 25 |", data=date.today().strftime("%d/%m/%Y")),
                           encoding="utf-8")
            with mock.patch.object(modulo_milheiro, "ARQUIVO_REGUA", arq):
                saida = self.rodar("--cash", "5546", "--taxas", "546", "--milhas", "50000", "--programa", "Smiles")
        self.assertIn("acima do valor da sua régua para Smiles (R$ 25,00)", saida)
        self.assertNotIn("[RECONFIRMAR", saida)

    def test_taxa_desconhecida_sai_marcada(self):
        saida = self.rodar("--cash", "2173", "--taxas", "desconhecida", "--milhas", "96000", "--programa", "smiles")
        self.assertIn("R$ 22,64/milheiro", saida)
        self.assertIn("[TAXA DESCONHECIDA", saida)

    def test_taxa_informada_nao_sai_marcada(self):
        saida = self.rodar("--cash", "2173", "--taxas", "100", "--milhas", "96000", "--programa", "smiles")
        self.assertNotIn("[TAXA DESCONHECIDA", saida)

    def test_regua_de_fabrica_sai_marcada_como_media(self):
        saida = self.rodar("--cash", "4272", "--taxas", "380", "--milhas", "70000", "--programa", "smiles")
        self.assertIn("[MÉDIA DE REFERÊNCIA", saida)
        self.assertNotIn("sua régua", saida)


class TestCliEstimar(unittest.TestCase):
    def rodar(self, *args):
        saida = io.StringIO()
        with mock.patch.object(sys, "argv", ["milheiro.py", *args]), contextlib.redirect_stdout(saida):
            modulo_milheiro.main()
        return saida.getvalue()

    def test_estimar_nao_exige_preco_em_dinheiro(self):
        saida = self.rodar("--estimar", "--milhas", "70.800", "--taxas", "245,36", "--programa", "lifemiles")
        self.assertIn(FALTA_PRECO, saida)

    def test_estimar_com_taxa_desconhecida_nao_finge_zero(self):
        saida = self.rodar("--estimar", "--milhas", "96000", "--taxas", "?", "--programa", "livelo")
        self.assertIn("[FALTA: taxas]", saida)

    def test_estimar_com_tabela_de_fabrica_avisa_que_e_media(self):
        saida = self.rodar("--estimar", "--milhas", "70000", "--taxas", "380", "--programa", "smiles")
        self.assertIn("média de referência", saida)

    def test_sem_estimar_exige_dinheiro_e_taxas(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.rodar("--milhas", "50000", "--programa", "Smiles")


def comandos_de_atualizar(texto):
    """Os comandos `claude plugin ...` da seção "Atualizar" de um README, na ordem em que aparecem."""
    secao = texto.split("\n## Atualizar")[1].split("\n## ")[0]
    return re.findall(r"^claude plugin .+$", secao, re.MULTILINE)


class TestDocumentacao(unittest.TestCase):
    ARQUIVOS = ["SKILL.md", "README.md", "MUDANCAS.md", *(f"references/{n}" for n in (
        "hoteis-trivago.md",
        "armadilhas.md", "extractor-navegador.md", "fatos-programas.md", "regua-milheiro.md", "seats-aero.md"))]

    def ler(self, nome):
        return (PASTA / nome).read_text(encoding="utf-8")

    def test_regua_ensina_a_taxa_subtraida(self):
        texto = self.ler("references/regua-milheiro.md")
        self.assertIn("(preço cash − taxas de emissão)", texto)
        self.assertNotIn("preço cash + taxas", texto)

    def test_contas_do_exemplo_batem(self):
        texto = EXEMPLO.read_text(encoding="utf-8")
        contas = re.findall(r"\(([\d.]+) − ([\d.]+)\) ÷ ([\d.]+) × 1\.000 = R\$ ([\d,]+)", texto)
        self.assertGreaterEqual(len(contas), 2)
        for cash, taxa, milhas, esperado in contas:
            with self.subTest(cash=cash):
                calc = milheiro(numero_br(cash), numero_br(taxa), numero_br(milhas))
                self.assertEqual(reais_br(calc), esperado)

    def test_exemplo_declara_regua_inventada(self):
        cabecalho = EXEMPLO.read_text(encoding="utf-8").split("## AVISOS")[0].replace("\n> ", " ")
        self.assertIn("milhas e régua abaixo são inventados", " ".join(cabecalho.split()))

    def test_arquivos_citados_existem(self):
        citacao = re.compile(r"`((?:references|scripts|exemplo)/[\w./-]+\.\w+)")
        for nome in self.ARQUIVOS:
            for citado in citacao.findall(self.ler(nome)):
                with self.subTest(arquivo=nome, citado=citado):
                    self.assertTrue((PASTA / citado).exists())

    def test_armadilhas_citadas_existem(self):
        existentes = {int(n) for n in re.findall(r"^(\d+)\. \*\*", self.ler("references/armadilhas.md"), re.MULTILINE)}
        self.assertEqual(existentes, set(range(1, max(existentes) + 1)))  # numeração sem buraco
        citacao = re.compile(r"armadilhas? (\d+(?:, \d+)*(?: e \d+)?)")
        for nome in self.ARQUIVOS:
            for grupo in citacao.findall(self.ler(nome)):
                for numero in re.findall(r"\d+", grupo):
                    with self.subTest(arquivo=nome, armadilha=numero):
                        self.assertIn(int(numero), existentes)

    def test_commit_do_google_flights_igual_em_todo_lugar(self):
        self.assertIn("9e26198", self.ler("SKILL.md"))
        self.assertIn("git checkout 9e26198", self.ler("README.md"))
        self.assertTrue(instalar.COMMIT_GF.startswith("9e26198"))
        self.assertEqual(len(instalar.COMMIT_GF), 40)  # o instalador confere o commit inteiro
        self.assertIn(f"git checkout {instalar.COMMIT_GF}", self.ler("README.md"))

    def test_textos_mandam_rodar_o_instalador(self):
        self.assertIn("python3 ~/.claude/skills/viagem-br/scripts/instalar.py", self.ler("README.md"))
        self.assertIn("scripts/instalar.py --conferir", self.ler("README.md"))
        self.assertIn("`python3 scripts/instalar.py --conferir`", self.ler("SKILL.md"))

    def test_enderecos_dos_servidores_iguais_no_readme_e_no_instalador(self):
        readme = self.ler("README.md")
        for url in (instalar.URL_SEATS, *instalar.OPCIONAIS.values()):
            with self.subTest(url=url):
                self.assertIn(url, readme)
        self.assertEqual(instalar.URL_SEATS, ponte_mcp.URL_SEATS_AERO)

    def test_nome_da_skill_igual_ao_da_pasta(self):
        self.assertIn("name: viagem-br\n", self.ler("SKILL.md"))

    def test_descricao_cabe_no_limite(self):
        descricao = re.search(r"^description: (.+)$", self.ler("SKILL.md"), re.MULTILINE).group(1)
        self.assertLessEqual(len(descricao), 1024)

    def test_marcadores_de_celula_vazia_do_metodo_passam_no_audit(self):
        skill = self.ler("SKILL.md")
        for marcador in audit._MARCADOR_VAZIO:
            with self.subTest(marcador=marcador):
                self.assertIn(marcador, skill)

    def test_credito_e_licenca_no_readme(self):
        readme = self.ler("README.md")
        for trecho in ("Travel Hacking Toolkit", "Michael Borohovski", "MIT"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, readme)

    def test_nenhum_valor_com_formato_de_chave_no_pacote(self):
        for arq in sorted(PASTA.rglob("*")):
            if arq.suffix in (".md", ".py"):
                with self.subTest(arquivo=arq.name):
                    self.assertIsNone(audit._CHAVE_RE.search(arq.read_text(encoding="utf-8")))

    def test_readme_manda_usar_a_propria_conta(self):
        readme = self.ler("README.md")
        for trecho in ("conecte a sua conta do seats.aero", "https://seats.aero/mcp",
                       "claude mcp login seats-aero", "plano Pro", "no dia em que for assinar"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, readme)

    def test_jetblue_consta_como_programa_do_mcp(self):
        # conferido em 2026-11-09: `jetblue` está em `programs` e responde sem login
        for nome in ("SKILL.md", "references/armadilhas.md"):
            with self.subTest(arquivo=nome):
                self.assertNotIn("JetBlue não existe no MCP", self.ler(nome))
        seats = self.ler("references/seats-aero.md")
        self.assertIn("34 em `programs`", seats)
        self.assertIn("`jetblue`", seats)

    def test_textos_mandam_a_regua_da_pessoa_pra_fora_da_pasta(self):
        for nome in ("SKILL.md", "README.md", "references/regua-milheiro.md"):
            with self.subTest(arquivo=nome):
                self.assertIn("~/.viagem-br/regua-milheiro.md", self.ler(nome))
        self.assertIn("scripts/milheiro.py --gravar regua", self.ler("SKILL.md"))
        self.assertIn("scripts/milheiro.py --gravar preco", self.ler("SKILL.md"))

    def test_nenhum_texto_manda_editar_a_tabela_dentro_da_pasta(self):
        self.assertNotIn("~/.claude/skills/viagem-br/references/regua-milheiro.md", self.ler("README.md"))
        self.assertNotIn("apague o `(média)`", self.ler("SKILL.md") + self.ler("README.md"))

    def test_lista_de_mudancas_tem_versao_e_data_em_ordem(self):
        versoes = re.findall(r"^## (\d+)\.(\d+)\.(\d+) \((\d{2}/\d{2}/\d{4})\)$",
                             self.ler("MUDANCAS.md"), re.MULTILINE)
        self.assertGreaterEqual(len(versoes), 4)
        numeros = [tuple(int(n) for n in v[:3]) for v in versoes]
        self.assertEqual(numeros, sorted(numeros, reverse=True))  # a mais nova no topo
        self.assertEqual(len(set(numeros)), len(numeros))

    def test_textos_dizem_onde_esta_a_versao(self):
        for nome in ("SKILL.md", "README.md"):
            with self.subTest(arquivo=nome):
                self.assertIn("MUDANCAS.md", self.ler(nome))

    def test_textos_explicam_o_filtro_de_preco_e_nao_culpam_o_login(self):
        # 2026-11-09 à noite: o que some é emissão dinâmica cara demais (filtro do seats.aero), e não a Azul.
        # Medido: Azul pra Lisboa, sem login até 149 mil; numa conta Pro, a mesma busca foi até 900 mil.
        frases = ("não mostra a Azul", "esconde a Azul", "sem a Azul", "esconde os voos da Azul", "Azul só em parte")
        arquivos = [a for a in self.ARQUIVOS if a != "MUDANCAS.md"] + ["scripts/ponte_mcp.py", "scripts/instalar.py"]
        for nome in arquivos:
            texto = self.ler(nome)
            for frase in frases:
                with self.subTest(arquivo=nome, frase=frase):
                    self.assertNotIn(frase, texto)
        for nome in ("SKILL.md", "README.md", "references/seats-aero.md", "scripts/ponte_mcp.py"):
            with self.subTest(arquivo=nome):
                self.assertIn("esconde emissão", self.ler(nome))
        armadilhas = self.ler("references/armadilhas.md")
        for trecho in ("docs.seats.aero", "149 mil", "900 mil", "Disable Dynamic Filtering"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, armadilhas)
        self.assertIn("armadilha 41", self.ler("SKILL.md"))

    def test_filtered_nao_vira_sem_estoque_nem_sem_login(self):
        skill = self.ler("SKILL.md")
        self.assertIn("preço alto, escondido pelo seats.aero", skill)
        self.assertNotIn("Azul `filtered` sem login", skill)

    def test_metodo_compara_ida_e_volta_com_dois_so_ida(self):
        skill = self.ler("SKILL.md")
        for trecho in ("dois só-ida", "ordem das contas", "armadilha 42", "dois bilhetes", "misto"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, skill)
        armadilhas = self.ler("references/armadilhas.md")
        for trecho in ("R$ 867", "R$ 5.488", "R$ 2.154"):  # as duas medições de 2026-11-09
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, armadilhas)

    def test_emissao_sem_numero_ganha_ponto_de_equilibrio(self):
        # pesquisa de Orlando, 2026-11-09: com o preço escondido, "vale emitir?" ficava sem resposta
        skill = self.ler("SKILL.md")
        self.assertGreaterEqual(skill.count("--equilibrio"), 3)  # Passo 7B, bloco MILHAS e PROIBIDO
        self.assertIn("ponto de equilíbrio", skill)
        self.assertIn("scripts/milheiro.py --equilibrio", self.ler("references/regua-milheiro.md"))
        self.assertIn("até quantos pontos", self.ler("README.md"))
        # a base: o limite sai por pessoa, e o preço em dinheiro que entra é dito
        for trecho in ("--pax <PAX>", "por pessoa e no total", "os três limites", "no máximo quatro limites"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, skill)
        self.assertIn("--pax", self.ler("references/regua-milheiro.md"))

    def test_ajustes_dos_leitores_novos_de_2026_11_10(self):
        # Campinas⇄Orlando e São Paulo⇄Recife, agentes novos, sem login
        skill = self.ler("SKILL.md")
        for trecho in ("é o número da viagem inteira, que vai no veredito",   # os dois passaram sozinhos
                       "outra companhia com as mesmas paradas não conta",      # o que é "voo melhor"
                       "explicação fica no fim da célula",                     # o conferidor recusou 2 de 2
                       "aponta os outros neste bloco",                         # veredito não repete 4 limites
                       "os três preços desse mesmo voo"):                      # segunda conta, em ida e volta
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, skill)

    def test_ida_e_volta_usa_o_dinheiro_que_a_emissao_evita(self):
        # pesquisa de Orlando, 2026-11-09: bilhete único mais barato que dois só-ida, e a conta
        # de cada sentido contra o só-ida dele mandava emitir uma viagem mais cara
        skill = self.ler("SKILL.md")
        for trecho in ("o que a emissão evita", "--ida-e-volta", "--so-ida", "--so-volta", "`--sentido ida`",
                       "`os-dois`", "contra o próprio só-ida", "armadilha 43", "mesmo voo da emissão"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, skill)
        self.assertNotIn("contra o só-ida em dinheiro do mesmo sentido", skill)  # a regra antiga saiu
        armadilhas = self.ler("references/armadilhas.md")
        for trecho in ("\n43. **", "R$ 11.699", "R$ 7.595", "R$ 5.781", "--ida-e-volta"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, armadilhas)
        regua = self.ler("references/regua-milheiro.md")
        for trecho in ("o que a emissão evita", "--ida-e-volta", "--sentido"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, regua)
        self.assertIn("dois só-ida", self.ler("MUDANCAS.md").split("## 1.5.0")[0])

    def test_ajustes_da_pesquisa_de_orlando(self):
        # pesquisa de ponta a ponta de 2026-11-09, Campinas⇄Orlando, sem login
        skill = self.ler("SKILL.md")
        for trecho in ("`maxResults` até 10", "um sentido basta", "mesmo voo da emissão", "não é programa de emissão",
                       "numa chamada de conferência por programa", "sem RESTRICOES, 1", "Em outra cidade o código não foi testado",
                       "da CABINE da ENTRADA traz o menor", "sem nenhuma emissão com número"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, skill)
        armadilhas = self.ler("references/armadilhas.md")
        for trecho in ("VCP→ORL", "R$ 158 mil", "aceita no máximo 10"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, armadilhas)

    def test_metodo_consulta_as_rotas_monitoradas(self):
        skill = self.ler("SKILL.md")
        self.assertIn("`list_routes`", skill)
        self.assertIn("sem dado: rota não monitorada pelo seats.aero", skill)
        self.assertIn("`list_routes`", skill.split("## Rota doméstica")[1].split("\n## ")[0])
        self.assertIn("| Rotas monitoradas |", self.ler("references/seats-aero.md"))

    def test_metodo_tem_a_rota_domestica(self):
        skill = self.ler("SKILL.md")
        self.assertIn("## Rota doméstica", skill)
        secao = skill.split("## Rota doméstica")[1].split("\n## ")[0]
        self.assertIn("não pesquisada: rota doméstica", secao)
        for programa in ("smiles", "azul", "american", "aeroplan", "united", "livelo", "delta", "virginatlantic"):
            with self.subTest(programa=programa):
                self.assertIn(f'"{programa}"', secao)
        # achados da pesquisa de ponta a ponta de 2026-11-09 (São Paulo⇄Recife, sem login)
        for trecho in ("Emirates", "LATAM", "app do banco", "armadilha 36", "armadilha 37", "por sentido",
                       "`max_stops: 0`", '`operating_carriers: ["LA"]`', "sem repetir programa",
                       "sem dado: programa fora do seats.aero"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, secao)

    def test_textos_nao_dizem_que_voo_da_latam_fica_de_fora(self):
        self.assertNotIn("LATAM Pass fica de fora", self.ler("README.md"))
        for nome in ("README.md", "references/fatos-programas.md", "references/seats-aero.md"):
            with self.subTest(arquivo=nome):
                self.assertIn("Virgin Atlantic", self.ler(nome))

    def test_metodo_traz_o_que_a_pesquisa_real_cobrou(self):
        # pesquisa de ponta a ponta de 2026-11-09, São Paulo⇄Recife
        skill = self.ler("SKILL.md")
        for trecho in ("`maxResults: 20`", "`--taxas desconhecida`", "--cambio", "PTAX", "bloco Return",
                       "`SAO`", "Data fixa na ENTRADA", "aviso `stale`", "--recorte",
                       "armadilha 38", "armadilha 39", "armadilha 40", "toda chamada de ferramenta",
                       "`>> POSSIVEL INJECTION`", "Tip:"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, skill)

    def test_piso_de_ida_e_volta_nao_e_a_primeira_opcao(self):
        # 2026-11-09, SAO⇄LIS em executiva, sortBy price: 1ª opção R$ 14.146, piso R$ 13.493 na 10ª
        self.assertIn("menor Return entre todas as opções", self.ler("SKILL.md"))
        self.assertIn("13.493", self.ler("references/armadilhas.md"))

    def test_densidade_de_ida_e_volta_avisa_do_corte(self):
        self.assertIn("corte de 20", self.ler("SKILL.md"))

    def test_objetivo_ausente_e_deduzido_e_pergunta_rapida_tem_criterio(self):
        skill = self.ler("SKILL.md")
        self.assertIn("OBJETIVO ausente", skill)
        self.assertIn("vale emitir", skill.split("Pergunta rápida")[1][:300])

    def test_monitoramento_so_quando_pedido(self):
        skill = self.ler("SKILL.md")
        self.assertIn("só se o OBJETIVO for MONITORAR ou a pessoa pedir", skill)
        self.assertNotIn("recorte colado junto", skill)
        self.assertNotIn("Baseline de track criado", EXEMPLO.read_text(encoding="utf-8"))

    def test_consulta_de_cambio_consta_na_privacidade(self):
        privacidade = self.ler("README.md").split("## Privacidade")[1]
        self.assertIn("Banco Central", privacidade)

    def test_regua_explica_taxa_desconhecida(self):
        self.assertIn("`--taxas desconhecida`", self.ler("references/regua-milheiro.md"))

    def test_readme_ensina_os_dois_jeitos_de_instalar(self):
        readme = self.ler("README.md")
        # pelo plugin: dois comandos dentro do Claude Code
        self.assertRegex(readme, r"(?m)^/plugin marketplace add [\w.-]+/viagem-br$")
        self.assertRegex(readme, r"(?m)^/plugin install viagem-br@viagem-br$")
        self.assertIn("roda o instalador da Viagem BR", readme)
        # pelo arquivo: continua como era
        self.assertIn("unzip -o ~/Downloads/viagem-br.skill -d ~/.claude/skills", readme)
        self.assertIn("python3 ~/.claude/skills/viagem-br/scripts/instalar.py", readme)
        # e cada jeito tem a sua atualização
        self.assertIn("claude plugin update viagem-br@viagem-br", readme)

    def test_atualizar_pelo_plugin_busca_o_catalogo_antes(self):
        # 2026-11-11, Claude Code 2.1.309: `claude plugin update` sozinho não busca o catálogo e
        # responde que a versão instalada já é a última. Com o catálogo atualizado antes, atualiza.
        readme = self.ler("README.md")
        self.assertEqual(comandos_de_atualizar(readme), ["claude plugin marketplace update viagem-br",
                                                         "claude plugin update viagem-br@viagem-br"])
        self.assertNotIn("um comando só", readme)

    def test_deu_errado_cobre_quem_atualizou_com_um_comando_so(self):
        # é o que aparece pra quem seguiu o guia da 1.6.0 ou da 1.6.1
        deu_errado = self.ler("README.md").split("\n## Deu errado?")[1].split("\n## ")[0]
        linha = next((l for l in deu_errado.splitlines() if "already at the latest version" in l), "")
        self.assertIn("`claude plugin marketplace update viagem-br`", linha)

    def test_mudancas_corrigem_o_jeito_de_atualizar_pelo_plugin(self):
        versoes = {bloco.split(" ")[0]: bloco for bloco in self.ler("MUDANCAS.md").split("\n## ")[1:]}
        correcao = versoes.get("1.6.2", "")
        self.assertIn("dois comandos", correcao)
        self.assertIn("claude plugin marketplace update viagem-br", correcao)

    def test_readme_diz_como_chamar_a_skill_em_cada_jeito(self):
        readme = self.ler("README.md")
        self.assertIn("`/viagem-br:viagem-br`", readme)  # pelo plugin, o nome leva o do plugin na frente
        self.assertIn("`/viagem-br`", readme)

    def test_login_do_seats_aero_tem_os_dois_nomes(self):
        pelo_plugin = f"claude mcp login {instalar.nome_no_plugin('seats-aero')}"
        for nome in ("README.md", "references/seats-aero.md", "references/armadilhas.md"):
            with self.subTest(arquivo=nome):
                self.assertIn(pelo_plugin, self.ler(nome))
                self.assertIn("claude mcp login seats-aero", self.ler(nome))

    def test_skill_reconhece_a_ferramenta_que_vem_do_plugin(self):
        self.assertIn("`mcp__plugin_viagem-br_seats-aero__get_flights`", self.ler("SKILL.md"))

    def test_skill_roda_o_instalador_a_pedido_e_sabe_do_plugin(self):
        skill = self.ler("SKILL.md")
        descricao = re.search(r"^description: (.+)$", skill, re.MULTILINE).group(1)
        self.assertIn("instalar, conferir ou atualizar a Viagem BR", descricao)
        requisito = skill.split("## Pré-requisito")[1].split("\n## ")[0]
        for trecho in ("tempo limite de 10 minutos", "Pelo plugin, o `seats-aero` já vem ligado",
                       "fecha e abre de novo"):
            with self.subTest(trecho=trecho):
                self.assertIn(trecho, requisito)

    def test_pasta_da_skill_nao_leva_arquivo_de_plugin(self):
        # com .claude-plugin ou .mcp.json aqui dentro, o arquivo .skill descompactado em
        # ~/.claude/skills viraria plugin por conta própria e ligaria o seats-aero sem o instalador
        for nome in (".claude-plugin", ".mcp.json"):
            with self.subTest(nome=nome):
                self.assertFalse((PASTA / nome).exists())

    def test_mudancas_contam_do_plugin_na_versao_em_que_ele_entrou(self):
        versoes = {bloco.split(" ")[0]: bloco for bloco in self.ler("MUDANCAS.md").split("\n## ")[1:]}
        self.assertIn("plugin", versoes["1.6.0"])
        self.assertIn("viagem-br.skill", versoes["1.6.0"])  # e diz que o arquivo continua valendo

    def test_sem_travessao_nos_textos(self):
        for nome in [*self.ARQUIVOS, "exemplo/pesquisa-exemplo.md"]:
            with self.subTest(arquivo=nome):
                self.assertNotIn(chr(0x2014), self.ler(nome))


@unittest.skipUnless(TEM_PLUGIN, "instalada pelo arquivo .skill: não há plugin em volta desta pasta")
class TestPlugin(unittest.TestCase):
    """Os arquivos que fazem do repositório um plugin do Claude Code e o catálogo dele mesmo."""

    @staticmethod
    def json_de(*partes):
        return json.loads(RAIZ_DO_PLUGIN.joinpath(*partes).read_text(encoding="utf-8"))

    def setUp(self):
        self.manifesto = self.json_de(".claude-plugin", "plugin.json")
        self.readme_da_raiz = (RAIZ_DO_PLUGIN / "README.md").read_text(encoding="utf-8")

    def test_versao_do_plugin_e_a_do_topo_das_mudancas(self):
        # o Claude Code só entrega atualização do plugin quando a versão do plugin.json muda
        topo = re.search(r"^## (\d+\.\d+\.\d+) \(", (PASTA / "MUDANCAS.md").read_text(encoding="utf-8"),
                         re.MULTILINE)
        self.assertEqual(self.manifesto["version"], topo.group(1))

    def test_nome_do_plugin_e_o_da_skill_e_o_do_instalador(self):
        self.assertEqual(self.manifesto["name"], "viagem-br")
        self.assertEqual(self.manifesto["name"], PASTA.name)
        self.assertEqual(self.manifesto["name"], instalar.PLUGIN)

    def test_catalogo_tem_um_plugin_so_apontando_pra_raiz(self):
        catalogo = self.json_de(".claude-plugin", "marketplace.json")
        self.assertEqual(catalogo["name"], "viagem-br")  # é o que vem depois do @ no comando de instalar
        self.assertTrue(catalogo["owner"]["name"])
        # sem versão aqui: a do plugin.json é a que vale, e duas versões brigam
        self.assertEqual(catalogo["plugins"], [{"name": self.manifesto["name"], "source": "./"}])

    def test_plugin_liga_so_o_seats_aero(self):
        # o google-flights é compilado no computador da pessoa: fica com o instalador
        servidores = self.json_de(".mcp.json")["mcpServers"]
        self.assertEqual(tuple(servidores), instalar.SERVIDORES_DO_PLUGIN)
        self.assertEqual(servidores["seats-aero"], {"type": "http", "url": instalar.URL_SEATS})

    def test_skill_fica_onde_o_plugin_procura(self):
        self.assertEqual(PASTA, RAIZ_DO_PLUGIN / "skills" / self.manifesto["name"])
        self.assertNotIn("skills", self.manifesto)  # caminho padrão, sem desvio no manifesto
        self.assertFalse((RAIZ_DO_PLUGIN / "SKILL.md").exists())

    def test_readme_da_raiz_tem_os_dois_comandos(self):
        self.assertRegex(self.readme_da_raiz, r"(?m)^/plugin marketplace add [\w.-]+/viagem-br$")
        self.assertRegex(self.readme_da_raiz, r"(?m)^/plugin install viagem-br@viagem-br$")
        self.assertIn("roda o instalador da Viagem BR", self.readme_da_raiz)

    def test_readme_da_raiz_atualiza_pelo_catalogo_antes(self):
        # o nome depois de `marketplace update` e depois do @ é o do catálogo
        catalogo = self.json_de(".claude-plugin", "marketplace.json")["name"]
        self.assertEqual(comandos_de_atualizar(self.readme_da_raiz),
                         [f"claude plugin marketplace update {catalogo}",
                          f"claude plugin update {self.manifesto['name']}@{catalogo}"])

    def test_endereco_do_repositorio_e_um_so(self):
        guia = (PASTA / "README.md").read_text(encoding="utf-8")
        enderecos = set(re.findall(r"plugin marketplace add ([\w.-]+/[\w.-]+)", self.readme_da_raiz + guia))
        self.assertEqual(len(enderecos), 1)
        endereco = enderecos.pop()
        for campo in ("repository", "homepage"):
            with self.subTest(campo=campo):
                self.assertEqual(self.manifesto[campo], f"https://github.com/{endereco}")

    def test_readme_da_raiz_aponta_pra_arquivos_que_existem(self):
        citados = re.findall(r"\]\((?!https?://)([^)#]+)", self.readme_da_raiz)
        self.assertIn("skills/viagem-br/README.md", citados)
        for citado in citados:
            with self.subTest(citado=citado):
                self.assertTrue((RAIZ_DO_PLUGIN / citado).exists())

    def test_readme_da_raiz_fala_do_login_com_o_nome_do_plugin(self):
        self.assertIn(f"claude mcp login {instalar.nome_no_plugin('seats-aero')}", self.readme_da_raiz)

    def test_arquivos_do_plugin_sem_travessao_e_sem_chave(self):
        arquivos = [RAIZ_DO_PLUGIN / "README.md", RAIZ_DO_PLUGIN / ".mcp.json",
                    *sorted((RAIZ_DO_PLUGIN / ".claude-plugin").iterdir())]
        for arq in arquivos:
            texto = arq.read_text(encoding="utf-8")
            with self.subTest(arquivo=arq.name):
                self.assertNotIn(chr(0x2014), texto)
                self.assertIsNone(audit._CHAVE_RE.search(texto))


class TestAudit(unittest.TestCase):
    def setUp(self):
        self.bom = EXEMPLO.read_text(encoding="utf-8")

    def test_exemplo_valido(self):
        self.assertEqual(audit.auditar(self.bom), [])

    def test_sem_avisos(self):
        viol = audit.auditar(self.bom.replace("## AVISOS", "## X"))
        self.assertTrue(any("AVISOS ausente" in v for v in viol))

    def test_avisos_sem_linha_marcador(self):
        sem_marcador = "\n".join(
            l for l in self.bom.splitlines() if not l.lstrip().startswith(">>"))
        viol = audit.auditar(sem_marcador)
        self.assertTrue(any("AVISOS sem linha" in v for v in viol))

    def test_celula_omitida(self):
        viol = audit.auditar(self.bom.replace("milhas × executiva", "milhas × removida"))
        self.assertTrue(any("célula" in v.lower() for v in viol))

    def test_celula_sem_piso_densidade(self):
        viol = audit.auditar(self.bom.replace("R$ 7.431 · 11 diretas/semana", "R$ 7.431"))
        self.assertTrue(any("piso" in v for v in viol))

    def test_celula_vazia_marcada_ok(self):
        viol = audit.auditar(self.bom.replace("R$ 14.980 · 4 opções/dia", "sem voo na data"))
        self.assertEqual(viol, [])

    def test_celula_ferramenta_bloqueada_ok(self):
        viol = audit.auditar(
            self.bom.replace("R$ 14.980 · 4 opções/dia", "sem dado: ferramenta bloqueada"))
        self.assertEqual(viol, [])

    def test_rota_domestica_sem_executiva_passa(self):
        # em rota doméstica a executiva não é pesquisada: as duas células saem marcadas, sem chamada
        domestica = (self.bom
                     .replace("R$ 14.980 · 4 opções/dia", "não pesquisada: rota doméstica")
                     .replace("390k milhas + R$ 350 · 2 voos", "não pesquisada: rota doméstica"))
        self.assertEqual(audit.auditar(domestica), [])

    def test_celula_de_executiva_em_branco_continua_reprovada(self):
        viol = audit.auditar(self.bom.replace("R$ 14.980 · 4 opções/dia", "não pesquisada"))
        self.assertTrue(any("dinheiro × executiva" in v for v in viol))

    def test_programa_fora_do_seats_aero_tem_marcador_proprio(self):
        # LATAM Pass não está no seats.aero: "sem estoque" afirmaria o que ninguém conferiu
        viol = audit.auditar(self.bom.replace("390k milhas + R$ 350 · 2 voos",
                                              "sem dado: programa fora do seats.aero"))
        self.assertEqual(viol, [])

    def test_exemplo_nao_chama_programa_sem_cobertura_de_sem_estoque(self):
        linhas_latam = [l for l in self.bom.splitlines() if "LATAM Pass" in l and l.startswith("|")]
        self.assertTrue(linhas_latam)
        for linha in linhas_latam:
            self.assertIn("sem dado: programa fora do seats.aero", linha)
            self.assertNotIn("sem estoque no cache", linha)

    def test_celula_em_pontos_ou_avios_ok(self):
        for piso in ("96k pontos + taxa desconhecida · 3 voos", "20 mil Avios + taxa desconhecida · 3 voos"):
            with self.subTest(piso=piso):
                self.assertEqual(audit.auditar(self.bom.replace("128k milhas + R$ 380 · 3 voos", piso)), [])

    def test_exemplo_tem_uma_linha_por_programa(self):
        self.assertNotIn("2 programas", self.bom)
        self.assertIn("milhas × econômica (Smiles)", self.bom)

    RECORTE = ("## AVISOS\n\n>> recorte: só a data mais barata\n\n## TABELA\n\n"
               "| dinheiro × econômica | R$ 2.080 · 5 opções |\n\n## VEREDITO\n\nVoar dia 18.\n\n"
               "## PRÓXIMOS PASSOS\n\nConferir o preço.\n")

    def test_recorte_nao_cobra_a_matriz(self):
        self.assertEqual(audit.auditar(self.RECORTE, recorte=True), [])

    def test_sem_recorte_continua_cobrando_a_matriz(self):
        self.assertTrue(any("célula ausente" in v for v in audit.auditar(self.RECORTE)))

    def test_recorte_ainda_exige_avisos_e_veredito(self):
        for secao in ("## AVISOS", "## VEREDITO"):
            with self.subTest(secao=secao):
                viol = audit.auditar(self.RECORTE.replace(secao, "## X"), recorte=True)
                self.assertTrue(any("ausente" in v for v in viol))

    def test_recorte_confere_a_celula_que_aparece(self):
        viol = audit.auditar(self.RECORTE.replace("R$ 2.080 · 5 opções", "R$ 2.080"), recorte=True)
        self.assertTrue(any("piso" in v for v in viol))

    def test_recorte_ainda_barra_chave_de_api(self):
        chave = "pro_" + "a" * 24
        viol = audit.auditar(self.RECORTE.replace("Voar dia 18.", chave), recorte=True)
        self.assertTrue(any("chave" in v for v in viol))

    def test_linha_de_comando_com_recorte(self):
        with tempfile.TemporaryDirectory() as td:
            arq = Path(td) / "saida.md"
            arq.write_text(self.RECORTE, encoding="utf-8")
            with mock.patch.object(sys, "argv", ["audit.py", "--recorte", str(arq)]), \
                    self.assertRaises(SystemExit) as fim, contextlib.redirect_stdout(io.StringIO()):
                audit.main()
        self.assertEqual(fim.exception.code, 0)

    def so_com(self, marcador):
        """SAÍDA em que a única linha de `milhas × executiva` traz só esse marcador."""
        linhas = [l for l in self.bom.splitlines() if not (l.startswith("|") and "LATAM Pass" in l)]
        return "\n".join(linhas).replace("390k milhas + R$ 350 · 2 voos", marcador)

    def test_marcador_de_preco_alto_escondido(self):
        # 2026-11-09: `filtered` é emissão dinâmica cara que o seats.aero esconde, não falta de assento
        self.assertEqual(audit.auditar(self.so_com("preço alto, escondido pelo seats.aero")), [])

    def test_marcador_de_rota_nao_monitorada(self):
        self.assertEqual(audit.auditar(self.so_com("sem dado: rota não monitorada pelo seats.aero")), [])

    def test_marcador_inventado_continua_reprovado(self):
        viol = audit.auditar(self.so_com("não achei nada"))
        self.assertTrue(any("milhas × executiva" in v for v in viol))

    def test_celula_sem_login_ok(self):
        viol = audit.auditar(
            self.bom.replace("390k milhas + R$ 350 · 2 voos", "sem dado: seats.aero sem login"))
        self.assertEqual(viol, [])

    def test_veredito_depois_da_tabela(self):
        texto = self.bom.split("## TABELA")
        viol = audit.auditar("## VEREDITO\nok\n\n## TABELA" + texto[1])
        self.assertTrue(any("VEREDITO" in v for v in viol))

    def test_sem_secao_milhas(self):
        self.assertIn("MILHAS", "".join(audit.auditar(self.bom.replace("## MILHAS", "## Y"))))

    def test_falta_declarada_no_cabecalho_sem_aviso(self):
        viol = audit.auditar(self.bom.replace(">> [FALTA: PAX]", ">> PAX não informado"))
        self.assertTrue(any("[FALTA:" in v for v in viol))

    def test_chave_api_exposta(self):
        # valor fictício montado só na hora do teste: nenhum arquivo do pacote guarda formato de chave
        ficticia = "pro_" + "FICTICIA" * 3
        viol = audit.auditar(self.bom + f"\nchave: {ficticia}\n")
        self.assertTrue(any("chave de API" in v for v in viol))


class TestPonteMcp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory()
        falso = Path(cls.pasta.name) / "servidor_falso.py"
        falso.write_text(SERVIDOR_FALSO, encoding="utf-8")
        cls.env = {"VIAGEM_BR_CMD_GOOGLE_FLIGHTS": json.dumps([sys.executable, str(falso)])}

    @classmethod
    def tearDownClass(cls):
        cls.pasta.cleanup()

    def rodar(self, *args):
        saida, erro = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.env), \
                contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = ponte_mcp.main(list(args))
        return codigo, saida.getvalue(), erro.getvalue()

    def test_servidor_nao_herda_segredo_do_ambiente(self):
        ambiente = {**self.env, "PATH": "/caminho/teste", "ANTHROPIC_API_KEY": "segredo", "MINHA_SENHA": "segredo"}
        with mock.patch.dict(os.environ, ambiente):
            _, env = ponte_mcp.comando("google-flights")
        self.assertEqual(env["PATH"], "/caminho/teste")
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("MINHA_SENHA", env)

    def test_skill_proibe_compra_emissao_e_transferencia(self):
        regras = (PASTA / "SKILL.md").read_text(encoding="utf-8").split("Regras de segurança:")[1][:2500]
        self.assertIn("Nunca compre, emita, reserve ou transfira pontos", regras)

    def test_chamada_devolve_texto_e_ignora_log_solto(self):
        codigo, saida, _ = self.rodar("google-flights", "eco", '{"texto": "GRU-LIS"}')
        self.assertEqual(codigo, 0)
        self.assertIn("GRU-LIS", saida)
        self.assertIn("[image omitido]", saida)

    def test_lista_mostra_ferramentas_e_parametros(self):
        codigo, saida, _ = self.rodar("google-flights", "--lista")
        self.assertEqual(codigo, 0)
        self.assertIn("eco(texto)", saida)

    def test_erro_da_ferramenta_sai_1_no_stderr(self):
        codigo, saida, erro = self.rodar("google-flights", "quebra", "{}")
        self.assertEqual((codigo, saida), (1, ""))
        self.assertIn("ferramenta falhou", erro)

    def test_json_invalido_sai_2(self):
        codigo, _, erro = self.rodar("google-flights", "eco", "{nada")
        self.assertEqual(codigo, 2)
        self.assertIn("JSON", erro)

    def test_argumento_que_nao_e_objeto_sai_2(self):
        self.assertEqual(self.rodar("google-flights", "eco", "[1, 2]")[0], 2)

    def test_servidor_desconhecido(self):
        with self.assertRaises(SystemExit) as ctx:
            ponte_mcp.comando("kayak")
        self.assertIn("desconhecido", str(ctx.exception))

    def test_servidor_que_morre_relata_e_nao_trava(self):
        morto = [sys.executable, "-c", "import sys; sys.stderr.write('sem chave\\n'); sys.exit(3)"]
        with self.assertRaises(SystemExit) as ctx:
            ponte_mcp.chamar(morto, None, "tools/list", timeout=10)
        self.assertIn("encerrou", str(ctx.exception))
        self.assertIn("sem chave", str(ctx.exception))

    def test_seats_aero_e_o_mcp_oficial_por_http(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VIAGEM_BR_CMD_SEATS_AERO", None)
            cmd, _ = ponte_mcp.comando("seats-aero")
        self.assertEqual(cmd, "https://seats.aero/mcp")

    def test_google_flights_na_pasta_do_readme(self):
        with tempfile.TemporaryDirectory() as td:
            indice = Path(td) / "mcp" / "google-flights-mcp" / "dist" / "index.js"
            indice.parent.mkdir(parents=True)
            indice.write_text("", encoding="utf-8")
            def achar(nome, path=None):
                return None if nome == "google-flights-mcp" else "/bin/node"
            with mock.patch.object(ponte_mcp.shutil, "which", achar), \
                    mock.patch.object(ponte_mcp.Path, "home", lambda: Path(td)):
                cmd, _ = ponte_mcp.comando("google-flights")
        self.assertEqual(cmd, ["/bin/node", str(indice)])

    def test_google_flights_ausente_aponta_o_readme(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.dict(os.environ, {"VIAGEM_BR_CMD_GOOGLE_FLIGHTS": ""}), \
                mock.patch.object(ponte_mcp.shutil, "which", lambda nome, path=None: None), \
                mock.patch.object(ponte_mcp.Path, "home", lambda: Path(td)):
            with self.assertRaises(SystemExit) as ctx:
                ponte_mcp.comando("google-flights")
        self.assertIn("README", str(ctx.exception))


class _HandlerMcp(http.server.BaseHTTPRequestHandler):
    """Servidor MCP falso por HTTP: JSON puro ou SSE, conforme o nome da ferramenta."""
    sessoes_vistas = []

    def log_message(self, *args):
        pass

    def responder(self, status, corpo, tipo):
        dados = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Mcp-Session-Id", "sessao-1")
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):
        msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _HandlerMcp.sessoes_vistas.append(self.headers.get("Mcp-Session-Id"))
        if "id" not in msg:
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if msg["method"] == "initialize":
            self.responder(200, json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {}}), "application/json")
            return
        nome = msg["params"].get("name")
        if nome == "http500":
            self.responder(500, "erro", "text/plain")
            return
        res = {"jsonrpc": "2.0", "id": msg["id"],
               "result": {"content": [{"type": "text", "text": f"resposta de {nome}"}]}}
        if nome == "estruturado":
            res["result"]["structuredContent"] = {"status": "results", "truncated_by": 7}
        if nome == "sse":
            self.responder(200, f"event: message\ndata: {json.dumps(res)}\n\n", "text/event-stream")
        else:
            self.responder(200, json.dumps(res), "application/json")


class TestPonteHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _HandlerMcp)
        cls.url = f"http://127.0.0.1:{cls.servidor.server_address[1]}/mcp"
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.servidor.shutdown()
        cls.servidor.server_close()

    def chamar(self, nome):
        return ponte_mcp.chamar(self.url, None, "tools/call", {"name": nome, "arguments": {}}, timeout=10)

    def test_resposta_em_json(self):
        self.assertEqual(ponte_mcp.texto(self.chamar("json")), "resposta de json")

    def test_resposta_em_sse(self):
        self.assertEqual(ponte_mcp.texto(self.chamar("sse")), "resposta de sse")

    def test_conteudo_estruturado_tem_prioridade(self):
        self.assertEqual(json.loads(ponte_mcp.texto(self.chamar("estruturado"))),
                         {"status": "results", "truncated_by": 7})

    def test_devolve_o_id_da_sessao(self):
        _HandlerMcp.sessoes_vistas.clear()
        self.chamar("json")
        self.assertEqual(_HandlerMcp.sessoes_vistas, [None, "sessao-1", "sessao-1"])

    def test_erro_http_vira_mensagem(self):
        with self.assertRaises(SystemExit) as ctx:
            self.chamar("http500")
        self.assertIn("500", str(ctx.exception))

    def test_sem_conexao_vira_mensagem(self):
        with self.assertRaises(SystemExit) as ctx:
            ponte_mcp.chamar("http://127.0.0.1:9/mcp", None, "tools/list", timeout=5)
        self.assertIn("sem conexão", str(ctx.exception))

    def test_aviso_de_sem_login_vai_no_stderr(self):
        saida, erro = io.StringIO(), io.StringIO()
        with mock.patch.object(ponte_mcp, "URL_SEATS_AERO", self.url), \
                mock.patch.object(ponte_mcp, "comando", lambda s: (self.url, None)), \
                contextlib.redirect_stdout(saida), contextlib.redirect_stderr(erro):
            codigo = ponte_mcp.main(["seats-aero", "json", "{}"])
        self.assertEqual(codigo, 0)
        self.assertIn("60 dias", erro.getvalue())
        self.assertNotIn("60 dias", saida.getvalue())


class _ComputadorFalso:
    """Finge o computador de quem instala: quais ferramentas existem e o que cada comando responde.
    Nada aqui toca rede, Node, Git ou a configuração real do Claude Code."""

    def __init__(self, pasta, ferramentas=("node", "git", "npm", "claude"), node="v24.15.0",
                 ligados=(), do_plugin=(), remoto=None, commit=None, build_ok=True, status="✓ Connected"):
        self.pasta = pasta
        self.ferramentas = set(ferramentas)
        self.node = node
        self.ligados = list(ligados)  # servidores ligados pela própria pessoa (claude mcp add)
        self.do_plugin = set(do_plugin)  # servidores que o plugin instalado liga sozinho
        self.remoto = remoto or instalar.REPO_GF
        self.commit = commit  # commit em que a pasta já está, se ela existir
        self.build_ok = build_ok
        self.status = status
        self.chamadas = []

    def achar(self, nome):
        return f"/falso/{nome}" if nome in self.ferramentas else None

    def feitas(self, *trecho):
        """Chamadas que contêm esse trecho, em ordem (ex.: feitas("mcp", "add"))."""
        n = len(trecho)
        return [c for c in self.chamadas if any(tuple(c[i:i + n]) == trecho for i in range(len(c)))]

    def rodar(self, cmd, cwd=None):
        cmd = [str(parte) for parte in cmd]
        self.chamadas.append(cmd)
        nome, resto = Path(cmd[0]).name, cmd[1:]
        if nome == "node" and resto == ["--version"]:
            return 0, self.node
        if nome == "git" and resto[:1] == ["clone"]:
            self.pasta.mkdir(parents=True)
            self.commit = "f" * 40  # o clone cai na ponta da branch, não no commit fixado
            return 0, ""
        if nome == "git" and resto[2:] == ["remote", "get-url", "origin"]:
            return 0, self.remoto + "\n"
        if nome == "git" and resto[2:] == ["rev-parse", "HEAD"]:
            return 0, self.commit + "\n"
        if nome == "git" and "checkout" in resto:
            self.commit = resto[-1]
            return 0, ""
        if nome == "git" and "fetch" in resto:
            return 0, ""
        if nome == "npm" and resto == ["ci"]:
            return 0, ""
        if nome == "npm" and resto == ["run", "build"]:
            if not self.build_ok:
                return 1, "erro de build inventado"
            (self.pasta / "dist").mkdir(exist_ok=True)
            (self.pasta / "dist" / "index.js").write_text("// falso", encoding="utf-8")
            return 0, "Build success"
        if nome == "claude" and resto[:2] == ["mcp", "get"]:
            pedido, prefixo = resto[2], f"plugin:{instalar.PLUGIN}:"
            if pedido in self.ligados:
                return 0, f"{pedido}:\n  Scope: User config\n  Status: {self.status}\n"
            # Visto no Claude Code 2.1.309: o servidor do plugin atende por plugin:<plugin>:<nome>
            # e some da lista quando a pessoa já ligou o mesmo endereço por conta própria.
            if pedido.startswith(prefixo):
                base = pedido[len(prefixo):]
                if base in self.do_plugin and base not in self.ligados:
                    return 0, (f"{pedido}:\n  Scope: Dynamic config (from command line)\n"
                               f"  Status: {self.status}\n  Type: http\n")
            return 1, f'No MCP server named "{pedido}".'
        if nome == "claude" and resto[:2] == ["mcp", "add"]:
            self.ligados.append("google-flights" if "google-flights" in resto else
                                next(n for n in ("seats-aero", *instalar.OPCIONAIS) if n in resto))
            return 0, "Added"
        raise AssertionError(f"comando inesperado no teste: {cmd}")


class TestInstalador(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.pasta = Path(td.name) / "mcp" / "google-flights-mcp"
        self.saida = []
        self.respostas_dos_servidores = []

    def pc(self, **como):
        return _ComputadorFalso(self.pasta, **como)

    def chamar_falso(self, cmd, env, metodo, params=None, timeout=None):
        self.respostas_dos_servidores.append(cmd)
        return {"content": [{"type": "text", "text": "LIS - Lisbon Humberto Delgado Airport"}]}

    def instalador(self, pc, chamar=None):
        return instalar.Instalador(rodar=pc.rodar, achar=pc.achar, chamar=chamar or self.chamar_falso,
                                   pasta_gf=self.pasta, dizer=self.saida.append)

    def texto(self):
        return "\n".join(self.saida)

    def test_do_zero_baixa_no_commit_fixado_compila_e_liga_os_dois_servidores(self):
        pc = self.pc()
        self.assertEqual(self.instalador(pc).instalar(), 0)
        self.assertEqual(len(pc.feitas("clone")), 1)
        self.assertIn(instalar.REPO_GF, pc.feitas("clone")[0])
        self.assertEqual(pc.commit, instalar.COMMIT_GF)
        self.assertEqual(len(pc.feitas("ci")), 1)
        self.assertEqual(len(pc.feitas("run", "build")), 1)
        google, seats = pc.feitas("mcp", "add")
        # `node` sem caminho, como no passo manual do README: sobrevive a trocar a versão do Node
        self.assertEqual(google[-3:], ["--", "node", str(self.pasta / "dist" / "index.js")])
        self.assertIn("google-flights", google)
        self.assertEqual(seats[-2:], ["seats-aero", instalar.URL_SEATS])
        self.assertIn("http", seats)
        for cmd in (google, seats):
            self.assertEqual(cmd[cmd.index("--scope") + 1], "user")
        self.assertIn("Tudo certo", self.texto())

    def test_padrao_nao_liga_os_opcionais(self):
        pc = self.pc()
        self.instalador(pc).instalar()
        self.assertEqual(sorted(pc.ligados), ["google-flights", "seats-aero"])

    def test_com_opcionais_liga_os_tres(self):
        pc = self.pc()
        self.assertEqual(self.instalador(pc).instalar(opcionais=True), 0)
        self.assertEqual(sorted(pc.ligados), ["google-flights", "kiwi", "seats-aero", "skiplagged", "trivago"])
        kiwi = next(c for c in pc.feitas("mcp", "add") if "kiwi" in c)
        self.assertEqual(kiwi[-1], instalar.OPCIONAIS["kiwi"])

    def test_rodar_de_novo_nao_baixa_nao_compila_e_nao_liga_outra_vez(self):
        pc = self.pc()
        self.instalador(pc).instalar()
        pc.chamadas.clear()
        self.assertEqual(self.instalador(pc).instalar(), 0)
        for trecho in (("clone",), ("ci",), ("run", "build"), ("mcp", "add"), ("checkout",)):
            with self.subTest(trecho=trecho):
                self.assertEqual(pc.feitas(*trecho), [])

    def test_node_antigo_para_antes_de_baixar_qualquer_coisa(self):
        pc = self.pc(node="v20.11.1")
        self.assertEqual(self.instalador(pc).instalar(), 1)
        self.assertEqual(pc.feitas("clone"), [])
        self.assertEqual(pc.feitas("mcp", "add"), [])
        self.assertIn("nodejs.org", self.texto())
        self.assertIn("22.12", self.texto())

    def test_node_22_11_ainda_e_antigo_e_22_12_serve(self):
        self.assertEqual(self.instalador(self.pc(node="v22.11.0")).instalar(), 1)
        self.assertEqual(self.instalador(self.pc(node="v22.12.0")).instalar(), 0)

    def test_ferramenta_faltando_lista_todas_e_para(self):
        pc = self.pc(ferramentas=("node", "npm"))
        self.assertEqual(self.instalador(pc).instalar(), 1)
        self.assertEqual(pc.feitas("clone"), [])
        self.assertIn("Git", self.texto())
        self.assertIn("Claude Code", self.texto())

    def test_pasta_de_outro_repositorio_para_sem_mexer(self):
        self.pasta.mkdir(parents=True)
        (self.pasta / "meu-arquivo.txt").write_text("não apague", encoding="utf-8")
        pc = self.pc(remoto="https://github.com/outra-pessoa/outra-coisa.git", commit="a" * 40)
        self.assertEqual(self.instalador(pc).instalar(), 1)
        self.assertTrue((self.pasta / "meu-arquivo.txt").exists())
        for trecho in (("checkout",), ("ci",), ("mcp", "add")):
            self.assertEqual(pc.feitas(*trecho), [])
        self.assertIn(str(self.pasta), self.texto())

    def test_pasta_em_outro_commit_volta_pro_fixado_e_recompila(self):
        self.pasta.mkdir(parents=True)
        (self.pasta / "dist").mkdir()
        (self.pasta / "dist" / "index.js").write_text("// versão antiga", encoding="utf-8")
        pc = self.pc(commit="b" * 40)
        self.assertEqual(self.instalador(pc).instalar(), 0)
        self.assertEqual(pc.feitas("clone"), [])
        self.assertEqual(pc.commit, instalar.COMMIT_GF)
        self.assertEqual(len(pc.feitas("run", "build")), 1)

    def test_endereco_do_repositorio_sem_ponto_git_tambem_vale(self):
        self.pasta.mkdir(parents=True)
        pc = self.pc(remoto=instalar.REPO_GF[:-len(".git")], commit=instalar.COMMIT_GF)
        self.assertEqual(self.instalador(pc).instalar(), 0)

    def test_build_que_falha_para_e_nao_liga_o_servidor(self):
        pc = self.pc(build_ok=False)
        self.assertEqual(self.instalador(pc).instalar(), 1)
        self.assertNotIn("google-flights", pc.ligados)
        self.assertIn("erro de build inventado", self.texto())

    def test_servidor_que_a_pessoa_ja_tinha_nao_e_mexido(self):
        pc = self.pc(ligados=("google-flights", "seats-aero"))
        self.assertEqual(self.instalador(pc).instalar(), 0)
        self.assertEqual(pc.feitas("mcp", "add"), [])
        self.assertIn("não mexi", self.texto())

    # ---- instalada como plugin: o plugin já liga o seats-aero ----

    def test_com_o_plugin_o_seats_aero_nao_e_ligado_de_novo(self):
        pc = self.pc(do_plugin=("seats-aero",))
        self.assertEqual(self.instalador(pc).instalar(), 0)
        ligados_agora = pc.feitas("mcp", "add")
        self.assertEqual(len(ligados_agora), 1)
        self.assertIn("google-flights", ligados_agora[0])
        self.assertEqual(pc.ligados, ["google-flights"])
        self.assertIn("seats-aero: o plugin da Viagem BR já liga", self.texto())
        self.assertIn("Tudo certo", self.texto())

    def test_com_o_plugin_o_login_indicado_leva_o_nome_do_plugin(self):
        pc = self.pc(do_plugin=("seats-aero",))
        self.instalador(pc).instalar()
        self.assertEqual(instalar.nome_no_plugin("seats-aero"), "plugin:viagem-br:seats-aero")
        self.assertIn("claude mcp login plugin:viagem-br:seats-aero\n", self.texto())
        self.assertNotIn("claude mcp login seats-aero\n", self.texto())

    def test_pelo_arquivo_o_login_indicado_continua_o_de_sempre(self):
        pc = self.pc()
        self.instalador(pc).instalar()
        self.assertIn("claude mcp login seats-aero\n", self.texto())
        self.assertNotIn("plugin:", self.texto())

    def test_servidor_que_a_pessoa_ligou_vale_por_cima_do_plugin(self):
        # quem veio do arquivo .skill e depois instalou o plugin: o Claude Code usa o servidor
        # que a pessoa ligou, e é nele que o login dela está
        pc = self.pc(ligados=("seats-aero",), do_plugin=("seats-aero",))
        self.assertEqual(self.instalador(pc).instalar(), 0)
        self.assertEqual([c for c in pc.feitas("mcp", "add") if "seats-aero" in c], [])
        self.assertIn("seats-aero: já estava ligado no Claude Code", self.texto())
        self.assertIn("claude mcp login seats-aero\n", self.texto())
        self.assertIn("seats-aero no Claude Code: ligado e conectado", self.texto())

    def test_conferir_aceita_o_seats_aero_que_vem_do_plugin(self):
        pc = self.pc(do_plugin=("seats-aero",))
        self.instalador(pc).instalar()
        pc.chamadas.clear()
        self.saida.clear()
        self.assertEqual(self.instalador(pc).conferir(), 0)
        self.assertIn("seats-aero no Claude Code: ligado pelo plugin e conectado", self.texto())
        self.assertIn("google-flights no Claude Code: ligado e conectado", self.texto())
        self.assertEqual(pc.feitas("mcp", "add"), [])

    def test_conferir_acusa_servidor_do_plugin_sem_conexao(self):
        pc = self.pc(do_plugin=("seats-aero",), status="✘ Failed to connect")
        self.instalador(pc).instalar()
        self.saida.clear()
        self.assertEqual(self.instalador(pc).conferir(), 1)
        self.assertIn("seats-aero no Claude Code: ligado pelo plugin, mas sem conexão", self.texto())

    def test_so_o_que_o_plugin_liga_e_procurado_pelo_nome_do_plugin(self):
        # google-flights, Kiwi, Skiplagged e Trivago não vêm no plugin: cada pergunta ao
        # Claude Code abre uma conexão, então não se pergunta à toa
        self.assertEqual(instalar.SERVIDORES_DO_PLUGIN, ("seats-aero",))
        pc = self.pc()
        self.instalador(pc).instalar(opcionais=True)
        perguntados = {c[-1] for c in pc.feitas("mcp", "get")}
        self.assertEqual({n for n in perguntados if n.startswith("plugin:")}, {"plugin:viagem-br:seats-aero"})

    def test_avisa_pra_fechar_e_abrir_o_claude_code(self):
        # rodado pelo Claude no meio de uma conversa, o servidor novo só aparece na próxima abertura
        pc = self.pc(do_plugin=("seats-aero",))
        self.instalador(pc).instalar()
        self.assertIn("Feche e abra de novo", self.texto())

    def test_nunca_faz_login_nem_apaga_nem_pede_administrador(self):
        cenarios = (dict(), dict(node="v20.0.0"), dict(build_ok=False), dict(ligados=("google-flights",)),
                    dict(do_plugin=("seats-aero",)), dict(ligados=("seats-aero",), do_plugin=("seats-aero",)))
        for como in cenarios:
            pc = self.pc(**como)
            inst = self.instalador(pc)
            inst.instalar(opcionais=True)
            inst.conferir()
            for cmd in pc.chamadas:
                with self.subTest(como=como, cmd=cmd):
                    self.assertFalse({"login", "logout", "remove", "sudo", "rm", "rmdir"} & set(cmd))
            if self.pasta.exists():
                import shutil
                shutil.rmtree(self.pasta)

    def test_conferir_chama_os_dois_servidores_e_nao_instala_nada(self):
        pc = self.pc()
        self.instalador(pc).instalar()
        pc.chamadas.clear()
        self.respostas_dos_servidores.clear()
        self.assertEqual(self.instalador(pc).conferir(), 0)
        self.assertEqual(self.respostas_dos_servidores,
                         [["/falso/node", str(self.pasta / "dist" / "index.js")], instalar.URL_SEATS])
        for trecho in (("clone",), ("ci",), ("run", "build"), ("mcp", "add")):
            self.assertEqual(pc.feitas(*trecho), [])
        self.assertIn("Tudo certo", self.texto())

    def test_conferir_sem_nada_instalado_diz_o_que_falta_e_sai_com_erro(self):
        pc = self.pc()
        self.assertEqual(self.instalador(pc).conferir(), 1)
        self.assertEqual(pc.feitas("clone"), [])
        self.assertIn("instalar.py", self.texto())

    def test_conferir_acusa_servidor_que_nao_responde(self):
        def chamar_quebrado(cmd, env, metodo, params=None, timeout=None):
            if isinstance(cmd, list):
                raise SystemExit("ERRO: o servidor encerrou em 'initialize'")
            return {"content": [{"type": "text", "text": "{}"}]}
        pc = self.pc()
        self.instalador(pc).instalar()
        self.saida.clear()
        self.assertEqual(self.instalador(pc, chamar=chamar_quebrado).conferir(), 1)
        self.assertIn("o servidor encerrou", self.texto())
        self.assertNotIn("Tudo certo", self.texto())

    def test_conferir_acusa_servidor_ligado_que_nao_conecta_no_claude_code(self):
        pc = self.pc(status="✘ Failed to connect")
        self.instalador(pc).instalar()
        self.saida.clear()
        self.assertEqual(self.instalador(pc).conferir(), 1)
        self.assertIn("Failed to connect", self.texto())

    def test_linha_de_comando(self):
        feito = []

        class Espiao:
            def __init__(self, **_):
                pass

            def instalar(self, opcionais=False):
                feito.append(("instalar", opcionais))
                return 0

            def conferir(self):
                feito.append(("conferir",))
                return 0
        with mock.patch.object(instalar, "Instalador", Espiao):
            self.assertEqual(instalar.main([]), 0)
            self.assertEqual(instalar.main(["--com-opcionais"]), 0)
            self.assertEqual(instalar.main(["--conferir"]), 0)
        self.assertEqual(feito, [("instalar", False), ("instalar", True), ("conferir",)])


if __name__ == "__main__":
    unittest.main()
