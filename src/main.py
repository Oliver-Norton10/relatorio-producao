"""
Ponto de entrada: lê a exportação, limpa, calcula e gera o relatório com um único comando.

Uso:
    python -m src.main
    python -m src.main --entrada dados/entrada/ordens_producao.csv --saida dados/saida
    python -m src.main --data-referencia 2026-09-29
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from .indicadores import calcular
from .leitura import ArquivoInvalidoError, ler_exportacao
from .limpeza import limpar
from .relatorio import gerar_excel

log = logging.getLogger("relatorio")


def configurar_log(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"execucao_{datetime.now():%Y%m%d_%H%M%S}.log"
    formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%d/%m/%Y %H:%M:%S")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    for handler in (logging.FileHandler(arquivo, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formato)
        log.addHandler(handler)
    return arquivo


def executar(entrada: Path, pasta_saida: Path, data_referencia: str | None = None) -> Path:
    inicio = time.perf_counter()
    log.info("Lendo %s", entrada)
    bruto = ler_exportacao(entrada)
    log.info("%d linhas lidas", len(bruto))

    resultado = limpar(bruto)
    log.info(
        "Limpeza: %d duplicadas removidas, %d setores padronizados, %d linhas rejeitadas, %d aproveitadas",
        resultado.duplicados_removidos,
        resultado.setores_corrigidos,
        len(resultado.rejeitados),
        len(resultado.dados),
    )
    for motivo, qtd in resultado.rejeitados["motivo"].value_counts().items():
        log.warning("Rejeitadas (%d): %s", qtd, motivo)

    if resultado.dados.empty:
        raise ArquivoInvalidoError("Nenhuma linha válida depois da limpeza. Relatório não gerado.")

    ref = pd.Timestamp(data_referencia) if data_referencia else None
    ind = calcular(resultado.dados, ref)
    r = ind.resumo
    log.info(
        "OTIF %.1f%% | atendimento %.1f%% | refugo %.2f%% | %d OPs atrasadas em aberto",
        r["otif"] * 100, r["atendimento_plano"] * 100, r["taxa_refugo"] * 100, r["atrasadas_abertas"],
    )

    destino = pasta_saida / f"relatorio_producao_{ind.data_referencia:%Y-%m-%d}.xlsx"
    gerar_excel(ind, resultado, len(bruto), destino)
    log.info("Relatório salvo em %s (%.1fs)", destino, time.perf_counter() - inicio)
    return destino


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o relatório de produção a partir da exportação do ERP.")
    parser.add_argument("--entrada", default="dados/entrada/ordens_producao.csv", help="arquivo .csv ou .xlsx")
    parser.add_argument("--saida", default="dados/saida", help="pasta onde o relatório será salvo")
    parser.add_argument("--data-referencia", help="data de corte AAAA-MM-DD (padrão: data mais recente dos dados)")
    parser.add_argument("--logs", default="logs", help="pasta dos arquivos de log")
    args = parser.parse_args(argv)

    arquivo_log = configurar_log(Path(args.logs))
    try:
        executar(Path(args.entrada), Path(args.saida), args.data_referencia)
        return 0
    except ArquivoInvalidoError as erro:
        log.error("%s", erro)
    except Exception:
        log.exception("Erro inesperado. Detalhes completos no log.")
    log.error("Execução falhou. Veja %s", arquivo_log)
    return 1


if __name__ == "__main__":
    sys.exit(main())
