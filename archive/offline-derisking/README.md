# `_offline/` — harnais d'itération physique focus_v2 (scratch, HORS livrable)

> ⚠️ **Chemin non standard / scratch.** Rien ici n'est un livrable. Le **modèle** va dans le core
> `LOTUSim/assets/models/focus_v2/`, les **contrôleurs/scénarios** dans `LOTUSim-generic-scenario/src/agents/`.
> Ce dossier sert à itérer/mesurer la physique en boucle fermée sans lancer gz/ROS/Unity.
> (Contient aussi du travail de juin : rendu Unity, démos round, `*.poses.json`, `*.world` — non lié à la session physique 2026-07-05.)

## Le harnais co-sim — `cosim.py`

Boucle fermée **Python ↔ `xdyn-for-cs`** (websocket RFC6455, stdlib pure, zéro dépendance).
`xdyn-for-cs` est un **serveur de pas** : on lui POST `{Dt, states:[état NED], commands}`, il intègre et
renvoie le nouvel état. `cosim.py` tient l'état, un contrôleur calcule barre+écoute, on avance. C'est la
**fondation de l'interface étudiante + du parcours** (le vrai lotusim fait pareil, en plus lourd).

```bash
# Docker doit tourner (image amd64/Rosetta lotusim:focus-v2 ; binaires LOTUSim/physics/xdyn{,-for-cs})
python3 _offline/cosim.py            # démo parcours (contrôleur WIP, cf état physique ci-dessous)
python3 _offline/cosim.py probe 0.005 # sonde robustesse (virage forcé)
```

## 🔑 Technique clé (RÉUTILISABLE) : découpler intégration et communication

Le co-sim **interdit les solveurs adaptatifs** (horloge monotone → `rkck` refusé : *history must be recorded
in strictly increasing order*). On est donc en **rk4 pas fixe**. MAIS `xdyn-for-cs` **sous-cadence** :

| paramètre | rôle |
|---|---|
| `--dt` (au lancement) | **pas d'intégration RÉEL** du solveur (« value of the fixed time step ») |
| `Dt` (dans le message websocket) | **horizon co-sim** — de combien avancer cet échange |

Si `Dt_message > --dt`, xdyn fait **plusieurs sous-pas `--dt`** par échange. **Pas effectif = min(--dt, Dt_message).**
Prouvé (`subdiv.py`) : `--dt=0.001` + `Dt_message=0.02` donne la trajectoire du **full-fin** (u=0.69), ≠ du
grossier `--dt=0.02` (u=0.62).

➡️ **On lance avec un `--dt` fin (0.001)** — propre au faible amortissement / aux manœuvres — **et on
communique/pilote plus lentement** (`Dt=0.02`, 50 Hz) : **stabilité numérique SANS surcoût de communication**.
Dans le vrai lotusim : lancer `xdyn-for-cs --dt 0.001`, le plugin gz envoie son `Dt` au rythme du rendu.
Coût : le calcul interne monte en ~`1/--dt` (pour 1 bateau c'est trivial ; garder les sims longues raisonnables).

## ⚠️ Cause racine (2026-07-05) — convention quaternion co-sim transposée

L'ingouvernabilité au près N'EST PAS un problème de physique : c'est la **convention quaternion du co-sim**.
xdyn (autorité) attend le quaternion d'état en **ned→corps** ; le chemin fournit l'attitude **corps→NED** →
rotation transposée → **la force des foils (quille+safran) dépend du cap** (correcte étrave N/S, inversée
ailleurs) → dérive vers le vent, ardente inversée, bateau ingouvernable. **La physique du yaml est saine.**
Prouvé single-step (`conjug_test`, `attitude_trigger`, `ned_vel_test`) : **quaternion conjugué + vitesse NED**
= foils corrects (`alpha` = vraie dérive, quille qui résiste) à **tous** les caps. Fix côté LOTUSim (plugin,
**PR-3**, couplée à **PR-1**). Détails complets : `../focus_v2_notes.md`.

⚠️ **Ce harnais** a la mauvaise convention câblée (vitesses corps + quaternion non conjugué) → à réécrire en
**conj+NED** (tout l'état) pour une démo boucle-fermée propre ; `HELM_SIGN` s'inverse alors.

**Acquis prouvés** : cause racine identifiée ; harnais boucle-fermée ; technique `--dt` ; introspection des
forces xdyn (`requested_output`) ; le 6-DOF suffit.

📖 **Vérité durable & détails** : `../focus_v2_notes.md` §2026-07-05 (params expérimentaux, diagnostic complet,
recette de virement, handoff experts). Méthodo debugging : skill `lotusim-developer/references/debugging-physics.md`.
