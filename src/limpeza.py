"""
Limpeza e validação dos dados.

Regra de ouro: nenhuma linha some sem explicação. Tudo que é descartado vai para
a tabela de rejeitados com o motivo, e aparece no relatório para quem precisar corrigir na origem.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

SETORES_VALIDOS = {"Corte", "Dobra", "Solda", "Pintura", "Montagem"}

# Grafias alternativas conhecidas -> nome oficial
APELIDOS_SETOR = {"Soldagem": "Solda"}


@dataclass
class ResultadoLimpeza:
    dados: pd.DataFrame
    rejeitados: pd.DataFrame
    duplicados_removidos: int
    setores_corrigidos: int


def normalizar_setor(valor: str) -> str:
    texto = " ".join(str(valor).split()).title()
    return APELIDOS_SETOR.get(texto, texto)


def _para_numero(serie: pd.Series) -> pd.Series:
    texto = serie.astype(str).str.strip().str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(texto.replace("", None), errors="coerce")


def _para_data(serie: pd.Series) -> pd.Series:
    return pd.to_datetime(serie.astype(str).str.strip().replace("", None), format="%d/%m/%Y", errors="coerce")


def limpar(bruto: pd.DataFrame) -> ResultadoLimpeza:
    df = bruto.copy()
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # 1. Duplicados exatos
    antes = len(df)
    df = df.drop_duplicates()
    duplicados = antes - len(df)

    # 2. Setor padronizado
    original = df["setor"].copy()
    df["setor"] = df["setor"].map(lambda s: normalizar_setor(s) if s else "")
    corrigidos = int(((original != df["setor"]) & (df["setor"] != "")).sum())

    # 3. Tipos
    numeros = ["qtd_planejada", "qtd_produzida", "qtd_refugo"]
    for col in numeros:
        df[col + "_num"] = _para_numero(df[col])
    datas = ["data_emissao", "data_prevista", "data_conclusao"]
    for col in datas:
        df[col + "_dt"] = _para_data(df[col])

    # 4. Validações: cada linha acumula seus motivos de rejeição
    motivos = pd.Series([[] for _ in range(len(df))], index=df.index)

    def marcar(mascara: pd.Series, motivo: str) -> None:
        for idx in df.index[mascara]:
            motivos[idx].append(motivo)

    marcar(df["numero_op"] == "", "Número da OP vazio")
    marcar(df["setor"] == "", "Setor vazio")
    marcar((df["setor"] != "") & ~df["setor"].isin(SETORES_VALIDOS), "Setor desconhecido")
    marcar(df["qtd_planejada_num"].isna(), "Quantidade planejada inválida")
    marcar(df["qtd_planejada_num"] <= 0, "Quantidade planejada zerada ou negativa")
    marcar(df["qtd_produzida_num"].isna(), "Quantidade produzida inválida")
    marcar(df["qtd_produzida_num"] < 0, "Quantidade produzida negativa")
    marcar(df["qtd_refugo_num"] < 0, "Refugo negativo")
    marcar(df["data_emissao_dt"].isna(), "Data de emissão inválida")
    marcar(df["data_prevista_dt"].isna(), "Data prevista inválida")
    marcar(
        (df["data_conclusao"] != "") & df["data_conclusao_dt"].isna(),
        "Data de conclusão inválida",
    )
    marcar(
        (df["status"] == "Encerrada") & df["data_conclusao_dt"].isna(),
        "OP encerrada sem data de conclusão",
    )

    # Mesma OP com conteúdo diferente: não dá para saber qual está certa
    conflito = df["numero_op"].duplicated(keep=False) & (df["numero_op"] != "")
    marcar(conflito, "OP repetida com dados diferentes")

    invalida = motivos.map(len) > 0
    rejeitados = bruto.loc[df.index[invalida]].copy()
    rejeitados["motivo"] = motivos[invalida].map("; ".join)

    limpos = df.loc[~invalida].copy()
    for col in numeros:
        limpos[col] = limpos[col + "_num"].astype(int)
    for col in datas:
        limpos[col] = limpos[col + "_dt"]
    limpos = limpos.drop(columns=[c for c in limpos.columns if c.endswith(("_num", "_dt"))])
    limpos = limpos.sort_values("numero_op").reset_index(drop=True)

    return ResultadoLimpeza(
        dados=limpos,
        rejeitados=rejeitados.reset_index(drop=True),
        duplicados_removidos=duplicados,
        setores_corrigidos=corrigidos,
    )
