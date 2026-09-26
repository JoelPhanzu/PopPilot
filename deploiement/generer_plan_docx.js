// Génère docs/Plan_deploiement_PopPilot.docx — les scripts sont LUS dans deploiement/.
// Usage (npm install docx dans un dossier de travail) : node generer_plan_docx.js <dossier PopPilot> <sortie.docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, LevelFormat, TableOfContents, Footer, Header, PageNumber,
  PageBreak,
} = require("docx");

const RACINE = process.argv[2];
const SORTIE = process.argv[3];
const lire = (p) => fs.readFileSync(path.join(RACINE, p), "utf8").replace(/^\uFEFF/, "").replace(/\r/g, "");

const BLEU = "0B3D5C", BLEU2 = "1B5E86", GRIS = "58595B", FOND = "F4F7FA", CODE = "F2F4F6";
const LARGEUR = 9638; // A4 portrait, marges 2 cm → 11906 - 2*1134

// ---------- briques ----------
const t = (texte, o = {}) => new TextRun({ text: texte, ...o });
const p = (enfants, o = {}) => new Paragraph({ spacing: { after: 120, line: 276 }, ...o,
  children: (Array.isArray(enfants) ? enfants : [enfants]).map((e) => (typeof e === "string" ? t(e) : e)) });
const h1 = (x) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t(x)] });
const h2 = (x) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [t(x)] });
const h3 = (x) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [t(x)] });
const puce = (enfants, niveau = 0) => new Paragraph({ numbering: { reference: "puces", level: niveau },
  spacing: { after: 60 }, children: (Array.isArray(enfants) ? enfants : [enfants]).map((e) => (typeof e === "string" ? t(e) : e)) });
const num = (enfants, ref = "etapes") => new Paragraph({ numbering: { reference: ref, level: 0 },
  spacing: { after: 60 }, children: (Array.isArray(enfants) ? enfants : [enfants]).map((e) => (typeof e === "string" ? t(e) : e)) });
const b = (x) => t(x, { bold: true });
const c = (x) => t(x, { font: "Consolas", size: 18, color: BLEU2 });
const saut = () => new Paragraph({ children: [new PageBreak()] });

function code(texte, titre) {
  const lignes = texte.replace(/\s+$/, "").split("\n");
  const out = [];
  if (titre) out.push(new Paragraph({ spacing: { before: 120, after: 0 }, keepNext: true,
    shading: { type: ShadingType.CLEAR, fill: BLEU, color: "auto" },
    children: [t(" " + titre, { font: "Consolas", size: 17, color: "FFFFFF", bold: true })] }));
  lignes.forEach((l, i) => out.push(new Paragraph({
    spacing: { before: 0, after: i === lignes.length - 1 ? 160 : 0, line: 228 },
    shading: { type: ShadingType.CLEAR, fill: CODE, color: "auto" },
    children: [t(l.length ? l : " ", { font: "Consolas", size: 16 })],
  })));
  return out;
}
const script = (chemin) => code(lire(chemin), chemin);

const bordure = { style: BorderStyle.SINGLE, size: 4, color: "C9D3DC" };
const bordures = { top: bordure, bottom: bordure, left: bordure, right: bordure };
function tableau(entetes, lignes, largeurs) {
  const total = largeurs.reduce((a, x) => a + x, 0);
  const cell = (contenu, entete, w) => new TableCell({
    borders: bordures, width: { size: w, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: entete ? BLEU : "FFFFFF", color: "auto" },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: (Array.isArray(contenu) ? contenu : [contenu]).map((x) => new Paragraph({ spacing: { after: 0 },
      children: [typeof x === "string" ? t(x, { bold: entete, color: entete ? "FFFFFF" : undefined, size: 19 }) : x] })),
  });
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: largeurs, rows: [
    new TableRow({ tableHeader: true, children: entetes.map((e, i) => cell(e, true, largeurs[i])) }),
    ...lignes.map((l) => new TableRow({ children: l.map((x, i) => cell(x, false, largeurs[i])) })),
  ] });
}
const encadre = (titre, texte, couleur = "FFF6E5", bordureCouleur = "E0A030") => new Table({
  width: { size: LARGEUR, type: WidthType.DXA }, columnWidths: [LARGEUR],
  rows: [new TableRow({ children: [new TableCell({
    width: { size: LARGEUR, type: WidthType.DXA },
    borders: { top: { style: BorderStyle.SINGLE, size: 4, color: bordureCouleur }, bottom: { style: BorderStyle.SINGLE, size: 4, color: bordureCouleur },
      left: { style: BorderStyle.SINGLE, size: 24, color: bordureCouleur }, right: { style: BorderStyle.SINGLE, size: 4, color: bordureCouleur } },
    shading: { type: ShadingType.CLEAR, fill: couleur, color: "auto" },
    margins: { top: 100, bottom: 100, left: 160, right: 160 },
    children: [new Paragraph({ spacing: { after: 60 }, children: [b(titre)] }),
      ...(Array.isArray(texte) ? texte : [texte]).map((x) => new Paragraph({ spacing: { after: 40 }, children: [t(x, { size: 20 })] }))],
  })] })],
});
const espace = () => new Paragraph({ spacing: { after: 80 }, children: [] });

