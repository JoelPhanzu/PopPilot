"""
PopPilot — contrôle après migration : compare deux bases PostgreSQL table par table.

    .venv\\Scripts\\python.exe outils\\comparer_bases.py "postgresql://…SOURCE" "postgresql://…CIBLE"

Pour chaque table du schéma public : nombre de lignes dans la source, dans la cible, écart.
Pour les tables datées (date_arrete) : nombre de lignes par arrêté, pour repérer un mois
manquant. Lecture seule sur les deux bases ; aucun mot de passe n'est affiché.
Code de sortie 0 si tout concorde, 1 sinon.
"""
from __future__ import annotations

import sys

from sqlalchemy import create_engine, inspect, text


def _moteur(url: str):
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return create_engine(url, pool_pre_ping=True)


def _hote(url: str) -> str:
    return url.split("@")[-1].split("/")[0] if "@" in url else url


def inventaire(moteur) -> dict[str, dict]:
    tables = {}
    insp = inspect(moteur)
    with moteur.connect() as c:
        for t in sorted(insp.get_table_names(schema="public")):
            n = c.execute(text(f'SELECT count(*) FROM public."{t}"')).scalar_one()
            par_arrete = {}
            if "date_arrete" in {col["name"] for col in insp.get_columns(t, schema="public")}:
                par_arrete = {str(d): k for d, k in c.execute(text(
                    f'SELECT date_arrete, count(*) FROM public."{t}" GROUP BY 1'))}
            tables[t] = {"n": n, "arretes": par_arrete}
    return tables


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, cib = (inventaire(_moteur(u)) for u in argv)
    print(f"Source : {_hote(argv[0])}\nCible  : {_hote(argv[1])}\n")
    print(f"{'Table':34} {'Source':>12} {'Cible':>12} {'Écart':>10}")
    ecarts = 0
    for t in sorted(set(src) | set(cib)):
        a, b = src.get(t, {}).get("n"), cib.get(t, {}).get("n")
        ok = a == b
        ecarts += not ok
        f = lambda v: "absente" if v is None else f"{v:,}".replace(",", " ")
        ecart = "" if ok else ("—" if a is None or b is None else f"{b - a:+,}".replace(",", " "))
        print(f"{t:34} {f(a):>12} {f(b):>12} {ecart:>10}{'' if ok else '  ◄'}")
        if not ok and a is not None and b is not None:
            for d in sorted(set(src[t]["arretes"]) | set(cib[t]["arretes"])):
                x, y = src[t]["arretes"].get(d, 0), cib[t]["arretes"].get(d, 0)
                if x != y:
                    print(f"{'':6}arrêté {d} : source {x:,} / cible {y:,}".replace(",", " "))
    print("\nTOUT CONCORDE." if not ecarts else f"\n{ecarts} table(s) en écart : voir ◄.")
    return 0 if not ecarts else 1


if __name__ == "__main__":
    sys.exit(main())
