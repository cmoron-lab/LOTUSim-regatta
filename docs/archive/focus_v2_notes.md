# Focus V2 (voilier RC 1 m) — notes de travail (source de vérité)

Modèle **three-foil** pour LOTUSim : voile = `aerodynamic polar`, quille + safran = `hydrodynamic polar`.
Runtime = image **amd64 `lotusim:focus-v2`** (Rosetta) ; tuning offline via `physics/xdyn` standalone et le
harnais boucle-fermée `_offline/cosim.py`. Licence EPL-2.0 : tout ré-authoré depuis des dimensions publiées.
Branches : **LOTUSim `feature/focus-v2-model`** (modèle), **generic-scenario `feature/focus-v2-helmsman`** (contrôleur).

## Objectif
Des étudiants pilotent focus_v2 dans lotusim pour tester des **algos de trajectoire et gagner une course**
(windward-leeward). Physique **arcade mais cohérente**, la **commande de voile doit être un vrai levier**.
« Réaliste au moins dans l'idée » : un algo qui marche ici doit transférer directionnellement au réel.

---

## Specs réelles Focus V2 (publiées)
- LOA 995 mm, bau 170 mm, creux coque 80 mm, masse RTR **2930 g**.
- Surface de voile : GV **0.342 m²**, foc **0.213 m²** → total ≈ **0.555 m²**.
- Hauteur mât 1578 mm ; hauteur totale (bulbe→tête de mât) 2046 mm.
- **ESTIMÉ** (pas de valeur publiée) : tirant d'eau quille ≈ **0.39 m** ; bulbe (lest) ≈ **1.9 kg** sur les
  2.93 kg ; CdG ≈ 0.25–0.30 m sous l'origine. Marquer tout estimé `# ESTIMATED — pending naval-engineer validation`.