// ---------- contenu ----------
const doc = [];

// Page de titre
doc.push(
  new Paragraph({ spacing: { before: 2400, after: 200 }, children: [t("PopPilot", { size: 64, bold: true, color: BLEU })] }),
  new Paragraph({ spacing: { after: 120 }, children: [t("Plateforme de pilotage MICROPOP", { size: 30, color: BLEU2 })] }),
  new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: "00AEEA", space: 6 } }, spacing: { after: 400 }, children: [] }),
  new Paragraph({ spacing: { after: 160 }, children: [t("Plans de déploiement", { size: 44, bold: true })] }),
  new Paragraph({ spacing: { after: 120 }, children: [t("A. Serveurs de MICROPOP — site, API et base sur le réseau interne", { size: 24 })] }),
  new Paragraph({ spacing: { after: 800 }, children: [t("B. Poste local du contrôle de gestion — base PostgreSQL sur l'ordinateur, à côté de l'API et du site", { size: 24 })] }),
  p([t("Version du 25 septembre 2026 · Contrôle de gestion", { color: GRIS })]),
  p([t("Tous les scripts cités sont joints dans le dépôt, dossier ", { color: GRIS }), c("deploiement/"), t(", et reproduits intégralement en annexe de chaque plan.", { color: GRIS })]),
  new Paragraph({ spacing: { before: 1600 }, children: [t("Je rêve, je réalise", { italics: true, color: BLEU2, size: 24 })] }),
  saut(),
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [t("Sommaire")] }),
  new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-2" }),
  saut(),
);

// 1. Vue d'ensemble
doc.push(
  h1("1. Vue d'ensemble"),
  h2("1.1 Pourquoi rapatrier la plateforme"),
  p("Aujourd'hui, la base de données est hébergée par Supabase au Canada, tandis que l'API et le site tournent sur le poste. Deux limites en découlent :"),
  puce([b("Lenteur : "), t("chaque calcul fait l'aller-retour entre Kinshasa et le Canada. Un tableau de bord crédit prenait 60 à 85 secondes ; avec une base sur le même réseau que l'API, il se calcule en quelques secondes.")]),
  puce([b("Capacité : "), t("l'offre gratuite de Supabase est plafonnée à 500 Mo. Un seul inventaire dépôt occupe 74 Mo ; les 20 derniers mois représentent environ 1,5 Go. L'historique ne peut donc pas être chargé dans le cloud actuel.")]),
  p("La décision du contrôle de gestion (25/09/2026) est de faire tourner les trois briques chez MICROPOP. En attendant les serveurs, la même installation peut être faite sur le poste du contrôle de gestion (plan B)."),
  h2("1.2 Les trois briques"),
  tableau(["Brique", "Technologie", "Rôle"], [
    ["Base de données", "Supabase = PostgreSQL 17 + service de connexion (Auth)", "Stocke les faits datés, les paramètres, les comptes. Le cloisonnement par agence (RLS) y est appliqué."],
    ["API", "Python / FastAPI (dossier api/)", "Expose les moteurs de calcul validés (PAR, provisions, états financiers, FINA, AML…). Ne recalcule rien ailleurs."],
    ["Site", "Next.js (dossier web/)", "Les écrans, les imports, les exports. N'affiche que ce que l'API calcule."],
  ], [1900, 3400, 4338]),
  espace(),
  p([b("Rien ne change dans le code : "), t("c'est la même technologie partout. Seules les adresses écrites dans deux fichiers de configuration changent : "), c("api/.env"), t(" et "), c("web/.env.local"), t(".")]),
  h2("1.3 Les deux plans comparés"),
  tableau(["", "A. Serveurs MICROPOP", "B. Poste local"], [
    ["Pour qui", "Tous les utilisateurs (DG, DAF, CDG, agences, audit)", "Le contrôle de gestion seul"],
    ["Accès", "Navigateur, https://poppilot.micropop.local", "Navigateur du poste, http://localhost:3000"],
    ["Capacité", "200 Go et plus (tout l'historique)", "Disque du poste (151 Go libres aujourd'hui)"],
    ["Disponibilité", "Permanente (service système, redémarrage auto)", "Seulement quand le poste est allumé et la plateforme démarrée"],
    ["Sauvegarde", "Chaque nuit, copie sur un autre serveur", "Chaque jour à 13 h, copie sur disque externe ou OneDrive"],
    ["Qui installe", "Service informatique + CDG (recette)", "CDG, avec ce guide"],
    ["Quand", "Dès que le serveur est livré", "Tout de suite"],
  ], [1700, 3969, 3969]),
  espace(),
  encadre("Ordre conseillé", [
    "1) Plan B tout de suite : le poste devient la plateforme de travail du CDG, l'historique y est chargé.",
    "2) Plan A à la livraison des serveurs : la base du poste y est transférée en une fois (§ 5), puis les agences s'y connectent.",
  ], "EAF4FB", "00AEEA"),
  h2("1.4 Règles qui valent pour les deux plans"),
  puce([b("Jamais de chargement SQL brut "), t("(COPY, éditeur SQL, pgAdmin) dans les tables de faits : il contournerait le classement des produits, la purge du mois, le journal des imports. Les imports passent par le site ou par le script "), c("api/outils/import_masse.py"), t(", qui appellent les mêmes fonctions.")]),
  puce([b("Secrets : "), t("mot de passe de la base, clé JWT, clé service_role restent dans les fichiers .env (ignorés par git) et dans le coffre-fort de MICROPOP. Jamais dans un courriel, jamais dans le site.")]),
  puce([b("Une sauvegarde non testée n'existe pas : "), t("restaurer une sauvegarde une fois par trimestre, sur une base d'essai.")]),
  puce([b("Contrôle après chaque transfert : "), c("api/outils/comparer_bases.py"), t(" compare, table par table et mois par mois, le nombre de lignes entre l'ancienne et la nouvelle base.")]),
  saut(),
);

