# Bug xdyn — la force des foils `hydrodynamic polar` dépend du CAP du véhicule

> **⚠️ Ce doc REMPLACE `PR-cosim-quaternion-brief.md`, qui était FAUX** (il visait la convention
> quaternion du plugin LOTUSim). Le vrai bug est **interne à xdyn**, dans `HydroPolarForceModel`.
> Il affecte **standalone ET co-sim**, tout véhicule à foil (voilier, AUV à gouvernes, dérive/quille…).

## 0. Statut — ✅ CORRIGÉ & VALIDÉ (2026-07-06)

Fix appliqué et prouvé dans l'image de build officielle (`sirehna/base-image-debian11-gcc10`, amd64) :

- **Test unitaire** `force_must_not_depend_on_vessel_heading` : ÉCHOUE sur le code d'origine
  (`F(ψ=0°).X = 296 431` vs `F(ψ=45°).X = 1 439 776`, ×5 pour la **même** dérive corps),
  **PASSE** après fix. **Suite complète : 925/925 tests verts** (aucune régression).
- **Preuve simulation** (xdyn standalone, modèle `focus_v2.yaml` réel, solveur rk4) — invariance
  par rotation, qui *doit* tenir (vent uniforme + amortissements/inerties en repère corps) :

  | | dérive | vitesse | gîte | identique selon le cap ? |
  |---|---|---|---|---|
  | **corrigé** | **+2,3° sous le vent** | 0,505 m/s | 5,9° | **oui — écart 0,000000** |
  | avant fix | −35° / −61° / +167° | 0,09–1,0 | 1–41° | non — chaos selon le cap |

  Avant : le bateau **dérive vers le vent** (dérive négative) et part en vrille, différemment à chaque
  cap. Après : petite dérive **sous le vent**, gîte douce, trajectoire corps **bit-à-bit identique** à
  tous les caps. Commande de safran (helm=10°) → même vitesse de lacet à tout cap ⇒ **gouvernable**.
- Branche `fix/hydro-polar-heading-dependence`, commit `da91a19`, diff 2 fichiers (+58/−7). PR à ouvrir sur #1.

## 1. Symptôme

La force latérale d'un `hydrodynamic polar` (quille, safran, dérive) **dépend du cap boussole** du
véhicule — physiquement impossible : la résistance d'un foil au glissement ne dépend que du flux **dans
son propre repère**, pas de la direction dans le monde. Correct **uniquement étrave Nord/Sud**, inversé
partout ailleurs. Conséquence sur un voilier : dérive vers le vent, ardente inversée, ingouvernabilité.

## 2. Convention xdyn (confirmée par la cinématique — c'est l'autorité)

État co-sim / interne = **standard** (prouvé par `Body.cpp` et un test position pur, cf §5) :
- quaternion `(qr,qi,qj,qk)` = **attitude corps→NED** ;
- vitesse linéaire `(u,v,w)` = **repère CORPS** ; vitesse angulaire `(p,q,r)` = **repère CORPS**.

