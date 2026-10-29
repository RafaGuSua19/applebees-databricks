"""Genera la figura del README a partir de evidencia real (dependencia opcional: matplotlib)."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/assets/comparaciones.png"))
    args = parser.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    evidence = json.loads(args.evidence.read_text())
    business = next(r for r in evidence["results"] if r["file"] == "negocio.sql")
    rows = {name: json.loads(value) for name, value in business["rows"]}
    total = rows["ticket_totals"]
    cash = rows["payment_Efectivo"]
    panels = [
        ("El efectivo concentra el descuento", ["Participación\nen venta", "Participación\nen descuento"],
         [cash["gross"] / total["gross"] * 100, cash["discount"] / total["discount"] * 100], 65,
         "Porcentaje del total de la cadena"),
        ("To Go tiene mayor tasa", ["In-Store", "To Go"],
         [rows["channel_In-Store"]["rate"] * 100, rows["channel_To Go"]["rate"] * 100], 15,
         "Descuento / venta bruta del canal"),
        ("Los tickets largos destacan", ["Menos de 4 h", "4 h o más"],
         [rows["duration_false"]["rate"] * 100, rows["duration_true"]["rate"] * 100], 26,
         "Descuento / venta bruta del grupo"),
    ]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "axes.spines.bottom": False})
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.1), facecolor="#f6f8fb")
    for ax, (title, labels, values, limit, denominator) in zip(axes, panels):
        ax.set_facecolor("#f6f8fb")
        bars = ax.bar(labels, values, color=["#87a4ba", "#0e7c86"], width=0.5, zorder=3)
        ax.set_ylim(0, limit)
        ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color="#152e45", pad=22)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
        ax.grid(axis="y", color="#dbe3ea", linewidth=0.7, zorder=0)
        ax.tick_params(axis="both", length=0, colors="#3e5265")
        ax.bar_label(bars, labels=[f"{x:.1f}%" for x in values], padding=7,
                     fontsize=14, fontweight="bold", color="#152e45")
        ax.set_xlabel(denominator, fontsize=9, color="#526778", labelpad=16)
    fig.suptitle("Applebee’s | Señales para priorizar una revisión", x=0.05, ha="left",
                 fontsize=19, fontweight="bold", color="#152e45", y=0.98)
    fig.text(0.05, 0.025, f"{total['tickets']:,} tickets · 127 tiendas · 28 abr–20 ago 2026  |  "
             "Fuente: gold_kpis_diarios y silver_checks. Señales, no prueba de fraude.",
             fontsize=9, color="#526778")
    fig.subplots_adjust(left=0.05, right=0.98, top=0.78, bottom=0.24, wspace=0.32)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(args.output)


if __name__ == "__main__":
    main()
