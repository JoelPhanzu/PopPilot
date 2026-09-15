-- ============================================================
-- PopPilot — Vérifier que le cloisonnement par agence fonctionne
-- ============================================================
-- À exécuter en se plaçant dans le contexte d'un utilisateur AGENCE.
-- Dans Supabase, l'éditeur SQL s'exécute en rôle "service" (bypass RLS) :
-- pour un vrai test, utilisez l'API depuis le front connecté en tant qu'agence,
-- OU simulez le contexte auth avec les commandes ci-dessous.

-- Simuler l'utilisateur "victoire" (remplacer par son vrai auth_uid) :
--   SELECT set_config('request.jwt.claims',
--     json_build_object('sub','<UUID_VICTOIRE>','role','authenticated')::text, true);
--   SET ROLE authenticated;

-- Test 1 : l'agence Victoire NE DOIT voir QUE ses propres crédits
--   SELECT DISTINCT agence FROM fait_credit;
--   → doit renvoyer uniquement 'AGENCE DE VICTOIRE'

-- Test 2 : compter les crédits visibles vs total réel
--   SELECT count(*) FROM fait_credit;                          -- vu par l'agence (cloisonné)
--   -- comparer avec le total réel (exécuté en service_role) : doit être < total

-- Réinitialiser :
--   RESET ROLE;

-- ✅ Si Victoire ne voit que ses lignes, le cloisonnement au niveau BASE est validé.
--    (bien plus sûr qu'un filtre d'interface : impossible à contourner)
