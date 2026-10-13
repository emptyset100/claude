# RealFn Viewer — guide pour l'enseignant

Extension Blender (4.3 → 5.2 LTS) pour faire **voir** des notions de
mathématiques et de mécanique. Tout se trouve dans la barre latérale de la
vue 3D (touche **N**), onglet **« Maths »**.

## Installation (une fois par poste)

1. Si l'ancienne extension « Vector Viewer » est installée : Edit ›
   Preferences › Add-ons, la **désinstaller**.
2. Edit › Preferences › Get Extensions › ⌄ › **Install from Disk…** →
   `realfn_viewer-6.0.0.zip`. SymPy est inclus : rien d'autre à installer.
3. Pour les panneaux 2 et 3 (animations) : Edit › Preferences › Save &
   Load › cocher **Auto Run Python Scripts**.

## Les panneaux, dans l'ordre de progression

| Panneau | Ce qu'on manipule | Notions illustrées |
|---|---|---|
| **1 · Fonctions, courbes, surfaces, champs** | y = f(x) ; courbes F(t) ; surfaces z = f(x, y) et paramétrées ; champs scalaires et vectoriels 3D ; banc de vecteurs | dérivées successives, tangente en x₀, polynômes de Taylor ; vecteur vitesse et accélération d'une courbe ; plan tangent et surfaces de Taylor ; champ scalaire coloré selon sa valeur, gradient, divergence, rotationnel ; produit scalaire/vectoriel, projections, Gram-Schmidt, rotations, quaternions |
| **2 · Mouvement : r, v, a animés** | x(t), y(t), z(t) parcourus en temps réel | MRUA, oscillateurs (amorti, battements), mouvement circulaire, Kepler, Lissajous, cycloïde, hélice… |
| **3 · Changement de référentiel** | translation O'(t) + rotation (angles d'Euler) du repère R' | composition des vitesses et des accélérations, accélération d'entraînement, **Coriolis**, pendule de Foucault, manège, roue qui roule, précession |
| **Couleurs** | palettes de couleurs | vitesse en vert, accélération en rouge partout ; position en bleu (panneau 1) ou jaune pâle (panneaux 2-3) |

## Idées de séquences

- **De la courbe au mouvement.** Panneau 1 : tracer le cercle
  F(t) = R cos t · x + R sin t · y, faire glisser t₀ pour voir v et a
  « figés ». Puis bouton **« Animer ce mouvement (r, v, a) »** : la même
  trajectoire est parcourue au cours du temps (Espace pour lancer la
  lecture), avec la valeur de R choisie au slider.
- **Taylor.** Panneau 1, une fonction y = f(x) avec plusieurs polynômes de
  Taylor ; déplacer x₀ et monter l'ordre pour voir l'approximation
  s'améliorer près de x₀ seulement. En 2D : surface z = f(x, y) avec sa
  surface de Taylor d'ordre 1 (plan tangent), 2, 3…
- **Coriolis.** Panneau 3, preset « Coriolis » ou « Manège » : comparer
  la trajectoire dans R et dans R', puis afficher une à une les
  accélérations (relative, d'entraînement, de Coriolis).

Chaque preset des panneaux 2 et 3 affiche sous son menu une note
**« À observer »** qui dit quoi regarder.

## Écrire une formule

Notation type calculatrice : `sin(x)`, `exp(-x**2)`, `sqrt(x)`, `log(x)`
(logarithme népérien), `abs(x)`, `x**3` (puissance), `pi`.
Aussi : `floor`, `ceil`, `frac`, `Mod`, `min`, `max`, `clamp`,
`Heaviside`, `atan2`, `asinh`, `acosh`, `atanh`.
Un symbole autre que la variable (`a`, `omega`…) doit être déclaré dans
« Paramètres libres » : il devient un slider.
