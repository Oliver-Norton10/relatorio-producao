import pandas as pd
import pytest

from src.indicadores import calcular

REF = pd.Timestamp("2026-07-20")


def op(numero, setor="Corte", planejada=100, produzida=100, refugo=0,
       prevista="2026-07-10", conclusao="2026-07-09", status="Encerrada"):
    return {
        "numero_op": numero,
        "codigo_produto": "PRD-1001",
        "descricao_produto": "Suporte",
        "setor": setor,
        "maquina": "M-01",
        "qtd_planejada": planejada,
        "qtd_produzida": produzida,
        "qtd_refugo": refugo,
        "data_emissao": pd.Timestamp("2026-07-01"),
        "data_prevista": pd.Timestamp(prevista),
        "data_conclusao": pd.Timestamp(conclusao) if conclusao else pd.NaT,
        "status": status,
    }


def test_otif_conta_so_no_prazo_e_completa():
    dados = pd.DataFrame([
        op("1"),                                   # no prazo e completa -> OTIF
        op("2", conclusao="2026-07-15"),           # atrasada
        op("3", produzida=95),                     # incompleta
        op("4", produzida=100, refugo=10),         # refugo deixa incompleta
    ])
    r = calcular(dados, REF).resumo
    assert r["otif"] == pytest.approx(0.25)
    assert r["no_prazo"] == pytest.approx(0.75)
    assert r["completas"] == pytest.approx(0.50)


def test_concluida_no_dia_do_prazo_conta_como_no_prazo():
    r = calcular(pd.DataFrame([op("1", conclusao="2026-07-10")]), REF).resumo
    assert r["otif"] == 1.0


def test_atrasada_em_aberto_e_dias_de_atraso():
    dados = pd.DataFrame([
        op("1", prevista="2026-07-15", conclusao=None, status="Em andamento", produzida=40),
        op("2", prevista="2026-07-25", conclusao=None, status="Em andamento", produzida=40),
    ])
    ind = calcular(dados, REF)
    assert ind.resumo["atrasadas_abertas"] == 1
    assert ind.atrasadas_abertas.loc[0, "numero_op"] == "1"
    assert ind.atrasadas_abertas.loc[0, "dias_atraso"] == 5


def test_taxa_de_refugo_e_atendimento():
    dados = pd.DataFrame([op("1", produzida=110, refugo=11), op("2", produzida=90)])
    r = calcular(dados, REF).resumo
    assert r["taxa_refugo"] == pytest.approx(11 / 200)
    assert r["atendimento_plano"] == pytest.approx(200 / 200)


def test_indicadores_por_setor_separam_os_setores():
    dados = pd.DataFrame([op("1", setor="Corte"), op("2", setor="Solda", conclusao="2026-07-12")])
    setores = calcular(dados, REF).por_setor.set_index("setor")
    assert setores.loc["Corte", "otif"] == 1.0
    assert setores.loc["Solda", "otif"] == 0.0
    assert setores.loc["Solda", "atraso_medio"] == 2.0
