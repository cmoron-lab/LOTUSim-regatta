# Focus V2 — Brief Fable, PASSE 2 (polish + textures)

> Suite de `focus_v2_fable_brief.md` (**lis-le d'abord** : toutes les CONTRAINTES DURES restent
> valables — 8 objets nommés séparés, étrave +Y / mât +Z, origine (0,0,0), LOA 0.995,
> pivots voiles GV `(0,0.08,0.116)` / foc `(0,0.498,0.055)`, `_preview` intouché, OBJ-exportable,
> noms de slots `focus_hull/focus_sail/focus_spar/focus_foil/focus_lead` conservés).
> Scène live déjà ouverte + résultat passe 1 en place. `ToolSearch "blender"`, boucle
> modéliser→screenshot→affiner, **save souvent**. **Ne ré-exporte PAS l'OBJ** (l'orchestrateur s'en charge).

## Nouvelle direction artistique : **Naval Group × Riva**
On garde le côté fun/premium mais on change de thème. Histoire cohérente :
**coque composite navy racing + pont/boiseries en acajou verni façon Riva + accents rouges Naval
Group + accastillage chrome.** Chic, pas criard.

### Palette (cibles sRGB hex — convertis en linéaire pour les base colors Principled)
- **Navy Naval Group** (topsides coque) : `#14213D` → `#1B2A4A` (bleu marine profond).
- **Rouge Naval Group** (accents, boot-stripe, graphismes) : `#E2001A` (rouge vif chaud).
- **Blanc** (liséré / détails) : `#F2F3F5`.
- **Acajou Riva** (pont, hiloire, listons) : base `#6B3A1E`, grain plus clair `#8A4A24`,
  joints/calfat `#2A1608` (fines lignes), **vernis très brillant** (roughness ~0.08, clearcoat).
- **Chrome/inox** (ferrures, chandeliers, winchs) : métallique, roughness ~0.15.

## Deltas à réaliser (par ordre de ROI visuel)
1. **Re-livrée complète** vers la palette ci-dessus : `focus_hull` → navy, `focus_deck` → **acajou
   Riva** (voir #4), `focus_accent` → **rouge** (boot-stripe le long du liston + un liséré blanc fin
   au-dessus). Remplace tous les corail/teal/jaune de la passe 1.
2. **Vraie découpe de cockpit** : boolean/inset réel dans le pont (plus le faux creux) — hiloire
   (coaming) en acajou verni, fond de cockpit acajou ou anti-dérapant sombre, banquettes si simple.
3. **Boiseries premium Riva = travail texture** (le point fort demandé) :
   - Le **pont**, l'**hiloire** et les **listons/rub-rail** en **acajou verni à lattes** : planches
     longitudinales + fines lignes de calfat, grain de bois, vernis miroir.
   - Fais-le en **texture bakée** (pas juste procédural) : shader bois procédural (wave/noise) →
     **bake la base color en image ~2k** → branchée en base color → l'OBJ/MTL l'exporte (`map_Kd`).
     Sauve les images à côté du .blend. (Alternative si dispo : PolyHaven — `search_polyhaven_assets`
     / `download_polyhaven_asset` pour un bois « wood_planks » ; sinon bake procédural.)
   - Ajoute quelques **ferrures chrome** (chandeliers/filière, winch, chaumard, cadène) pour le luxe.
4. **Graphismes coque** : sur le navy, un **liséré rouge** + un **wordmark/logo type Naval Group**
   (forme d'onde/carène stylisée, rouge/blanc) posé sur les topsides — texture bakée ou décalque.
   Reste sobre et symétrique bâbord/tribord.
5. **Voiles** : lattes **plus fines** (vraies lattes, pas des bandes larges). Remplace l'insigne
   « soleil » corail par un **numéro de voile rouge** + petit logo discret ; toile blanc cassé
   premium. Garde le galbe.
6. **Bulbe +chunky** (torpille ~20 % plus volumineuse), rouge ou chrome selon ce qui claque.
7. Foils (quille/safran) : navy ou chrome (accord avec la coque), profil NACA conservé.

## Budget & garde-fous
- Passe **coûteuse** : décisif, gros gains d'abord (re-livrée #1 = énorme impact immédiat, fais-la
  en premier et sauve). Le travail texture bois (#3) est le morceau riche voulu — investis là, mais
  garde les autres surfaces en **matériaux stylisés propres** (pas besoin de texturer tout).
- Polycount : tu as ~60k tris de marge (actuel 17.5k). La découpe cockpit + bulbe chunky OK.
- **Contraintes dures inchangées** — re-vérifie-les avant de rendre la main (les origines des voiles
  ne doivent pas bouger, LOA 0.995, 8 objets, `_preview` intact).

## Report attendu (ton message final revient à l'orchestrateur — substance brute)
- Deltas réalisés vs ce brief (par point), matériaux/couleurs finales, images de texture générées
  (chemins) et comment elles sont branchées (base color / map_Kd).
- Polycount final, confirmation contraintes dures OK, `.blend` sauvé, `_preview` intact, OBJ non ré-exporté.
- Auto-évaluation honnête depuis le screenshot final (ce qui claque, ce qui reste faible).
