> # ⛔ PÉRIMÉ / FAUX — NE PAS UTILISER
> Ce brief visait la convention quaternion du **plugin LOTUSim** (PR-3). **Diagnostic erroné.**
> Le vrai bug est **interne à xdyn** (`HydroPolarForceModel`, foil dépendant du cap) — voir
> **`xdyn-foil-heading-bug.md`**. Conjuguer le quaternion côté plugin rendrait les foils "justes"
> mais casserait la cinématique. Conservé ci-dessous seulement comme trace de l'investigation.
> (PR-1 — swap j/k du plugin — reste elle un vrai fix, indépendant, à valider pour elle-même.)

---

# Brief agent — Corriger la convention quaternion du co-sim xdyn↔LOTUSim (entrée + sortie)

> **Statut** : cause racine **prouvée** (niveau protocole brut). Ce doc est auto-suffisant — tu n'as
> besoin d'aucun contexte de conversation. C'est un **complément/extension de la "PR-1" connue** (swap j/k
> en entrée) : les deux sont le même bug de convention quaternion du plugin, un par sens de l'aller-retour.
> Traite-les **ensemble** comme un seul fix cohérent.

## 1. Résumé exécutif

Dans le co-simulateur, la **force latérale des foils `hydrodynamic polar` (quille, safran) dépend du CAP**
du bateau — physiquement impossible. Conséquence : tout véhicule à foils (voilier surtout) devient
**ingouvernable dès que son cap n'est pas Nord/Sud** (dérive vers le vent, ardente inversée, refus de pointer).
Cause : le plugin gz de LOTUSim envoie/lit le quaternion d'état **dans la mauvaise convention** vis-à-vis de
celle qu'attend xdyn. **xdyn est le co-simulateur = l'autorité ; on ne le touche pas. On corrige le plugin
LOTUSim** pour qu'il s'y conforme.

## 2. La convention que xdyn attend (AUTORITÉ — prouvée, ne pas discuter)

Pour l'état co-sim (`states[...]`), xdyn attend :
- **Quaternion `(qr,qi,qj,qk)` = rotation NED→CORPS** (ned→body), PAS l'attitude corps→NED usuelle.
  - Source : `LOTUSim-Xdyn/code/xdyn/core/BodyStates.cpp:141-143` —
    `get_rot_from_ned_to_body()` renvoie `Eigen::Quaternion(qr,qi,qj,qk).matrix()` et l'utilise **tel quel**
    comme rotation NED→corps. Tous les foils s'en servent : `HydroPolarForceModel.cpp:123`
    (`Rot_NED_to_body = states.n()`), puis `V_water_name = Rot_NED_to_name * V_name_NED` (ligne 136),
    d'où l'angle d'attaque `beta`/`alpha` (ligne 159).
