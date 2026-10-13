---
title: "RealFn Viewer — Guide pour l'enseignant"
subtitle: "Prise en main, 70 travaux pratiques et 10 défis de mathématiques et de mécanique"
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

# Travaux pratiques — première série

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

# Travaux pratiques — deuxième série

Même présentation que la première série. Les TP de cette série
utilisent d'autres presets et prolongent la première série, partie par
partie.

## H. Fonctions d'une variable (suite)

### TP 38 — Asymptotes et comportement à l'infini

*Niveau : 1re–Terminale · Durée : 45 min*

**Mise en place.** Presets **« Fonction rationnelle : (x²-1)/(x²+1) »**,
**« Hyperbole : 1/x »** et **« Tangente : tan(x) »**, avec l'ordre des
dérivées 1. Élargir l'intervalle (x min = −10, x max = 10) pour la
rationnelle.

**Questions.**

1. Rationnelle : vers quelle valeur tend f quand x devient grand ? La
   courbe coupe-t-elle cette droite ?
2. Écrire f(x) = 1 − 2/(x² + 1) et en déduire le minimum de f.
3. Tangente : où sont les asymptotes verticales ? Pourquoi la courbe
   f' reste-t-elle toujours au-dessus de y = 1 ?

**Éléments de réponse.** Asymptote y = 1, jamais atteinte (f < 1).
Minimum f(0) = −1, zéros en ±1. tan' = 1 + tan² ≥ 1 ; asymptotes en
x = π/2 + kπ.

### TP 39 — Fonctions hyperboliques et chaînette

*Niveau : Terminale–Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Caténaire : a · cosh(x/a) »**, puis
« Modifier la formule / les ordres » : ordre des dérivées 1, ordre de
Taylor 2, x₀ = 0. Ouvrir aussi **« Sinus hyperbolique : sinh(x) »**.

**Questions.**

1. Quelle est la dérivée de a·cosh(x/a) ? La comparer au preset sinh.
2. Écrire T₂ en 0. Une chaînette est-elle une parabole ?
3. Faire varier a : comment évolue la « largeur » de la chaînette ?

**Éléments de réponse.** (a cosh(x/a))' = sinh(x/a).
T₂(x) = a + x²/(2a) : près du bas, la chaînette ressemble à une
parabole, mais elle croît exponentiellement loin de 0. cosh² − sinh² = 1.

### TP 40 — Polynôme de Tchebychev

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Preset **« Polynôme de Tchebychev T₅(x) »**
(16x⁵ − 20x³ + 5x) ; régler x min = −1,2, x max = 1,2 ; ordre des
dérivées 1.

**Questions.**

1. Sur [−1, 1], entre quelles valeurs la courbe reste-t-elle ?
2. Combien de fois atteint-elle ±1 ? Combien de racines ?
3. Vérifier que T₅(cos θ) = cos(5θ) pour θ = 0, π/5, π/2.

**Éléments de réponse.** |T₅| ≤ 1 sur [−1, 1] ; ±1 atteint en 6 points
xₖ = cos(kπ/5) ; 5 racines cos((2k+1)π/10). C'est l'équioscillation
qui rend ces polynômes optimaux pour l'approximation.

### TP 41 — Partie entière, partie fractionnaire, modulo

*Niveau : 2de–1re · Durée : 30 min*

**Mise en place.** Créer successivement `floor(x)`, `frac(x)`,
`Mod(x, 2)`, `x - floor(x)`, `max(x, 0)`, `clamp(x, -1, 1)` sur
[−3, 3], avec l'ordre des dérivées 1.

**Questions.**

1. Comparer `frac(x)` et `x - floor(x)`.
2. Quelle est la période de `Mod(x, 2)` ?
3. Où ces fonctions sont-elles discontinues ? Que montre la courbe f'
   entre deux sauts ?
4. Les sauts apparaissent comme des segments presque verticaux.
   Font-ils partie du graphe ?

**Éléments de réponse.** frac(x) = x − ⌊x⌋ ; Mod(x, 2) est 2-périodique.
⌊x⌋ est discontinue aux entiers et de dérivée nulle entre eux. Les
segments verticaux sont un artefact du tracé (points voisins reliés),
pas des points du graphe.

### TP 42 — Transformations de courbes

*Niveau : 2de–1re · Durée : 45 min*