// 2. Préalables communs
doc.push(
  h1("2. Préalables communs"),
  tableau(["Préalable", "Détail", "Plan"], [
    ["Code de PopPilot", "Dépôt git github.com/JoelPhanzu/PopPilot (branche main), à jour et poussé.", "A et B"],
    ["Accès internet", "Pour télécharger les images Docker (≈ 3 Go), les paquets Python et Node, une fois à l'installation.", "A et B"],
    ["Mot de passe du cloud actuel", "Adresse DATABASE_URL du fichier api/.env actuel : sert à copier les données existantes.", "A et B"],
    ["Liste des comptes", "Adresse, rôle (DIRECTION, CDG, AGENCE, AUDIT) et agence de chaque utilisateur.", "A et B"],
    ["Sauvegarde du cloud", "Fichier .dump produit par l'étape de copie : il est conservé dans sauvegardes/.", "A et B"],
    ["Nom de domaine interne", "poppilot.micropop.local (ou autre) déclaré dans le DNS de MICROPOP.", "A"],
    ["Certificat HTTPS", "Délivré par l'autorité interne de MICROPOP (ou auto-signé pour la recette).", "A"],
    ["Emplacement de sauvegarde externe", "Dossier d'un autre serveur ou d'un NAS (A) ; disque externe ou OneDrive (B).", "A et B"],
  ], [2500, 5638, 1500]),
  saut(),
);

