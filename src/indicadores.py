"""
Cálculo dos indicadores de produção.

Definições usadas (iguais às do README):
- No prazo:   OP encerrada com data de conclusão <= data prevista
- Completa:   quantidade boa (produzida - refugo) >= quantidade planejada
- OTIF:       % de OPs encerradas que foram no prazo E completas
- Atendimento do plano: soma produzida / soma planejada (OPs encerradas)
- Taxa de refugo: refugo / produzido
- Atrasada em aberto: OP não encerrada cuja data prevista já passou
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Indicadores:
    data_referencia: pd.Timestamp
    resumo: dict
    por_setor: pd.DataFrame
    por_maquina: pd.DataFrame
    atrasadas_abertas: pd.DataFrame
    evolucao_semanal: pd.DataFrame


def _pct(parte: float, total: float) -> float:
    return round(parte / total, 4) if total else 0.0


def preparar(df: pd.DataFrame, data_referencia: pd.Timestamp) -> pd.DataFrame:
    d = df.copy()
    d["encerrada"] = d["status"].eq("Encerrada")
    d["qtd_boa"] = d["qtd_produzida"] - d["qtd_refugo"]
    d["no_prazo"] = d["encerrada"] & (d["data_conclusao"] <= d["data_prevista"])
    d["completa"] = d["encerrada"] & (d["qtd_boa"] >= d["qtd_planejada"])
    d["otif"] = d["no_prazo"] & d["completa"]
    d["dias_atraso"] = (d["data_conclusao"] - d["data_prevista"]).dt.days.clip(lower=0)
    d["atrasada_aberta"] = ~d["encerrada"] & (d["data_prevista"] < data_referencia)
    d.loc[d["atrasada_aberta"], "dias_atraso"] = (data_referencia - d["data_prevista"]).dt.days
    return d


def _agrupar(d: pd.DataFrame, chave: list[str]) -> pd.DataFrame:
    enc = d[d["encerrada"]]
    g_total = d.groupby(chave).agg(
        ordens=("numero_op", "count"),
        atrasadas_abertas=("atrasada_aberta", "sum"),
        produzido=("qtd_produzida", "sum"),
        refugo=("qtd_refugo", "sum"),
    )
    g_enc = enc.groupby(chave).agg(
        encerradas=("numero_op", "count"),
        planejado_enc=("qtd_planejada", "sum"),
        produzido_enc=("qtd_produzida", "sum"),
        otif_qtd=("otif", "sum"),
        atraso_medio=("dias_atraso", lambda s: s[s > 0].mean() if (s > 0).any() else 0),
    )
    g = g_total.join(g_enc, how="left").fillna(0)
    g["otif"] = (g["otif_qtd"] / g["encerradas"]).where(g["encerradas"] > 0, 0).round(4)
    g["atendimento_plano"] = (g["produzido_enc"] / g["planejado_enc"]).where(g["planejado_enc"] > 0, 0).round(4)
    g["taxa_refugo"] = (g["refugo"] / g["produzido"]).where(g["produzido"] > 0, 0).round(4)
    g["atraso_medio"] = g["atraso_medio"].round(1)
    colunas = [
        "ordens", "encerradas", "otif", "atendimento_plano", "produzido",
        "refugo", "taxa_refugo", "atraso_medio", "atrasadas_abertas",
    ]
    g = g[colunas].astype({"ordens": int, "encerradas": int, "produzido": int, "refugo": int, "atrasadas_abertas": int})
    return g.reset_index()


def calcular(df: pd.DataFrame, data_referencia: pd.Timestamp | None = None) -> Indicadores:
    if data_referencia is None:
        candidatos = pd.concat([df["data_emissao"], df["data_conclusao"]]).dropna()
        data_referencia = candidatos.max().normalize()
    data_referencia = pd.Timestamp(data_referencia)

    d = preparar(df, data_referencia)
    enc = d[d["encerrada"]]

    resumo = {
        "ordens": int(len(d)),
        "encerradas": int(d["encerrada"].sum()),
        "em_aberto": int((~d["encerrada"]).sum()),
        "atrasadas_abertas": int(d["atrasada_aberta"].sum()),
        "otif": _pct(enc["otif"].sum(), len(enc)),
        "no_prazo": _pct(enc["no_prazo"].sum(), len(enc)),
        "completas": _pct(enc["completa"].sum(), len(enc)),
        "atendimento_plano": _pct(enc["qtd_produzida"].sum(), enc["qtd_planejada"].sum()),
        "produzido": int(d["qtd_produzida"].sum()),
        "refugo": int(d["qtd_refugo"].sum()),
        "taxa_refugo": _pct(d["qtd_refugo"].sum(), d["qtd_produzida"].sum()),
    }

    por_setor = _agrupar(d, ["setor"]).sort_values("otif")
    por_maquina = _agrupar(d, ["setor", "maquina"]).sort_values(["setor", "maquina"])

    atrasadas = (
        d[d["atrasada_aberta"]]
        .sort_values("dias_atraso", ascending=False)[
            ["numero_op", "codigo_produto", "descricao_produto", "setor", "maquina",
             "qtd_planejada", "qtd_produzida", "data_prevista", "dias_atraso", "status"]
        ]
        .reset_index(drop=True)
    )

    semanal = enc.assign(semana=enc["data_conclusao"].dt.to_period("W-SUN").dt.start_time)
    evolucao = (
        semanal.groupby("semana")
        .agg(encerradas=("numero_op", "count"), otif_qtd=("otif", "sum"), produzido=("qtd_produzida", "sum"))
        .reset_index()
    )
    evolucao["otif"] = (evolucao["otif_qtd"] / evolucao["encerradas"]).round(4)
    evolucao = evolucao.drop(columns="otif_qtd")

    return Indicadores(data_referencia, resumo, por_setor, por_maquina, atrasadas, evolucao)
