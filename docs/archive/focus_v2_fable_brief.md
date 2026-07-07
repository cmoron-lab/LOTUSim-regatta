# Focus V2 — Brief de modélisation pour Fable 5

> Tu es Fable 5, appelé pour ta qualité en modélisation/texturing 3D. Scène **déjà ouverte et
> préparée** dans Blender (`/Users/cyril/src/lotusim-lab/focus_v2.blend`). Tu travailles sur la
> **session Blender live** via les outils MCP `blender` (fais `ToolSearch "blender"` pour charger
> leurs schémas). Boucle de travail : modéliser → `get_viewport_screenshot` pour te juger → affiner.
> **Sauve souvent** (`bpy.ops.wm.save_mainfile()`). Backup pristine = `focus_v2.baseline.blend`.

## Mission
Transformer un placeholder low-poly (voiles = triangles plats, coque en losange) en un voilier
**détaillé, fun, stylisé cartoon** — couleurs vives, formes exagérées mais **silhouette de voilier
reconnaissable**. Cible finale = **démo Unity/HDRP** (le mesh est réexporté en OBJ). Donc : beau
ET exportable.

## État de départ (mesuré)
- 8 objets séparés, nommés : `Hull` (451v), `Keel`, `Rudder`, `Bulb` (146v), `Mast`, `Boom`,
  `Mainsail` (triangle plat 3v + Solidify), `Jib` (idem). **0 UV, 0 texture, 0 armature.**
- 5 matériaux plats : `focus_hull` (rouge), `focus_sail` (blanc), `focus_spar` (sombre),
  `focus_foil`, `focus_lead`.
- Collections prêtes : `focus_v2` → { `Hull`, `Rig`, `Sails`, `Appendages` } + `_preview`
  (lumières + caméra beauty, **NE PAS toucher, exclu de l'export**).

## CONTRAINTES DURES — ne PAS casser (contrat pipeline)
1. **Orientation** : étrave **+Y**, mât **+Z**, tribord **+X**. Conserver.
2. **Origine monde (0,0,0)** = point de référence du navire. Ne déplace pas l'origine globale ;
   la coque reste centrée dessus (elle doit flotter correctement dans le monde sim).
3. **Échelle** : LOA ≈ **0.995 m** (réel), bau ≈ 0.18 m, tête de mât ≈ z 1.63. Le cartoon peut
   exagérer les proportions mais **garde la longueur ~1 m** (le monde a une bouée r=0.15 m).
4. **Garde les 8 objets, chacun SÉPARÉ, mêmes noms** (`Hull, Keel, Rudder, Bulb, Mast, Boom,
   Mainsail, Jib`). Tu peux **ajouter** des objets de détail (accastillage, etc.), mais ces 8-là
   restent distincts et gardent leur nom (le pipeline les référence).
5. **Garde les 5 noms de slots matériaux** de base (`focus_hull, focus_sail, focus_spar,
   focus_foil, focus_lead`). Ajoute autant de matériaux que tu veux à côté.
6. **Range** toute géométrie du bateau dans `focus_v2` (sous-collection adaptée). **Jamais** de
   géométrie dans `_preview`.
7. **Reste exportable OBJ** : applique/collapse les modifiers exotiques (geometry nodes, particles
   ne s'exportent pas). Tris/quads OK. Polycount cible **~20k–80k tris total** (largement suffisant,
   pas besoin de millions).

## Voiles — préparer la ROTATION (border/choquer)
Le mouvement demandé = la voile pivote autour de son guindant (câblé côté Unity plus tard). Donc :
- `Mainsail` & `Jib` restent **séparés**.
- **Grand-voile** : le guindant (bord d'attaque) **reste collé à l'axe du mât** (x=0, y=0.08),
  la bordure le long de la bôme. **Pivot de bordage = point (0, 0.08, 0.116), rotation autour de
  world +Z.** → À la fin, **place l'origine de l'objet `Mainsail` sur (0, 0.08, 0.116)**.
- **Foc** : le guindant **reste sur la ligne d'étai** : TACK (0, 0.498, 0.055) [pont d'étrave] →
  HEAD (0, 0.08, 1.63) [tête de mât]. Pivot ≈ cette ligne. → **place l'origine de `Jib` sur le
  point d'amure (0, 0.498, 0.055)**.
- **Pas d'armature** (ne survit pas à l'OBJ ; le mouvement est câblé dans Unity). Donne juste aux
  voiles un vrai **galbe cartoon figé** (creux/belly, un peu de rond de chute) — c'est visuel.

## Direction créative (cartoon / fun) — la partie plaisir
- **Coque** : forme de racer exagérée et sympa — étrave évasée/plongeante, belle ligne de sheer,
  **pont détaillé** (cockpit, capot, rails, ferrure d'étrave, tableau arrière). Livrée **vive**
  (couleur franche + bande/graphisme). Look « jouet premium », rondeurs assumées.
- **Gréement** : mât avec du détail (barres de flèche, vit-de-mulet), bôme, **haubans/étai en fine
  géométrie** (lignes), drisses. Cartoon-épais accepté.
- **Voiles** : galbées, stylisées ; GV avec **lattes + rond de chute**, foc ; numéro de voile /
  logo fun optionnel. Panneaux blanc cassé ou couleur fun.
- **Foils** : quille (fin) + **bulbe (torpille)** + safran, sections de profil propres, couleur
  d'accent fun.
- **Matériaux / textures** : **UV-unwrap APRÈS** avoir figé la géométrie. PBR-ish OU stylisé
  (gelcoat brillant coque, toile mate voiles, métal ferrures, foils peints). L'export OBJ+MTL doit
  porter au minimum **base color + roughness** (Unity récupère ça). Procédural OK si tu bakes en
  texture avant export.

## Workflow
1. `ToolSearch "blender"` → charge les outils MCP. La scène est déjà ouverte et prête.
2. Ordre conseillé (gros gains d'abord, pour que même une passe courte impressionne) :
   **coque+pont → livrée/matériau coque → voiles galbées → gréement → foils → UV+textures**.
3. Après chaque gros bloc : `get_viewport_screenshot` (caméra beauty / material preview) pour
   t'auto-juger, puis `save_mainfile()`.
4. Ne touche pas `_preview`.

## Definition of Done (auto-vérif avant de rendre la main)
- [ ] Les 8 objets nommés présents et séparés, dans les sous-collections `focus_v2`.
- [ ] Étrave +Y, mât +Z, origine (0,0,0), LOA ~1 m conservés.
- [ ] Guindants GV/foc sur mât/étai ; **origines** `Mainsail`/`Jib` posées sur leurs pivots.
- [ ] UV sur tout ce qui est texturé ; matériaux exportent base color + roughness.
- [ ] Rendu **détaillé & fun** (screenshot à l'appui).
- [ ] `.blend` sauvé.
- [ ] **(Étape finale)** Ré-export OBJ+MTL → `LOTUSim/assets/models/focus_v2/meshes/focus_v2.obj`
      (sélection = collection `focus_v2` uniquement ; **conserve l'orientation actuelle** — si doute,
      pas de remap d'axes, l'orientation Unity se re-vérifie manuellement côté Editor).

> Contexte projet plus large : `focus_v2_notes.md` (physique/scénario — le mesh est **purement
> visuel** côté Unity, la physique est séparée dans xdyn, donc tu as toute liberté sur le mesh).
