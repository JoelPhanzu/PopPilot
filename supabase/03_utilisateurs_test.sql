-- ============================================================
-- PopPilot — Utilisateurs de test
-- ============================================================
-- IMPORTANT : les comptes de connexion (email + mot de passe) se créent d'abord
-- dans Supabase → Authentication → Users (bouton "Add user"), OU via l'API d'auth.
-- Ensuite, on lie chaque compte auth à une ligne de la table utilisateur ci-dessous,
-- en renseignant auth_uid = l'UUID du compte créé dans Authentication.
--
-- Étapes :
-- 1. Créer 4 users dans Authentication (ex. dg@poppilot.cd, cdg@poppilot.cd,
--    victoire@poppilot.cd, audit@poppilot.cd) avec un mot de passe chacun.
-- 2. Copier l'UUID de chacun (colonne "UID" dans la liste des users).
-- 3. Remplacer les <UUID_...> ci-dessous par les vrais UUID, puis exécuter.

INSERT INTO utilisateur (login, nom_complet, role, agence, actif, date_creation, mot_de_passe_hash, sel, auth_uid)
VALUES
 ('dg',       'Directeur Général Adjoint', 'DIRECTION', NULL,                 true, CURRENT_DATE, 'supabase', 'supabase', '<UUID_DG>'),
 ('cdg',      'Contrôleur de gestion',     'CDG',       NULL,                 true, CURRENT_DATE, 'supabase', 'supabase', '<UUID_CDG>'),
 ('victoire', 'Responsable Victoire',      'AGENCE',    'AGENCE DE VICTOIRE', true, CURRENT_DATE, 'supabase', 'supabase', '<UUID_VICTOIRE>'),
 ('audit',    'Auditeur interne',          'AUDIT',     NULL,                 true, CURRENT_DATE, 'supabase', 'supabase', '<UUID_AUDIT>')
ON CONFLICT (login) DO UPDATE
  SET role = EXCLUDED.role, agence = EXCLUDED.agence, auth_uid = EXCLUDED.auth_uid;
-- Note : mot_de_passe_hash/sel ne servent plus (l'auth est gérée par Supabase),
-- mais restent NOT NULL dans le schéma → on met une valeur neutre.
