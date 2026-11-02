"""
Gera uma exportação FICTÍCIA de ordens de produção, no formato típico de um ERP:
CSV separado por ponto e vírgula, datas no padrão brasileiro e decimais com vírgula.

De propósito, o arquivo vem com os problemas que aparecem em exportações reais:
linhas duplicadas, campos vazios, nomes de setor escritos de jeitos diferentes,
datas inválidas e quantidades negativas. Assim a etapa de limpeza tem trabalho de verdade.

Uso:
    python -m src.gerar_dados                 # 600 ordens, semente fixa
    python -m src.gerar_dados --ordens 2000   # mais ordens
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SETORES = {
    "Corte": ["CNC-01", "CNC-02", "Serra-01"],
    "Dobra": ["Dobradeira-01", "Dobradeira-02"],
    "Solda": ["Solda-01", "Solda-02", "Solda-03"],
    "Pintura": ["Cabine-01", "Cabine-02"],
    "Montagem": ["Linha-01", "Linha-02"],
}

# Variações de escrita que um ERP ou um digitador costuma produzir
VARIACOES_SETOR = {
    "Corte": ["CORTE", "corte ", " Corte"],
    "Dobra": ["DOBRA", "dobra"],
    "Solda": ["SOLDA", "Soldagem", "solda "],
    "Pintura": ["PINTURA", "pintura", "Pintura "],
    "Montagem": ["MONTAGEM", "montagem", "Montagem "],
}

PRODUTOS = [
    ("PRD-1001", "Suporte metálico 40x40"),
    ("PRD-1002", "Painel lateral 1200mm"),
    ("PRD-1003", "Base estrutural reforçada"),
    ("PRD-1004", "Tampa frontal pintada"),
    ("PRD-1005", "Quadro de comando 600mm"),
    ("PRD-1006", "Chassi soldado modelo A"),
    ("PRD-1007", "Chassi soldado modelo B"),
    ("PRD-1008", "Prateleira industrial 900mm"),
    ("PRD-1009", "Guarda-corpo modular"),
    ("PRD-1010", "Caixa de passagem 300mm"),
]

COLUNAS = [
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


def _br(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _num_br(valor: float) -> str:
    """Formata número como o ERP exporta: vírgula decimal."""
    if float(valor).is_integer():
        return str(int(valor))
    return f"{valor:.2f}".replace(".", ",")


def gerar_ordens(qtd: int, inicio: date, dias: int, rng: random.Random) -> list[dict]:
    ordens = []
    hoje = inicio + timedelta(days=dias)

    for i in range(qtd):
        setor = rng.choice(list(SETORES))
        maquina = rng.choice(SETORES[setor])
        codigo, descricao = rng.choice(PRODUTOS)

        emissao = inicio + timedelta(days=rng.randint(0, dias - 5))
        prazo = emissao + timedelta(days=rng.randint(3, 15))
        planejada = rng.choice([50, 80, 100, 120, 150, 200, 250, 300, 400, 500])

        # Cada setor tem um "perfil" de desempenho, para o relatório mostrar diferenças reais
        chance_atraso = {"Corte": 0.10, "Dobra": 0.15, "Solda": 0.30, "Pintura": 0.22, "Montagem": 0.12}[setor]
        taxa_refugo = {"Corte": 0.01, "Dobra": 0.02, "Solda": 0.05, "Pintura": 0.035, "Montagem": 0.015}[setor]

        concluida = prazo < hoje - timedelta(days=2) or rng.random() < 0.4
        if concluida:
            atraso = rng.randint(1, 9) if rng.random() < chance_atraso else -rng.randint(0, 2)
            conclusao = min(prazo + timedelta(days=atraso), hoje)
            conclusao = max(conclusao, emissao)
            # A fábrica produz um pouco a mais para cobrir o refugo; às vezes falta material e fica abaixo
            refugo = round(planejada * rng.uniform(0, taxa_refugo * 2))
            fator = rng.uniform(0.88, 0.99) if rng.random() < 0.12 else rng.uniform(1.0, 1.02)
            produzida = round(planejada * fator) + refugo
            status = "Encerrada"
        else:
            conclusao = None
            produzida = round(planejada * rng.uniform(0, 0.8))
            refugo = round(produzida * rng.uniform(0, taxa_refugo * 2))
            status = "Em andamento" if produzida > 0 else "Liberada"

        ordens.append(
            {
                "numero_op": f"OP{240000 + i:06d}",
                "codigo_produto": codigo,
                "descricao_produto": descricao,
                "setor": setor,
                "maquina": maquina,
                "qtd_planejada": planejada,
                "qtd_produzida": produzida,
                "qtd_refugo": refugo,
                "data_emissao": emissao,
                "data_prevista": prazo,
                "data_conclusao": conclusao,
                "status": status,
            }
        )
    return ordens


def sujar_dados(ordens: list[dict], rng: random.Random) -> list[dict]:
    """Insere os defeitos típicos de uma exportação real."""
    linhas = [dict(o) for o in ordens]

    for linha in linhas:
        if rng.random() < 0.18:  # setor escrito de outro jeito
            linha["setor"] = rng.choice(VARIACOES_SETOR[linha["setor"]])

    # Duplicados exatos (exportação feita duas vezes, filtro mal aplicado)
    for linha in rng.sample(linhas, k=max(1, len(linhas) // 40)):
        linhas.append(dict(linha))

    alvos = rng.sample(range(len(linhas)), k=max(4, len(linhas) // 30))
    for n, idx in enumerate(alvos):
        tipo = n % 4
        if tipo == 0:
            linhas[idx]["setor"] = ""  # campo obrigatório vazio
        elif tipo == 1:
            linhas[idx]["data_prevista"] = "31/02/2024"  # data que não existe
        elif tipo == 2:
            linhas[idx]["qtd_produzida"] = -abs(linhas[idx]["qtd_produzida"]) or -1  # estorno lançado errado
        else:
            linhas[idx]["qtd_planejada"] = 0  # OP sem quantidade

    rng.shuffle(linhas)
    return linhas


def salvar_csv(linhas: list[dict], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        escritor.writeheader()
        for linha in linhas:
            saida = {}
            for col in COLUNAS:
                valor = linha[col]
                if isinstance(valor, date):
                    valor = _br(valor)
                elif valor is None:
                    valor = ""
                elif isinstance(valor, (int, float)):
                    valor = _num_br(valor)
                saida[col] = valor
            escritor.writerow(saida)


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera exportação fictícia de ordens de produção.")
    parser.add_argument("--ordens", type=int, default=600, help="quantidade de ordens (padrão: 600)")
    parser.add_argument("--inicio", default="2026-07-01", help="data inicial AAAA-MM-DD")
    parser.add_argument("--dias", type=int, default=90, help="período coberto em dias")
    parser.add_argument("--semente", type=int, default=42, help="semente para resultados repetíveis")
    parser.add_argument("--saida", default="dados/entrada/ordens_producao.csv")
    args = parser.parse_args()

    rng = random.Random(args.semente)
    ordens = gerar_ordens(args.ordens, date.fromisoformat(args.inicio), args.dias, rng)
    linhas = sujar_dados(ordens, rng)
    salvar_csv(linhas, Path(args.saida))
    print(f"{len(linhas)} linhas geradas em {args.saida}")


if __name__ == "__main__":
    main()
