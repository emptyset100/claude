---
title: "RealFn Viewer — Guide pour l'enseignant"
subtitle: "Prise en main et 37 travaux pratiques de mathématiques et de mécanique"
lang: fr
---

# Présentation

RealFn Viewer est une extension de Blender (versions 4.3 à 5.2 LTS) qui
fait **voir** des notions de mathématiques et de mécanique : courbes et
leurs dérivées, polynômes de Taylor, surfaces et plans tangents, champs
de vecteurs, vecteurs vitesse et accélération animés, changements de
référentiel.

Les élèves tapent une formule comme sur une calculatrice ; Blender
dessine l'objet en 3D, et des **curseurs** (sliders) permettent de faire
varier un point, un paramètre ou un ordre d'approximation en direct.

Tout se trouve dans la barre latérale de la vue 3D (touche **N**),
onglet **« Maths »**.

## Installation (une fois par poste)

1. Si l'ancienne extension « Vector Viewer » est installée : Edit ›
   Preferences › Add-ons, la **désinstaller**.
2. Edit › Preferences › Get Extensions › menu ⌄ en haut à droite ›
   **Install from Disk…** → `realfn_viewer-6.0.0.zip`.
   SymPy est inclus : rien d'autre à installer.
3. Pour les panneaux 2 et 3 (animations) : Edit › Preferences › Save &
   Load › cocher **Auto Run Python Scripts**.

## Les panneaux, dans l'ordre de progression

| Panneau | Ce qu'on manipule | Notions illustrées |
|---|---|---|
| **1 · Fonctions, courbes, surfaces, champs** | y = f(x) ; courbes F(t) ; surfaces z = f(x, y) et paramétrées ; champs scalaires et vectoriels 3D ; banc de vecteurs | dérivées successives, tangente en x₀, polynômes de Taylor ; vitesse et accélération le long d'une courbe ; plan tangent et surfaces de Taylor ; champ scalaire coloré selon sa valeur, gradient, divergence, rotationnel ; produit vectoriel, projections, Gram-Schmidt, rotations, quaternions |
| **2 · Mouvement : r, v, a animés** | x(t), y(t), z(t) parcourus en temps réel | MRUA, oscillateurs, mouvement circulaire, ellipse, Lissajous, cycloïde, hélice… |
| **3 · Changement de référentiel** | translation O'(t) + rotation (angles d'Euler) d'un repère R' | composition des vitesses et des accélérations, accélération d'entraînement, **Coriolis**, pendule de Foucault |
| **Couleurs** | palettes de couleurs | vitesse en vert, accélération en rouge partout ; position en bleu (panneau 1) ou jaune pâle (panneaux 2-3) |

## Gestes de base

- **Créer un objet** (panneau 1) : déplier la rubrique *Courbes*,
  *Surfaces*, *Champs 3D* ou *Banc de vecteurs*, cliquer sur
  « Créer… », remplir la boîte de dialogue, valider.
- **Charger un exemple tout prêt** : une fois un objet du bon type
  sélectionné, la sous-rubrique **« Presets … »** apparaît ; choisir un
  preset puis **Appliquer**. Les noms de presets cités dans ce guide sont
  ceux de ces menus.
- **Faire varier** : la sous-rubrique « Paramètres du modifier » contient
  tous les curseurs (point x₀, bornes, paramètres libres, cases
  « Visible · … » pour afficher ou cacher chaque courbe).
- **Corriger une formule** : le champ de formule du panneau se modifie
  directement ; l'objet est reconstruit. Pour une courbe y = f(x), le
  bouton **« Modifier la formule / les ordres »** permet aussi de changer
  le nombre de dérivées et de polynômes de Taylor tracés.
- **Animer** : panneaux 2 et 3, choisir un preset puis **Appliquer**,
  ou taper x(t), y(t), z(t) puis **Construire / Mettre à jour** ;
  lancer la lecture avec **Espace**.
- **Passer d'une courbe au mouvement** : sur une courbe F(t) du
  panneau 1, le bouton **« Animer ce mouvement (r, v, a) »** envoie la
  même trajectoire dans le panneau 2.
- **Vue** : pavé numérique 1 / 3 / 7 pour les vues de face, de côté, de
  dessus ; 5 pour basculer perspective / orthographique ; molette pour
  zoomer.

## Écrire une formule

Notation type calculatrice : `sin(x)`, `exp(-x**2)`, `sqrt(x)`,
`log(x)` (logarithme népérien), `abs(x)`, `x**3` (puissance), `pi`.
Aussi : `floor`, `ceil`, `frac`, `Mod`, `min`, `max`, `clamp`,
`Heaviside`, `atan2`, `asinh`, `acosh`, `atanh`.