- **Vitesse linéaire `(u,v,w)` = repère NED (monde)**.
- ⚠️ La **doc** xdyn (`Xdyn-User-Guide.md`) décrit le quaternion comme *"orientation in the NED frame (BODY/NED)"*,
  ce qui **sonne corps→NED** — c'est **trompeur**. Le **comportement du code fait autorité** : c'est ned→corps.
  (À signaler éventuellement en amont à l'équipe xdyn, mais **ne pas** modifier xdyn.)

## 3. Ce que le plugin LOTUSim fait aujourd'hui (les deux bugs, couplés)

Fichier : `LOTUSim/systems/physics_engine_interface/src/xdyn_websocket.cpp`
(branche `feature/focus-v2-model`, PR-1 **non** appliquée).

Helpers (haut du fichier, ~L14-31) :
```cpp
quatEnuToNed(q) = q_ned_to_enu.Inverse() * q * q_ned_to_enu;   // SIMILARITÉ : ré-exprime la rotation, NE l'inverse PAS
vecEnuToNed(v)  = {v.Y(), v.X(), -v.Z()};                       // vecteur ENU->NED : OK
```

- **SORTIE (plugin→xdyn), `getNewState`, ~L308** :
  ```cpp
  gz::math::Quaterniond ned_quad = quatEnuToNed(previous_state.pose.Rot());   // = attitude CORPS→NED  ❌
  ```
  `pose.Rot()` = orientation du corps dans le monde gz (corps→ENU). `quatEnuToNed` la ré-exprime en NED →
  **corps→NED**. Or xdyn veut **ned→corps** ⇒ rotation **transposée**. (La vitesse `vecEnuToNed(lin_vel)` = NED,
  elle, est **correcte** — ne pas y toucher.)
- **ENTRÉE (xdyn→plugin), `onMessage`, ~L268-272** (= le "bug PR-1") :
  ```cpp
  auto ned_quad = gz::math::Quaterniond(reply["qr"], reply["qi"], reply["qk"], reply["qj"]);  // j/k SWAPPÉS ❌
  ```
  Lit `qj`/`qk` **inversés** — puis `quatNedToEnu` → reconstruit la `pose`.

**Couplage crucial** : la SORTIE réutilise `previous_state.pose.Rot()`, c-à-d la pose reconstruite par l'ENTRÉE.
Le swap d'entrée corrompt la pose, qui corrompt le quaternion de sortie. **⇒ Les deux se composent : à corriger
et vérifier ENSEMBLE, pas en isolation.**

Pour un lacet pur, `R(ψ)` et sa transposée `R(-ψ)` coïncident **seulement à ψ=0°/180°** → c'est pourquoi les
foils sont corrects étrave Nord/Sud et **inversés partout ailleurs**.

## 4. Preuve reproductible (protocole BRUT, court-circuite le plugin)

Ce test parle en JSON direct à `xdyn-for-cs` (pas via le plugin) et démontre (a) le bug et (b) la convention
correcte. Il réutilise les helpers de `_offline/cosim.py` (websocket stdlib, `launch_xdyn`, `write_model`).
Prérequis : Docker up, image **`lotusim:focus-v2`** (amd64), modèle `assets/models/focus_v2/focus_v2.yaml`.

```python
import sys, os, math, time, json
sys.path.insert(0, os.path.expanduser("~/src/lotusim-lab/_offline"))
from cosim import write_model, launch_xdyn, stop_xdyn, ws_connect, ws_send, ws_recv, INIT

def e2q(phi, th, psi):
    cp, sp = math.cos(phi/2), math.sin(phi/2); ct, st = math.cos(th/2), math.sin(th/2); cy, sy = math.cos(psi/2), math.sin(psi/2)
    return (cp*ct*cy+sp*st*sy, sp*ct*cy-cp*st*sy, cp*st*cy+sp*ct*sy, cp*ct*sy-sp*st*cy)
def Rb2n(qr, qi, qj, qk):
    return [[1-2*(qj*qj+qk*qk), 2*(qi*qj-qk*qr), 2*(qi*qk+qj*qr)],
            [2*(qi*qj+qk*qr), 1-2*(qi*qi+qk*qk), 2*(qj*qk-qi*qr)],
            [2*(qi*qk-qj*qr), 2*(qj*qk+qi*qr), 1-2*(qi*qi+qj*qj)]]
B = "focus_v2"; REQ = [f"alpha(keel,{B})", f"Fy(keel,{B},{B})"]; T = [0.0]
def probe(sock, q, vel):
    st = dict(INIT); st["u"], st["v"], st["w"] = vel; st["qr"], st["qi"], st["qj"], st["qk"] = q; st["t"] = T[0]; T[0] += 0.5
    ws_send(sock, json.dumps({"Dt": 0.005, "states": [st],
        "commands": {"mainsail(sheet)": 0.0, "rudder(helm)": 0.0}, "requested_output": REQ}))
    ex = json.loads(ws_recv(sock))["extra_observations"]
    return math.degrees(ex[f"alpha(keel,{B})"][-1]), ex[f"Fy(keel,{B},{B})"][-1]
write_model(180, wind_speed=0.0); launch_xdyn(solver="rk4", dt=0.001)
try:
    time.sleep(4); sock = ws_connect("127.0.0.1", 12345)
    ub, vb = 0.6, -0.2      # dérive CORPS fixe = atan2(v,u) = +18.5deg, à tous les caps
    print("dérive corps réelle = +18.5deg (constante). alpha_keel devrait valoir +18.5 partout.")
    for yaw in (0, 52, 90, 180):
        A = e2q(0, 0, math.radians(yaw)); Ac = (A[0], -A[1], -A[2], -A[3])       # Ac = conjugué
        ned = [sum(Rb2n(*A)[i][j]*[ub, vb, 0][j] for j in range(3)) for i in range(3)]
        a1, f1 = probe(sock, A, [ub, vb, 0])     # attitude corps->NED + vitesse corps  (ce que font les clients bugués)
        a2, f2 = probe(sock, Ac, ned)            # CONJUGÉ (ned->corps) + vitesse NED   (ce que xdyn veut)
        print(f"yaw {yaw:3d} | client-bugué: alpha={a1:+6.1f} Fy={f1:+5.2f} | CORRECT(conj+NED): alpha={a2:+6.1f} Fy={f2:+5.2f}")
finally:
    stop_xdyn()
```

**Sortie attendue** (Fy(keel)>0 = la quille résiste correctement au glissement bâbord) :
```
yaw   0 | client-bugué: alpha= +18.5 Fy=+5.84 | CORRECT(conj+NED): alpha= +18.5 Fy=+5.84
yaw  52 | client-bugué: alpha= -33.5 Fy=-4.92 | CORRECT(conj+NED): alpha= +18.1 Fy=+5.90
yaw  90 | client-bugué: alpha= -71.5 Fy=-6.22 | CORRECT(conj+NED): alpha= +17.5 Fy=+5.78
yaw 180 | client-bugué: alpha= +19.2 Fy=+5.63 | CORRECT(conj+NED): alpha= +19.2 Fy=+5.63
```
→ colonne "client-bugué" : `alpha` varie avec le cap, `Fy` s'inverse. Colonne "CORRECT" : `alpha`≈+18.5 et
`Fy`>0 à **tous** les caps. **C'est la démonstration du bug ET de la convention cible.**

## 5. Le correctif (plugin, deux sens — À VÉRIFIER par toi en compilant/testant)

Objectif : que le plugin **envoie et lise le quaternion en ned→corps**, conformément à xdyn.

Pistes (candidates — vérifie le résultat exact, les conventions ENU/NED sont piégeuses) :
- **Sortie (~L308)** : envoyer l'inverse, p.ex.
  `gz::math::Quaterniond ned_quad = quatEnuToNed(previous_state.pose.Rot()).Inverse();`
  (ou inverser la rotation de pose avant conversion). Laisser la **vitesse** telle quelle (déjà NED).
- **Entrée (~L268-272)** : lire **sans** le swap j/k **et** reconstruire l'attitude corps→NED par inversion, p.ex.
  `auto ned_quad = gz::math::Quaterniond(qr, qi, qj, qk).Inverse();` puis `quatNedToEnu(ned_quad)` pour la pose.
- Ces deux changements sont **couplés** → les faire ensemble et valider l'aller-retour.

⚠️ Ne te fie pas aveuglément aux one-liners ci-dessus : **valide numériquement**. Le critère de vérité est la
section 6.

## 6. Vérification OBLIGATOIRE (preuve d'exécution)

1. **Aller-retour d'attitude** : injecter une pose à cap {45,90,135}, avancer avec commandes nulles, vérifier que
   la pose renvoyée **ne dérive/ne flippe pas** (round-trip identité aux erreurs d'intégration près).
2. **Force des foils à tous les caps** : via `requested_output` (`alpha(keel,focus_v2)`, `Fy(keel,focus_v2,focus_v2)`),
   confirmer que la quille **résiste** au glissement (`Fy` opposé à `v_corps`, `alpha`≈vraie dérive) à **tous** les
   caps, pas seulement N/S. Le repro §4 devient alors correct dans la colonne "client-bugué" une fois le plugin fixé
   (si tu testes via le plugin) — ou reste le témoin si tu testes le plugin séparément.
3. **Bout-en-bout** (si faisable) : un voilier en co-sim gz doit **tenir le près** et faire une dérive **sous le
   vent** et **petite** à un cap quelconque.

## 7. Périmètre & garde-fous

- **NE PAS modifier** `LOTUSim-Xdyn/` (xdyn) — c'est l'autorité, LOTUSim s'y adapte.
- Le fix vit dans `LOTUSim/systems/physics_engine_interface/src/xdyn_websocket.cpp` (+ tests éventuels du même module).
- **Aval, hors périmètre de CE bug** (à savoir, ne pas traiter ici) :
  - Le harnais scratch `_offline/cosim.py` a **la même erreur de convention** (il envoie corps→NED + vitesse corps) —
    c'est pourquoi le bug se reproduit **sans** le plugin. Sera réécrit en conj+NED séparément.
  - Les contrôleurs (generic-scenario `src/agents/`) ont un `HELM_SIGN`/gain **calibrés contre la convention buguée**
    → à re-caler une fois le quaternion corrigé (le sens du safran s'inverse).
  - La physique du modèle yaml (`focus_v2.yaml`) est **saine** — **rien à changer** côté physique pour ce bug.

## 8. Fichiers de référence
- Plugin (À corriger) : `LOTUSim/systems/physics_engine_interface/src/xdyn_websocket.cpp`
  (helpers L14-31 ; entrée L~260-295 ; sortie L~300-335).
- Convention xdyn (RÉFÉRENCE, ne pas toucher) : `LOTUSim-Xdyn/code/xdyn/core/BodyStates.cpp:141-143` ;
  `LOTUSim-Xdyn/code/xdyn/force_models/HydroPolarForceModel.cpp:119-185`.
- Doc protocole co-sim : `LOTUSim.wiki/Xdyn-User-Guide.md` (§ co-simulation, entrées/sorties d'état).
- Contexte physique voilier & cause racine détaillée : `focus_v2_notes.md` (racine du dépôt).
- Runtime : Docker image `lotusim:focus-v2` (amd64/Rosetta) ; binaire `/lab/LOTUSim/physics/xdyn-for-cs` ;
  helpers websocket réutilisables dans `_offline/cosim.py`.
