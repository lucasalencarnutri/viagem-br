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

    def test_estimar_com_tabela_de_fabrica_avisa_que_e_media(self):
        saida = self.rodar("--estimar", "--milhas", "70000", "--taxas", "380", "--programa", "smiles")
        self.assertIn("média de referência", saida)

    def test_sem_estimar_exige_dinheiro_e_taxas(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.rodar("--milhas", "50000", "--programa", "Smiles")


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

    def test_nenhum_texto_diz_que_a_azul_some_sem_login(self):
        # 2026-11-09: sem login a Azul apareceu em rota doméstica e pra Lisboa. Ela aparece em parte.
        frases = ("não mostra a Azul", "esconde a Azul", "sem a Azul", "esconde os voos da Azul")
        arquivos = [*self.ARQUIVOS, "scripts/ponte_mcp.py", "scripts/instalar.py"]
        for nome in arquivos:
            texto = self.ler(nome)
            for frase in frases:
                with self.subTest(arquivo=nome, frase=frase):
                    self.assertNotIn(frase, texto)
        for nome in ("SKILL.md", "README.md", "references/seats-aero.md", "scripts/ponte_mcp.py"):
            with self.subTest(arquivo=nome):
                self.assertIn("Azul só em parte", self.ler(nome))

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

    def test_sem_travessao_nos_textos(self):
        for nome in [*self.ARQUIVOS, "exemplo/pesquisa-exemplo.md"]:
            with self.subTest(arquivo=nome):
                self.assertNotIn(chr(0x2014), self.ler(nome))


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
                     .replace("390k milhas + R$ 350 · 2 programas (Azul, Smiles)", "não pesquisada: rota doméstica"))
        self.assertEqual(audit.auditar(domestica), [])

    def test_celula_de_executiva_em_branco_continua_reprovada(self):
        viol = audit.auditar(self.bom.replace("R$ 14.980 · 4 opções/dia", "não pesquisada"))
        self.assertTrue(any("dinheiro × executiva" in v for v in viol))

    def test_programa_fora_do_seats_aero_tem_marcador_proprio(self):
        # LATAM Pass não está no seats.aero: "sem estoque" afirmaria o que ninguém conferiu
        viol = audit.auditar(self.bom.replace("390k milhas + R$ 350 · 2 programas (Azul, Smiles)",
                                              "sem dado: programa fora do seats.aero"))
        self.assertEqual(viol, [])

    def test_exemplo_nao_chama_programa_sem_cobertura_de_sem_estoque(self):
        linhas_latam = [l for l in self.bom.splitlines() if "LATAM Pass" in l and l.startswith("|")]
        self.assertTrue(linhas_latam)
        for linha in linhas_latam:
            self.assertIn("sem dado: programa fora do seats.aero", linha)
            self.assertNotIn("sem estoque no cache", linha)

    def test_celula_sem_login_ok(self):
        viol = audit.auditar(
            self.bom.replace("390k milhas + R$ 350 · 2 programas (Azul, Smiles)", "sem dado: seats.aero sem login"))
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
                 ligados=(), remoto=None, commit=None, build_ok=True, status="✓ Connected"):
        self.pasta = pasta
        self.ferramentas = set(ferramentas)
        self.node = node
        self.ligados = list(ligados)
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
            if resto[2] in self.ligados:
                return 0, f"{resto[2]}:\n  Scope: User config\n  Status: {self.status}\n"
            return 1, f'No MCP server named "{resto[2]}".'
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

    def test_nunca_faz_login_nem_apaga_nem_pede_administrador(self):
        cenarios = (dict(), dict(node="v20.0.0"), dict(build_ok=False), dict(ligados=("google-flights",)))
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