## Schéma xdyn — VÉRIFIÉ depuis les sources naval-group/LOTUSim-Xdyn
Frames : **NED** (X-nord, Y-est, Z-**bas**) ; corps X-avant, Y-tribord, Z-bas ; rotations `[psi,theta',phi'']` ;
quaternion `qr,qi,qj,qk` (réel d'abord). Normales STL **vers l'extérieur**. `air rho` requis pour l'aéro.

**Voile** = `aerodynamic polar` : xdyn calcule le **vent apparent vrai** = vent(NED) − vitesse du corps au point
de calcul. `AWA` = angle du vent apparent (0° = debout au vent, 90° = travers, 180° = plein vent arrière).
`alpha = AWA − commande` (la commande borde/choque la voile). CoE au point `calculation point` (z<0 = au-dessus de l'eau).

**Quille & safran** = `hydrodynamic polar` : force latérale issue de l'incidence du flux (dérive). Quille = pas
de commande (fixe). Safran = avec commande (`alpha = beta + commande`). ⚠️ le point de calcul doit être **z>0
(sous l'eau)** sinon warning + force nulle. `take waves orbital velocity into account: false` requis.

**Clés de commande (modèle actuel)** : `mainsail(sheet)` et `rudder(helm)` (valeurs `angle command:` du yaml).
Format co-sim/JSON : `<nom du force model>(<angle command>)`. ⚠️ `commands.at(key)` **lève** si la clé est
absente à t=0 → nécessite le seeding `<control_surfaces>` en co-sim (le bloc yaml `commands:` n'est lu qu'en
standalone, `xdyn-for-cs` l'ignore).

**Vent** : `direction` = **cap vers lequel le vent SOUFFLE** (N0 E90 S180 W270). Ex. `direction: 180` = vent du Nord.

## Chemin co-sim (vérifié)
gz `physics_interface_plugin` s'abonne à `/<world>/vessel_cmd_array`, relaie chaque `VesselCmd.cmd_string`
(JSON) tel quel à xdyn (`data["commands"]=json::parse(...)`). Le contrôleur publie `{"mainsail(sheet)":..,
"rudder(helm)":..}`. Le world a besoin de `<gravity>0 0 0</gravity>` ; ajouter `SceneBroadcaster` + un `<visual>`
pour voir le bateau dans le GUI gz.

## Emplacements (conventions projet)
- **Modèle** (config/sdf/yaml/meshes) + world de démo → **core** `assets/models/focus_v2/`, `assets/worlds/`.
- **Corrections moteur** → **core** `systems/physics_engine_interface/`.
- **Contrôleur** (skipper boucle-fermée) → **generic-scenario** `src/agents/focus_v2/`.
- Précédents de référence : `wamv`, `dtmb_hull`, `lrauv_propeller.py`, `defenseScenario.json`.

## Corrections moteur (cibles PR)
- **PR-1 swap quaternion j/k** — `systems/physics_engine_interface/src/xdyn_websocket.cpp:268-272` construit
  `Quaterniond(qr,qi,qk,qj)` (j/k inversés) → le lacet ne s'accumule pas → les bateaux avancent tout droit.
  L'empaquetage sortant `:315-330` est correct. **Requis pour que le bateau tourne** en co-sim gz.
- **PR-2 seeding `<control_surfaces>`** — le plugin ne seede que depuis `<thrusters>`. Ajouter le parsing
  `<control_surfaces>` seedant les clés angle (`mainsail(sheet)`, `rudder(helm)`) à 0.0 pour que `commands.at()`
  ne lève pas avant le 1er setpoint ROS.
- **PR-3 convention quaternion co-sim (sortie plugin→xdyn) — LE fix de l'ingouvernabilité** —
  `xdyn_websocket.cpp:308` envoie `quatEnuToNed(pose.Rot())` = l'attitude **corps→NED** (`quatEnuToNed` est
  une similarité qui ré-exprime la rotation, ne l'inverse PAS). Or xdyn ATTEND le quaternion d'état en
  **ned→corps** : `BodyStates::get_rot_from_ned_to_body()` (`BodyStates.cpp:143`) = `Quaternion(qr,qi,qj,qk).matrix()`
  utilisé tel quel comme rotation NED→corps par TOUS les foils (`HydroPolarForceModel.cpp:123`). → le plugin envoie
  la rotation **transposée** → **la force des foils (quille+safran) dépend du CAP** (juste étrave N/S, inversée
  ailleurs) → dérive au vent, ardente inversée, **voilier ingouvernable**. **Fix LOTUSim** : envoyer l'inverse,
  `quatEnuToNed(pose.Rot()).Inverse()` (la vitesse `vecEnuToNed(lin_vel)` = NED est déjà correcte).
  **xdyn dicte la convention** (co-simulateur = autorité), LOTUSim s'y adapte — on ne touche pas xdyn. Frère de la
  PR-1 (même famille quaternion : PR-1 = entrée avec swap j/k, PR-3 = sortie transposée) → réconcilier les deux et
  vérifier l'aller-retour complet en sim. Cause racine prouvée au niveau protocole (`_offline/conjug_test`), cf ci-dessous.

---

# PHYSIQUE DU VOILIER — état & découvertes (itération 2026-07-05)

Itération sur la physique pour l'usage pédago. Standalone xdyn / co-sim uniquement (pas de gz/ROS/Unity pour
l'instant = itération 2). Spec + plan : `docs/superpowers/{specs,plans}/2026-07-05-focus-v2-physique-arcade*`.

## 🔑🔑 CAUSE RACINE — convention quaternion co-sim transposée → force des foils dépendante du CAP → voilier ingouvernable

**Le fait (prouvé, single-step non ambigu — `_offline/conjug_test`, `attitude_trigger`).** Dans le co-sim, la
force latérale des foils (quille + safran) **dépend du cap boussole** — physiquement impossible. À vitesses corps
identiques, tourner l'étrave change l'angle d'attaque `alpha` que la quille voit (mesuré : **+18.5° à cap 0**,
**-33° à cap 52**, **-72° à cap 90**, **+19° à cap 180**). Correcte seulement étrave **Nord/Sud** (rotations
symétriques), **inversée** partout ailleurs.

**Le mécanisme.** xdyn construit la rotation NED→corps via `BodyStates::get_rot_from_ned_to_body()`
(`BodyStates.cpp:143`) = `Quaternion(qr,qi,qj,qk).matrix()`, en lisant le quaternion d'état comme **ned→corps**
(convention interne de xdyn = autorité). Le chemin co-sim fournit l'attitude **corps→NED** (l'inverse). → rotation
**transposée**. Pour un lacet pur, `R(ψ)` et sa transposée `R(-ψ)` sont **identiques à ψ=0°/180°** mais
**différentes à 90°/270°** → foils justes N/S, cassés E/O. Les foils utilisent cette rotation pour l'angle du flux
(`HydroPolarForceModel.cpp:123,136,159`) → leur portance **s'inverse** dès cap≠0.

**La conséquence.** Foils inversés = ils **entretiennent** la dérive au lieu de la freiner → le bateau **dérive vers
le vent** (mesuré : cap 52, route au vent, `Fy(keel)` du mauvais côté), l'**ardente s'inverse** (abattée), le bateau
**refuse de pointer** et est **ingouvernable au cap**. C'est ce qui faisait partir nos contrôleurs au mauvais bord.

**La preuve du fix.** La combinaison **quaternion CONJUGÉ (ned→corps) + vitesse NED** rend `alpha` correct
(**+18.5° = la vraie dérive corps, quille qui RÉSISTE**) à **TOUS** les caps (`_offline/conjug_test`, `ned_vel_test`).
→ la physique du modèle est **saine**. Le fix est **côté LOTUSim** (plugin, cf **PR-3**) — xdyn dicte, LOTUSim s'adapte.
⚠️ PR-3 est **couplée à PR-1** : l'entrée du plugin (swap j/k, PR-1, non appliquée sur `feature/focus-v2-model`)
corrompt la `pose`, que la sortie (PR-3) réutilise → fixer les deux ENSEMBLE + vérifier l'aller-retour en sim.

**⚠️ RÉCITS PRÉCÉDENTS INVALIDÉS.** « Résistance latérale de coque = 0 / il faut la modéliser » et « la quille
décroche à 50° » étaient **FAUX** — des symptômes de la convention transposée mesurés à cap≠0, **pas** la cause.
Le captif à plat (cap 0) montrait des foils **corrects** ; tout se cassait à cap≠0 uniquement (c'est pourquoi les
premiers tests, à cap Nord, semblaient sains → on tournait en rond). La recherche « comment modéliser la coque /
dérivées Fossen DF95 » reste un bon fond de culture mais **n'est pas nécessaire** ici. **Rien à changer dans le
yaml** pour la cause racine. Le harnais `_offline/cosim.py` a lui aussi la mauvaise convention câblée (vitesses
corps + quaternion non conjugué) → à réécrire en **conj+NED** pour toute future démo boucle-fermée.

## 🔑 DÉCOUVERTE — sous-cadençage `--dt` : découpler l'intégration de la communication
Le co-sim **interdit les solveurs adaptatifs** (horloge monotone → `rkck` refusé : *history must be recorded in
strictly increasing order*). On est en **rk4 pas fixe**. MAIS `xdyn-for-cs` **sous-cadence** :
- flag de lancement **`--dt` = pas d'intégration RÉEL** du solveur (« value of the fixed time step ») ;
- **`Dt` du message websocket = horizon co-sim** (de combien avancer cet échange).
- Si `Dt_message > --dt`, xdyn fait plusieurs sous-pas. **Pas effectif = min(--dt, Dt_message).** Prouvé
  (`_offline/subdiv.py`) : `--dt=0.001` + `Dt=0.02` == trajectoire du full-fin, ≠ du grossier `--dt=0.02`.

➡️ On lance avec un **`--dt` fin (0.001)** — propre au faible amortissement / aux manœuvres — et on **communique/
pilote plus lentement** (`Dt=0.02`, 50 Hz) : **stabilité numérique SANS surcoût de communication**. Dans le vrai
lotusim : lancer `xdyn-for-cs --dt 0.001`, le plugin gz envoie son `Dt` au rythme du rendu. Coût wall-clock du
pas fin ≈ 1/`--dt` (trivial pour 1 bateau ; garder les sims longues raisonnables). **Le 6-DOF suffit → pas besoin
de dé-raidir en 4-DOF** (la houle est préservée).

## Découverte — le « 360 » de juin était NUMÉRIQUE, pas physique
Le bateau qui faisait des 360 / divergeait (préparatifs démo) = artefact du solveur **rk4 pas fixe à dt=0.02**
(trop grossier pour un modèle raide). Même modèle, en `rkck` (standalone) ou `rk4 dt≤0.005` : navigue. Le modèle
n'était pas cassé ; la béquille « gros amortissement de lacet » masquait juste le problème numérique. (Mémoire
native : [[focus-v2-divergence-was-numerical]].)

## État actuel & prochaines étapes
**Acquis (prouvés)** :
1. **Cause racine de l'ingouvernabilité TROUVÉE et prouvée** : convention quaternion co-sim transposée (cf ci-dessus,
   **PR-3**). La physique du modèle yaml est **saine** — rien à corriger côté physique.