**Mise en place.** « Créer une courbe… » avec `a*exp(-(b*(x - c))**2) + d`
et les paramètres libres `a, b, c, d`.

**Questions.** Faire varier un seul curseur à la fois. Quel paramètre :
translate horizontalement ? verticalement ? étire verticalement ?
comprime horizontalement ? Que se passe-t-il pour a < 0 ? Pour b < 0 ?

**Éléments de réponse.** c : translation horizontale ; d : verticale ;
a : dilatation verticale (symétrie par rapport à l'axe Ox si a < 0) ;
b : contraction horizontale de facteur |b|. Pour b < 0 rien ne change
car la fonction est paire.

### TP 43 — Méthode de Newton

*Niveau : Terminale–Supérieur · Durée : 45 min*

**Mise en place.** Courbe `x**2 - 2`, ordre de Taylor 1 (tangente T₁),
x₀ = 2. Vue de face, orthographique (touches 1 et 5).

**Questions.**

1. Où la tangente coupe-t-elle l'axe des abscisses ? Appeler ce point x₁.
2. Placer x₀ en x₁ et recommencer trois fois. Vers quoi tend la suite ?
3. Démontrer xₙ₊₁ = xₙ − f(xₙ)/f'(xₙ).
4. Que se passe-t-il si on part de x₀ = 0 ?

**Éléments de réponse.** x₁ = 1,5 ; x₂ ≈ 1,4167 ; x₃ ≈ 1,41422 → √2
(le nombre de décimales justes double à chaque étape). En x₀ = 0 la
tangente est horizontale : la méthode échoue.

### TP 44 — Inégalités de convexité

*Niveau : Terminale · Durée : 30 min*

**Mise en place.** Ordre de Taylor 1 : `exp(x)` avec x₀ = 0, `log(x)`
avec x₀ = 1 (x min = 0,05), `sin(x)` avec x₀ = 0 sur [0, π].

**Questions.** Comparer chaque courbe à sa tangente. En déduire trois
inégalités. Déplacer x₀ : la position relative change-t-elle ?

**Éléments de réponse.** eˣ ≥ 1 + x (convexe, au-dessus de toutes ses
tangentes) ; ln x ≤ x − 1 (concave, en dessous) ; sin x ≤ x pour
x ≥ 0. Pour une fonction convexe, la position reste la même quel que
soit x₀.

### TP 45 — Majorer l'erreur de Taylor

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Preset **« Taylor sin(x) : approximations
successives »**. Le panneau affiche le polynôme de chaque ordre.

**Questions.**

1. Calculer T₁(1), T₃(1), T₅(1) et comparer à sin 1 ≈ 0,841471.
2. Comparer chaque erreur à la majoration de Taylor-Lagrange
   |x|ⁿ⁺¹/(n+1)!.
3. Quel ordre faut-il pour avoir sin 1 à 10⁻⁶ près ?

**Éléments de réponse.** T₁(1) = 1 (erreur 0,159) ;
T₃(1) = T₄(1) ≈ 0,833333 (erreur 0,0081 ≤ 1/5! ≈ 0,0083) ;
T₅(1) = T₆(1) ≈ 0,841667 (erreur 0,000196 ≤ 1/7! ≈ 0,000198).
1/9! ≈ 2,8·10⁻⁶ ne suffit pas encore, 1/11! ≈ 2,5·10⁻⁸ suffit : il
faut aller jusqu'à x⁹ (T₉ = T₁₀).

### TP 46 — Approcher le nombre e

*Niveau : Terminale · Durée : 20 min*

**Mise en place.** Preset **« Taylor exp(x) : approximations
successives »** (x₀ = 0, ordres 1 à 5).

**Questions.** Lire le polynôme de chaque ordre et calculer sa valeur en
x = 1. Vers quel nombre la suite converge-t-elle ? Avec quelle vitesse ?

**Éléments de réponse.** 2 ; 2,5 ; 2,6667 ; 2,7083 ; 2,7167 → e ≈ 2,71828.
L'erreur après l'ordre n est de l'ordre de 1/(n+1)! : convergence très
rapide.

## I. Courbes paramétrées (suite)

### TP 47 — La lemniscate : passer deux fois au même point

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Lemniscate de Bernoulli »** ; placer t₀
en π/2 puis en 3π/2.

**Questions.** Le point M passe deux fois par l'origine. Avec la même
vitesse ? Quel angle font les deux tangentes ?

**Éléments de réponse.** En t = π/2, v = (−a/2, −a/2) ; en t = 3π/2,
v = (a/2, −a/2) : les deux tangentes sont perpendiculaires. Un point
double n'a pas « une » tangente.

### TP 48 — La spirale logarithmique : un angle constant

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Spirale logarithmique amortie »**
(paramètre k = 3) ; vecteurs position et vitesse affichés ; faire
glisser t₀.

**Questions.** L'angle entre OM et la vitesse change-t-il ? Le calculer.
Que devient-il quand k augmente ?

**Éléments de réponse.** cos α = −1/√(k² + 1), constant : environ 108°
pour k = 3. Quand k → ∞, α → 90° (on tend vers le cercle).

### TP 49 — Courbes tracées sur une surface

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Presets **« Courbe de Viviani (intersection sphère /
cylindre) »** et **« Hélice conique »**.

**Questions.**

1. Viviani : F(t) = R(1 + cos t, sin t, 2 sin(t/2)). Calculer ‖F(t)‖.
   Sur quelle sphère est la courbe ? Sur quel cylindre ?
2. Hélice conique : montrer que z / √(x² + y²) est constant. Sur quelle
   surface est la courbe ?

**Éléments de réponse.** ‖F‖ = 2R : sphère de centre O et de rayon 2R ;
(x − R)² + y² = R² : cylindre. Hélice conique : z/√(x²+y²) = b/a, la
courbe est tracée sur un cône de sommet O.

### TP 50 — Compter les pointes

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Presets **« Épicycloïde (k=5) »**, **« Deltoïde »**,
**« Astroïde »**, **« Cardioïde »**.

**Questions.** Prévoir le nombre de pointes, puis compter. Pour
l'épicycloïde (1,2 cos t − 0,2 cos 6t, 1,2 sin t − 0,2 sin 6t), résoudre
v(t) = 0.

**Éléments de réponse.** v = 0 ⇔ 6t ≡ t (mod 2π) ⇔ t = 2kπ/5 :
5 pointes. Deltoïde 3, astroïde 4, cardioïde 1.

### TP 51 — Longueur d'une courbe

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Astroïde : (cos³t, sin³t) »** et
**« Cycloïde : roue qui roule »** (R = 1). Observer ‖v‖ en faisant
glisser t₀.

**Questions.** Exprimer ‖v(t)‖, puis la longueur L = ∫ ‖v(t)‖ dt sur une
période (astroïde) ou une arche (cycloïde).

**Éléments de réponse.** Astroïde : ‖v‖ = 3|sin t cos t|, L = 6.
Cycloïde : ‖v‖ = 2R|sin(t/2)|, une arche mesure 8R.

### TP 52 — Rayon de courbure

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Créer la courbe vectorielle
`2*cos(t)*N.x + sin(t)*N.y + 0*N.z` ; placer t₀ en 0 puis en π/2.

**Questions.** Calculer le rayon de courbure ρ = ‖v‖³ / ‖v × a‖ aux
sommets de l'ellipse. Où l'ellipse est-elle la plus « pointue » ?

**Éléments de réponse.** En t = 0, ρ = 1/2 ; en t = π/2, ρ = 4. La
courbure est maximale aux extrémités du grand axe.

## J. Mouvement animé (suite) — panneau 2

### TP 53 — Tir parabolique animé

*Niveau : 1re–Terminale / physique · Durée : 30 min*

**Mise en place.** Presets **« Rectiligne uniformément accéléré »** puis
**« Tir parabolique (g=1) »** (x = t, z = 2t − t²/2). Mettre la
lecture en pause à différents instants.

**Questions.** À quel instant le projectile est-il au sommet ? Où
retombe-t-il ? Comment évoluent les composantes de v ?

**Éléments de réponse.** Sommet à t = 2, en (2, 0, 2) ; retour au sol
à t = 4, en x = 4. vₓ = 1 constante, v_z = 2 − t décroît
linéairement ; a = (0, 0, −1).

### TP 54 — Vérifier une affirmation : la rosace

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Rosace polaire (3 pétales) »**. Avant de
lire la note, demander aux élèves : « la vitesse s'annule-t-elle à la
pointe des pétales ? à l'origine ? »

**Questions.** Calculer ‖v‖² pour r = cos 3θ. Le point s'arrête-t-il
quelque part ?

**Éléments de réponse.** ‖v‖² = r'² + r² = 9 sin²3t + cos²3t ≥ 1 : la
vitesse ne s'annule jamais. À l'origine ‖v‖ = 3 (le point y passe
vite) ; à la pointe des pétales ‖v‖ = 1. Pas de rebroussement.

### TP 55 — Même trajectoire, autre loi horaire

*Niveau : Terminale–Supérieur · Durée : 45 min*

**Mise en place.** Taper successivement dans le panneau 2 :
(`cos(t)`, `sin(t)`, `0`), (`cos(t**2/2)`, `sin(t**2/2)`, `0`),
(`cos(sin(t))`, `sin(sin(t))`, `0`).

**Questions.** Les trois trajectoires sont-elles les mêmes ? Comment
diffèrent les mouvements ? Dans le troisième cas, le point fait-il le
tour du cercle ?

**Éléments de réponse.** Tous sur le cercle unité, mais : vitesse
constante ; vitesse croissante (accélération tangentielle) ; va-et-vient
sur l'arc d'angle [−1, 1] rad. La trajectoire ne suffit pas à décrire
un mouvement.

### TP 56 — Oscillateur amorti

*Niveau : Supérieur / physique · Durée : 30 min*

**Mise en place.** Panneau 1, courbe vectorielle, preset **« Oscillateur
harmonique amorti (réponse libre) »** (x = e^(−γt) cos(ωt), γ = 0,3,
ω = 3), puis **« Animer ce mouvement (r, v, a) »**.

**Questions.** Mesurer la durée entre deux maximums de x. Calculer le
rapport de deux maximums successifs. Que se passe-t-il si γ augmente ?

**Éléments de réponse.** Pseudo-période 2π/ω ≈ 2,09 ; rapport
e^(−2πγ/ω) ≈ 0,53 (décrément logarithmique 2πγ/ω ≈ 0,63). L'amplitude
décroît plus vite quand γ augmente.

## K. Fonctions de deux variables (suite)

### TP 57 — Le cône : pas de plan tangent au sommet

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Cône z = √(x²+y²) »** ; plan tangent
affiché ; approcher (x₀, y₀) de (0, 0) par différents côtés.

**Questions.** Comment se comporte le plan tangent près du sommet ?
Calculer ‖∇f‖. f est-elle différentiable en (0, 0) ?

**Éléments de réponse.** ∇f = (x, y)/r, de norme 1 partout sauf en 0.
Le plan tangent change brutalement selon la direction d'approche :
pas de plan tangent en (0, 0), f n'y est pas différentiable.

### TP 58 — Le chapeau mexicain : un cercle de minimums

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Chapeau mexicain z = ((x²+y²)² −
4(x²+y²))/8 »** ; plan tangent affiché.

**Questions.** Trouver les points où le plan tangent est horizontal.
Combien y a-t-il de minimums ?

**Éléments de réponse.** En posant ρ = x² + y² : z = (ρ² − 4ρ)/8,
minimal pour ρ = 2. Tout le cercle de rayon √2 est formé de minimums
(z = −1/2) ; maximum local en 0 (z = 0).

### TP 59 — Trouver tous les points critiques

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Bosse dipolaire z = x·exp(-(x²+y²)) »**
et **« Quadrupôle gaussien z = x·y·exp(-(x²+y²)/2) »**.

**Questions.** Résoudre ∇f = 0, puis vérifier chaque point à l'écran en
y plaçant (x₀, y₀). Préciser la nature (minimum, maximum, col).

**Éléments de réponse.** Bosse : maximum en (1/√2, 0), minimum en
(−1/√2, 0), valeurs ±e^(−1/2)/√2 ≈ ±0,43. Quadrupôle : col en (0, 0),
maximums en (1, 1) et (−1, −1), minimums en (1, −1) et (−1, 1),
valeurs ±1/e ≈ ±0,37.

### TP 60 — Onde plane et direction de plus grande pente

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Preset **« Hauteur ondulée z = sin(a·x + b·y) »** ;
faire varier a et b.

**Questions.** Le long de quelles droites la hauteur est-elle constante ?
Dans quelle direction la pente est-elle la plus forte ? Lien avec le
gradient ?

**Éléments de réponse.** z est constante sur les droites
ax + by = constante. ∇f = cos(ax + by)·(a, b) : la plus grande pente est
dans la direction (a, b), perpendiculaire aux crêtes.

### TP 61 — Surfaces de révolution et surfaces réglées

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** Presets **« Vase de révolution sinusoïdal »**,
**« Cône de révolution »**, **« Cylindre R·(cos v, sin v, u) »**,
**« Hélicoïde droit »**, **« Conoïde de Plücker »**,
**« Pseudosphère (tractricoïde) »**.

**Questions.** Lesquelles sont de révolution ? Lesquelles contiennent des
droites (surfaces réglées) ? Pour une surface de révolution, retrouver
la courbe génératrice.

**Éléments de réponse.** Révolution : vase, cône, cylindre,
pseudosphère (génératrice : la tractrice du TP 19). Réglées : cône,
cylindre, hélicoïde, conoïde de Plücker.

## L. Champs (suite)

### TP 62 — Fonctions harmoniques et équation de Laplace

*Niveau : Supérieur · Durée : 45 min*

**Mise en place.** « Créer un champ de vecteurs… », mode **« Gradient d'un
potentiel ϕ(x,y,z) »**. Essayer ϕ = `x**2 + y**2 - 2*z**2`,
`(2*z**2 - x**2 - y**2)/2`, `x**2 + y**2 + z**2`, `x*y*z`,
`1/sqrt(x**2 + y**2 + z**2)`. Le panneau affiche la divergence ∇·V.

**Questions.** Pourquoi ∇·(∇ϕ) = Δϕ ? Quelles fonctions ϕ sont
harmoniques (Δϕ = 0) ?

**Éléments de réponse.** div grad = Laplacien. Harmoniques :
x² + y² − 2z², (2z² − x² − y²)/2, xyz, 1/r (hors de l'origine) ;
pour r², Δϕ = 6.

### TP 63 — Comparer des potentiels

*Niveau : Supérieur / physique · Durée : 30 min*

**Mise en place.** Champ scalaire : presets **« Potentiel coulombien :
k/r »**, **« Potentiel de Yukawa : exp(-2r)/r »**, **« Potentiel d'un
dipôle : p·z / r³ »**, **« Dipôle fini »**. Même f min / f max pour
tous.

**Questions.** Lequel décroît le plus vite avec r ? Le potentiel du
dipôle a-t-il la symétrie sphérique ? Où est-il nul ?

**Éléments de réponse.** Yukawa décroît exponentiellement, plus vite que
1/r ; le dipôle décroît en 1/r². Le potentiel du dipôle est nul dans
le plan z = 0 et change de signe de part et d'autre.

### TP 64 — Champs de Beltrami : rot V colinéaire à V

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Presets **« Écoulement ABC (Arnold–Beltrami–Childress) »**
et **« Champ de Beltrami plan : V = (cos z, sin z, 0) »**. Lire le
rotationnel affiché.

**Questions.** Comparer rot V et V dans chaque cas. Que vaut div V ?

**Éléments de réponse.** ABC : rot V = V. Beltrami plan :
rot V = −V. Les deux ont une divergence nulle.

### TP 65 — Champ hélicoïdal et compression anisotrope

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Presets **« Champ tournant ascendant V = (-y, x, c) »**
et **« Compression anisotrope : V = (a·x, b·y, c·z) »** ; faire varier
les curseurs.

**Questions.** Calculer div V et rot V. Pour la compression, quelle
condition sur a, b, c rend le champ incompressible ? Les valeurs du
preset la vérifient-elles ?

**Éléments de réponse.** Champ tournant : div 0, rot (0, 0, 2).
Compression : div V = a + b + c, rot V = 0. Avec a = 1, b = 0,5,
c = −1,5 : a + b + c = 0, le champ est incompressible.

## M. Calcul vectoriel (suite)

### TP 66 — Réflexion par rapport à un plan

*Niveau : Supérieur · Durée : 30 min*

**Mise en place.** Banc prêt à l'emploi **« Réflexion (plan XY) »**
(refl = v − 2·proj(v, ê_z)) ; faire varier θ.

**Questions.** La réflexion conserve-t-elle la longueur ? L'angle avec
le plan ? Écrire la matrice de cette réflexion : que vaut son
déterminant ?

**Éléments de réponse.** Longueurs et angles conservés ; seule la
composante normale (selon ê_z) change de signe. Matrice
diag(1, 1, −1), de déterminant −1 : la réflexion inverse
l'orientation, contrairement à une rotation.

### TP 67 — Repère tournant

*Niveau : Supérieur · Durée : 20 min*

**Mise en place.** Banc **« Repère orthonormé tournant »** ; faire
varier θ.

**Questions.** Les vecteurs e1, e2, e3 restent-ils orthogonaux et de
même norme ? Écrire la matrice de la rotation d'angle θ autour de Oz.

**Éléments de réponse.** Oui, une rotation conserve produit scalaire et
normes ; matrice [[cos θ, −sin θ, 0], [sin θ, cos θ, 0], [0, 0, 1]].

## N. Changement de référentiel (suite) — panneau 3

### TP 68 — Manège qui accélère

*Niveau : Supérieur / physique · Durée : 30 min*

**Mise en place.** Preset **« Manège uniformément accéléré »**
(ψ = t²/4, M fixe en (1, 0, 0) dans R').

**Questions.** Décomposer aₑ en une composante tangentielle et une
composante centripète. Laquelle est constante ?

**Éléments de réponse.** Ω = t/2 : composante tangentielle
dΩ/dt × O'M de norme 1/2 (constante), composante centripète
Ω² = t²/4 (croissante).

### TP 69 — Manège qui monte, ascenseur qui tombe

*Niveau : Supérieur / physique · Durée : 30 min*

**Mise en place.** Presets **« Manège tournant + montée verticale »** et
**« Repère en chute libre tournant »**.

**Questions.** Quelle est la trajectoire de M dans R pour le premier ?
Dans le second, que vaut l'accélération de O' ?

**Éléments de réponse.** Une hélice. Dans le second, O' a
l'accélération (0, 0, −1) : c'est la situation de l'ascenseur en chute
libre (impesanteur). La rotation ajoute à aₑ une composante
centripète, et Coriolis apparaît dès que M bouge dans R'.

### TP 70 — Coriolis change de signe

*Niveau : Supérieur / physique · Durée : 30 min*

**Mise en place.** Preset **« Masse oscillant radialement sur disque
tournant »** (r' = (1 + 0,5 cos 2t, 0, 0), ψ = t).

**Questions.** Quand la masse s'éloigne du centre, de quel côté est
dirigée a_c ? Et quand elle se rapproche ?

**Éléments de réponse.** vᵣ = (−sin 2t, 0, 0) et
a_c = 2Ω × vᵣ = (0, −2 sin 2t, 0) : a_c change de sens à chaque
demi-oscillation, toujours perpendiculaire à vᵣ.

## O. Défis

Sujets ouverts pour les élèves rapides, un devoir maison ou une
évaluation. Chaque défi se vérifie à l'écran.

1. Trouver une fonction dont la tangente en x = 1 est la droite
   y = 2x − 1, puis une autre.
2. Trouver une fonction dont les courbes f et f' se coupent exactement
   en x = 0.
3. Trouver un polynôme de degré 3 ayant un maximum en −1 et un minimum
   en 2.
4. Créer une courbe F(t) dont la vitesse s'annule exactement trois fois
   sur [0, 2π].
5. Créer un mouvement circulaire dont la vitesse double toutes les
   2 secondes.
6. Trouver une surface z = f(x, y) qui a deux minimums et un col.
7. Trouver un champ de vecteurs de divergence nulle et de rotationnel
   non nul, puis un champ de divergence non nulle et de rotationnel nul.
8. Trouver un potentiel ϕ, non constant et différent de ceux du TP 62,
   tel que Δϕ = 0.
9. Construire un mouvement dans R' qui donne une trajectoire rectiligne
   dans R alors que R' tourne.
10. Trouver une fonction dont le polynôme de Taylor d'ordre 3 en 0 est
    1 + x + x²/2 + x³/6, mais qui n'est pas eˣ.

# Pour aller plus loin

- **Projets d'élèves** : chaque groupe choisit une courbe ou une surface,
  l'étudie (dérivées, points remarquables, tangentes) et présente ses
  captures d'écran.
- **Créer ses propres presets** : un élève prépare un exemple, le
  bouton *Enregistrer* le garde, *Exporter* le partage avec la classe.
- **Lien avec la physique** : les TP 14 à 24, 35 à 37, 53 à 56 et
  68 à 70 se prêtent à un travail commun mathématiques-physique
  (cinématique, oscillateurs, référentiels non galiléens).
