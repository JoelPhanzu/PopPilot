"""Écriture du rapport AML/LBC-FT complet — remplit REPORTING LBC-FT depuis toutes les sources."""
from __future__ import annotations
import datetime as dt
import shutil
import openpyxl
from engine.aml import operations_especes, transferts_grand_livre, portefeuille_client


def ecrire_aml(path_source_xls, sortie, periode_debut, periode_fin,
               path_inventaire=None, taux_cdf=None, db_path="socle/micropop.db",
               encours_credit_usd=None, nb_credits=None,
               credit_conso_cdf=None, nb_credits_conso=None):
    tmp = "/tmp/_aml_src.xlsx"
    shutil.copy(path_source_xls, tmp)

    if taux_cdf is None:
        try:
            from engine.etats_financiers import taux_change
            from socle.schema import get_session
            d = periode_fin.date() if hasattr(periode_fin, "date") else periode_fin
            s = get_session(db_path); taux_cdf = taux_change(s, d); s.close()
        except Exception:
            taux_cdf = 2263.57

    ops = operations_especes(tmp, taux_cdf)
    tr = transferts_grand_livre(tmp, taux_cdf)
    pf = portefeuille_client(path_inventaire, taux_cdf) if path_inventaire else None

    wb = openpyxl.load_workbook(tmp)
    ws = wb["REPORTING LBC-FT"]

    def sv(r, n, v):
        if n is not None: ws.cell(row=r, column=2, value=n)
        if v is not None: ws.cell(row=r, column=3, value=round(v, 2))

    # période
    ws.cell(row=5, column=2, value=periode_debut)
    ws.cell(row=6, column=2, value=periode_fin)

    # totaux espèces
    dep_nb, dep_cdf = ops["depot"]["total_nb"], ops["depot"]["total_cdf"]
    ret_nb, ret_cdf = ops["retrait"]["total_nb"], ops["retrait"]["total_cdf"]
    tot_esp_nb = dep_nb + ret_nb
    tot_esp_cdf = dep_cdf + ret_cdf
    tot_op_nb = tot_esp_nb + tr["nombre"]
    tot_op_cdf = tot_esp_cdf + tr["volume_cdf"]

    # 1. TAILLE
    sv(13, tot_op_nb, tot_op_cdf)          # Total Opérations = espèces + transferts
    sv(14, tot_esp_nb, tot_esp_cdf)        # Total Opérations en espèces = dépôts + retraits
    if encours_credit_usd is not None:
        sv(15, nb_credits, encours_credit_usd * taux_cdf)   # Total encours crédit (CDF)
    if credit_conso_cdf is not None:
        sv(16, nb_credits_conso, credit_conso_cdf)          # Crédits à la consommation
    sv(25, dep_nb, dep_cdf)                # Total Dépôts

    # 2. PORTEFEUILLE CLIENT
    if pf:
        sv(35, pf["pp_nombre"], pf["pp_solde"])   # Personnes physiques
        sv(39, pf["pp_nombre"], pf["pp_solde"])   # · Autres (= tout PP faute de sous-classif)
        sv(40, pf["pm_nombre"], pf["pm_solde"])   # Personnes morales

    # 3. Opérations en espèces par seuil
    sv(53, ops["depot"][">=10k"][0], ops["depot"][">=10k"][1])
    sv(54, ops["retrait"][">=10k"][0], ops["retrait"][">=10k"][1])
    sv(55, ops["depot"]["5k-10k"][0], ops["depot"]["5k-10k"][1])
    sv(56, ops["retrait"]["5k-10k"][0], ops["retrait"]["5k-10k"][1])

    # 7. LOCALISATION (provinces) — écrit à partir de L149
    if pf:
        prov_rows = {"HAUT-KATANGA": 149, "NORD-KIVU": 150, "KINSHASA": 151}
        for prov, r in prov_rows.items():
            if prov in pf["localisation"]:
                v = pf["localisation"][prov]
                # ne pas écraser un libellé existant : n'écrit que si la ligne correspond
                lib = str(ws.cell(row=r, column=1).value or "").upper()
                if prov.split("-")[0] in lib or lib == "":
                    sv(r, v["nombre"], v["volume"])

    wb.save(sortie)
    return {"sortie": sortie, "taux_cdf": taux_cdf,
            "total_operations": (tot_op_nb, tot_op_cdf),
            "total_especes": (tot_esp_nb, tot_esp_cdf),
            "total_depots": (dep_nb, dep_cdf),
            "transferts": tr, "portefeuille": pf,
            "depot_10k": ops["depot"][">=10k"], "depot_5k": ops["depot"]["5k-10k"],
            "retrait_5k": ops["retrait"]["5k-10k"]}