2. Harnais boucle-fermée Python↔`xdyn-for-cs` (`_offline/cosim.py`) — fondation de l'interface étudiante
   (⚠️ convention à corriger en conj+NED).
3. Technique **`--dt` sous-cadencé** (stabilité numérique au faible amorti, sans surcoût comm).
4. Le **6-DOF suffit** (pas de 4-DOF, houle gardée).
5. Introspection des forces xdyn en co-sim (`requested_output: Fy/alpha(model,body,frame)`) — outil de debug clé.

**Prochaines étapes (dans l'ordre)** :
1. **PR-3 + PR-1 ensemble** (LOTUSim, plugin) : corriger la convention quaternion (sortie transposée + entrée swap j/k),
   vérifier l'aller-retour en sim → foils corrects à tous les caps dans le vrai simulateur.
2. **Réécrire `_offline/cosim.py`** en conj+NED (tout l'état : quaternion conjugué, vitesses NED, vitesses angulaires),
   re-caler le signe safran (`HELM_SIGN` s'inverse avec la convention corrigée) → démo boucle-fermée propre.
3. **Re-baseliner + re-tuner la physique** MAINTENANT que les foils sont corrects — les réglages passés (CoE reculé,
   quille agrandie, amortissements) **compensaient l'artefact** et sont à **ré-évaluer depuis `a6c6534`** : viser
   une dérive réaliste (5-10°) et une tenue de près naturelle, puis virement + parcours.

Baseline propre du modèle = commit **`a6c6534`** (aucun changement yaml requis pour la cause racine).

## Harnais `_offline/` (scratch, hors livrable)
Voir `_offline/README.md`. Principaux : `cosim.py` (boucle fermée + helpers), `physics_check.py` (batterie
standalone), `subdiv.py` (preuve du sous-cadençage). Le modèle va dans le core `assets/`, le contrôleur dans
generic-scenario `src/agents/`. Méthodo debugging : skill `lotusim-developer/references/debugging-physics.md`.
