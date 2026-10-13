# Journal des modifications

# RealFn Viewer 6.0.0 — fusion avec Vector Viewer

Les deux extensions n'en font plus qu'une : **RealFn Viewer** (même
identifiant `realfn_viewer`, donc mise à jour sur place et presets
personnels conservés). Vector Viewer devient le sous-paquet
`kinematics`.

**Avant d'installer la 6.0, désinstallez l'ancienne extension « Vector
Viewer »** : les deux déclarent les mêmes opérateurs. Si elle est encore
activée, la partie cinématique ne se charge pas et un message l'indique
dans la console. Les presets personnels de Vector Viewer sont conservés
(ils sont rangés dans le dossier de configuration de Blender).

- **Un seul onglet « Maths »** dans la barre latérale (N), avec des
  panneaux numérotés dans un ordre de progression :
  1 · Fonctions, courbes, surfaces, champs — 2 · Mouvement : r, v, a
  animés — 3 · Changement de référentiel — Couleurs (palettes).
- **Note « À observer »** sous le menu des presets de cinématique :
  chaque preset y explique ce qu'il faut regarder (ex. MCU : « v
  tangente unitaire, a centripète unitaire »). Ces textes existaient
  dans les presets mais n'étaient jamais affichés.
- **Nouveau bouton « Animer ce mouvement (r, v, a) »** sur une courbe
  F(t) du panneau 1 : la même trajectoire est envoyée au panneau 2 et
  parcourue au cours du temps, avec ses vecteurs vitesse et accélération.
  Les paramètres libres (R, ω…) y prennent la valeur des sliders.
- Une seule copie de SymPy et de la couche de compatibilité Blender 5.2.


# Vector Viewer

## 1.1.0 — Adaptation à Blender 5.2.2 LTS

Testé avec `bpy==5.2.2` : les 15 presets « simple » et les 14 presets
« composition » (+ Foucault) se construisent ; les flèches bougent avec le
temps, chaque driver est valide, les sliders d'échelle agissent en direct ;
enregistrement / rechargement du .blend OK. Compatible Blender 4.2 → 5.1.

- **Bloquant sous 5.2** : la construction échouait pour tous les presets
  (`mod["Socket_N"] = …` → `TypeError` sur la nouvelle API des entrées du
  modifier). Ajout de `modifier_inputs.py` (le même que RealFn Viewer).
- **Drivers** : les variables qui lisent les sliders « Échelle v / a / Ω »
  pointent vers le chemin 5.2 (`modifiers["…"].properties.inputs.Socket_N.value`).
  Les fichiers enregistrés avec une version antérieure sont convertis
  automatiquement à l'ouverture.
- **SymPy inclus** (wheels sympy 1.14 + mpmath 1.3) : plus besoin de
  `pip install sympy` dans le Python de Blender.
- Matériaux : `Material.use_nodes` n'est plus utilisé à partir de 5.0.

# RealFn Viewer

## 5.6.0 — Adaptation à Blender 5.2.2 LTS

Testé avec le module officiel `bpy==5.2.2` : les 137 presets intégrés se
construisent et s'évaluent, tous les opérateurs fonctionnent, et les 10
panneaux se dessinent sans erreur (FR / EN, LaTeX activé ou non).
Compatibilité conservée avec Blender 4.3 → 5.1.

### Compatibilité Blender 5.2 (bloquant)

- **Nouvelle API des entrées du modifier Geometry Nodes.** Blender 5.2 ne
  stocke plus les valeurs des sockets comme IDProperties :
  `mod["Socket_2"]` lève désormais
  `TypeError: this type doesn't support IDProperties`. La nouvelle API est
  `mod.properties.inputs.Socket_2.value`. Conséquences dans la 5.5.0 sous
  Blender 5.2 : aucun slider dans les panneaux (371 champs cassés), presets
  et snapshots ne lisant/écrivant plus rien, x₀ non synchronisé, animation
  du point de base, bascules de visibilité et couleurs cinématiques
  inopérantes.
  Nouveau module `modifier_inputs.py` qui gère les deux API ; tous les
  accès (lecture, écriture, dessin UI, chemins d'animation) passent par
  lui.
- Animation du point de base : chemin d'animation au format 5.2
  (`modifiers["…"].properties.inputs.Socket_N.value`) ; « Effacer
  l'animation » retire aussi les anciennes courbes d'un fichier antérieur.
- Matériaux : `Material.use_nodes` est obsolète depuis Blender 5.0 ; il
  n'est plus utilisé qu'avant 5.0.

### Corrections

- **`log(x)` était faux** : le nœud Math « Logarithme » calcule log_B(A)
  avec une base B par défaut à 0,5, donc `log(x)` affichait −log₂(x)
  (presets « Logarithme naturel », « Taylor log(x) »…). La base est
  maintenant e.
- Le preset **« Marche de Heaviside »** échouait (`Heaviside` non pris en
  charge par le compilateur).
- `atan2`, `asinh`, `acosh`, `atanh` et `clamp` étaient acceptés par
  l'analyseur mais refusés à la compilation : ils fonctionnent désormais.
- Matériaux de la palette : le nœud Principled BSDF est cherché par type et
  non par nom, ce qui échouait avec l'option « Traduire les nouvelles
  données » (nom « BSDF Principled » en français).
- Les arbres de nœuds remplacés (reconstruction, preset, édition de
  formule, restauration de snapshot) sont supprimés au lieu de
  s'accumuler dans le .blend.

### Performances

- Les surfaces z = f(x, y) et paramétrées avec polynômes de Taylor d'ordre
  8 étaient très lentes à construire : chaque `nodes.new()` fait une mise à
  jour complète de l'arbre, donc un arbre de N nœuds coûte O(N²). Les
  grands termes de Taylor sont maintenant compilés dans de petits groupes
  de nœuds cachés (`.REALFNSURF_… D3`).
  « Ondes croisées amorties » : 86 s → 7 s ; « Ondes radiales »,
  « Sinc 2D », « Ondulation radiale » : plus de 5 min (non terminé) →
  10–15 s.
- Calcul symbolique des termes de Taylor ~2× plus rapide (dérivées
  partielles réutilisées, `xreplace` au lieu de `subs`).
- Les constantes (π·√2, log 3, coefficients de Taylor…) sont réduites à un
  seul nombre au lieu d'une chaîne de nœuds Math.

### Nouveautés

- Nouvelles fonctions dans les formules : `floor`, `ceil`/`ceiling`,
  `frac`, `Mod`/`mod`, `min`/`Min`, `max`/`Max`. Leurs dérivées sont
  prises en charge (nulles entre les sauts).
- Tests headless dans `tests/` (voir `tests/README.md`).
