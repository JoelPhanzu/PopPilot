"""
Écriture du FINA dans le gabarit BCC .xls (Rapport 3, assemblage final) — CLAUDE.md §32-37.

Remplit F0 (bilan), F1 (compte de résultat), F5 (ventilation crédit), F11 (balance âgée)
avec les valeurs du socle, EN CDF (balance CDF, sans conversion). Le résultat net est calculé
depuis les classes 6/7 (le compte 13 est à 0 en cours d'année).

Mapping code FINA → préfixe(s) de compte, calé sur le gabarit MFII.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from socle.schema import FaitCredit, get_session
from engine.fina import _soldes_cdf, _somme_prefixes


def _mixte(soldes, *prefixes):
    """(part actif, part passif) d'un compte MIXTE — le signe décide, COMPTE PAR COMPTE (§40).

    POURQUOI : les comptes 37, 40, 42-47, 53 et 56 vivent des deux côtés du bilan. En
    prenant leur somme nette et en l'écrivant à l'actif (A) ET au passif (P), on posait
    le MÊME montant des deux côtés avec des signes opposés : F0a.05 sortait à
    −1 782 915 519 CDF et F0p.04 à +1 782 915 519. Un actif négatif dans une déclaration
    BCC n'a aucun sens. On répartit donc compte par compte, comme le fait déjà le bilan
    (engine/etats_financiers.py) : soldes débiteurs à l'actif, créditeurs au passif.
    """
    def concerne(c):
        return any(str(c).startswith(p) for p in prefixes)
    actif = sum(v for c, v in soldes.items() if concerne(c) and v > 0)
    passif = -sum(v for c, v in soldes.items() if concerne(c) and v < 0)
    return actif, passif


def _agr(soldes):
    """Agrégats CDF par ligne FINA. Actif = débiteur (+), passif/produits = créditeur (−→+)."""
    A = lambda *p: _somme_prefixes(soldes, *p)          # actif (débiteur +)
    P = lambda *p: -_somme_prefixes(soldes, *p)         # passif (créditeur → +)
    produits = P("70", "71", "72", "73", "74", "76", "77", "78", "79")
    charges = A("60", "61", "62", "63", "64", "65", "66", "67", "68", "69")
    resultat = produits - charges

    # Comptes mixtes : une seule lecture, répartie entre les deux côtés.
    a53, p53 = _mixte(soldes, "53")
    a56, p56 = _mixte(soldes, "56")
    a40, p40 = _mixte(soldes, "40")
    a42, p42 = _mixte(soldes, "42")
    a43, p43 = _mixte(soldes, "43")
    a46, p46 = _mixte(soldes, "46")
    a47, p47 = _mixte(soldes, "47")
    # Parts sans case dans le gabarit (56 n'a pas de ligne au passif, 42 pas à l'actif) :
    # signalées au lieu d'être écrites au mauvais endroit ou perdues sans bruit.
    mixtes_non_affectes = {k: v for k, v in
                           {"56 (part passif)": p56, "42 (part actif)": a42}.items()
                           if abs(v) > 0.5}

    return {
        # F0 ACTIF
        "F0a.03": A("57"), "F0a.04": a56, "F0a.05": a53, "F0a.06": A("52"),
        "F0a.09": A("32"), "F0a.10": A("31"), "F0a.11": A("30"),
        "F0a.13": -A("38"), "F0a.14": A("39"),
        "F0a.16": a40, "F0a.18": a43, "F0a.21": a46, "F0a.22": a47,
        "F0a.25": A("20"), "F0a.26": A("22"), "F0a.31": A("27"), "F0a.32": A("28"),
        # F0 PASSIF
        "F0p.04": p53, "F0p.06": P("33"), "F0p.07": P("34"), "F0p.09": P("36"),
        "F0p.12": p40, "F0p.13": p42, "F0p.14": p43, "F0p.17": p46,
        "F0p.18": p47, "F0p.22": P("18"),
        "F0p.24": P("14"), "F0p.25": resultat, "F0p.26": P("12"), "F0p.27": P("11"),
        "F0p.28": P("10"),
        "_F0_mixtes_non_affectes": mixtes_non_affectes,
        # F1 COMPTE DE RÉSULTAT
        "F1.02": P("71"), "F1.03": P("72"), "F1.04": P("73"),
        "F1.05": A("60"), "F1.06": A("61"), "F1.07": A("62"), "F1.08": A("63"),
        "F1.10": P("74"), "F1.11": A("64"), "F1.12": A("65"), "F1.13": A("66"),
        "F1.16": P("79"), "F1.17": A("68"), "F1.18": A("69"),
        "F1.21": P("77"), "F1.23": A("86"), "F1.26": resultat,
        "_resultat": resultat, "_produits": produits, "_charges": charges,
    }


def valeurs_fina(date_arrete, db_path="socle/micropop.db", rh=None, ventilation_f10=None):
    s = get_session(db_path)
    soldes = _soldes_cdf(s, date_arrete)
    if not soldes:
        s.close()
        raise ValueError("Balance CDF absente.")
    prets = s.execute(select(FaitCredit).where(FaitCredit.date_arrete == date_arrete)).scalars().all()
    from socle.schema import FaitEpargne
    from sqlalchemy import func as _func
    nb_emprunteurs = s.execute(
        select(_func.count(_func.distinct(FaitCredit.numero_client)))
        .where(FaitCredit.date_arrete == date_arrete)).scalar_one()
    nb_epargnants = s.execute(
        select(_func.count(_func.distinct(FaitEpargne.id_client)))
        .where(FaitEpargne.date_arrete == date_arrete)).scalar_one() or 0
    s.close()
    ag = _agr(soldes)

    # F5 : ventilation crédit (CT=32, MT=31, retard=39) × groupe (LISANGA)
    ct = _somme_prefixes(soldes, "32"); mt = _somme_prefixes(soldes, "31")
    ret = _somme_prefixes(soldes, "39")
    enc_credit = sum(p.encours or 0 for p in prets)
    prop = ((ct + mt + ret) / enc_credit) if enc_credit else 0
    grp_ct = sum(p.encours or 0 for p in prets if p.est_groupe and (p.jours_de_retard or 0) == 0) * prop
    grp_ret = sum(p.encours or 0 for p in prets if p.est_groupe and (p.jours_de_retard or 0) > 0) * prop
    ag["F5_CT_client"] = ct - grp_ct
    ag["F5_CT_groupe"] = grp_ct
    ag["F5_MT_total"] = mt
    ag["F5_retard_client"] = ret - grp_ret
    ag["F5_retard_groupe"] = grp_ret
    ag["F5_total"] = ct + mt + ret

    # F11 : balance âgée par tranche (depuis le crédit, proportionné au CDF)
    def tr_sum(champ):
        return sum(getattr(p, champ) or 0 for p in prets) * prop
    ag["F11_CT_encours"] = ct
    ag["F11_MT_encours"] = mt
    ag["F11_total_encours"] = ct + mt + ret
    ag["F11_retard"] = ret
    ag["F11_1_30"] = (tr_sum("tr_1_7") + tr_sum("tr_8_30"))
    ag["F11_31_60"] = tr_sum("tr_31_60")
    ag["F11_61_90"] = tr_sum("tr_61_90")
    ag["F11_91_180"] = tr_sum("tr_91_180")
    ag["F11_180plus"] = tr_sum("tr_181_360") + tr_sum("tr_361_plus")

    # F2 : éléments de portée (portée = stats ; effectifs RH saisis)
    rh = rh or {}
    ag["F2b.01"] = nb_emprunteurs
    ag["F2b.03"] = nb_epargnants
    ag["F2b.05"] = rh.get("nb_employes")       # saisie RH
    ag["F2b.07"] = rh.get("nb_agents_credit")  # saisie RH

    # ── F6 : épargne détaillée par compte (33/34/35) × Client/Groupe ──
    # Montants comptables depuis la balance CDF ; ventilation groupe depuis l'épargne
    P = lambda *p: -_somme_prefixes(soldes, *p)
    ep_33 = P("33"); ep_34 = P("34"); ep_35 = P("35")
    # Part groupe de l'épargne (§51.3). DEUX PIÈGES CORRIGÉS ICI :
    #
    # 1. La proportion se calcule sur une base HOMOGÈNE (tout converti en USD).
    #    En devise d'origine, la somme additionnait des USD et des CDF bruts : le
    #    dénominateur était dominé par les CDF et la part groupe sortait à 0,02 % au
    #    lieu de 1,82 % — un facteur 100 sur la ventilation F6, sans alerte.
    # 2. Une épargne absente ne vaut PAS « 0 % de groupe » : l'ancien `except: prop=0`
    #    faisait passer une donnée manquante pour une ventilation calculée. On laisse
    #    la ventilation VIDE et on le signale ; les cases F6 groupe ne sont pas écrites.
    prop_ep = None
    ag["_F6_groupe_indisponible"] = None
    try:
        from engine.epargne import synthese_epargne
        syn = synthese_epargne(date_arrete, db_path=db_path, en_usd=True)
        total_ep = syn["encours_total"]
        prop_ep = (syn["epargne_groupe"] / total_ep) if total_ep else None
        if prop_ep is None:
            ag["_F6_groupe_indisponible"] = "encours épargne nul"
    except Exception as e:                       # noqa: BLE001 — motif conservé, pas avalé
        ag["_F6_groupe_indisponible"] = f"{type(e).__name__}: {e}"
    ag["_F6_part_groupe"] = prop_ep
    ag["F6_33_total"] = ep_33
    ag["F6_33_groupe"] = (ep_33 * prop_ep) if prop_ep is not None else None
    ag["F6_33_client"] = (ep_33 * (1 - prop_ep)) if prop_ep is not None else None
    ag["F6_34_total"] = ep_34
    ag["F6_35_total"] = ep_35

    # ── F7 : comptes Nostri (530 prêts à terme, 560 comptes nostri) ──
    ag["F7_560_nostri"] = _somme_prefixes(soldes, "56")
    ag["F7_530_terme"] = _somme_prefixes(soldes, "53")
    ag["F7_total"] = ag["F7_560_nostri"] + ag["F7_530_terme"]

    # ── F3 : flux de trésorerie (agrégats de produits/charges encaissés) ──
    ag["F3_produits_expl"] = P("70", "71", "74")
    ag["F3_charges_interets"] = _somme_prefixes(soldes, "60", "61")

    # ── F10 : ventilation sectorielle par TAUX saisis (commerce/agricole/services/autres) ──
    # ventilation = dict de taux, ex. {"commerce":0.80,"agricole":0.0,"services":0.15,"autres":0.05}
    total_f10 = ct + mt + ret
    vent = (ventilation_f10 or {})
    ag["F10_total_encours"] = total_f10
    ag["F10_commerce"] = total_f10 * vent.get("commerce", 0)
    ag["F10_agricole"] = total_f10 * vent.get("agricole", 0)
    ag["F10_services"] = total_f10 * vent.get("services", 0)
    ag["F10_autres"] = total_f10 * vent.get("autres", 0)
    ag["_F10_somme_taux"] = sum(vent.get(k, 0) for k in ("commerce", "agricole", "services", "autres"))

    # ── CONTRÔLE F0 : la somme des lignes écrites = le bilan de la balance CDF ──
    # Un contrôle n'a de valeur que s'il peut échouer. Ici on confronte DEUX chemins
    # indépendants : les lignes F0 (mapping case par case, ci-dessus) et le bilan
    # reconstruit par engine/etats_financiers.py (mapping par préfixe, validé écart nul).
    # Un compte non repris dans une case F0, ou une case mal affectée, apparaît aussitôt.
    ag.update(_controle_f0(ag, date_arrete, db_path))
    return ag


def _controle_f0(ag, date_arrete, db_path):
    """Écart entre les lignes F0 et le bilan de la balance CDF (actif et passif)."""
    from engine.etats_financiers import etats_financiers
    try:
        ef = etats_financiers(date_arrete, db_path=db_path, devise="CDF")
    except Exception as e:                       # noqa: BLE001
        return {"_F0_controle": f"non calculé ({type(e).__name__}: {e})"}
    # F0a.13 = provisions sur créances (compte 38). Le gabarit les porte en POSITIF sur
    # une ligne qui se DÉDUIT de l'actif, alors que le bilan les compte négativement.
    # Le contrôle doit connaître cette convention, sinon il crie un écart de 2 × 38.
    DEDUITES = {"F0a.13"}
    actif_f0 = sum((-v if k in DEDUITES else v) for k, v in ag.items()
                   if k.startswith("F0a.") and isinstance(v, (int, float)))
    passif_f0 = sum(v for k, v in ag.items()
                    if k.startswith("F0p.") and isinstance(v, (int, float)))
    ecart_a = actif_f0 - ef["total_actif"]
    ecart_p = passif_f0 - ef["total_passif"]
    return {
        "_F0_actif_total": actif_f0, "_F0_passif_total": passif_f0,
        "_F0_bilan_actif": ef["total_actif"], "_F0_bilan_passif": ef["total_passif"],
        "_F0_ecart_actif": ecart_a, "_F0_ecart_passif": ecart_p,
        # tolérance : 1 CDF (le franc congolais n'a pas de subdivision utile ici)
        "_F0_controle": "ok" if max(abs(ecart_a), abs(ecart_p)) < 1 else "ECART",
    }


def _ecrire(feuille, ligne, colonne, valeur, cases_vides=None, repere=""):
    """Écrit une valeur dans le gabarit, et NE FAIT RIEN si elle est indisponible (None).

    POURQUOI : `valeurs_fina` met délibérément certaines cases à None quand la donnée
    manque — la ventilation groupe de F6 quand l'épargne du mois n'est pas chargée (ou
    quand le taux n'est pas saisi), avec le commentaire « les cases F6 groupe ne sont
    pas écrites ». Le bloc d'écriture, lui, faisait `round(None, 2)` : TypeError, et le
    FINA ENTIER était perdu — F0, F1, F5, F11 compris, alors que ces feuilles-là étaient
    parfaitement calculées. Une case manquante doit coûter une case, pas le rapport.

    Les cases sautées sont collectées : un rapport incomplet doit se DIRE incomplet,
    sinon on livre un gabarit à trous à la BCC sans le savoir.
    """
    if valeur is None:
        if cases_vides is not None and repere:
            cases_vides.append(repere)
        return False
    feuille.write(ligne, colonne, round(valeur, 2) if isinstance(valeur, float) else valeur)
    return True


def ecrire_fina(date_arrete, gabarit, sortie, db_path="socle/micropop.db", rh=None,
                ventilation_f10=None):
    """Copie le gabarit .xls et remplit les feuilles concernées depuis le socle (CDF).

    Feuilles REMPLIES : F0, F1, F2, F3, F5, F6, F7, F10, F11.
    Feuilles JAMAIS TOUCHÉES (non concernées) : F4a, F4b, F8, F9, F12.
    """
    import xlrd
    from xlutils.copy import copy as xl_copy

    NE_PAS_TOUCHER = {"F4a", "F4b", "F8", "F9", "F12"}

    ag = valeurs_fina(date_arrete, db_path, rh=rh, ventilation_f10=ventilation_f10)
    rb = xlrd.open_workbook(gabarit, formatting_info=True)
    wb = xl_copy(rb)
    cases_vides: list[str] = []          # cases laissées vides faute de donnée

    def write_by_code(sheet_name, col=2, mapping_key=lambda c: c.replace("V1.", "").strip()):
        sh = rb.sheet_by_name(sheet_name); w = wb.get_sheet(sheet_name)
        for r in range(sh.nrows):
            key = mapping_key(str(sh.cell_value(r, 0)).strip())
            if key in ag and ag[key] is not None:
                w.write(r, col, round(ag[key], 2) if isinstance(ag[key], float) else ag[key])

    # F0, F1, F2 : valeur en colonne 2 (C), par code
    write_by_code("F0"); write_by_code("F1"); write_by_code("F2")

    # F5 : ventilation par colonnes Client(2)/Groupe(3)/Autres(4)/TOTAL(5)
    sh5 = rb.sheet_by_name("F5"); w5 = wb.get_sheet("F5")
    f5_lignes = {
        "V1.F5.08": (ag["F5_MT_total"], 0, 0),               # (31) MT
        "V1.F5.14": (ag["F5_MT_total"], 0, 0),
        "V1.F5.15": (ag["F5_CT_client"], ag["F5_CT_groupe"], 0),  # (32) CT
        "V1.F5.19": (ag["F5_CT_client"], ag["F5_CT_groupe"], 0),
        "V1.F5.21": (ag["F5_retard_client"], ag["F5_retard_groupe"], 0),  # (39) retard
        "V1.F5.22": (ag["F5_retard_client"], ag["F5_retard_groupe"], 0),
    }
    for r in range(sh5.nrows):
        code = str(sh5.cell_value(r, 0)).strip()
        if code in f5_lignes:
            cli, grp, aut = f5_lignes[code]
            w5.write(r, 2, round(cli, 2)); w5.write(r, 3, round(grp, 2))
            w5.write(r, 4, round(aut, 2)); w5.write(r, 5, round(cli + grp + aut, 2))

    # F11 : balance âgée. Lignes CT (V1.F11.01), MT (V1.F11.08), TOTAL (V1.F11.22)
    sh11 = rb.sheet_by_name("F11"); w11 = wb.get_sheet("F11")
    # colonnes : 2 encours brut, 3 retard, 4:1-30, 5:31-60, 6:61-90, 7:91-180, 8:>180
    tot_row = (ag["F11_total_encours"], ag["F11_retard"], ag["F11_1_30"], ag["F11_31_60"],
               ag["F11_61_90"], ag["F11_91_180"], ag["F11_180plus"])
    for r in range(sh11.nrows):
        code = str(sh11.cell_value(r, 0)).strip()
        if code == "V1.F11.01":   # CT — approx tout le retard porté en CT (le gros du portefeuille)
            w11.write(r, 2, round(ag["F11_CT_encours"], 2))
        elif code == "V1.F11.08":  # MT
            w11.write(r, 2, round(ag["F11_MT_encours"], 2))
        elif code == "V1.F11.22":  # TOTAL avec toutes les tranches
            for i, v in enumerate(tot_row):
                w11.write(r, 2 + i, round(v, 2))

    # F6 : épargne détaillée (33 client/groupe, 34, 35)
    # La ventilation Client/Groupe vient de l'épargne : elle peut légitimement manquer
    # (inventaire du mois non chargé, taux non saisi). Les totaux, eux, viennent de la
    # balance CDF et sont toujours là. On écrit donc ce qu'on a, case par case.
    sh6 = rb.sheet_by_name("F6"); w6 = wb.get_sheet("F6")
    for r in range(sh6.nrows):
        code = str(sh6.cell_value(r, 0)).strip()
        if code == "V1.F6.01":   # (33) épargnes et dépôts ordinaires
            _ecrire(w6, r, 2, ag["F6_33_client"], cases_vides, "F6.01 client (ventilation groupe)")
            _ecrire(w6, r, 3, ag["F6_33_groupe"], cases_vides, "F6.01 groupe (ventilation groupe)")
            _ecrire(w6, r, 5, ag["F6_33_total"], cases_vides, "F6.01 total")
        elif code == "V1.F6.08":  # (34) dépôts à terme
            _ecrire(w6, r, 2, ag["F6_34_total"], cases_vides, "F6.08")
            _ecrire(w6, r, 5, ag["F6_34_total"], cases_vides, "F6.08 total")
        elif code == "V1.F6.10":  # (35) dépôts régime spécial
            _ecrire(w6, r, 5, ag["F6_35_total"], cases_vides, "F6.10 total")

    # F7 : comptes Nostri
    sh7 = rb.sheet_by_name("F7"); w7 = wb.get_sheet("F7")
    for r in range(sh7.nrows):
        code = str(sh7.cell_value(r, 0)).strip()
        if code == "V1.F7.04":   # (560) comptes nostri
            w7.write(r, 3, round(ag["F7_560_nostri"], 2)); w7.write(r, 4, round(ag["F7_560_nostri"], 2))
        elif code == "V1.F7.07":  # TOTAL
            w7.write(r, 3, round(ag["F7_total"], 2)); w7.write(r, 4, round(ag["F7_total"], 2))

    # F10 : ventilation sectorielle par TAUX saisis.
    # Colonnes : 2=Commerces, 3=Produits agricoles, 4=Services, 5=Autres, 6=TOTAL.
    sh10 = rb.sheet_by_name("F10"); w10 = wb.get_sheet("F10")
    for r in range(sh10.nrows):
        code = str(sh10.cell_value(r, 0)).strip()
        if code in ("V1.F10.02", "V1.F10.04"):
            w10.write(r, 2, round(ag["F10_commerce"], 2))
            w10.write(r, 3, round(ag["F10_agricole"], 2))
            w10.write(r, 4, round(ag["F10_services"], 2))
            w10.write(r, 5, round(ag["F10_autres"], 2))
            w10.write(r, 6, round(ag["F10_total_encours"], 2))

    wb.save(sortie)
    # `complet` répond à la seule question qui compte avant d'envoyer à la BCC :
    # est-ce que toutes les cases calculables ont été remplies ? Un fichier à trous
    # produit sans un mot est le pire des deux mondes.
    return {"sortie": sortie, "resultat_net": ag["_resultat"],
            "F5_total": ag["F5_total"], "nb_emprunteurs": ag["F2b.01"],
            "nb_epargnants": ag["F2b.03"],
            "complet": not cases_vides,
            "cases_vides": cases_vides,
            "motif_cases_vides": ag.get("_F6_groupe_indisponible")}


if __name__ == "__main__":
    # Démo : chemins relatifs au dossier de données local, pas à un /mnt ou /tmp Linux.
    import os
    import tempfile
    gabarit = os.environ.get("FINA_GABARIT", "MFII0043m072026.xls")
    sortie = os.path.join(tempfile.gettempdir(), "FINA_juillet_genere.xls")
    r = ecrire_fina(dt.date(2026, 7, 31), gabarit, sortie)
    print("Généré:", r)
