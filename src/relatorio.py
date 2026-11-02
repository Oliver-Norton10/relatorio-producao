"""Geração do relatório final em Excel, formatado e com gráficos, usando openpyxl."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .indicadores import Indicadores
from .limpeza import ResultadoLimpeza

AZUL = "1F3A5F"
AZUL_CLARO = "E8EEF5"
CINZA = "6B7280"
VERDE = "D1FAE5"
AMARELO = "FEF3C7"
VERMELHO = "FEE2E2"

META_OTIF = 0.85
META_REFUGO = 0.03

FINO = Side(style="thin", color="D1D5DB")
BORDA = Border(left=FINO, right=FINO, top=FINO, bottom=FINO)

TITULOS = {
    "setor": "Setor",
    "maquina": "Máquina",
    "ordens": "OPs",
    "encerradas": "Encerradas",
    "otif": "OTIF",
    "atendimento_plano": "Atend. plano",
    "produzido": "Produzido",
    "refugo": "Refugo",
    "taxa_refugo": "% Refugo",
    "atraso_medio": "Atraso médio (dias)",
    "atrasadas_abertas": "Atrasadas abertas",
    "numero_op": "OP",
    "codigo_produto": "Produto",
    "descricao_produto": "Descrição",
    "qtd_planejada": "Planejado",
    "qtd_produzida": "Produzido",
    "qtd_refugo": "Refugo",
    "data_emissao": "Emissão",
    "data_prevista": "Previsão",
    "data_conclusao": "Conclusão",
    "dias_atraso": "Dias de atraso",
    "status": "Status",
    "semana": "Semana",
    "motivo": "Motivo da rejeição",
}

PERCENTUAIS = {"otif", "atendimento_plano", "taxa_refugo"}
DATAS = {"data_emissao", "data_prevista", "data_conclusao", "semana"}


def _titulo(ws: Worksheet, texto: str, subtitulo: str) -> None:
    ws["A1"] = texto
    ws["A1"].font = Font(size=16, bold=True, color=AZUL)
    ws["A2"] = subtitulo
    ws["A2"].font = Font(size=10, color=CINZA)
    ws.sheet_view.showGridLines = False
    # Impressão: paisagem, ajustada à largura da página
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def _tabela(ws: Worksheet, df: pd.DataFrame, linha_inicial: int = 4) -> tuple[int, int]:
    """Escreve o DataFrame como tabela formatada. Retorna (linha do cabeçalho, última linha)."""
    for j, col in enumerate(df.columns, start=1):
        c = ws.cell(row=linha_inicial, column=j, value=TITULOS.get(col, col))
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDA

    for i, linha in enumerate(df.itertuples(index=False), start=linha_inicial + 1):
        zebra = PatternFill("solid", fgColor=AZUL_CLARO) if (i - linha_inicial) % 2 == 0 else None
        for j, (col, valor) in enumerate(zip(df.columns, linha), start=1):
            if isinstance(valor, pd.Timestamp):
                valor = valor.to_pydatetime() if not pd.isna(valor) else None
            elif pd.isna(valor) if not isinstance(valor, (list, dict)) else False:
                valor = None
            c = ws.cell(row=i, column=j, value=valor)
            c.border = BORDA
            if zebra:
                c.fill = zebra
            if col in PERCENTUAIS:
                c.number_format = "0.0%"
            elif col in DATAS:
                c.number_format = "DD/MM/YYYY"
            elif isinstance(valor, (int, float)):
                c.number_format = "#,##0" if float(valor).is_integer() else "#,##0.0"

    ultima = linha_inicial + len(df)
    ws.freeze_panes = ws.cell(row=linha_inicial + 1, column=1)
    if len(df):
        ws.auto_filter.ref = f"A{linha_inicial}:{get_column_letter(len(df.columns))}{ultima}"
    _ajustar_larguras(ws, df, linha_inicial)
    return linha_inicial, ultima


def _ajustar_larguras(ws: Worksheet, df: pd.DataFrame, linha_inicial: int) -> None:
    for j, col in enumerate(df.columns, start=1):
        titulo = TITULOS.get(col, col)
        maior = max([len(str(titulo))] + [len(str(v)) for v in df[col].head(200)])
        if col in DATAS:
            maior = 12
        ws.column_dimensions[get_column_letter(j)].width = min(max(maior + 3, 10), 60)


def _semaforo(ws: Worksheet, coluna: str, inicio: int, fim: int, meta: float, maior_melhor: bool) -> None:
    faixa = f"{coluna}{inicio}:{coluna}{fim}"
    bom, ruim = ("greaterThanOrEqual", "lessThan") if maior_melhor else ("lessThanOrEqual", "greaterThan")
    ws.conditional_formatting.add(faixa, CellIsRule(operator=bom, formula=[str(meta)], fill=PatternFill("solid", fgColor=VERDE)))
    ws.conditional_formatting.add(faixa, CellIsRule(operator=ruim, formula=[str(meta)], fill=PatternFill("solid", fgColor=VERMELHO)))


def _aba_resumo(wb: Workbook, ind: Indicadores, limpeza: ResultadoLimpeza, linhas_lidas: int) -> None:
    ws = wb.active
    ws.title = "Resumo"
    _titulo(ws, "Relatório de Produção", f"Data de referência: {ind.data_referencia:%d/%m/%Y}  ·  gerado automaticamente")

    r = ind.resumo
    cartoes = [
        ("OTIF", r["otif"], "0.0%", f"Meta {META_OTIF:.0%}", r["otif"] >= META_OTIF),
        ("Atendimento do plano", r["atendimento_plano"], "0.0%", "Produzido / planejado", r["atendimento_plano"] >= 0.98),
        ("Taxa de refugo", r["taxa_refugo"], "0.00%", f"Meta até {META_REFUGO:.0%}", r["taxa_refugo"] <= META_REFUGO),
        ("OPs atrasadas em aberto", r["atrasadas_abertas"], "#,##0", "Prazo vencido e não encerradas", r["atrasadas_abertas"] == 0),
    ]
    for k, (nome, valor, fmt, nota, ok) in enumerate(cartoes):
        col = 1 + k * 2
        letra = get_column_letter(col)
        ws.merge_cells(start_row=4, start_column=col, end_row=4, end_column=col + 1)
        ws.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col + 1)
        ws.merge_cells(start_row=6, start_column=col, end_row=6, end_column=col + 1)
        cor = VERDE if ok else VERMELHO
        for linha in (4, 5, 6):
            for c in (col, col + 1):
                ws.cell(row=linha, column=c).fill = PatternFill("solid", fgColor=cor)
        ws[f"{letra}4"] = nome
        ws[f"{letra}4"].font = Font(size=10, bold=True, color=CINZA)
        ws[f"{letra}5"] = valor
        ws[f"{letra}5"].number_format = fmt
        ws[f"{letra}5"].font = Font(size=22, bold=True, color=AZUL)
        ws[f"{letra}6"] = nota
        ws[f"{letra}6"].font = Font(size=9, color=CINZA)
        for linha in (4, 5, 6):
            ws[f"{letra}{linha}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[5].height = 34
    for c in range(1, 9):
        ws.column_dimensions[get_column_letter(c)].width = 15

    ws["A8"] = "Números gerais"
    ws["A8"].font = Font(size=12, bold=True, color=AZUL)
    gerais = [
        ("Ordens analisadas", r["ordens"]),
        ("Encerradas", r["encerradas"]),
        ("Em aberto", r["em_aberto"]),
        ("Encerradas no prazo", r["no_prazo"]),
        ("Encerradas completas", r["completas"]),
        ("Peças produzidas", r["produzido"]),
        ("Peças refugadas", r["refugo"]),
    ]
    for i, (nome, valor) in enumerate(gerais, start=9):
        ws.cell(row=i, column=1, value=nome)
        c = ws.cell(row=i, column=3, value=valor)
        c.number_format = "0.0%" if isinstance(valor, float) else "#,##0"
        c.font = Font(bold=True)

    ws["E8"] = "Qualidade dos dados de entrada"
    ws["E8"].font = Font(size=12, bold=True, color=AZUL)
    qualidade = [
        ("Linhas lidas", linhas_lidas),
        ("Duplicadas removidas", limpeza.duplicados_removidos),
        ("Setores padronizados", limpeza.setores_corrigidos),
        ("Linhas rejeitadas", len(limpeza.rejeitados)),
        ("Linhas aproveitadas", len(limpeza.dados)),
    ]
    for i, (nome, valor) in enumerate(qualidade, start=9):
        ws.cell(row=i, column=5, value=nome)
        c = ws.cell(row=i, column=7, value=valor)
        c.number_format = "#,##0"
        c.font = Font(bold=True)
    ws["E14"] = "Detalhes na aba 'Rejeitados'."
    ws["E14"].font = Font(size=9, italic=True, color=CINZA)

    # Tabela por setor + gráfico
    ws["A17"] = "Desempenho por setor"
    ws["A17"].font = Font(size=12, bold=True, color=AZUL)
    setores = ind.por_setor[["setor", "ordens", "otif", "taxa_refugo", "atrasadas_abertas"]]
    cab, fim = _tabela(ws, setores, linha_inicial=18)
    ws.freeze_panes = None
    ws.auto_filter.ref = None
    _semaforo(ws, "C", cab + 1, fim, META_OTIF, maior_melhor=True)
    _semaforo(ws, "D", cab + 1, fim, META_REFUGO, maior_melhor=False)
    for c in range(1, 9):
        ws.column_dimensions[get_column_letter(c)].width = 15

    grafico = BarChart()
    grafico.type = "bar"
    grafico.title = "OTIF por setor"
    grafico.y_axis.number_format = "0%"
    grafico.y_axis.scaling.min = 0
    grafico.y_axis.scaling.max = 1
    grafico.y_axis.majorGridlines = None
    grafico.legend = None
    grafico.add_data(Reference(ws, min_col=3, min_row=cab, max_row=fim), titles_from_data=True)
    grafico.set_categories(Reference(ws, min_col=1, min_row=cab + 1, max_row=fim))
    grafico.series[0].graphicalProperties.solidFill = AZUL
    grafico.height, grafico.width = 7.5, 13
    ws.add_chart(grafico, "A26")


def _aba_setores(wb: Workbook, ind: Indicadores) -> None:
    ws = wb.create_sheet("Por setor")
    _titulo(ws, "Indicadores por setor e máquina", "Verde = dentro da meta  ·  Vermelho = fora da meta")
    cab, fim = _tabela(ws, ind.por_maquina, linha_inicial=4)
    col_otif = get_column_letter(list(ind.por_maquina.columns).index("otif") + 1)
    col_ref = get_column_letter(list(ind.por_maquina.columns).index("taxa_refugo") + 1)
    _semaforo(ws, col_otif, cab + 1, fim, META_OTIF, maior_melhor=True)
    _semaforo(ws, col_ref, cab + 1, fim, META_REFUGO, maior_melhor=False)


def _aba_evolucao(wb: Workbook, ind: Indicadores) -> None:
    ws = wb.create_sheet("Evolução semanal")
    _titulo(ws, "Evolução semanal", "OPs encerradas por semana de conclusão")
    cab, fim = _tabela(ws, ind.evolucao_semanal, linha_inicial=4)
    if fim <= cab:
        return
    col_otif = list(ind.evolucao_semanal.columns).index("otif") + 1
    grafico = LineChart()
    grafico.title = "OTIF semanal"
    grafico.y_axis.number_format = "0%"
    grafico.y_axis.scaling.min = 0
    grafico.y_axis.scaling.max = 1
    grafico.x_axis.number_format = "DD/MM"
    grafico.legend = None
    grafico.add_data(Reference(ws, min_col=col_otif, min_row=cab, max_row=fim), titles_from_data=True)
    grafico.set_categories(Reference(ws, min_col=1, min_row=cab + 1, max_row=fim))
    grafico.series[0].graphicalProperties.line.solidFill = AZUL
    grafico.series[0].graphicalProperties.line.width = 28000
    grafico.height, grafico.width = 8, 18
    ws.add_chart(grafico, "G4")


def _aba_atrasadas(wb: Workbook, ind: Indicadores) -> None:
    ws = wb.create_sheet("Atrasadas")
    _titulo(ws, "OPs atrasadas em aberto", "Ordenadas da mais atrasada para a menos atrasada")
    if ind.atrasadas_abertas.empty:
        ws["A4"] = "Nenhuma OP atrasada em aberto."
        return
    cab, fim = _tabela(ws, ind.atrasadas_abertas, linha_inicial=4)
    col = get_column_letter(list(ind.atrasadas_abertas.columns).index("dias_atraso") + 1)
    ws.conditional_formatting.add(
        f"{col}{cab + 1}:{col}{fim}",
        CellIsRule(operator="greaterThan", formula=["7"], fill=PatternFill("solid", fgColor=VERMELHO)),
    )
    ws.conditional_formatting.add(
        f"{col}{cab + 1}:{col}{fim}",
        CellIsRule(operator="between", formula=["1", "7"], fill=PatternFill("solid", fgColor=AMARELO)),
    )


def _aba_rejeitados(wb: Workbook, limpeza: ResultadoLimpeza) -> None:
    ws = wb.create_sheet("Rejeitados")
    _titulo(ws, "Linhas rejeitadas na validação", "Corrigir na origem (ERP) para entrarem no próximo relatório")
    if limpeza.rejeitados.empty:
        ws["A4"] = "Nenhuma linha rejeitada."
        return
    colunas = ["motivo"] + [c for c in limpeza.rejeitados.columns if c != "motivo"]
    _tabela(ws, limpeza.rejeitados[colunas], linha_inicial=4)


def _aba_dados(wb: Workbook, limpeza: ResultadoLimpeza) -> None:
    ws = wb.create_sheet("Dados tratados")
    _titulo(ws, "Base tratada", "Dados já limpos, usados nos cálculos")
    _tabela(ws, limpeza.dados, linha_inicial=4)


def gerar_excel(
    ind: Indicadores, limpeza: ResultadoLimpeza, linhas_lidas: int, destino: str | Path
) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    _aba_resumo(wb, ind, limpeza, linhas_lidas)
    _aba_setores(wb, ind)
    _aba_evolucao(wb, ind)
    _aba_atrasadas(wb, ind)
    _aba_rejeitados(wb, limpeza)
    _aba_dados(wb, limpeza)
    wb.save(destino)
    return destino
