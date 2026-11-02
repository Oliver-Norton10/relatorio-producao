import pandas as pd
import pytest

from src.leitura import COLUNAS_OBRIGATORIAS, ArquivoInvalidoError, ler_exportacao
from src.limpeza import limpar, normalizar_setor


def linha(**sobrescrever) -> dict:
    base = {
        "numero_op": "OP000001",
        "codigo_produto": "PRD-1001",
        "descricao_produto": "Suporte",
        "setor": "Corte",
        "maquina": "CNC-01",
        "qtd_planejada": "100",
        "qtd_produzida": "100",
        "qtd_refugo": "0",
        "data_emissao": "01/07/2026",
        "data_prevista": "10/07/2026",
        "data_conclusao": "09/07/2026",
        "status": "Encerrada",
    }
    base.update(sobrescrever)
    return base


def df(*linhas) -> pd.DataFrame:
    return pd.DataFrame(list(linhas), columns=COLUNAS_OBRIGATORIAS)


@pytest.mark.parametrize(
    "entrada, esperado",
    [("CORTE", "Corte"), ("  corte ", "Corte"), ("Soldagem", "Solda"), ("pintura", "Pintura")],
)
def test_normalizar_setor(entrada, esperado):
    assert normalizar_setor(entrada) == esperado


def test_linha_valida_passa_e_converte_tipos():
    r = limpar(df(linha()))
    assert len(r.dados) == 1 and r.rejeitados.empty
    assert r.dados.loc[0, "qtd_planejada"] == 100
    assert r.dados.loc[0, "data_prevista"] == pd.Timestamp("2026-07-10")


def test_duplicados_exatos_sao_removidos():
    r = limpar(df(linha(), linha()))
    assert r.duplicados_removidos == 1
    assert len(r.dados) == 1


def test_mesma_op_com_dados_diferentes_e_rejeitada():
    r = limpar(df(linha(), linha(qtd_produzida="90")))
    assert r.dados.empty
    assert (r.rejeitados["motivo"] == "OP repetida com dados diferentes").all()


@pytest.mark.parametrize(
    "campo, valor, motivo",
    [
        ("setor", "", "Setor vazio"),
        ("setor", "Almoxarifado", "Setor desconhecido"),
        ("data_prevista", "31/02/2024", "Data prevista inválida"),
        ("qtd_produzida", "-5", "Quantidade produzida negativa"),
        ("qtd_planejada", "0", "Quantidade planejada zerada ou negativa"),
        ("data_conclusao", "", "OP encerrada sem data de conclusão"),
    ],
)
def test_linhas_invalidas_vao_para_rejeitados_com_motivo(campo, valor, motivo):
    r = limpar(df(linha(**{campo: valor})))
    assert r.dados.empty
    assert motivo in r.rejeitados.loc[0, "motivo"]


def test_numero_com_virgula_decimal():
    r = limpar(df(linha(qtd_produzida="1.250", qtd_planejada="1250")))
    assert r.dados.loc[0, "qtd_produzida"] == 1250


def test_arquivo_sem_coluna_obrigatoria(tmp_path):
    arquivo = tmp_path / "ruim.csv"
    arquivo.write_text("numero_op;setor\nOP1;Corte\n", encoding="utf-8")
    with pytest.raises(ArquivoInvalidoError, match="Colunas obrigatórias ausentes"):
        ler_exportacao(arquivo)


def test_arquivo_inexistente():
    with pytest.raises(ArquivoInvalidoError, match="não encontrado"):
        ler_exportacao("nao_existe.csv")
