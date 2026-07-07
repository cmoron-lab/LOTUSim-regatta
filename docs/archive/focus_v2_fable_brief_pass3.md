# Focus V2 — Brief Fable, PASSE 3 (finitions & détails)

> Suite de `focus_v2_fable_brief.md` (CONTRAINTES DURES) + `focus_v2_fable_brief_pass2.md`
> (palette Naval-navy/rouge + bois Riva + branding **LOTUSim**). Scène live déjà ouverte, résultat
> passe 2 en place et sauvé. `ToolSearch "blender"`, boucle modéliser→screenshot→affiner,
> **save souvent**, **ne ré-exporte PAS l'OBJ**.

## Verdict utilisateur : la FORME et les TEXTURES sont bonnes, mais les DÉTAILS sont trop légers.
Cette passe ne change ni la silhouette ni la palette ni le bois. Elle **corrige 3 défauts précis** et
**monte le niveau de détail** (accastillage). Priorité = les 3 fixes, puis le détail.

## Fix 1 — Cockpit vide → habiter le POSTE DE PILOTAGE (priorité n°1)
Le cockpit est une coquille vide. Ajoute au minimum une **barre**, et de quoi montrer le poste :
- **Barre** : soit un **tiller** (barre franche) partant de la tête de safran vers l'avant dans le
  cockpit (le plus juste pour ce type de bateau), soit une **petite roue sur colonne** (look premium)
  — choisis ce qui rend le mieux, mais le poste doit être lisible.
- Détail cockpit : **rail d'écoute (traveler) + palan/poulie de grand-voile**, un **taquet/winch**
  déjà présents à raccorder visuellement, un petit **compas/instrument** ou console. Optionnel : une
  banquette/hiloire de descente. Bois verni ou chrome selon cohérence. Ne surcharge pas : lisible et net.

## Fix 2 — Numéro de voile "42" barré par les lattes
Le "42" est traversé par les lattes horizontales → illisible. Corrige :
- Place le **"42" dans un panneau propre** (typiquement le **tiers inférieur** de la GV, sous la
  latte la plus basse, ou clairement **entre deux lattes** dans un espace dégagé), bien centré,
  taille lisible, **des deux côtés**. **Aucune latte/ligne décorative ne doit croiser le numéro.**
- Le petit logo **LOTUSim** sur la voile : dans un coin propre (près de la bordure/point d'écoute),
  ne le laisse pas non plus chevaucher une latte.
- (Si plus simple : décale légèrement les lattes vers le haut/la chute pour libérer la zone du numéro.)

## Fix 3 — Wordmark coque LOTUSim mal placé + font basique
- **Repositionne** le "LOTUSim" sur les topsides navy : bien **aligné le long de la ligne de sheer**,
  sur le **quartier avant** (pas collé au tableau), **symétrique bâbord/tribord**, taille équilibrée.
- **Vraie typo dessinée** (pas la font par défaut) : un **logotype moderne** propre — sans-serif
  géométrique, léger italique/vitesse OK, éventuellement une **petite glyphe onde/carène** en lockup.
  Blanc (ou blanc + accent rouge) sur le navy. Refais le décalque baké proprement (base color).

## Détail global (le « trop léger ») — accastillage premium, sans clutter
Ajoute du détail crédible qui monte en gamme (garde ça net, pas de forêt de bidules) :
- **Base de mât** : cadènes, taquets de drisse, vit-de-mulet détaillé, **hale-bas de bôme (vang)**.
- **Pont** : **ferrure/davier d'étrave** propre, poignées de capot, éventuels **chandeliers bas /
  filière** ou un **liston/toe-rail** fin, chaumards. Chrome/inox pour l'éclat.
- **Gréement** : barres de flèche + terminaisons de haubans un poil plus détaillées.
- Reste dans le budget tris (actuel 54k, plafond 80k) — le détail fin d'abord, pas de subdivision inutile.

## Contraintes dures — INCHANGÉES, re-vérifie avant de rendre la main
8 objets nommés séparés (Hull, Keel, Rudder, Bulb, Mast, Boom, Mainsail, Jib — les nouveaux détails
= objets en plus dans les bonnes sous-collections `focus_v2`) ; **origines voiles inchangées**
(GV (0,0.08,0.116), foc (0,0.498,0.055)) ; LOA ~0.995 ; étrave +Y / mât +Z / origine (0,0,0) ;
noms de slots de base conservés ; `_preview` intouché ; OBJ-exportable (modifiers appliqués) ;
**ne ré-exporte PAS l'OBJ**.

## Report attendu (revient à l'orchestrateur — substance brute)
- Fix 1/2/3 : ce qui a été fait (type de barre, nouvelle position du 42, nouvelle position+typo du
  wordmark), objets/textures ajoutés + chemins des images bakées.
- Accastillage ajouté (liste). Polycount final. Contraintes dures re-vérifiées. `.blend` sauvé.
  `_preview` intact. OBJ non ré-exporté.
- Auto-évaluation honnête depuis le screenshot final (le poste de pilotage est-il lisible ? le 42
  est-il dégagé ? le wordmark est-il pro ?).
