"""
Paramètres initiaux datés (Lot 0.2) — valeurs connues de la base de connaissances.
Tous versionnés à une date d'effet ; modifiables sans toucher au code (§18.4).
Date d'effet initiale : 2025-01-01 (à ajuster selon l'historique réel).
"""
import datetime as dt

from socle.schema import (
    init_db, get_session,
    ParamBaremeProvision, ParamBaremePrime, ParamTauxIBP, ParamReintegration,
    ParamTauxChange,
)

EFFET = dt.date(2025, 1, 1)


def seed(db_path="socle/micropop.db"):
    init_db(db_path)
    s = get_session(db_path)

    # Barème de provision (§4.4) — 7 tranches
    bareme = [
        (0, 0, "Sain", 0.0, 0),
        (1, 30, "PAR 1-30", 0.05, 1),
        (31, 60, "PAR 31-60", 0.25, 2),
        (61, 90, "PAR 61-90", 0.50, 3),
        (91, 180, "PAR 91-180", 0.75, 4),
        (181, 360, "PAR 181-360", 1.00, 5),
        (361, None, "PAR 361+", 1.00, 6),
    ]
    if not s.query(ParamBaremeProvision).first():
        for mn, mx, tr, tx, code in bareme:
            s.add(ParamBaremeProvision(date_effet=EFFET, min_jours=mn, max_jours=mx,
                                       tranche=tr, taux=tx, code=code))

    # Barème de primes + correcteur PAR (§60)
    if not s.query(ParamBaremePrime).first():
        correcteurs = [(0.0, 0.03, 1.0), (0.03, 0.05, 0.7), (0.05, 0.07, 0.5), (0.07, None, 0.0)]
        for pmin, pmax, corr in correcteurs:
            s.add(ParamBaremePrime(date_effet=EFFET, prime_volume=150, prime_nombre=90,
                                   prime_couverture=60, seuil_realisation=1.0,
                                   par_min=pmin, par_max=pmax, correcteur=corr))

    # Taux IBP légal (§67)
    if not s.query(ParamTauxIBP).first():
        s.add(ParamTauxIBP(date_effet=EFFET, taux=0.30))

    # Réintégrations fiscales connues (§67) — grille complète à compléter avec le DAF
    if not s.query(ParamReintegration).first():
        s.add(ParamReintegration(date_effet=EFFET, compte_ou_ligne="communication",
                                 taux_reintegration=0.50))
        s.add(ParamReintegration(date_effet=EFFET, compte_ou_ligne="dons_personnel",
                                 taux_reintegration=1.00))

    # Taux de change (§42) — exemple juillet 2026 vu dans le fichier magique
    if not s.query(ParamTauxChange).first():
        s.add(ParamTauxChange(date_effet=dt.date(2026, 7, 1),
                              devise_source="USD", devise_cible="CDF", taux=2268.75))

    s.commit()
    print("Paramètres initiaux chargés.")
    print(f"  barème provision : {s.query(ParamBaremeProvision).count()} tranches")
    print(f"  barème primes    : {s.query(ParamBaremePrime).count()} lignes")
    print(f"  réintégrations   : {s.query(ParamReintegration).count()} (à compléter avec le DAF)")
    s.close()


if __name__ == "__main__":
    seed()