// 3. PLAN A
doc.push(
  h1("3. Plan A — Serveurs de MICROPOP"),
  h2("3.1 Architecture"),
  ...code([
    " Navigateurs (réseau MICROPOP)",
    "        │ HTTPS (443)",
    "        ▼",
    " ┌──────────────────── serveur PopPilot ────────────────────┐",
    " │ nginx ── /           → site Next.js        127.0.0.1:3000 │",
    " │       ── /supabase/  → Supabase (Kong)     127.0.0.1:8000 │",
    " │ API FastAPI  127.0.0.1:8001  ◄── appelée par le site seul │",
    " │ PostgreSQL 17 (Supabase) ◄── API + Auth                   │",
    " └───────────────────────────────────────────────────────────┘",
  ].join("\n")),
  p("Seul le port 443 (HTTPS) est ouvert au réseau. L'API et la base ne sont jamais exposées : le pare-feu (ufw) est réglé par l'étape 1."),
  h2("3.2 Serveur"),
  tableau(["Élément", "Minimum conseillé"], [
    ["Système", "Ubuntu Server 22.04 ou 24.04 LTS (Windows Server possible : § 3.8)"],
    ["Processeur", "4 cœurs (8 conseillés)"],
    ["Mémoire", "16 Go : Supabase ≈ 4 Go, API ≈ 2 Go, site ≈ 1 Go, marge pour les imports lourds"],
    ["Disque", "200 Go SSD : base (historique complet ≈ 5-10 Go à terme), archives de rapports, 30 jours de sauvegardes"],
    ["Réseau", "Adresse IP fixe, nom DNS interne, accès internet à l'installation"],
    ["Sauvegarde", "Un emplacement sur un AUTRE serveur ou un NAS, monté sur ce serveur"],
  ], [2200, 7438]),
  h2("3.3 Préalables à demander au service informatique"),
  puce("Serveur livré avec Ubuntu, accès administrateur (sudo) par SSH."),
  puce("Nom DNS poppilot.micropop.local pointant sur le serveur."),
  puce("Certificat HTTPS (fichiers .crt et .key) déposé dans /etc/ssl/poppilot/."),
  puce("Dossier de sauvegarde distant monté (ex. /mnt/nas/poppilot)."),
  puce("Ouverture du port 443 depuis les postes des agences (VPN pour les agences distantes)."),
  h2("3.4 Étapes"),
  tableau(["#", "Étape", "Script", "Durée"], [
    ["1", "Préparer le serveur (Docker, Python, Node, nginx, client PostgreSQL 17, pare-feu)", "01_preparer_serveur.sh", "20 min"],
    ["2", "Installer Supabase et générer tous les secrets", "02_installer_supabase.sh", "15 min"],
    ["3", "Poser le schéma PopPilot", "03_appliquer_schema.sh", "2 min"],
    ["4", "Reprendre les données (cloud ou sauvegarde du poste)", "04_reprendre_donnees.sh", "5-30 min"],
    ["5", "Installer l'API en service permanent", "05_installer_api.sh", "15 min"],
    ["6", "Installer le site en service permanent", "06_installer_site.sh", "10 min"],
    ["7", "Publier en HTTPS (nginx)", "nginx_poppilot.conf", "10 min"],
    ["8", "Recréer les comptes et les relier à leur rôle", "Console + lier_utilisateurs.py", "15 min"],
    ["9", "Contrôler la reprise et faire la recette", "comparer_bases.py + § 3.6", "30 min"],
    ["10", "Programmer les sauvegardes", "07_sauvegarde.sh", "5 min"],
  ], [500, 5000, 2838, 1300]),
  espace(),
  p([t("Toutes les commandes se lancent depuis "), c("/opt/poppilot"), t(" (le dépôt cloné à la fin de l'étape 1).")]),
  h3("Étape 1 — Préparer le serveur"),
  ...code("sudo bash deploiement/serveur/01_preparer_serveur.sh\nsudo -u poppilot git clone https://github.com/JoelPhanzu/PopPilot.git /opt/poppilot"),
  h3("Étape 2 — Supabase auto-hébergé"),
  p("Le script génère le mot de passe de la base, le secret JWT, les clés anon et service_role, et le mot de passe de la console. Il les affiche une seule fois à la fin : les noter dans le coffre-fort de MICROPOP."),
  ...code("cd /opt/poppilot\nsudo DOMAINE=poppilot.micropop.local bash deploiement/serveur/02_installer_supabase.sh"),
  encadre("À vérifier à la première installation", [
    "La connexion de l'API passe par le « pooler » de Supabase (utilisateur postgres.poppilot, port 5432). Si la version de Supabase installée expose la base autrement, lire la section « db » / « supavisor » de /opt/supabase/docker/docker-compose.yml et adapter DATABASE_URL (étape 5).",
  ]),
  h3("Étape 3 — Schéma PopPilot"),
  ...code("sudo bash deploiement/serveur/03_appliquer_schema.sh"),
  h3("Étape 4 — Reprise des données"),
  p("Deux sources possibles. La source n'est que lue ; la table des utilisateurs n'est pas reprise (étape 8)."),
  ...code("# Depuis le cloud Supabase actuel\nsudo SOURCE_URL='postgresql://postgres.[REF]:[MDP]@aws-0-ca-central-1.pooler.supabase.com:5432/postgres' \\\n     bash deploiement/serveur/04_reprendre_donnees.sh\n\n# OU depuis une sauvegarde du poste local (plan B)\nsudo DUMP=/srv/sauvegardes/poppilot_2026-10-01.dump bash deploiement/serveur/04_reprendre_donnees.sh"),
  h3("Étape 5 — API"),
  ...code("sudo DOMAINE=poppilot.micropop.local PG_PASS='[étape 2]' JWT_SECRET='[étape 2]' \\\n     bash deploiement/serveur/05_installer_api.sh"),
  p("Le script crée l'environnement Python, écrit api/.env, crée les tables manquantes, lance la campagne de tests (sur des bases de test, jamais la production) et démarre le service poppilot-api."),
  h3("Étape 6 — Site"),
  ...code("sudo DOMAINE=poppilot.micropop.local ANON_KEY='[étape 2]' bash deploiement/serveur/06_installer_site.sh"),
  h3("Étape 7 — HTTPS"),
  ...code("sudo cp deploiement/serveur/nginx_poppilot.conf /etc/nginx/sites-available/poppilot\nsudo ln -s /etc/nginx/sites-available/poppilot /etc/nginx/sites-enabled/poppilot\nsudo nginx -t && sudo systemctl reload nginx"),
  h3("Étape 8 — Comptes utilisateurs"),
  num([t("Ouvrir la console "), c("https://poppilot.micropop.local/supabase"), t(" (identifiants de l'étape 2) → Authentication → Users → Add user, pour chaque personne (case « Auto confirm » cochée).")], "comptesA"),
  num([t("Compléter la correspondance adresse → rôle → agence dans "), c("api/lier_utilisateurs.py"), t(" (variable CORRESPONDANCE).")], "comptesA"),
  num([t("Relier les comptes : "), c("cd /opt/poppilot/api && sudo -u poppilot .venv/bin/python lier_utilisateurs.py")], "comptesA"),
  num([t("Vérifier le cloisonnement : "), c("sudo -u poppilot .venv/bin/python verifier_supabase.py")], "comptesA"),
  p("Recréer les comptes plutôt que copier ceux du cloud : c'est l'occasion de supprimer les comptes de démonstration et de fixer des mots de passe forts."),
  h3("Étape 9 — Contrôle de la reprise"),
  ...code("cd /opt/poppilot/api\nsudo -u poppilot .venv/bin/python outils/comparer_bases.py \\\n  'postgresql://…SOURCE (cloud)…' 'postgresql://postgres.poppilot:[MDP]@127.0.0.1:5432/postgres'"),
  p("Attendu : « TOUT CONCORDE », sauf la table utilisateur (recréée). Toute autre différence est détaillée mois par mois."),
  h3("Étape 10 — Sauvegardes"),
  ...code("sudo cp deploiement/serveur/07_sauvegarde.sh /usr/local/bin/poppilot-sauvegarde\nsudo chmod +x /usr/local/bin/poppilot-sauvegarde\necho '0 2 * * * root COPIE_DISTANTE=/mnt/nas/poppilot /usr/local/bin/poppilot-sauvegarde' | sudo tee /etc/cron.d/poppilot"),
  h2("3.5 Chargement de l'historique (20 mois d'inventaires)"),
  p("Une fois la reprise contrôlée, les fichiers lourds se chargent sans passer par le navigateur :"),
  ...code("cd /opt/poppilot/api\nsudo -u poppilot .venv/bin/python outils/import_masse.py /srv/import/inventaires --a-blanc\nsudo -u poppilot .venv/bin/python outils/import_masse.py /srv/import/inventaires\nsudo -u poppilot .venv/bin/python outils/import_masse.py /srv/import/credit --domaine credit"),
  p("Le mois est lu dans le nom de chaque fichier (« Inventaire dépôt Janvier 2025.csv », « inventaire_2025-01.xlsx »…). Un nom ambigu est refusé avant toute écriture. Une coupure ? Relancer la même commande : les mois déjà en base sont sautés."),
  h2("3.6 Recette de mise en service"),
  tableau(["Contrôle", "Résultat attendu"], [
    ["https://poppilot.micropop.local/login, compte CDG", "Connexion, menu complet"],
    ["Crédit, arrêté du 31/05/2026", "Encours 10 814 330,66 ; PAR30 1 052 118,05 ; 517 décaissements"],
    ["Épargne, arrêté du 31/08/2026", "Encours 6 429 239,22 USD ; 67 610 épargnants"],
    ["Compte d'exploitation, 31/07/2026", "Résultat MICROPOP 24 798,80"],
    ["Compte AGENCE (ex. Victoire)", "Ne voit que son agence, sur tous les écrans et dans les exports"],
    ["Page Import → journal", "Tous les imports repris, dont ceux de l'historique"],
    ["Export PDF d'un tableau", "Fichier téléchargé, lisible"],
  ], [4200, 5438]),
  h2("3.7 Exploitation courante"),
  tableau(["Action", "Commande"], [
    ["État des services", "systemctl status poppilot-api poppilot-web ; docker ps"],
    ["Journaux de l'API", "journalctl -u poppilot-api -f"],
    ["Mettre à jour PopPilot", "sudo bash deploiement/serveur/mettre_a_jour.sh (sauvegarde + tests avant redémarrage)"],
    ["Restaurer une sauvegarde", "sudo bash deploiement/serveur/08_restaurer.sh /srv/sauvegardes/poppilot_AAAA-MM-JJ.dump"],
    ["Nouveau script SQL (supabase/09_…)", "docker exec -i supabase-db psql -U postgres -d postgres < supabase/09_….sql"],
  ], [3000, 6638]),
  h2("3.8 Variante Windows Server"),
  puce("Supabase : Docker Desktop (moteur WSL2), mêmes étapes 2 à 4 que le poste local (plan B), en remplaçant localhost par le nom du serveur."),
  puce([t("API et site en services Windows avec NSSM : "), c("nssm install PopPilotAPI C:\\poppilot\\api\\.venv\\Scripts\\uvicorn.exe main:app --host 127.0.0.1 --port 8001")]),
  puce("Publication HTTPS : IIS avec ARR (proxy inverse) ou nginx pour Windows, mêmes règles que nginx_poppilot.conf."),
  puce("Sauvegarde : sauvegarder.ps1 du plan B, planifié par le Planificateur de tâches."),
  h2("3.9 Scripts du plan A (intégraux)"),
  ...script("deploiement/serveur/01_preparer_serveur.sh"),
  ...script("deploiement/serveur/02_installer_supabase.sh"),
  ...script("deploiement/serveur/03_appliquer_schema.sh"),
  ...script("deploiement/serveur/04_reprendre_donnees.sh"),
  ...script("deploiement/serveur/05_installer_api.sh"),
  ...script("deploiement/serveur/poppilot-api.service"),
  ...script("deploiement/serveur/06_installer_site.sh"),
  ...script("deploiement/serveur/poppilot-web.service"),
  ...script("deploiement/serveur/nginx_poppilot.conf"),
  ...script("deploiement/serveur/07_sauvegarde.sh"),
  ...script("deploiement/serveur/08_restaurer.sh"),
  ...script("deploiement/serveur/mettre_a_jour.sh"),
  saut(),
);