Piège de nommage : `BodyStates::get_rot_from_ned_to_body()` (`core/BodyStates.cpp:143`) renvoie en réalité
**R_corps→NED** (et NON R_ned→corps comme son nom l'indique). Preuve : `core/Body.cpp:173-175` l'utilise
(via le frame-graph, même matrice) comme R_corps→NED pour la cinématique `dx/dt = R·(u,v,w)_corps = v_NED`,
et cette cinématique est correcte (test position §5).

## 3. Cause racine (ligne par ligne)

`code/xdyn/force_models/HydroPolarForceModel.cpp`, `get_force()` :
```cpp
const RotationMatrix Rot_NED_to_body = states.get_rot_from_ned_to_body();  // NOM= ned→corps, VALEUR= R_corps→NED  (BUG latent)
...
const Eigen::Vector3d V_body_NED(states.u(), states.v(), states.w());      // NOM= vitesse en NED, VALEUR= vitesse CORPS
const Eigen::Vector3d V_name_NED = V_body_NED + Rot_body_to_NED * Omega_body.cross(P_name_body);
Eigen::Vector3d V_water_name = Rot_NED_to_name * V_name_NED;               // Rot_NED_to_name = Rot_NED_to_body * (foil mounting)
const double beta = - atan2(V_water_name(1), V_water_name(0));             // angle d'attaque
```
Pour une quille (repère foil = corps), `Rot_NED_to_name = Rot_NED_to_body = R_corps→NED`, donc :
```
V_water_name = R_corps→NED · (vitesse CORPS) = la vitesse dans le repère MONDE (NED)
beta = atan2 sur la vitesse MONDE  ->  = f(route/cap)  ->  DÉPEND DU CAP
```
L'attitude aurait dû **s'annuler** (`R_NED→foil · R_corps→NED · v_corps = R_corps→foil · v_corps`), mais comme
`get_rot_from_ned_to_body()` renvoie R_corps→NED (au lieu de R_ned→corps), et que `(u,v,w)` sont déjà en corps,
elle ne s'annule pas. Deux hypothèses inversées se cumulent : **sens de rotation** ET **repère de vitesse**.
(À cap 0/180, `R(ψ)=R(ψ)ᵀ` → l'erreur disparaît → c'est pour ça que ça "marche" là, et que les TU existants,
qui ne testent le corps qu'à attitude identité, ne l'ont jamais vu.)

## 4. Correctif proposé (à compiler/valider par le TU §6)

L'inflow dû à la **vitesse propre du véhicule** ne doit dépendre **que** de la vitesse corps + de
l'orientation de **montage** du foil (jamais de l'attitude). Seuls **courant/houle** (donnés en NED) doivent
être tournés par l'attitude.
```cpp
// (u,v,w),(p,q,r) sont en repère CORPS (convention cinématique xdyn).
const Eigen::Vector3d V_body(states.u(), states.v(), states.w());
const Eigen::Vector3d Omega_body(states.p(), states.q(), states.r());
const Eigen::Vector3d P_name_body = env.k->get(body_name, name).get_point().v;
const ssc::kinematics::RotationMatrix Rot_body_to_name = env.k->get(name, body_name).get_rot(); // corps -> repère foil
// flux (eau immobile) au point du foil, dans le repère du foil — l'attitude n'entre PAS :
Eigen::Vector3d V_water_name = Rot_body_to_name * (V_body + Omega_body.cross(P_name_body));
// courant/houle : donnés en NED -> repère foil = R_corps→foil · R_ned→corps
const ssc::kinematics::RotationMatrix Rot_ned_to_body = states.get_rot_from_ned_to_body().transpose(); // renvoie R_corps→NED, d'où transpose
const ssc::kinematics::RotationMatrix Rot_ned_to_name = Rot_body_to_name * Rot_ned_to_body;
// P_name_NED (waves) : P_body_NED + R_corps→NED · P_name_body
// V_water_name -= Rot_ned_to_name * V_Current_NED;  (et houle idem)
```
⚠️ Les sens exacts de `env.k->get(name,body).get_rot()` et le `.transpose()` sont à **valider numériquement**
(conventions ssc trompeuses). Le critère de vérité = le TU §6. `AeroPolarForceModel` (voile) a probablement
le même schéma (mais le vent en NED légitime en partie la rotation → erreur plus petite) : **à vérifier aussi**.

## 5. Reproduction minimale

**(a) Cinématique = attitude+corps (prouve la convention)** — surge pur, sans foils, position = vérité :
en envoyant le quaternion d'attitude `(cos(ψ/2),0,0,sin(ψ/2))` + `(u,v,w)=(0.5,0,0)`, le déplacement (COG)
vaut **exactement ψ** à tous les caps (0/45/90/135/225/270). → `(u,v,w)`=corps, quaternion=attitude.

