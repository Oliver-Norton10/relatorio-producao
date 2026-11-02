"""Roda o fluxo inteiro: gera dados fictícios, processa e confere o Excel gerado."""

import random
from datetime import date

from openpyxl import load_workbook

from src.gerar_dados import gerar_ordens, salvar_csv, sujar_dados
from src.main import main


def test_fluxo_completo_gera_excel_com_todas_as_abas(tmp_path):
    rng = random.Random(1)
    entrada = tmp_path / "ordens.csv"
    salvar_csv(sujar_dados(gerar_ordens(200, date(2026, 7, 1), 60, rng), rng), entrada)

    codigo = main(["--entrada", str(entrada), "--saida", str(tmp_path / "saida"), "--logs", str(tmp_path / "logs")])

    assert codigo == 0
    gerados = list((tmp_path / "saida").glob("relatorio_producao_*.xlsx"))
    assert len(gerados) == 1
    wb = load_workbook(gerados[0])
    assert wb.sheetnames == ["Resumo", "Por setor", "Evolução semanal", "Atrasadas", "Rejeitados", "Dados tratados"]
    assert wb["Rejeitados"].max_row > 4  # os defeitos inseridos foram detectados
    assert list((tmp_path / "logs").glob("*.log"))


def test_arquivo_inexistente_retorna_erro_sem_quebrar(tmp_path):
    codigo = main(["--entrada", str(tmp_path / "nada.csv"), "--saida", str(tmp_path), "--logs", str(tmp_path / "logs")])
    assert codigo == 1