// 4. PLAN B
doc.push(
  h1("4. Plan B — Base locale sur le poste du contrôle de gestion"),
  h2("4.1 Architecture"),
  ...code([
    " Poste du contrôle de gestion (Windows 11)",
    " ┌──────────────────────────────────────────────────────────┐",
    " │ Navigateur → http://localhost:3000   site Next.js         │",
    " │                 │                                         │",
    " │                 ▼                                         │",
    " │          API FastAPI  http://127.0.0.1:8000               │",
    " │                 │                                         │",
    " │                 ▼                                         │",
    " │ Docker Desktop (WSL2) : Supabase local                    │",
    " │   PostgreSQL 17  127.0.0.1:54322   Auth  127.0.0.1:54321  │",
    " │   Console Studio http://127.0.0.1:54323                   │",
    " └──────────────────────────────────────────────────────────┘",
  ].join("\n")),
  p("Les trois briques sont sur la même machine : plus aucun aller-retour vers le Canada. La base locale est la même technologie que la future base des serveurs (Supabase, PostgreSQL 17) : le passage au plan A se fera par simple copie (§ 5)."),
  h2("4.2 Votre poste (mesuré le 25/09/2026)"),
  tableau(["Élément", "Constat", "Conséquence"], [
    ["Système", "Windows 11 Professionnel", "Compatible Docker Desktop"],
    ["Processeur", "Intel Core i5-1135G7, 8 cœurs logiques", "Suffisant"],
    ["Mémoire", "7,7 Go", "Juste : Docker limité à 4 Go, services Supabase inutiles désactivés, fermer les applications lourdes pendant les imports"],
    ["Disque C:", "151 Go libres", "Suffisant pour 20 mois d'historique (≈ 1,5 Go) et 30 jours de sauvegardes"],
    ["WSL2", "Présent", "Rien à faire"],
    ["Docker Desktop", "Absent", "Installé par l'étape 1"],
    ["Python / Node.js", "3.14 / 24", "Déjà utilisés par PopPilot"],
  ], [1800, 3300, 4538]),
  espace(),
  encadre("Si le poste devient trop lent", [
    "Porter la mémoire à 16 Go règle la question. À défaut : arrêter la plateforme (arreter_poppilot.ps1) quand on ne s'en sert pas, et lancer les gros imports en fin de journée.",
  ]),
  h2("4.3 Étapes"),
  tableau(["#", "Étape", "Script", "Durée"], [
    ["1", "Prérequis : Docker Desktop, limite mémoire de WSL2", "01_prerequis.ps1", "20 min + redémarrage"],
    ["2", "Démarrer Supabase local (première fois : téléchargement)", "02_demarrer_supabase_local.ps1", "10-20 min"],
    ["3", "Poser le schéma PopPilot", "03_appliquer_schema.ps1", "2 min"],
    ["4", "Copier les données du cloud", "04_copier_donnees_cloud.ps1", "5-10 min"],
    ["5", "Faire pointer l'API et le site vers la base locale", "05_basculer_base.ps1 -Cible local", "1 min"],
    ["6", "Recréer les comptes et les relier à leur rôle", "Studio + lier_utilisateurs.py", "10 min"],
    ["7", "Contrôler la copie", "comparer_bases.py", "2 min"],
    ["8", "Démarrer la plateforme et faire la recette", "demarrer_poppilot.ps1", "5 min"],
    ["9", "Programmer la sauvegarde quotidienne", "sauvegarder.ps1 -Planifier", "2 min"],
    ["10", "Charger l'historique (20 mois)", "import_masse.py", "1-2 h"],
  ], [500, 4700, 3138, 1300]),
  espace(),
  p([t("Toutes les commandes se lancent dans PowerShell, depuis le dossier "), c("PopPilot"), t(". Préfixe à utiliser pour chaque script : "), c("powershell -ExecutionPolicy Bypass -File"), t(".")]),
  h3("Étape 1 — Prérequis (PowerShell en administrateur)"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\01_prerequis.ps1"),
  p("Après l'installation de Docker Desktop : redémarrer Windows, ouvrir Docker Desktop une fois et accepter ses conditions. Dans Docker Desktop → Settings → General, cocher « Start Docker Desktop when you sign in » si la plateforme doit être disponible dès l'ouverture de session."),
  h3("Étape 2 — Supabase local"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\02_demarrer_supabase_local.ps1"),
  p("Le script affiche à la fin les adresses et les clés (JWT secret, anon key) : l'étape 5 les lit elle-même, rien à recopier."),
  h3("Étape 3 — Schéma"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\03_appliquer_schema.ps1"),
  h3("Étape 4 — Copie des données du cloud"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\04_copier_donnees_cloud.ps1"),
  p("Le cloud n'est que lu. La copie est conservée dans le dossier sauvegardes/ (sauvegarde du cloud au passage)."),
  h3("Étape 5 — Bascule vers la base locale"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\05_basculer_base.ps1 -Cible local"),
  p([t("La configuration cloud actuelle est gardée en "), c("api\\.env.cloud"), t(" et "), c("web\\.env.cloud"), t(". Retour au cloud à tout moment : "), c("-Cible cloud"), t(".")]),
  h3("Étape 6 — Comptes"),
  num([t("Console Studio : "), c("http://127.0.0.1:54323"), t(" → Authentication → Add user, avec les adresses de api/lier_utilisateurs.py (daf@, cdg@, bmvictoire@, audit@poppilot.com) ; cocher « Auto confirm user ».")], "comptesB"),
  num([c("cd api"), t(" puis "), c(".venv\\Scripts\\python.exe lier_utilisateurs.py")], "comptesB"),
  num([c(".venv\\Scripts\\python.exe verifier_supabase.py"), t(" : tous les contrôles au vert.")], "comptesB"),
  h3("Étape 7 — Contrôle de la copie"),
  ...code("cd api\n.venv\\Scripts\\python.exe outils\\comparer_bases.py \"[DATABASE_URL de api\\.env.cloud]\" \"postgresql://postgres:postgres@127.0.0.1:54322/postgres\""),
  h3("Étape 8 — Démarrage et recette"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\demarrer_poppilot.ps1"),
  p("Le navigateur s'ouvre sur la page de connexion. Refaire les contrôles du § 3.6 (mêmes chiffres attendus), avec l'adresse http://localhost:3000."),
  h3("Étape 9 — Sauvegarde quotidienne"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\sauvegarder.ps1 -Planifier\n# Sauvegarde immédiate avec copie sur disque externe :\npowershell -ExecutionPolicy Bypass -File deploiement\\poste\\sauvegarder.ps1 -Copie E:\\Sauvegardes_PopPilot"),
  h3("Étape 10 — Historique"),
  ...code("cd api\n.venv\\Scripts\\python.exe outils\\import_masse.py \"D:\\Inventaires\" --a-blanc\n.venv\\Scripts\\python.exe outils\\import_masse.py \"D:\\Inventaires\""),
  p("Vérifié à blanc sur l'inventaire réel de juillet 2026 : 169 799 comptes, lus en 38 secondes."),
  h2("4.4 Usage quotidien"),
  tableau(["Action", "Commande"], [
    ["Démarrer la plateforme", "deploiement\\poste\\demarrer_poppilot.ps1 (Docker Desktop lancé)"],
    ["Après une mise à jour du code du site", "deploiement\\poste\\demarrer_poppilot.ps1 -Reconstruire"],
    ["Arrêter et libérer la mémoire", "deploiement\\poste\\arreter_poppilot.ps1 (données conservées)"],
    ["Revenir au cloud", "deploiement\\poste\\05_basculer_base.ps1 -Cible cloud, puis redémarrer"],
    ["Restaurer une sauvegarde", "deploiement\\poste\\sauvegarder.ps1 -Restaurer sauvegardes\\poppilot_….dump"],
  ], [3300, 6338]),
  h2("4.5 Limites à connaître"),
  puce("Plateforme disponible seulement quand le poste est allumé et la plateforme démarrée."),
  puce("Accessible depuis ce poste uniquement (les agences continuent d'utiliser le cloud ou attendent le plan A)."),
  puce("Pendant la période sur le poste, les imports faits dans le cloud par d'autres personnes n'arrivent pas sur le poste, et inversement : désigner UNE base de référence (le poste) et n'importer que là."),
  puce("La sauvegarde protège de l'erreur, pas de la panne du poste, sauf si elle est copiée ailleurs (option -Copie)."),
  h2("4.6 Scripts du plan B (intégraux)"),
  ...script("deploiement/poste/01_prerequis.ps1"),
  ...script("deploiement/poste/02_demarrer_supabase_local.ps1"),
  ...script("deploiement/poste/03_appliquer_schema.ps1"),
  ...script("deploiement/poste/04_copier_donnees_cloud.ps1"),
  ...script("deploiement/poste/05_basculer_base.ps1"),
  ...script("deploiement/poste/demarrer_poppilot.ps1"),
  ...script("deploiement/poste/arreter_poppilot.ps1"),
  ...script("deploiement/poste/sauvegarder.ps1"),
  saut(),
);

// 5. Passage B → A
doc.push(
  h1("5. Passage du poste aux serveurs MICROPOP"),
  num("Sur le poste : sauvegarde fraîche.", "passage"),
  ...code("powershell -ExecutionPolicy Bypass -File deploiement\\poste\\sauvegarder.ps1"),
  num("Copier le fichier sauvegardes\\poppilot_….dump sur le serveur, dans /srv/sauvegardes/.", "passage"),
  num("Sur le serveur : étapes 1 à 3 du plan A, puis l'étape 4 avec DUMP=… (pas SOURCE_URL).", "passage"),
  ...code("sudo DUMP=/srv/sauvegardes/poppilot_2026-10-01.dump bash deploiement/serveur/04_reprendre_donnees.sh"),
  num("Étapes 5 à 10 du plan A. Contrôle : comparer_bases.py entre la base du poste et celle du serveur.", "passage"),
  num("Annoncer la nouvelle adresse aux utilisateurs ; arrêter la plateforme du poste pour éviter deux bases de référence.", "passage"),
  saut(),
);

// 6. Outils communs
doc.push(
  h1("6. Outils communs"),
  h2("6.1 Contrôle après transfert — comparer_bases.py"),
  p("Compare deux bases, table par table, puis mois par mois pour les tables datées. Lecture seule. Testé sur la base de production le 25/09/2026 (39 tables, « TOUT CONCORDE »)."),
  ...script("api/outils/comparer_bases.py"),
  h2("6.2 Import en masse — import_masse.py"),
  p("Appelle les fonctions d'import du site (mêmes règles, même journal). Options : --a-blanc, --remplacer, --correspondance, --domaine credit, --oui, --base-sqlite. Testé de bout en bout (tests/test_import_masse.py) et à blanc sur l'inventaire réel de juillet 2026."),
  ...script("api/outils/import_masse.py"),
  saut(),
);

// 7. Dépannage & annexes
doc.push(
  h1("7. Dépannage"),
  tableau(["Symptôme", "Cause probable", "Solution"], [
    ["« supabase start » échoue", "Docker Desktop n'est pas lancé", "Ouvrir Docker Desktop, attendre « Engine running », relancer"],
    ["Le site affiche « l'API ne répond pas »", "API arrêtée, ou mauvaise adresse dans web/.env.local", "Relancer demarrer_poppilot.ps1 ; vérifier NEXT_PUBLIC_POPPILOT_API"],
    ["Connexion refusée sur la page de login", "Compte non créé dans la base locale, ou non relié", "Étape 6 (Studio + lier_utilisateurs.py)"],
    ["« The specified alg value is not allowed »", "Clés JWT de l'autre base", "Refaire 05_basculer_base.ps1 ; redémarrer l'API"],
    ["pg_restore : avertissements", "Tables déjà remplies, ou version", "comparer_bases.py dit ce qui manque ; ne pas relancer la copie sur une base déjà chargée sans --clean"],
    ["Poste très lent", "Mémoire saturée (7,7 Go)", "Fermer les applications lourdes ; arreter_poppilot.ps1 hors usage ; 16 Go conseillés"],
    ["« bad interpreter » sur le serveur", "Fins de ligne Windows dans un .sh", "Le dépôt force les fins de ligne Linux (.gitattributes) : recloner, ou dos2unix"],
    ["Import refusé « mois ambigu »", "Nom de fichier sans mois clair", "Renommer, ou --correspondance fichier.txt (nom;AAAA-MM)"],
  ], [2700, 3200, 3738]),
  h1("8. Annexes"),
  h2("8.1 Ports"),
  tableau(["Service", "Plan A (serveur)", "Plan B (poste)", "Exposé au réseau"], [
    ["Site Next.js", "127.0.0.1:3000 → 443 via nginx", "localhost:3000", "A : oui (HTTPS) ; B : non"],
    ["API FastAPI", "127.0.0.1:8001", "127.0.0.1:8000", "Jamais"],
    ["Supabase Auth (Kong)", "127.0.0.1:8000 → /supabase/", "127.0.0.1:54321", "A : via nginx ; B : non"],
    ["PostgreSQL", "pooler 127.0.0.1:5432", "127.0.0.1:54322", "Jamais"],
    ["Console Studio", "via /supabase/ (mot de passe)", "127.0.0.1:54323", "A : via nginx ; B : non"],
  ], [2200, 2700, 2200, 2538]),
  h2("8.2 Fichiers de configuration"),
  tableau(["Fichier", "Contenu", "Versionné ?"], [
    ["api/.env", "DATABASE_URL, SUPABASE_URL, SUPABASE_JWT_SECRET, POPPILOT_ARCHIVES_DIR", "Non (secret)"],
    ["web/.env.local", "NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_POPPILOT_API", "Non"],
    ["api/.env.cloud, .env.poste (et web/…)", "Les deux configurations du plan B, activées par 05_basculer_base.ps1", "Non"],
    ["/opt/supabase/docker/.env", "Secrets du Supabase auto-hébergé (plan A)", "Non (coffre-fort)"],
    ["supabase/config.toml", "Projet Supabase local (plan B), créé par l'étape 2", "Oui (sans secret)"],
  ], [3000, 5138, 1500]),
  h2("8.3 État de validation des scripts"),
  p("Vérifié le 25/09/2026 : syntaxe de tous les scripts (analyseur PowerShell, bash -n) ; générateur de clés Supabase validé par la bibliothèque JWT de l'API ; comparer_bases.py exécuté sur la production ; import_masse.py testé de bout en bout et à blanc sur l'inventaire réel de juillet 2026."),
  p([b("Non exécutés à ce jour : "), t("les étapes d'installation Docker / Supabase (Docker n'est pas encore installé sur le poste, et le serveur n'est pas livré). Ils seront validés à la première installation ; tout écart constaté sera corrigé dans le dépôt et dans ce document.")]),
);

const document = new Document({
  creator: "Contrôle de gestion MICROPOP",
  title: "PopPilot — Plans de déploiement",
  description: "Serveurs MICROPOP et poste local",
  styles: {
    default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: BLEU, font: "Calibri" }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: BLEU2, font: "Calibri" }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, color: BLEU, font: "Calibri" }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "puces", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
    ...["etapes", "comptesA", "comptesB", "passage"].map((r) => ({ reference: r, levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] })),
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [t("PopPilot — Plans de déploiement", { size: 16, color: GRIS })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("MICROPOP · Contrôle de gestion · page ", { size: 16, color: GRIS }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GRIS })] })] }) },
    children: doc,
  }],
});

Packer.toBuffer(document).then((buf) => { fs.writeFileSync(SORTIE, buf); console.log("écrit :", SORTIE, buf.length, "octets"); });