**(b) Foil dépendant du cap** — à `(u,v)` corps FIXES (surge 0.6, sway -0.2 = dérive 18.4°), en variant
seulement le quaternion d'attitude, `alpha(keel)` observé : **+18.5° à cap 0, -33° à 52°, -72° à 90°, +19° à
180°**. Devrait valoir ~±18.5° partout. (Testé via `xdyn-for-cs` en single-step + `requested_output:
["alpha(keel,body)","Fy(keel,body,body)"]`.)

## 6. Test unitaire (échoue sur le code actuel, passe après fix)

À ajouter dans `code/xdyn/force_models/unit_tests/HydroPolarForceModelTest.cpp` (calé sur `orientation_test`) :
```cpp
namespace {
// comme get_states() mais pose une ATTITUDE (cap psi) — corrige aussi le typo qk/qr de get_states()
BodyStates get_states_at_heading(const double psi, const double u, const double v)
{
    BodyStates states(0);
    states.convention = YamlRotation("angle", {"z","y'","x''"});
    states.x.record(0,0); states.y.record(0,0); states.z.record(0,0);
    states.u.record(0,u); states.v.record(0,v); states.w.record(0,0);
    states.p.record(0,0); states.q.record(0,0); states.r.record(0,0);
    states.qr.record(0, std::cos(psi/2.));   // attitude corps->NED, lacet psi
    states.qi.record(0, 0.);
    states.qj.record(0, 0.);
    states.qk.record(0, std::sin(psi/2.));
    return states;
}
}

TEST_F(HydroPolarForceModelTest, keel_force_must_not_depend_on_vessel_heading)
{
    HydroPolarForceModel::Input input;
    input.name = "keel";
    input.internal_frame = YamlPosition(YamlCoordinates(0,0,1), YamlAngle(0,0,0), "body");
    input.reference_area = 100;
    input.angle_of_attack   = {0.,0.12217305,0.15707963,0.20943951,0.48869219,1.04719755,1.57079633,2.0943951,2.61799388,M_PI};
    input.lift_coefficient  = {0.00000,0.94828,1.13793,1.25000,1.42681,1.38319,1.26724,0.93103,0.38793,0.};
    input.drag_coefficient  = {0.03448,0.01724,0.01466,0.01466,0.02586,0.11302,0.38250,0.96888,1.31578,1.34483};
    input.use_waves_velocity = false;
    EnvironmentAndFrames env; env.rho = 1000; env.rot = YamlRotation("angle", {"z","y'","x''"});
    const HydroPolarForceModel fm(input, "body", env);

    // MÊME dérive corps (surge 5, sway 1). La force (repère foil = corps) doit être IDENTIQUE quel que soit le cap.
    const auto F0   = fm.get_force(get_states_at_heading(0.0,     5, 1), 0, env, {});
    const auto F45  = fm.get_force(get_states_at_heading(M_PI/4., 5, 1), 0, env, {});
    const auto F90  = fm.get_force(get_states_at_heading(M_PI/2., 5, 1), 0, env, {});
    ASSERT_NEAR(F0.X(), F45.X(), 1e-6);  ASSERT_NEAR(F0.Y(), F45.Y(), 1e-6);
    ASSERT_NEAR(F0.X(), F90.X(), 1e-6);  ASSERT_NEAR(F0.Y(), F90.Y(), 1e-6);
}
```
Sur le code actuel : `F0 != F90` → **FAIL** (démontre le bug). Après fix : **PASS**.

## 7. Build (pour valider TU + patch)

xdyn se build via CMake (submodule `code/ssc` présent ; Boost/Eigen/gtest requis). Le pipeline officiel
(`ninja_debian.sh`) utilise l'image `sirehna/base-image-debian11-gcc10` (non présente localement). Un build
dans l'image runtime `lotusim:focus-v2` (amd64/Rosetta, gcc/jazzy) est possible mais **lourd et à risque de
mismatch de versions**. Recommandation : valider TU+patch dans la CI xdyn (env gcc10 propre), ou fork local.