Un symbole autre que la variable (`a`, `omega`…) doit être déclaré dans
« Paramètres libres » : il devient un curseur.

Courbes vectorielles F(t) du panneau 1 : on écrit les trois composantes
sur la base `N.x`, `N.y`, `N.z`, par exemple
`cos(t)*N.x + sin(t)*N.y + t*N.z`.

Panneaux 2 et 3 : x(t), y(t), z(t) dans trois champs séparés.

# Conseils pour les séances

- **Faire prédire avant de montrer.** Le plus efficace : demander
  d'abord ce qu'on va voir (signe de la dérivée, direction de
  l'accélération…), puis vérifier à l'écran.
- **Un écran pour deux élèves** : l'un manipule, l'autre note et
  calcule ; on échange à mi-séance.
- **Garder la trace** : chaque élève peut enregistrer ses propres
  presets (bouton *Enregistrer*) et les exporter ; le fichier `.blend`
  enregistré garde aussi tout l'état de la séance.
- **Domaine de définition** : Blender calcule la formule partout sur
  l'intervalle choisi. Pour `log(x)`, `sqrt(x)` ou `1/x`, régler
  *x min* et *x max* pour rester dans le domaine, sinon une partie de la
  courbe n'a pas de sens.
- **Lisibilité** : en classe entière, augmenter l'épaisseur des courbes
  (« Épaisseur · … ») et la taille du marqueur, et passer en vue
  orthographique (touche 5) pour lire des pentes.

## Fiche élève type (à adapter)

1. **Je prévois** : ce que je pense observer, et pourquoi.
2. **J'observe** : capture d'écran ou croquis, valeurs lues.
3. **Je calcule** : le calcul qui confirme ou infirme la prévision.
4. **Je conclus** : la propriété mathématique en une phrase.

# Les travaux pratiques

Chaque TP indique le niveau conseillé (à titre indicatif), une durée,
les objectifs, la mise en place dans l'extension, des questions pour
les élèves, et des éléments de réponse pour l'enseignant.

## A. Fonctions d'une variable — panneau 1, « Courbes »

### TP 1 — Dérivée et tangente

*Niveau : 1re · Durée : 45 min*

**Objectifs.** Relier le nombre dérivé f'(x₀) à la pente de la tangente.

**Mise en place.** « Créer une courbe… » avec f(x) = `x**2`,
ordre des dérivées 1, ordre de Taylor 1. On voit la parabole f, la
droite f' et T₁ (la tangente en x₀). Faire glisser **x₀**.

**Questions.**

1. Quand x₀ augmente, comment évolue la pente de T₁ ?
2. Lire f'(x₀) sur la courbe f' pour x₀ = −1, 0, 1, 2. Comparer à la
   pente de T₁.
3. Pour quelle valeur de x₀ la tangente est-elle horizontale ?
4. Recommencer avec `x**3` : la tangente en 0 traverse-t-elle la
   courbe ?

**Éléments de réponse.** f'(x₀) = 2x₀ ; T₁ : y = 2x₀(x − x₀) + x₀².
Tangente horizontale en x₀ = 0. Pour x³, la tangente en 0 (y = 0)
traverse la courbe : point d'inflexion, f'(0) = 0 sans extremum.

### TP 2 — Variations et extremums

*Niveau : 1re · Durée : 45 min*

**Mise en place.** Preset **« Cubique avec extrema : x³ - 3x »**
(f, f' et f'' affichées).

**Questions.**

1. Repérer les zéros de f'. Que se passe-t-il pour f en ces points ?
2. Dresser le tableau de variations de f à partir du signe de f'.
3. Où f'' s'annule-t-elle ? Comment est la courbe de f de part et
   d'autre ?
4. Cacher f (case « Visible · f ») et retrouver les variations de f
   uniquement à partir de f'.

**Éléments de réponse.** f'(x) = 3x² − 3 s'annule en ±1 : maximum
local f(−1) = 2, minimum local f(1) = −2. f''(x) = 6x s'annule en 0 :
point d'inflexion, f concave à gauche, convexe à droite.

### TP 3 — Trois extremums et deux inflexions

*Niveau : Terminale · Durée : 30 min*

**Mise en place.** Preset **« Quartique : x⁴ - 4x² »**, puis
« Modifier la formule / les ordres » : ordre des dérivées 2.

**Questions.** Combien d'extremums ? Calculer leurs abscisses et
vérifier. Calculer les abscisses des points d'inflexion et les situer
à l'écran avec x₀.

**Éléments de réponse.** f'(x) = 4x³ − 8x = 4x(x² − 2) : extremums en
0 et ±√2 ≈ ±1,41. f''(x) = 12x² − 8 : inflexions en ±√(2/3) ≈ ±0,82.

### TP 4 — La fonction égale à sa dérivée

*Niveau : Terminale · Durée : 20 min*

**Mise en place.** Preset **« Exponentielle : exp(x) »**, puis
« Modifier la formule / les ordres » : ordre des dérivées 2.

**Questions.** Combien de courbes voit-on ? Décocher une à une les
cases « Visible ». Qu'en déduire ? Essayer `exp(2*x)` : que devient
f' ?

**Éléments de réponse.** Les trois courbes sont confondues :
(eˣ)' = eˣ. Pour e²ˣ, f' = 2f : la courbe de f' est « deux fois plus
haute ».

### TP 5 — Logarithme et fonction inverse

*Niveau : Terminale · Durée : 30 min*

**Mise en place.** Preset **« Logarithme naturel : log(x) »**, ordre
des dérivées 1 (« Modifier la formule / les ordres ») ; régler
**x min = 0,05**.
Créer à côté une courbe `1/x` (ou preset **« Hyperbole : 1/x »**).

**Questions.**

1. Comparer la courbe f' du logarithme avec l'hyperbole.
2. Où la tangente au logarithme passe-t-elle par l'origine ?
3. Pourquoi faut-il x min > 0 ?

**Éléments de réponse.** (ln x)' = 1/x. La tangente en x₀ est
y = (x − x₀)/x₀ + ln x₀ ; elle passe par O si ln x₀ = 1, donc x₀ = e.
ln n'est définie que sur ]0, +∞[.

### TP 6 — Fonctions à paramètre

*Niveau : 1re–Terminale · Durée : 45 min*

**Mise en place.** Trois presets, chacun avec son curseur :
**« Gaussienne : exp(-x²/σ²) »** (σ), **« Sigmoïde : 1 / (1 + exp(-k·x)) »**
(k), **« Sinus amorti : exp(-a·x) · sin(b·x) »** (a et b).

**Questions.**

1. Gaussienne : où sont les points d'inflexion ? Comment se
   déplacent-ils quand σ change ?
2. Sigmoïde : quelle est la pente de la tangente en 0 ? Vérifier pour
   k = 1, 2, 4.
3. Sinus amorti : quel curseur règle la fréquence, lequel règle
   l'amortissement ?

**Éléments de réponse.** Gaussienne : f''(x) = 0 pour x = ±σ/√2.
Sigmoïde : f'(0) = k/4. Sinus amorti : b fixe la pulsation, a le
taux de décroissance de l'enveloppe e^(−ax).

### TP 7 — Battements

*Niveau : Terminale / physique · Durée : 30 min*

**Mise en place.** Preset **« Battement : sin(a·x) + sin(b·x) »** ;
mettre a et b proches (par exemple 5 et 5,5) et élargir l'intervalle.

**Questions.** Mesurer la période de l'enveloppe. La relier à a et b
grâce à sin p + sin q = 2 sin((p+q)/2) cos((p−q)/2).

**Éléments de réponse.** L'enveloppe |2 cos((a−b)x/2)| a pour période
2π/|a − b| (deux « ventres » par période du cosinus, soit une
pulsation des battements |a − b|).

### TP 8 — Continuité et dérivabilité

*Niveau : Terminale–Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Valeur absolue : |x| »** (passer
l'ordre des dérivées à 1 avec « Modifier la formule / les ordres »), **« Marche de Heaviside »**,
**« Sinus cardinal : sin(x)/x »**, **« Oscillation pathologique : x·sin(1/x) »**.

**Questions.**

1. |x| : que montre la courbe f' en 0 ? La fonction est-elle continue,
   dérivable en 0 ?
2. Heaviside : déplacer le saut avec le curseur a. La fonction est-elle
   continue ?
3. sin(x)/x : quelle valeur semble prendre la fonction en 0 ?
4. x·sin(1/x) : zoomer près de 0. La courbe reste-t-elle entre deux
   droites ? Lesquelles ?

**Éléments de réponse.** |x| est continue mais pas dérivable en 0
(f' saute de −1 à 1). Heaviside n'est pas continue en a.
sin(x)/x → 1 en 0 (prolongement par continuité). |x·sin(1/x)| ≤ |x| :
encadrée par y = ±x, donc tend vers 0, mais (x sin(1/x))/x = sin(1/x)
n'a pas de limite : pas dérivable en 0.

### TP 9 — Polynômes de Taylor de sin

*Niveau : Terminale–Supérieur · Durée : 45 min*

**Mise en place.** Preset **« Taylor sin(x) : approximations
successives »** (T₁ à T₅ autour de x₀ = 0). Le panneau affiche le
polynôme de l'ordre choisi (« Polynôme de Taylor, ordre … »).

**Questions.**

1. Pourquoi T₂ et T₁ sont-elles confondues ? Et T₄ et T₃ ?
2. Sur quel intervalle T₅ semble-t-elle « coller » à sin ?
3. Déplacer x₀ : que deviennent les polynômes ?

**Éléments de réponse.** sin est impaire : ses dérivées d'ordre pair
sont nulles en 0, donc T₂ = T₁ = x et T₄ = T₃ = x − x³/6. Plus l'ordre
monte, plus l'intervalle d'accord s'élargit, mais l'approximation reste
locale autour de x₀.

### TP 10 — Rayon de convergence : 1/(1 − x)

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Taylor 1/(1-x) : série géométrique »**,
puis élargir le domaine : x min = −1,5, x max = 1,5.

**Questions.** Pour |x| < 1, que font les polynômes quand l'ordre
augmente ? Et pour x < −1 ? Relier au rayon de convergence de
∑ xⁿ.

**Éléments de réponse.** Tₙ(x) = 1 + x + … + xⁿ converge vers 1/(1−x)
seulement pour |x| < 1 ; pour |x| > 1 les polynômes divergent, quel
que soit l'ordre.

### TP 11 — Une fonction partout définie, mais un rayon fini : arctan

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Taylor arctan(x) en x₀=0 »** ; comparer
avec le preset **« Taylor exp(x) : approximations successives »**.

**Questions.** arctan est définie sur ℝ entier. Pourtant, que se
passe-t-il pour |x| > 1 ? Et pour exp ?

**Éléments de réponse.** arctan x = x − x³/3 + x⁵/5 − … converge
seulement pour |x| ≤ 1 (le rayon vient des pôles complexes ±i de
1/(1+x²)). Pour exp, le rayon est infini : les polynômes finissent
par approcher partout.

### TP 12 — Taylor en un point autre que 0 : log en 1

*Niveau : Supérieur · Durée : 20 min*

**Mise en place.** Preset **« Taylor log(x) en x₀=1 »** ; élargir à
x max = 3.

**Questions.** Sur quel intervalle l'approximation s'améliore-t-elle
avec l'ordre ? Que se passe-t-il au-delà de x = 2 ?

**Éléments de réponse.** ln(1 + h) = h − h²/2 + h³/3 − … converge pour
−1 < h ≤ 1, soit 0 < x ≤ 2 ; au-delà les polynômes divergent.

### TP 13 — Animer la tangente, comparer deux fonctions

*Niveau : 1re–Terminale · Durée : 20 min*

**Mise en place.** Créer `sin(x)` et `cos(x)` avec l'ordre des dérivées 1.
Cocher **« Synchroniser x₀ »**, puis **« Animer le point de base »** et
lancer la lecture.

**Questions.** Quand la tangente à sin est horizontale, où en est
cos ? Que vaut sin'(x₀) comparé à cos(x₀) ?

**Éléments de réponse.** sin' = cos : la tangente à sin est horizontale
exactement quand cos s'annule.

## B. Courbes paramétrées — panneau 1, « Courbe vectorielle F(t) »

### TP 14 — Mouvement circulaire uniforme

*Niveau : Terminale / physique · Durée : 45 min*

**Mise en place.** « Créer une courbe vectorielle F(t)… » puis preset
**« Mouvement circulaire uniforme : R·(cos(ω·t), sin(ω·t)) »**. Afficher
les vecteurs position, vitesse et accélération ; faire glisser **t₀**.

**Questions.**

1. Quel angle font la vitesse et le rayon ? L'accélération et le
   rayon ?
2. Doubler ω : comment changent ‖v‖ et ‖a‖ ?
3. Retrouver ‖a‖ = v²/R.
4. Cliquer **« Animer ce mouvement (r, v, a) »** et observer le
   mouvement dans le panneau 2.

**Éléments de réponse.** v ⟂ OM, a dirigée vers le centre.
‖v‖ = Rω, ‖a‖ = Rω² = v²/R : doubler ω double ‖v‖ et quadruple ‖a‖.

### TP 15 — La cycloïde : une vitesse nulle, une accélération non nulle

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Cycloïde : roue qui roule »** ; t₀ = 0
puis t₀ = 2π.

**Questions.** Que vaut la vitesse aux points de rebroussement ?
Et l'accélération ? Comment est la tangente à la courbe en ces points ?

**Éléments de réponse.** F(t) = R(t − sin t, 1 − cos t),
F'(t) = R(1 − cos t, sin t) = 0 en t = 2kπ, mais
F''(t) = R(sin t, cos t) a une norme constante R. La vitesse s'annule :
la courbe peut avoir un point anguleux (rebroussement).

### TP 16 — Tir parabolique

*Niveau : 1re–Terminale / physique · Durée : 45 min*

**Mise en place.** Preset **« Projectile : tir avec angle θ »** (curseurs
v0, θ, g) ; aussi **« Chute libre depuis (0, h₀) avec vitesse initiale
(v₀, 0) »**.

**Questions.**

1. Comment est l'accélération le long de la trajectoire ?
2. Au sommet, que vaut la composante verticale de la vitesse ?
3. Pour quel angle θ la portée est-elle maximale (g et v0 fixés) ?

**Éléments de réponse.** a = (0, −g) constante. Au sommet vᵧ = 0.
Portée v0² sin(2θ)/g, maximale pour θ = π/4 ≈ 0,785.

### TP 17 — L'hélice

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Hélice circulaire (rayon R, pas h) »**.

**Questions.** ‖v‖ dépend-elle de t ? Dans quelle direction pointe
l'accélération ? Que se passe-t-il pour h = 0 ?

**Éléments de réponse.** F(t) = (R cos t, R sin t, ht/2π) :
‖v‖ = √(R² + (h/2π)²) constante ; a = (−R cos t, −R sin t, 0) est
horizontale et pointe vers l'axe. Pour h = 0 on retrouve le cercle.

### TP 18 — Figures de Lissajous

*Niveau : Terminale–Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Figure de Lissajous (a, b) »** ;
essayer (a, b) = (1, 1), (1, 2), (3, 2), puis a = 1, b = 1,414.

**Questions.** Quand la courbe se referme-t-elle sur [0, 2π] ? Que
se passe-t-il quand b/a est irrationnel ?

**Éléments de réponse.** Pour a, b entiers la courbe est fermée de
période 2π. Si b/a est irrationnel, la courbe ne se referme jamais et
remplit peu à peu le carré (on augmente t max pour le voir).

### TP 19 — Courbes remarquables

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Astroïde : (cos³t, sin³t) »**,
**« Cardioïde »**, **« Deltoïde (hypocycloïde à 3 pointes) »**,
**« Spirale d'Archimède : r=a·t »**, **« Tractrice : (t − tanh t, 1/cosh t) »**.

**Questions.** Pour chacune : où la vitesse s'annule-t-elle ? Y
a-t-il des points de rebroussement ? Pour la spirale, comment varie la
distance entre deux spires ?

**Éléments de réponse.** Astroïde : v = 0 en t = kπ/2 (4 pointes).
Deltoïde : 3 pointes. Spirale d'Archimède : écart constant 2πa entre
deux spires.

## C. Mouvement animé — panneau 2

### TP 20 — Oscillateur harmonique

*Niveau : Terminale / physique · Durée : 30 min*

**Mise en place.** Preset **« Oscillateur harmonique 1D »**
(x(t) = cos(2t)) ; lire la note « À observer ».

**Questions.** Où est le point quand la vitesse est maximale ? Quand
l'accélération est maximale ? Comparer le sens de a et celui de x.

**Éléments de réponse.** v est maximale au centre, a est maximale aux
extrémités ; a = −4x (a = −ω²x, ω = 2) : l'accélération ramène
toujours vers le centre.

### TP 21 — Oscillation amortie et battements animés

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Presets **« Oscillation amortie 1D »** et
**« Battement (2 oscillations 1D) »**.

**Questions.** Comment décroissent ‖v‖ et ‖a‖ ? Pour le battement,
mesurer la durée d'une modulation.

**Éléments de réponse.** e^(−t/4) cos(2t) : enveloppe e^(−t/4).
cos t + cos(1,1 t) = 2 cos(1,05 t) cos(0,05 t) : enveloppe de
pulsation 0,05, une modulation (deux « ventres ») tous les
π/0,05 ≈ 63 s.

### TP 22 — Accélération tangentielle et normale

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Preset **« Circulaire uniformément accéléré »**
(θ(t) = t²/2 sur le cercle unité). Comparer avec **« Circulaire uniforme
(MCU) »**.

**Questions.** Décomposer a selon la tangente et selon le rayon.
Laquelle des deux composantes reste constante ? Laquelle croît ?

**Éléments de réponse.** aₜ = Rθ'' = 1 (constante),
aₙ = Rθ'² = t² (croissante). Pour le MCU, aₜ = 0 et a est purement
centripète.

### TP 23 — L'ellipse : esprit critique

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Orbite elliptique (Kepler simplifié) »**
(x = 2 cos t, y = sin t).

**Questions.** Vers quel point pointe l'accélération ? Est-ce le foyer
de l'ellipse ? Ce mouvement peut-il être celui d'une planète ?

**Éléments de réponse.** a = (−2 cos t, −sin t) = −OM : elle pointe
vers le **centre**, pas vers le foyer (√3, 0). C'est le mouvement d'un
oscillateur harmonique 2D, pas une orbite képlérienne : une planète
a une accélération dirigée vers le Soleil, placé à un foyer (voir la
note du preset).

### TP 24 — Du tracé au mouvement

*Niveau : Terminale–Supérieur · Durée : 30 min*

**Mise en place.** Dans le panneau 1, créer une courbe F(t) (par
exemple **« Cardioïde »** ou **« Nœud de trèfle (courbe 3D fermée) »**),
régler les paramètres, puis **« Animer ce mouvement (r, v, a) »**.

**Questions.** La trajectoire est-elle la même ? Qu'apporte
l'animation par rapport au tracé figé ? Où le point ralentit-il ?

**Éléments de réponse.** Même courbe, mais l'animation montre la
**loi horaire** : le point ralentit là où ‖v‖ est petite (pointes,
virages serrés).

## D. Fonctions de deux variables — panneau 1, « Surfaces »

### TP 25 — Plan tangent

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** « Créer une surface z = f(x, y)… » puis preset
**« Paraboloïde elliptique z = x²+y² »** ; cocher **« Afficher le plan
tangent »** et déplacer **x₀**, **y₀**.

**Questions.**

1. Écrire l'équation du plan tangent en (x₀, y₀).
2. Où le plan tangent est-il horizontal ?
3. Le paraboloïde est-il toujours au-dessus de son plan tangent ?

**Éléments de réponse.** z = x₀² + y₀² + 2x₀(x − x₀) + 2y₀(y − y₀).
Horizontal en (0, 0) seulement. Oui : f est convexe.

### TP 26 — Points critiques : minimum, col, selle du singe

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Paraboloïde hyperbolique (selle) z = x²-y² »**,
**« Selle de cheval z = x·y »**, **« Selle du singe z = x³-3xy² »** ;
mettre x₀ = y₀ = 0, afficher le plan tangent puis la surface de Taylor
d'ordre 2 (**« Afficher la surface de Taylor »**, **Ordre de Taylor = 2**).

**Questions.**

1. En (0, 0), le plan tangent est-il horizontal ? Est-ce un extremum ?
2. Calculer la hessienne en (0, 0) pour chaque surface.
3. Pourquoi la surface de Taylor d'ordre 2 de la selle du singe est-elle
   plate ? Que faut-il pour la voir ?

**Éléments de réponse.** Les trois ont un point critique en 0 sans
extremum. Hessiennes : diag(2, −2) et [[0,1],[1,0]] (valeurs propres
de signes opposés : col) ; pour la selle du singe toutes les dérivées
secondes sont nulles en 0, la hessienne ne conclut pas : il faut
l'ordre 3 (la surface elle-même, de degré 3).

### TP 27 — Surfaces de Taylor

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Calotte osculatrice — gaussienne »** ;
faire varier l'**Ordre de Taylor** de 0 à 8, puis déplacer (x₀, y₀).

**Questions.** Que représentent les ordres 0, 1, 2 ? Où l'accord avec la
surface est-il bon ? Que se passe-t-il loin du point ?

**Éléments de réponse.** Ordre 0 : plan horizontal z = f(x₀, y₀) ;
ordre 1 : plan tangent ; ordre 2 : quadrique osculatrice. L'accord
s'étend avec l'ordre mais reste local.

### TP 28 — La vallée de Rosenbrock

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Vallée de Rosenbrock (réduite) »**
(z = ((1 − x)² + 4(y − x²)²)/20) ; plan tangent affiché.

**Questions.** Trouver le minimum en déplaçant (x₀, y₀) jusqu'à rendre
le plan tangent horizontal. Pourquoi une méthode de « descente » serait
lente ici ?

**Éléments de réponse.** Minimum en (1, 1), z = 0. La vallée est
étroite et courbée le long de y = x² : le gradient pointe surtout vers
le fond de la vallée, pas vers le minimum.

### TP 29 — Surfaces paramétrées

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** « Créer une surface paramétrée… » puis presets
**« Sphère de rayon R »**, **« Tore (R, r) »**, **« Ruban de Möbius »**,
**« Caténoïde »**, **« Hélicoïde droit »**,
**« Bouteille de Klein (immersion en 8) »**. Sur la sphère, afficher le
plan tangent et déplacer (u₀, v₀).

**Questions.**

1. Sphère : quel angle fait le plan tangent avec le rayon ?
2. Möbius : combien de faces ? Suivre un bord du doigt.
3. Tore : faire varier R et r ; que se passe-t-il si r > R ?

**Éléments de réponse.** Le plan tangent à la sphère est orthogonal au
rayon. Le ruban de Möbius n'a qu'une face et un seul bord. Pour r > R
le tore s'auto-intersecte.

## E. Champs — panneau 1, « Champs 3D »

### TP 30 — Visualiser un champ scalaire

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** « Créer un champ scalaire ƒ(x, y, z)… » puis presets
**« Distance euclidienne √(x²+y²+z²) »**, **« Potentiel coulombien : k/r »**,
**« Gaussienne 3D »**. Régler **f min** / **f max** pour la couleur,
cocher **« Afficher les étiquettes numériques »**.

**Questions.** Quels points ont la même couleur ? Quelle forme ont les
surfaces de niveau ? Pourquoi faut-il régler f max pour le potentiel
coulombien ?

**Éléments de réponse.** Pour ces trois champs, la valeur ne dépend
que de r : surfaces de niveau sphériques. k/r tend vers l'infini en 0 :
sans borne f max, la couleur est écrasée.

### TP 31 — Gradient d'un potentiel

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** « Créer un champ de vecteurs V(x, y, z)… », mode
**« Gradient d'un potentiel ϕ(x,y,z) »**, ϕ = `x**2 + y**2 + z**2` ;
puis presets **« Gradient d'une gaussienne 3D »** et
**« Force coulombienne : V = -∇(k/r) »**. Lire la divergence et le
rotationnel affichés dans le panneau.

**Questions.**

1. Dans quelle direction pointent les flèches par rapport aux surfaces
   de niveau de ϕ ?
2. Que vaut le rotationnel d'un gradient ?
3. Où les flèches sont-elles les plus longues ?

**Éléments de réponse.** ∇ϕ est orthogonal aux surfaces de niveau et
pointe vers les ϕ croissants. rot(∇ϕ) = 0 (affiché par le panneau).
Pour ϕ = r², ∇ϕ = 2(x, y, z), plus long loin de l'origine.

### TP 32 — Divergence et rotationnel

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Champ radial V = (x, y, z) »**,
**« Rotation autour de Oz : V = (-y, x, 0) »**,
**« Cisaillement simple : V = (y, 0, 0) »**,
**« Point de stagnation : V = (x, y, −2z) »**.

**Questions.** Pour chaque champ, prévoir le signe de la divergence et
le rotationnel, puis vérifier dans le panneau. Le cisaillement
« tourne »-t-il ?

**Éléments de réponse.**

| Champ | div V | rot V |
|---|---|---|
| (x, y, z) | 3 | 0 |
| (−y, x, 0) | 0 | (0, 0, 2) |
| (y, 0, 0) | 0 | (0, 0, −1) |
| (x, y, −2z) | 0 | 0 |

Le cisaillement a un rotationnel non nul alors que les flèches sont
toutes parallèles : un petit objet entraîné par ce champ tourne sur
lui-même.

## F. Calcul vectoriel — panneau 1, « Banc de vecteurs »

### TP 33 — Produit vectoriel et projections

*Niveau : Terminale–Supérieur · Durée : 45 min*

**Mise en place.** Rubrique *Banc de vecteurs*, boutons **« Bancs
prêts à l'emploi »** : **« Produit vectoriel a × b »** et
**« Projection / décomposition »** ; faire varier les curseurs.

**Questions.** a × b est-il orthogonal à a et à b ? Que devient-il
quand a et b sont colinéaires ? Échanger a et b. Comment la projection
de b sur a se compare-t-elle à b ?

**Éléments de réponse.** a × b ⟂ a, b ; nul si a ∥ b ; b × a = −a × b ;
‖a × b‖ = aire du parallélogramme. proj = (a·b/‖a‖²) a, et
b − proj ⟂ a.

### TP 34 — Bases orthonormées et rotations

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Bancs prêts à l'emploi **« Gram–Schmidt (orthonormalisation) »**,
**« Ordres d'Euler comparés »**, **« Composition de rotations
(quaternions) »**, **« Lerp vs Slerp »**.

**Questions.** Gram-Schmidt : vérifier que les vecteurs obtenus sont
orthogonaux et unitaires. Euler : deux rotations composées dans des
ordres différents donnent-elles le même résultat ? Lerp vs Slerp :
laquelle garde une norme constante ?

**Éléments de réponse.** Les rotations ne commutent pas. Slerp
interpole sur la sphère (norme constante, vitesse angulaire
constante) ; lerp coupe la corde et raccourcit le vecteur.

## G. Changement de référentiel — panneau 3

### TP 35 — Translation, entraînement et pseudo-force

*Niveau : Supérieur / physique · Durée : 45 min*

**Mise en place.** Presets **« Cas test : R' galiléen (R'=R) »**,
**« Translation rectiligne uniforme »**, **« Translation uniformément
accélérée »**, **« Cabine de grande roue (translation circulaire
pure) »**. Utiliser les cases d'affichage pour ne montrer qu'une
flèche à la fois.

**Questions.** Dans quels cas l'accélération d'entraînement aₑ est-elle
nulle ? La cabine de grande roue « tourne »-t-elle (Ω) ? A-t-elle une
accélération d'entraînement ?

**Éléments de réponse.** aₑ = 0 si R' est en translation uniforme
(référentiel galiléen). La cabine : Ω = 0 (R' ne tourne pas) mais
aₑ ≠ 0 (O' décrit un cercle) — rotation et accélération d'entraînement
sont deux choses différentes.

### TP 36 — Le manège et la force de Coriolis

*Niveau : Supérieur / physique · Durée : 1 h*

**Mise en place.** Presets **« Manège — point fixe sur la plateforme »**,
**« Coriolis — trajectoire radiale sur disque tournant »**,
**« Masse oscillant radialement sur disque tournant »**,
**« Projectile vu de la Terre tournante »**.

**Questions.**

1. Manège : M est fixe dans R'. Que valent vᵣ et aᵣ ? Vers où pointe aₑ ?
2. Coriolis : M avance en ligne droite dans R'. Quelle est sa
   trajectoire dans R ?
3. Vérifier la composition : afficher aᵣ, aₑ, a_c et aₐ et constater que
   aₐ = aᵣ + aₑ + a_c.
4. Projectile : de quel côté est-il dévié ?

**Éléments de réponse.** Manège : vᵣ = aᵣ = 0, aₑ centripète.
Coriolis : trajectoire en spirale dans R ; a_c = 2 Ω × vᵣ,
perpendiculaire à vᵣ. Le projectile est dévié vers l'est (voir la note
du preset).

### TP 37 — Pendule de Foucault, roue, gyroscope

*Niveau : Supérieur / physique · Durée : 1 h*

**Mise en place.** Preset **« Pendule de Foucault (Paris, φ=48.85°) »** ;
changer la latitude et cliquer **« Recalculer pour cette latitude »**.
Puis **« Roue qui roule sans glisser (cycloïde) »** et
**« Précession (gyroscope) »**.

**Questions.**

1. Foucault : comment la vitesse de rotation du plan d'oscillation
   dépend-elle de la latitude ? Que se passe-t-il à l'équateur ? au
   pôle ?
2. Roue : comparer la trajectoire de M avec la cycloïde du TP 15. Où
   est M quand sa vitesse est nulle ?
3. Gyroscope : le vecteur Ω garde-t-il une direction fixe ?

**Éléments de réponse.** La précession est proportionnelle à sin φ :
nulle à l'équateur, maximale au pôle (un tour par rotation du
référentiel). Roue : même cycloïde ; v = 0 au point de contact avec le
sol. Gyroscope : Ω change de norme et de direction.

# Pour aller plus loin

- **Projets d'élèves** : chaque groupe choisit une courbe ou une surface,
  l'étudie (dérivées, points remarquables, tangentes) et présente ses
  captures d'écran.
- **Créer ses propres presets** : un élève prépare un exemple, le
  bouton *Enregistrer* le garde, *Exporter* le partage avec la classe.
- **Lien avec la physique** : les TP 14 à 24 et 35 à 37 se prêtent à un
  travail commun mathématiques-physique (cinématique, référentiels non
  galiléens).
