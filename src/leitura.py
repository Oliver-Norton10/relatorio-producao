"""Leitura da exportação do ERP (CSV ou Excel) com checagem das colunas obrigatórias."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUNAS_OBRIGATORIAS = [
    "numero_op",
    "codigo_produto",
    "descricao_produto",
    "setor",
    "maquina",
    "qtd_planejada",
    "qtd_produzida",
    "qtd_refugo",
    "data_emissao",
    "data_prevista",
    "data_conclusao",
    "status",
]


class ArquivoInvalidoError(Exception):
    """O arquivo de entrada não tem o formato esperado."""


def ler_exportacao(caminho: str | Path) -> pd.DataFrame:
    """
    Lê o arquivo exatamente como veio, tudo como texto.
    A conversão de tipos fica para a limpeza, onde cada erro é registrado.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise ArquivoInvalidoError(f"Arquivo não encontrado: {caminho}")

    if caminho.suffix.lower() == ".csv":
        df = pd.read_csv(caminho, sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False)
    elif caminho.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(caminho, dtype=str, keep_default_na=False)
    else:
        raise ArquivoInvalidoError(f"Formato não suportado: {caminho.suffix} (use .csv ou .xlsx)")

    df.columns = [c.strip().lower() for c in df.columns]
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        raise ArquivoInvalidoError(f"Colunas obrigatórias ausentes: {', '.join(faltando)}")

    if df.empty:
        raise ArquivoInvalidoError("O arquivo não tem nenhuma linha de dados.")

    return df[COLUNAS_OBRIGATORIAS].copy()
