"""
Built-in preset catalogue for RealFnViewer.

Twenty curated functions covering the standard pedagogical territory:
polynomials, trigonometry, exponential / logarithmic, rational
functions with poles, special functions, and a few classical Taylor
demonstrations.

Each entry is a dict in the same JSON schema as user presets (see
:mod:`presets`), so applying a built-in is the exact same code path
as applying a user-saved one. They differ only in *where* they live
— built-ins are emitted from Python on demand and installed into the
user presets directory (with a ``_builtin_`` filename prefix so the
filesystem distinguishes them).

Rebuilding the catalogue
------------------------
The ``reinstall_builtins`` operator walks ``BUILTIN_PRESETS`` and
writes each entry to ``<user-presets>/_builtin_<slug>.json``,
overwriting any existing version. Users who accidentally delete a
built-in can recover it; users who edit one can either keep their
edits (they live in a regular ``_builtin_*.json`` file they can
freely modify) or reinstall to reset.

Defaults convention
-------------------
Sampling ranges, x₀ defaults and orders are chosen so the *first
visual impression* is informative:

* Trigonometric / oscillatory: a few periods of x ∈ [-2π, 2π],
  Taylor of mid-order (3-5) centred at 0 — student sees the
  approximation converge near the centre and diverge at the edges.
* Polynomials: x ∈ [-2, 2], full derivative chain visible.
* Exponential / log: x range that respects the domain, defaults
  near a "natural" point of the function (e.g. x₀=1 for log).
"""

from __future__ import annotations

import math


# --------------------------------------------------------------------------- #
# Helpers to keep the catalogue entries compact and readable
# --------------------------------------------------------------------------- #
# English display names for the built-in presets. Looked up by name
# in each builder so the 108 call sites stay untouched; user presets
# have no entry here and so display under their own (user-chosen)
# name in both languages. The panel picks name vs name_en via the
# active UI language (see presets._display_name).
_NAME_EN = {
    "Parabole : x²": "Parabola: x²",
    "Cubique avec extrema : x³ - 3x": "Cubic with extrema: x³ - 3x",
    "Quartique : x⁴ - 4x²": "Quartic: x⁴ - 4x²",
    "Selle du singe : x³ - 3xy² (projection y=0)": "Monkey saddle: x³ - 3xy² (projection y=0)",
    "Hyperbole : 1/x": "Hyperbola: 1/x",
    "Sinus : sin(x)": "Sine: sin(x)",
    "Cosinus : cos(x)": "Cosine: cos(x)",
    "Tangente : tan(x)": "Tangent: tan(x)",
    "Sinus amorti : exp(-a·x) · sin(b·x)": "Damped sine: exp(-a·x) · sin(b·x)",
    "Battement : sin(a·x) + sin(b·x)": "Beat: sin(a·x) + sin(b·x)",
    "Exponentielle : exp(x)": "Exponential: exp(x)",
    "Gaussienne : exp(-x²/σ²)": "Gaussian: exp(-x²/σ²)",
    "Sigmoïde : 1 / (1 + exp(-k·x))": "Sigmoid: 1 / (1 + exp(-k·x))",
    "Logarithme naturel : log(x)": "Natural logarithm: log(x)",
    "Caténaire : a · cosh(x/a)": "Catenary: a · cosh(x/a)",
    "Taylor sin(x) : approximations successives": "Taylor sin(x): successive approximations",
    "Taylor 1/(1-x) : série géométrique": "Taylor 1/(1-x): geometric series",
    "Taylor arctan(x) en x₀=0": "Taylor arctan(x) at x₀=0",
    "Valeur absolue : |x|": "Absolute value: |x|",
    "Marche de Heaviside": "Heaviside step",
    "Sinus cardinal : sin(x)/x": "Cardinal sine: sin(x)/x",
    "Sinus hyperbolique : sinh(x)": "Hyperbolic sine: sinh(x)",
    "Polynôme de Tchebychev T₅(x)": "Chebyshev polynomial T₅(x)",
    "Oscillation pathologique : x·sin(1/x)": "Pathological oscillation: x·sin(1/x)",
    "Taylor exp(x) : approximations successives": "Taylor exp(x): successive approximations",
    "Taylor log(x) en x₀=1": "Taylor log(x) at x₀=1",
    "Fonction rationnelle : (x²-1)/(x²+1)": "Rational function: (x²-1)/(x²+1)",
    "Mouvement rectiligne uniforme : v·t": "Uniform linear motion: v·t",
    "Mouvement uniformément accéléré : a·t²/2": "Uniformly accelerated motion: a·t²/2",
    "Mouvement circulaire uniforme : R·(cos(ω·t), sin(ω·t))": "Uniform circular motion: R·(cos(ω·t), sin(ω·t))",
    "Mouvement circulaire uniformément accéléré (φ(t)=α·t²/2)": "Uniformly accelerated circular motion (φ(t)=α·t²/2)",
    "Cycloïde : roue qui roule": "Cycloid: rolling wheel",
    "Lemniscate de Bernoulli": "Bernoulli lemniscate",
    "Figure de Lissajous (a, b)": "Lissajous figure (a, b)",
    "Spirale d'Archimède : r=a·t": "Archimedean spiral: r=a·t",
    "Spirale logarithmique amortie": "Damped logarithmic spiral",
    "Hélice circulaire (rayon R, pas h)": "Circular helix (radius R, pitch h)",
    "Hélice conique": "Conical helix",
    "Courbe de Viviani (intersection sphère / cylindre)": "Viviani's curve (sphere / cylinder intersection)",
    "Chute libre depuis (0, h₀) avec vitesse initiale (v₀, 0)": "Free fall from (0, h₀) with initial velocity (v₀, 0)",
    "Projectile : tir avec angle θ": "Projectile: launch at angle θ",
    "Oscillateur harmonique amorti (réponse libre)": "Damped harmonic oscillator (free response)",
    "Astroïde : (cos³t, sin³t)": "Astroid: (cos³t, sin³t)",
    "Cardioïde": "Cardioid",
    "Deltoïde (hypocycloïde à 3 pointes)": "Deltoid (3-cusped hypocycloid)",
    "Nœud de trèfle (courbe 3D fermée)": "Trefoil knot (closed 3D curve)",
    "Tractrice : (t − tanh t, 1/cosh t)": "Tractrix: (t − tanh t, 1/cosh t)",
    "Épicycloïde (k=5)": "Epicycloid (k=5)",
    "Paraboloïde elliptique z = x²+y²": "Elliptic paraboloid z = x²+y²",
    "Paraboloïde hyperbolique (selle) z = x²-y²": "Hyperbolic paraboloid (saddle) z = x²-y²",
    "Selle du singe z = x³-3xy²": "Monkey saddle z = x³-3xy²",
    "Plan z = a·x + b·y + c": "Plane z = a·x + b·y + c",
    "Gaussienne z = exp(-(x²+y²)/σ²)": "Gaussian z = exp(-(x²+y²)/σ²)",
    "Sinc 2D z = sin(√(x²+y²)) / √(x²+y²)": "2D sinc z = sin(√(x²+y²)) / √(x²+y²)",
    "Cône z = √(x²+y²)": "Cone z = √(x²+y²)",
    "Vagues z = sin(x)·cos(y)": "Waves z = sin(x)·cos(y)",
    "Ondes radiales z = sin(√(x²+y²))": "Radial waves z = sin(√(x²+y²))",
    "Selle de cheval z = x·y": "Horse saddle z = x·y",
    "Monkey saddle 2 — z = sin(x)+sin(y)": "Monkey saddle 2 — z = sin(x)+sin(y)",
    "Hauteur ondulée z = sin(a·x + b·y)": "Rippled height z = sin(a·x + b·y)",
    "Bosse dipolaire z = x·exp(-(x²+y²))": "Dipole bump z = x·exp(-(x²+y²))",
    "Chapeau mexicain z = ((x²+y²)² − 4(x²+y²))/8": "Mexican hat z = ((x²+y²)² − 4(x²+y²))/8",
    "Vallée de Rosenbrock (réduite)": "Rosenbrock valley (reduced)",
    "Quadrupôle gaussien z = x·y·exp(-(x²+y²)/2)": "Gaussian quadrupole z = x·y·exp(-(x²+y²)/2)",
    "Ondes croisées amorties": "Damped crossed waves",
    "Paraboloïde osculateur — vagues sin(x)·cos(y)": "Osculating paraboloid — waves sin(x)·cos(y)",
    "Calotte osculatrice — gaussienne": "Osculating cap — Gaussian",
    "Osculation d'ordre 2 — ondes radiales": "Order-2 osculation — radial waves",
    "Tore — nappe osculatrice (ordre 2)": "Torus — osculating patch (order 2)",
    "Sphère — calotte osculatrice (ordre 2)": "Sphere — osculating cap (order 2)",
    "Sphère unitaire": "Unit sphere",
    "Sphère de rayon R": "Sphere of radius R",
    "Tore (R, r)": "Torus (R, r)",
    "Hélicoïde droit": "Right helicoid",
    "Caténoïde": "Catenoid",
    "Cylindre R·(cos v, sin v, u)": "Cylinder R·(cos v, sin v, u)",
    "Cône de révolution": "Cone of revolution",
    "Ruban de Möbius": "Möbius strip",
    "Surface d'Enneper (minimale)": "Enneper surface (minimal)",
    "Pseudosphère (tractricoïde)": "Pseudosphere (tractricoid)",
    "Conoïde de Plücker": "Plücker's conoid",
    "Bouteille de Klein (immersion en 8)": "Klein bottle (figure-8 immersion)",
    "Vase de révolution sinusoïdal": "Sinusoidal vase of revolution",
    "Distance carrée x²+y²+z²": "Squared distance x²+y²+z²",
    "Distance euclidienne √(x²+y²+z²)": "Euclidean distance √(x²+y²+z²)",
    "Potentiel coulombien : k/r": "Coulomb potential: k/r",
    "Potentiel d'un dipôle : p·z / r³": "Dipole potential: p·z / r³",
    "Gaussienne 3D : exp(-(x²+y²+z²)/σ²)": "3D Gaussian: exp(-(x²+y²+z²)/σ²)",
    "Décroissance exponentielle radiale : exp(-r/λ)": "Radial exponential decay: exp(-r/λ)",
    "Oscillateur harmonique 3D isotrope : ½ω²(x²+y²+z²)": "Isotropic 3D harmonic oscillator: ½ω²(x²+y²+z²)",
    "Oscillateur anisotrope : ½(a·x² + b·y² + c·z²)": "Anisotropic oscillator: ½(a·x² + b·y² + c·z²)",
    "Harmonique sphérique l=2, m=0 : ½·(3z² − r²)": "Spherical harmonic l=2, m=0: ½·(3z² − r²)",
    "Champ trilinéaire x·y·z": "Trilinear field x·y·z",
    "Onde stationnaire 3D : sin(πx)·sin(πy)·sin(πz)": "3D standing wave: sin(πx)·sin(πy)·sin(πz)",
    "Potentiel de Yukawa : exp(-2r)/r": "Yukawa potential: exp(-2r)/r",
    "Fonction harmonique : x² + y² − 2z²": "Harmonic function: x² + y² − 2z²",
    "Potentiel périodique : cos(πx)+cos(πy)+cos(πz)": "Periodic potential: cos(πx)+cos(πy)+cos(πz)",
    "Dipôle fini : deux charges opposées en z=±0.6": "Finite dipole: two opposite charges at z=±0.6",
    "Champ constant V = e_z": "Constant field V = e_z",
    "Champ radial V = (x, y, z) (divergence non nulle)": "Radial field V = (x, y, z) (nonzero divergence)",
    "Rotation autour de Oz : V = (-y, x, 0) (rotationnel pur)": "Rotation about Oz: V = (-y, x, 0) (pure curl)",
    "Rotation autour de e_z amortie : V = (-y, x, 0)·exp(-r²)": "Damped rotation about e_z: V = (-y, x, 0)·exp(-r²)",
    "Force coulombienne : V = -∇(k/r) (= k·r/r³)": "Coulomb force: V = -∇(k/r) (= k·r/r³)",
    "Force gravitationnelle : V = -∇(-GM/r)": "Gravitational force: V = -∇(-GM/r)",
    "Gradient du paraboloïde : V = ∇(x²+y²+z²) = (2x, 2y, 2z)": "Paraboloid gradient: V = ∇(x²+y²+z²) = (2x, 2y, 2z)",
    "Gradient d'une gaussienne 3D": "Gradient of a 3D Gaussian",
    "Champ d'un dipôle électrique (axe e_z) — composantes explicites": "Electric dipole field (axis e_z) — explicit components",
    "Champ tournant ascendant V = (-y, x, c) (hélicoïdal)": "Ascending rotating field V = (-y, x, c) (helical)",
    "Écoulement ABC (Arnold–Beltrami–Childress)": "ABC flow (Arnold–Beltrami–Childress)",
    "Cisaillement simple : V = (y, 0, 0)": "Simple shear: V = (y, 0, 0)",
    "Point de stagnation : V = (x, y, −2z)": "Stagnation point: V = (x, y, −2z)",
    "Champ de Beltrami plan : V = (cos z, sin z, 0)": "Planar Beltrami field: V = (cos z, sin z, 0)",
    "Compression anisotrope : V = (a·x, b·y, c·z)": "Anisotropic compression: V = (a·x, b·y, c·z)",
}


def _preset(name, expr, *,
             allowed_params=(),
             derivative_order=1,
             taylor_order=0,
             x_min=-5.0, x_max=5.0, x_0=0.0,
             params=None,
             resolution=256,
             marker_size=0.1,
             pieces_overrides=None):
    """Build a preset dict in the standard schema.

    ``pieces_overrides`` lets a preset tweak per-piece thickness
    (e.g. make f thicker than f' for emphasis). It's a dict of
    ``{label: {"thickness": ..., "visible": ...}}`` with both keys
    optional.
    """
    # Build the pieces dict from the requested orders. Defaults:
    # thickness=0.01 everywhere, visible=True everywhere — matches
    # what make_realfn_tree would produce on a fresh build.
    pieces = {}

    # Derivatives f, f', f'', ..., f^(k)
    for k in range(derivative_order + 1):
        if k == 0:
            label = "f"
        elif k == 1:
            label = "f'"
        elif k == 2:
            label = "f''"
        elif k == 3:
            label = "f'''"
        else:
            label = f"f^({k})"
        pieces[label] = {"thickness": 0.01, "visible": True}

    # Taylor polynomials T_1, T_2, ..., T_n
    for n in range(1, taylor_order + 1):
        pieces[f"T_{n}"] = {"thickness": 0.01, "visible": True}

    # Apply user overrides on top of the defaults.
    if pieces_overrides:
        for label, over in pieces_overrides.items():
            if label in pieces:
                pieces[label].update(over)

    return {
        "schema": 1,
        "name": name,
        "name_en": _NAME_EN.get(name, name),
        "builtin": True,    # marker so the panel can label these
        "formula": {
            "expr": expr,
            "allowed_params": list(allowed_params),
            "derivative_order": derivative_order,
            "taylor_order": taylor_order,
        },
        "range": {
            "x_min": x_min, "x_max": x_max, "x_0": x_0,
            "resolution": resolution,
            "marker_size": marker_size,
        },
        "params": dict(params) if params else {},
        "pieces": pieces,
    }


# --------------------------------------------------------------------------- #
# The catalogue
# --------------------------------------------------------------------------- #
# Grouped by mathematical theme so the panel can render section
# headers. The order inside each group is from simple to elaborate.
BUILTIN_PRESETS = [

    # ----- Polynomials & rational functions ----------------------------------
    _preset(
        "Parabole : x²",
        "x**2",
        derivative_order=2, taylor_order=0,
        x_min=-3.0, x_max=3.0, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Cubique avec extrema : x³ - 3x",
        "x**3 - 3*x",
        derivative_order=2, taylor_order=0,
        x_min=-2.5, x_max=2.5, x_0=1.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Quartique : x⁴ - 4x²",
        "x**4 - 4*x**2",
        derivative_order=2, taylor_order=0,
        x_min=-2.5, x_max=2.5, x_0=0.0,
    ),
    _preset(
        "Selle du singe : x³ - 3xy² (projection y=0)",
        "x**3",
        derivative_order=3, taylor_order=0,
        x_min=-2.0, x_max=2.0, x_0=0.0,
    ),
    _preset(
        "Hyperbole : 1/x",
        "1/x",
        derivative_order=1, taylor_order=0,
        x_min=0.2, x_max=4.0, x_0=1.0,
    ),

    # ----- Trigonometric ----------------------------------------------------
    _preset(
        "Sinus : sin(x)",
        "sin(x)",
        derivative_order=1, taylor_order=3,
        x_min=-2*math.pi, x_max=2*math.pi, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Cosinus : cos(x)",
        "cos(x)",
        derivative_order=1, taylor_order=3,
        x_min=-2*math.pi, x_max=2*math.pi, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Tangente : tan(x)",
        "tan(x)",
        derivative_order=1, taylor_order=1,
        x_min=-1.4, x_max=1.4, x_0=0.0,
    ),
    _preset(
        "Sinus amorti : exp(-a·x) · sin(b·x)",
        "exp(-a*x) * sin(b*x)",
        allowed_params=("a", "b"),
        derivative_order=1, taylor_order=0,
        x_min=0.0, x_max=10.0, x_0=1.0,
        params={"a": 0.3, "b": 3.0},
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Battement : sin(a·x) + sin(b·x)",
        "sin(a*x) + sin(b*x)",
        allowed_params=("a", "b"),
        derivative_order=0, taylor_order=0,
        x_min=-10.0, x_max=10.0, x_0=0.0,
        params={"a": 5.0, "b": 5.5},
        pieces_overrides={"f": {"thickness": 0.015}},
    ),

    # ----- Exponential / logarithmic ----------------------------------------
    _preset(
        "Exponentielle : exp(x)",
        "exp(x)",
        derivative_order=0, taylor_order=4,
        x_min=-3.0, x_max=3.0, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Gaussienne : exp(-x²/σ²)",
        "exp(-x**2 / sigma**2)",
        allowed_params=("sigma",),
        derivative_order=2, taylor_order=0,
        x_min=-3.0, x_max=3.0, x_0=0.0,
        params={"sigma": 1.0},
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Sigmoïde : 1 / (1 + exp(-k·x))",
        "1 / (1 + exp(-k*x))",
        allowed_params=("k",),
        derivative_order=2, taylor_order=0,
        x_min=-6.0, x_max=6.0, x_0=0.0,
        params={"k": 1.5},
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Logarithme naturel : log(x)",
        "log(x)",
        derivative_order=1, taylor_order=3,
        x_min=0.1, x_max=5.0, x_0=1.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Caténaire : a · cosh(x/a)",
        "a * cosh(x/a)",
        allowed_params=("a",),
        derivative_order=1, taylor_order=2,
        x_min=-3.0, x_max=3.0, x_0=0.0,
        params={"a": 1.0},
        pieces_overrides={"f": {"thickness": 0.015}},
    ),

    # ----- Classical Taylor demos -------------------------------------------
    _preset(
        "Taylor sin(x) : approximations successives",
        "sin(x)",
        derivative_order=0, taylor_order=5,
        x_min=-math.pi, x_max=math.pi, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.01}},
    ),
    _preset(
        "Taylor 1/(1-x) : série géométrique",
        "1/(1-x)",
        derivative_order=0, taylor_order=4,
        x_min=-0.95, x_max=0.95, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.01}},
    ),
    _preset(
        "Taylor arctan(x) en x₀=0",
        "atan(x)",
        derivative_order=0, taylor_order=5,
        x_min=-1.2, x_max=1.2, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.01}},
    ),

    # ----- Special / piecewise ---------------------------------------------
    _preset(
        "Valeur absolue : |x|",
        "Abs(x)",
        derivative_order=0, taylor_order=0,
        x_min=-3.0, x_max=3.0, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.015}},
    ),
    _preset(
        "Marche de Heaviside",
        "Heaviside(x - a)",
        allowed_params=("a",),
        derivative_order=0, taylor_order=0,
        x_min=-3.0, x_max=3.0, x_0=0.0,
        params={"a": 0.0},
        pieces_overrides={"f": {"thickness": 0.015}},
    ),

    _preset(
        "Sinus cardinal : sin(x)/x",
        "sin(x)/x",
        x_min=-15.0, x_max=15.0, x_0=1.0,
        derivative_order=1, resolution=512,
        # 256+ échantillons sur [-15,15] : x=0 n'est jamais
        # échantillonné exactement (pas irrationnel vs bornes), la
        # singularité apparente est invisible et la limite 1 se lit.
    ),
    _preset(
        "Sinus hyperbolique : sinh(x)",
        "sinh(x)",
        x_min=-3.0, x_max=3.0, x_0=0.0,
        derivative_order=2,
        # f'' = sinh = f : la courbe est sa propre dérivée seconde.
    ),
    _preset(
        "Polynôme de Tchebychev T₅(x)",
        "16*x**5 - 20*x**3 + 5*x",
        x_min=-1.0, x_max=1.0, x_0=0.3,
        derivative_order=1,
        # Équioscillation entre -1 et 1 : cinq extrema alternés.
    ),
    _preset(
        "Oscillation pathologique : x·sin(1/x)",
        "x*sin(1/x)",
        x_min=-0.5, x_max=0.5, x_0=0.15,
        derivative_order=0, resolution=2048,
        # Continuité en 0 sans dérivabilité : l'enveloppe |x| se voit,
        # les oscillations s'accumulent. Résolution élevée nécessaire.
    ),
    _preset(
        "Taylor exp(x) : approximations successives",
        "exp(x)",
        derivative_order=0, taylor_order=5,
        x_min=-3.0, x_max=2.0, x_0=0.0,
        pieces_overrides={"f": {"thickness": 0.01}},
    ),
    _preset(
        "Taylor log(x) en x₀=1",
        "log(x)",
        derivative_order=0, taylor_order=4,
        x_min=0.1, x_max=3.0, x_0=1.0,
        pieces_overrides={"f": {"thickness": 0.01}},
        # Rayon de convergence 1 : T_n colle sur (0,2) et diverge
        # au-delà de x=2 — très visible en scrubbant x₀.
    ),
    _preset(
        "Fonction rationnelle : (x²-1)/(x²+1)",
        "(x**2 - 1)/(x**2 + 1)",
        x_min=-5.0, x_max=5.0, x_0=1.0,
        derivative_order=1,
        # Asymptote horizontale y=1, minimum -1 en 0.
    ),
]


# --------------------------------------------------------------------------- #
# Slug naming convention
# --------------------------------------------------------------------------- #
# Built-ins are stored as ``_builtin_<slug>.json`` so they sort to the
# top of a directory listing AND the underscore prefix lets the panel
# tell them apart from user presets without opening every file.
BUILTIN_FILE_PREFIX = "_builtin_"


def reinstall_builtins() -> int:
    """Write every built-in preset to the user presets directory.

    Returns the number of files written. Existing files of the same
    name are overwritten — this is the documented behaviour of the
    operator, since the typical use case is "I tweaked one of the
    built-ins by mistake, give me back the original".
    """
    from . import presets

    n = 0
    for preset in BUILTIN_PRESETS:
        # Force the builtin-style slug so the file is recognisable
        # as ours and survives renames of the display ``name``.
        slug = BUILTIN_FILE_PREFIX + presets._slugify(preset["name"])
        fp = presets._presets_dir() / (slug + ".json")
        import json
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_builtin_file(path) -> bool:
    """True if ``path`` looks like one of our installed built-ins.

    Tested by filename prefix so we don't have to open the file just
    to render the list of presets in the panel."""
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_FILE_PREFIX)


# =========================================================================== #
# Vector built-in presets
# =========================================================================== #
# A curated catalogue of classic vector functions used in mechanics and
# differential geometry. Each entry is shaped to match the schema written
# by :func:`presets.snapshot_vector_modifier`, so loading one is a plain
# round-trip — no special-case translation needed.

BUILTIN_VECTOR_FILE_PREFIX = "_builtin_vec_"


def _v_preset(name: str, expr: str, *,
               t_min: float = 0.0, t_max: float = 6.283,
               t_0: float = 0.0,
               allowed_params: tuple = (),
               params: dict | None = None,
               resolution: int = 256,
               trace_thickness: float = 0.02,
               marker_size: float = 0.08,
               show_position: bool = True,
               show_velocity: bool = True,
               show_acceleration: bool = True) -> dict:
    """Concise builder for a vector preset dict.

    Filling defaults here rather than at the call site keeps the
    catalogue below readable — each entry says only what differs from
    the canonical defaults, the rest is implicit. The output dict
    follows the v1 vector preset schema exactly, with no missing fields,
    so it can be applied without further normalisation.
    """
    import datetime
    return {
        "schema": 1,
        "kind": "vector",
        "name": name,
        "name_en": _NAME_EN.get(name, name),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "formula": {
            "expr": expr,
            "var_name": "t",
            "allowed_params": list(allowed_params),
        },
        "range": {
            "t_min": float(t_min),
            "t_max": float(t_max),
            "t_0": float(t_0),
            "resolution": int(resolution),
        },
        "params": dict(params or {}),
        "trace": {
            "thickness": float(trace_thickness),
            "material_name": "",
        },
        "arrows": {
            "position":     {"visible": bool(show_position),
                              "material_name": ""},
            "vitesse":      {"visible": bool(show_velocity),
                              "material_name": ""},
            "accélération": {"visible": bool(show_acceleration),
                              "material_name": ""},
        },
        "marker": {
            "size": float(marker_size),
            "material_name": "",
        },
    }


# Catalogue
# ---------
# Five categories of pedagogical interest:
#
#  * Mouvements rectilignes    — droite uniforme, uniformément accéléré;
#  * Mouvements circulaires    — MCU, MCUA;
#  * Trajectoires planes       — cycloïde, lemniscate, Lissajous, spirale;
#  * Trajectoires 3D           — hélice, hélice conique, courbe de Viviani;
#  * Mouvements physiques      — chute libre, projectile, oscillation amortie.
BUILTIN_VECTOR_PRESETS = [

    # ----- Mouvements rectilignes -----------------------------------------
    _v_preset(
        "Mouvement rectiligne uniforme : v·t",
        "v*t*N.x + 0*N.y + 0*N.z",
        allowed_params=("v",),
        params={"v": 1.0},
        t_min=-3.0, t_max=3.0, t_0=0.0,
        # Pas d'accélération → on la cache par défaut, mais on la laisse
        # disponible : décocher manuellement si on veut illustrer "0 = pas
        # de flèche affichée même quand le toggle est ON".
        show_acceleration=False,
    ),
    _v_preset(
        "Mouvement uniformément accéléré : a·t²/2",
        "(a*t**2/2)*N.x + 0*N.y + 0*N.z",
        allowed_params=("a",),
        params={"a": 1.0},
        t_min=0.0, t_max=4.0, t_0=2.0,
    ),

    # ----- Mouvements circulaires -----------------------------------------
    _v_preset(
        "Mouvement circulaire uniforme : R·(cos(ω·t), sin(ω·t))",
        "R*cos(omega*t)*N.x + R*sin(omega*t)*N.y + 0*N.z",
        allowed_params=("R", "omega"),
        params={"R": 1.0, "omega": 1.0},
        t_min=0.0, t_max=6.283, t_0=0.0,
    ),
    _v_preset(
        "Mouvement circulaire uniformément accéléré (φ(t)=α·t²/2)",
        "R*cos(alpha*t**2/2)*N.x + R*sin(alpha*t**2/2)*N.y + 0*N.z",
        allowed_params=("R", "alpha"),
        params={"R": 1.0, "alpha": 0.5},
        t_min=0.0, t_max=4.0, t_0=1.0,
    ),

    # ----- Trajectoires planes --------------------------------------------
    _v_preset(
        "Cycloïde : roue qui roule",
        "(R*(t - sin(t)))*N.x + (R*(1 - cos(t)))*N.y + 0*N.z",
        allowed_params=("R",),
        params={"R": 1.0},
        t_min=0.0, t_max=12.566, t_0=3.14,   # deux tours, on s'arrête en cusp
        resolution=512,                       # cusps + arches → fine sampling
    ),
    _v_preset(
        "Lemniscate de Bernoulli",
        # Forme paramétrique standard ; le facteur t/(1+t²) est régulier.
        "a*cos(t)/(1 + sin(t)**2)*N.x + "
        "a*sin(t)*cos(t)/(1 + sin(t)**2)*N.y + 0*N.z",
        allowed_params=("a",),
        params={"a": 1.5},
        t_min=0.0, t_max=6.283, t_0=0.0,
        resolution=512,
    ),
    _v_preset(
        "Figure de Lissajous (a, b)",
        "cos(a*t)*N.x + sin(b*t)*N.y + 0*N.z",
        allowed_params=("a", "b"),
        params={"a": 3.0, "b": 2.0},
        t_min=0.0, t_max=6.283, t_0=0.0,
        resolution=512,
    ),
    _v_preset(
        "Spirale d'Archimède : r=a·t",
        "(a*t*cos(t))*N.x + (a*t*sin(t))*N.y + 0*N.z",
        allowed_params=("a",),
        params={"a": 0.1},
        t_min=0.0, t_max=12.566, t_0=3.14,
    ),
    _v_preset(
        "Spirale logarithmique amortie",
        "exp(-t/k)*cos(t)*N.x + exp(-t/k)*sin(t)*N.y + 0*N.z",
        allowed_params=("k",),
        params={"k": 3.0},
        t_min=0.0, t_max=12.566, t_0=2.0,
        resolution=512,
    ),

    # ----- Trajectoires 3D -------------------------------------------------
    _v_preset(
        "Hélice circulaire (rayon R, pas h)",
        "R*cos(t)*N.x + R*sin(t)*N.y + (h*t/(2*pi))*N.z",
        allowed_params=("R", "h"),
        params={"R": 1.0, "h": 1.0},
        t_min=0.0, t_max=12.566, t_0=3.14,    # deux tours
    ),
    _v_preset(
        "Hélice conique",
        "(a*t)*cos(t)*N.x + (a*t)*sin(t)*N.y + (b*t)*N.z",
        allowed_params=("a", "b"),
        params={"a": 0.1, "b": 0.2},
        t_min=0.0, t_max=12.566, t_0=4.0,
    ),
    _v_preset(
        "Courbe de Viviani (intersection sphère / cylindre)",
        # Sphère de rayon 2R centrée à l'origine, cylindre de rayon R
        # centré en (R, 0). Paramétrage standard.
        "R*(1 + cos(t))*N.x + R*sin(t)*N.y + (2*R*sin(t/2))*N.z",
        allowed_params=("R",),
        params={"R": 1.0},
        t_min=-6.283, t_max=6.283, t_0=0.0,
        resolution=512,
    ),

    # ----- Mouvements physiques --------------------------------------------
    _v_preset(
        "Chute libre depuis (0, h₀) avec vitesse initiale (v₀, 0)",
        "(v0*t)*N.x + (h0 - g*t**2/2)*N.y + 0*N.z",
        allowed_params=("v0", "h0", "g"),
        params={"v0": 2.0, "h0": 5.0, "g": 9.81},
        t_min=0.0, t_max=1.0, t_0=0.5,
    ),
    _v_preset(
        "Projectile : tir avec angle θ",
        "(v0*cos(theta)*t)*N.x + "
        "(v0*sin(theta)*t - g*t**2/2)*N.y + 0*N.z",
        allowed_params=("v0", "theta", "g"),
        # θ = π/4 ≈ 0.785 : portée maximale ; v₀ = 10 m/s ; g = 9.81 m/s²
        params={"v0": 10.0, "theta": 0.785, "g": 9.81},
        t_min=0.0, t_max=1.5, t_0=0.7,
    ),
    _v_preset(
        "Oscillateur harmonique amorti (réponse libre)",
        # Position d'un oscillateur amorti faible : x(t) = exp(-γt)·cos(ωt)
        "exp(-gamma*t)*cos(omega*t)*N.x + 0*N.y + 0*N.z",
        allowed_params=("gamma", "omega"),
        params={"gamma": 0.3, "omega": 3.0},
        t_min=0.0, t_max=10.0, t_0=1.0,
        resolution=512,
    ),

    _v_preset(
        "Astroïde : (cos³t, sin³t)",
        "(cos(t))**3*N.x + (sin(t))**3*N.y + 0*N.z",
        t_min=0.0, t_max=6.283, t_0=0.7,
        # Hypocycloïde à 4 rebroussements : la vitesse s'annule aux
        # pointes (vecteur vitesse → 0), l'accélération non.
    ),
    _v_preset(
        "Cardioïde",
        "a*(2*cos(t) - cos(2*t))*N.x + a*(2*sin(t) - sin(2*t))*N.y + 0*N.z",
        allowed_params=("a",),
        params={"a": 0.7},
        t_min=0.0, t_max=6.283, t_0=1.0,
    ),
    _v_preset(
        "Deltoïde (hypocycloïde à 3 pointes)",
        "0.6*(2*cos(t) + cos(2*t))*N.x + 0.6*(2*sin(t) - sin(2*t))*N.y + 0*N.z",
        t_min=0.0, t_max=6.283, t_0=0.5,
    ),
    _v_preset(
        "Nœud de trèfle (courbe 3D fermée)",
        "(sin(t) + 2*sin(2*t))*N.x + (cos(t) - 2*cos(2*t))*N.y + (-sin(3*t))*N.z",
        t_min=0.0, t_max=6.283, t_0=0.8,
        trace_thickness=0.03,
        # Le plus simple des nœuds non triviaux — fermé, sans
        # auto-intersection en 3D (les croisements apparents
        # disparaissent en orbitant la vue).
    ),
    _v_preset(
        "Tractrice : (t − tanh t, 1/cosh t)",
        "(t - tanh(t))*N.x + (1/cosh(t))*N.y + 0*N.z",
        t_min=-4.0, t_max=4.0, t_0=1.2,
        # Courbe du chien tiré en laisse ; sa surface de révolution
        # est la pseudosphère (cf. presets de surfaces paramétriques).
    ),
    _v_preset(
        "Épicycloïde (k=5)",
        "(1.2*cos(t) - 0.2*cos(6*t))*N.x + (1.2*sin(t) - 0.2*sin(6*t))*N.y + 0*N.z",
        t_min=0.0, t_max=6.283, t_0=0.4,
    ),
]


def reinstall_vector_builtins() -> int:
    """Write every built-in vector preset to the user vector-presets
    directory. Returns the number of files written.

    Same overwrite policy as the scalar variant: if the user has tweaked
    a builtin preset, calling this restores the original.
    """
    from . import presets

    n = 0
    for preset in BUILTIN_VECTOR_PRESETS:
        slug = BUILTIN_VECTOR_FILE_PREFIX + presets._slugify(preset["name"])
        fp = presets._vector_presets_dir() / (slug + ".json")
        import json
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_vector_builtin_file(path) -> bool:
    """True if ``path`` looks like one of our installed vector built-ins."""
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_VECTOR_FILE_PREFIX)


# =========================================================================== #
# Built-in surface presets (explicit z = f(x, y))
# =========================================================================== #

BUILTIN_SURFACE_FILE_PREFIX = "_builtin_surf_"


def _s_preset(name: str, expr: str, *,
                x_min: float = -3.0, x_max: float = 3.0,
                y_min: float = -3.0, y_max: float = 3.0,
                x_0: float = 0.5, y_0: float = 0.5,
                resolution_x: int = 64, resolution_y: int = 64,
                marker_size: float = 0.15,
                tangent_size: float = 1.5,
                tangent_resolution: int = 8,
                show_tangent: bool = True,
                show_taylor: bool = False,
                taylor_order: int = 2,
                taylor_size: float = 1.5,
                taylor_resolution: int = 24,
                allowed_params: tuple = (),
                params: dict | None = None) -> dict:
    """Concise builder for a built-in explicit-surface preset.

    ``show_taylor`` / ``taylor_order`` drive the osculating-Taylor-surface
    feature; presets leaving ``show_taylor`` False behave exactly as
    before (the ``taylor`` section is read back with ``.get`` defaults, so
    it is harmless on trees built before the feature existed)."""
    import datetime
    return {
        "schema": 1,
        "kind": "surface",
        "name": name,
        "name_en": _NAME_EN.get(name, name),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "formula": {
            "expr": expr,
            "x_name": "x", "y_name": "y",
            "allowed_params": list(allowed_params),
        },
        "range": {
            "x_min": float(x_min), "x_max": float(x_max),
            "y_min": float(y_min), "y_max": float(y_max),
            "x_0": float(x_0), "y_0": float(y_0),
            "resolution_x": int(resolution_x),
            "resolution_y": int(resolution_y),
        },
        "params": dict(params or {}),
        "surface": {"material_name": ""},
        "marker": {"size": float(marker_size), "material_name": ""},
        "tangent": {
            "visible": bool(show_tangent),
            "size": float(tangent_size),
            "resolution": int(tangent_resolution),
            "material_name": "",
        },
        "taylor": {
            "visible": bool(show_taylor),
            "order": int(taylor_order),
            "size": float(taylor_size),
            "resolution": int(taylor_resolution),
            "material_name": "",
        },
    }


# Catalogue
# ---------
# Standard examples for multivariable calculus / differential geometry:
#
#  * Surfaces quadratiques simples (paraboloïde, selle…)
#  * Surfaces périodiques (vagues, papiers ondulés)
#  * Surfaces à symétrie radiale (gaussienne, sinc 2D)
#  * Surfaces avec point singulier intéressant (cône, valeur absolue 2D)
BUILTIN_SURFACE_PRESETS = [

    # ----- Paraboloïdes et selles ---------------------------------------
    _s_preset(
        "Paraboloïde elliptique z = x²+y²",
        "x**2 + y**2",
        x_min=-2, x_max=2, y_min=-2, y_max=2,
        x_0=0.5, y_0=0.5, tangent_size=1.5,
    ),
    _s_preset(
        "Paraboloïde hyperbolique (selle) z = x²-y²",
        "x**2 - y**2",
        x_min=-2, x_max=2, y_min=-2, y_max=2,
        x_0=0.0, y_0=0.0, tangent_size=2.0,
        # Au point selle (0, 0) le plan tangent est horizontal — joli
        # contraste avec la courbure dans les deux directions.
    ),
    _s_preset(
        "Selle du singe z = x³-3xy²",
        "x**3 - 3*x*y**2",
        x_min=-2, x_max=2, y_min=-2, y_max=2,
        x_0=0.3, y_0=0.3, tangent_size=1.5,
    ),
    _s_preset(
        "Plan z = a·x + b·y + c",
        "a*x + b*y + c",
        allowed_params=("a", "b", "c"),
        params={"a": 0.5, "b": 0.3, "c": 0.0},
        x_min=-3, x_max=3, y_min=-3, y_max=3,
        # Le plan tangent est exactement la surface — démo conceptuelle
        # de "la dérivée d'une fonction affine est elle-même".
        x_0=0.0, y_0=0.0,
    ),

    # ----- Symétrie radiale --------------------------------------------
    _s_preset(
        "Gaussienne z = exp(-(x²+y²)/σ²)",
        "exp(-(x**2 + y**2)/sigma**2)",
        allowed_params=("sigma",),
        params={"sigma": 1.0},
        x_min=-3, x_max=3, y_min=-3, y_max=3,
        x_0=0.5, y_0=0.5, tangent_size=1.5,
    ),
    _s_preset(
        "Sinc 2D z = sin(√(x²+y²)) / √(x²+y²)",
        # SymPy gère bien le 0/0 au centre comme limite ; le sampling
        # mesh prend juste la valeur en chaque vertex, qui sera très
        # proche de 1 près de l'origine (les vertex tombent rarement
        # sur exactement (0, 0)).
        "sin(sqrt(x**2 + y**2))/sqrt(x**2 + y**2)",
        x_min=-8, x_max=8, y_min=-8, y_max=8,
        x_0=2.0, y_0=2.0,
        resolution_x=128, resolution_y=128,
        tangent_size=3.0,
    ),
    _s_preset(
        "Cône z = √(x²+y²)",
        "sqrt(x**2 + y**2)",
        x_min=-2, x_max=2, y_min=-2, y_max=2,
        x_0=0.5, y_0=0.5,
        # Au sommet (0, 0) la surface n'est pas différentiable —
        # bouger le marqueur vers (0, 0) montre le plan tangent qui
        # devient instable. C'est volontairement pédagogique.
    ),

    # ----- Surfaces périodiques ----------------------------------------
    _s_preset(
        "Vagues z = sin(x)·cos(y)",
        "sin(x)*cos(y)",
        x_min=-6.28, x_max=6.28, y_min=-6.28, y_max=6.28,
        x_0=1.0, y_0=1.0,
        resolution_x=96, resolution_y=96,
        tangent_size=2.0,
    ),
    _s_preset(
        "Ondes radiales z = sin(√(x²+y²))",
        "sin(sqrt(x**2 + y**2))",
        x_min=-6, x_max=6, y_min=-6, y_max=6,
        x_0=1.5, y_0=1.5,
        resolution_x=96, resolution_y=96,
    ),

    # ----- Surfaces ondulées ou exotiques -------------------------------
    _s_preset(
        "Selle de cheval z = x·y",
        "x*y",
        x_min=-2, x_max=2, y_min=-2, y_max=2,
        x_0=0.5, y_0=0.5, tangent_size=1.5,
    ),
    _s_preset(
        "Monkey saddle 2 — z = sin(x)+sin(y)",
        "sin(x) + sin(y)",
        x_min=-6.28, x_max=6.28, y_min=-6.28, y_max=6.28,
        x_0=1.57, y_0=1.57,   # (π/2, π/2) : minimum local
        resolution_x=96, resolution_y=96,
    ),
    _s_preset(
        "Hauteur ondulée z = sin(a·x + b·y)",
        "sin(a*x + b*y)",
        allowed_params=("a", "b"),
        params={"a": 2.0, "b": 1.0},
        x_min=-3.14, x_max=3.14, y_min=-3.14, y_max=3.14,
        x_0=0.5, y_0=0.5,
    ),

    _s_preset(
        "Bosse dipolaire z = x·exp(-(x²+y²))",
        "x*exp(-(x**2 + y**2))",
        x_min=-3.0, x_max=3.0, y_min=-3.0, y_max=3.0,
        x_0=0.7, y_0=0.0,
        # Un pic et un creux symétriques : ∂f/∂x change de signe le
        # long de l'axe x, point selle à l'origine.
    ),
    _s_preset(
        "Chapeau mexicain z = ((x²+y²)² − 4(x²+y²))/8",
        "((x**2 + y**2)**2 - 4*(x**2 + y**2))/8",
        x_min=-2.0, x_max=2.0, y_min=-2.0, y_max=2.0,
        x_0=1.0, y_0=0.5,
        # Potentiel « sombrero » : maximum local à l'origine, cercle
        # de minima en r=√2 — brisure spontanée de symétrie.
    ),
    _s_preset(
        "Vallée de Rosenbrock (réduite)",
        "((1 - x)**2 + 4*(y - x**2)**2)/20",
        x_min=-2.0, x_max=2.0, y_min=-1.0, y_max=3.0,
        x_0=0.0, y_0=0.0,
        # La « vallée banane » des cours d'optimisation : minimum
        # global en (1, 1) au fond d'une vallée courbe très plate.
    ),
    _s_preset(
        "Quadrupôle gaussien z = x·y·exp(-(x²+y²)/2)",
        "x*y*exp(-(x**2 + y**2)/2)",
        x_min=-3.0, x_max=3.0, y_min=-3.0, y_max=3.0,
        x_0=1.0, y_0=1.0,
        # Quatre lobes alternés (+,−,+,−) — symétrie du produit xy.
    ),
    _s_preset(
        "Ondes croisées amorties",
        "cos(x)*cos(y)*exp(-(x**2 + y**2)/6)",
        x_min=-5.0, x_max=5.0, y_min=-5.0, y_max=5.0,
        x_0=0.0, y_0=0.0,
        resolution_x=96, resolution_y=96,
    ),

    # ----- Surfaces de Taylor osculatrices -------------------------------
    # Démarrage avec la nappe de Taylor visible (ordre 2) sur un point
    # où la courbure est franche : on voit d'emblée le paraboloïde
    # osculateur épouser la surface. Tangent plane masqué pour ne pas
    # surcharger. Scrubber « Ordre de Taylor » pour comparer 1 / 2 / 3…
    _s_preset(
        "Paraboloïde osculateur — vagues sin(x)·cos(y)",
        "sin(x)*cos(y)",
        x_min=-6.28, x_max=6.28, y_min=-6.28, y_max=6.28,
        x_0=1.0, y_0=0.5,
        resolution_x=96, resolution_y=96,
        show_tangent=False,
        show_taylor=True, taylor_order=2,
        taylor_size=2.6, taylor_resolution=28,
    ),
    _s_preset(
        "Calotte osculatrice — gaussienne",
        "exp(-(x**2 + y**2)/sigma**2)",
        allowed_params=("sigma",),
        params={"sigma": 1.0},
        x_min=-3, x_max=3, y_min=-3, y_max=3,
        x_0=0.7, y_0=0.4,
        show_tangent=False,
        show_taylor=True, taylor_order=2,
        taylor_size=2.0, taylor_resolution=28,
    ),
    _s_preset(
        "Osculation d'ordre 2 — ondes radiales",
        "sin(sqrt(x**2 + y**2))",
        x_min=-6, x_max=6, y_min=-6, y_max=6,
        x_0=1.5, y_0=1.5,
        resolution_x=96, resolution_y=96,
        show_tangent=False,
        show_taylor=True, taylor_order=2,
        taylor_size=2.4, taylor_resolution=28,
    ),
]


def reinstall_surface_builtins() -> int:
    """Write every built-in surface preset to the user surface-preset
    directory. Returns the number of files written."""
    from . import presets

    n = 0
    for preset in BUILTIN_SURFACE_PRESETS:
        slug = BUILTIN_SURFACE_FILE_PREFIX + presets._slugify(preset["name"])
        fp = presets._surface_presets_dir() / (slug + ".json")
        import json
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_surface_builtin_file(path) -> bool:
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_SURFACE_FILE_PREFIX)


# =========================================================================== #
# Built-in parametric surface presets
# =========================================================================== #

BUILTIN_PARAMETRIC_SURFACE_FILE_PREFIX = "_builtin_psurf_"


def _ps_preset(name: str, x_expr: str, y_expr: str, z_expr: str, *,
                 u_min: float = 0.0, u_max: float = 6.283,
                 v_min: float = 0.0, v_max: float = 3.142,
                 u_0: float = 1.0, v_0: float = 1.0,
                 resolution_u: int = 64, resolution_v: int = 64,
                 marker_size: float = 0.10,
                 tangent_size: float = 1.0,
                 tangent_resolution: int = 8,
                 show_tangent: bool = True,
                 show_taylor: bool = False,
                 taylor_order: int = 2,
                 taylor_size: float = 1.0,
                 taylor_resolution: int = 24,
                 allowed_params: tuple = (),
                 params: dict | None = None) -> dict:
    import datetime
    return {
        "schema": 1,
        "kind": "parametric_surface",
        "name": name,
        "name_en": _NAME_EN.get(name, name),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "formula": {
            "components": [x_expr, y_expr, z_expr],
            "u_name": "u", "v_name": "v",
            "allowed_params": list(allowed_params),
        },
        "range": {
            "u_min": float(u_min), "u_max": float(u_max),
            "v_min": float(v_min), "v_max": float(v_max),
            "u_0": float(u_0), "v_0": float(v_0),
            "resolution_u": int(resolution_u),
            "resolution_v": int(resolution_v),
        },
        "params": dict(params or {}),
        "surface": {"material_name": ""},
        "marker": {"size": float(marker_size), "material_name": ""},
        "tangent": {
            "visible": bool(show_tangent),
            "size": float(tangent_size),
            "resolution": int(tangent_resolution),
            "material_name": "",
        },
        "taylor": {
            "visible": bool(show_taylor),
            "order": int(taylor_order),
            "size": float(taylor_size),
            "resolution": int(taylor_resolution),
            "material_name": "",
        },
    }


BUILTIN_PARAMETRIC_SURFACE_PRESETS = [

    # ----- Surfaces fermées classiques ---------------------------------
    _ps_preset(
        "Sphère unitaire",
        "sin(u)*cos(v)", "sin(u)*sin(v)", "cos(u)",
        u_min=0, u_max=3.142, v_min=0, v_max=6.283,
        u_0=1.0, v_0=1.0,
        # Au pôle nord (u=0) ∂F/∂u et ∂F/∂v ne sont plus linéairement
        # indépendants — démo pédagogique : déplacer u₀ vers 0 dégrade
        # le plan tangent.
    ),
    _ps_preset(
        "Sphère de rayon R",
        "R*sin(u)*cos(v)", "R*sin(u)*sin(v)", "R*cos(u)",
        allowed_params=("R",),
        params={"R": 2.0},
        u_min=0, u_max=3.142, v_min=0, v_max=6.283,
        u_0=1.0, v_0=1.0,
    ),
    _ps_preset(
        "Tore (R, r)",
        "(R + r*cos(u))*cos(v)",
        "(R + r*cos(u))*sin(v)",
        "r*sin(u)",
        allowed_params=("R", "r"),
        params={"R": 2.0, "r": 0.7},
        u_min=0, u_max=6.283, v_min=0, v_max=6.283,
        u_0=1.0, v_0=1.0,
        resolution_u=64, resolution_v=64,
    ),

    # ----- Surfaces minimales / hélicoïdes ------------------------------
    _ps_preset(
        "Hélicoïde droit",
        "u*cos(v)", "u*sin(v)", "v",
        u_min=-1.5, u_max=1.5, v_min=0, v_max=6.283,
        u_0=1.0, v_0=1.0,
        resolution_u=32, resolution_v=64,
    ),
    _ps_preset(
        "Caténoïde",
        "cosh(u)*cos(v)", "cosh(u)*sin(v)", "u",
        u_min=-1.5, u_max=1.5, v_min=0, v_max=6.283,
        u_0=0.5, v_0=1.0,
        resolution_u=32, resolution_v=64,
    ),

    # ----- Surfaces de révolution --------------------------------------
    _ps_preset(
        "Cylindre R·(cos v, sin v, u)",
        "R*cos(v)", "R*sin(v)", "u",
        allowed_params=("R",),
        params={"R": 1.0},
        u_min=-2, u_max=2, v_min=0, v_max=6.283,
        u_0=0.5, v_0=1.0,
        resolution_u=16, resolution_v=64,
    ),
    _ps_preset(
        "Cône de révolution",
        "u*cos(v)", "u*sin(v)", "u",
        u_min=0, u_max=2, v_min=0, v_max=6.283,
        u_0=1.0, v_0=1.0,
        resolution_u=24, resolution_v=64,
    ),

    # ----- Surfaces réglées exotiques ----------------------------------
    _ps_preset(
        "Ruban de Möbius",
        # Forme paramétrique classique avec rayon R et largeur w
        "(R + w*v*cos(u/2))*cos(u)",
        "(R + w*v*cos(u/2))*sin(u)",
        "w*v*sin(u/2)",
        allowed_params=("R", "w"),
        params={"R": 1.0, "w": 0.4},
        u_min=0, u_max=6.283, v_min=-1.0, v_max=1.0,
        u_0=1.5, v_0=0.0,
        resolution_u=128, resolution_v=8,
    ),

    _ps_preset(
        "Surface d'Enneper (minimale)",
        "u - u**3/3 + u*v**2",
        "v - v**3/3 + v*u**2",
        "u**2 - v**2",
        u_min=-1.2, u_max=1.2, v_min=-1.2, v_max=1.2,
        u_0=0.5, v_0=0.3,
        # Surface minimale auto-intersectante au-delà de |u|,|v| ≳ √3.
    ),
    _ps_preset(
        "Pseudosphère (tractricoïde)",
        "cos(v)/cosh(u)",
        "sin(v)/cosh(u)",
        "u - tanh(u)",
        u_min=-3.0, u_max=3.0, v_min=0.0, v_max=6.283,
        u_0=1.0, v_0=1.0,
        # Courbure de Gauss constante −1 : le modèle local de la
        # géométrie hyperbolique, révolution de la tractrice.
    ),
    _ps_preset(
        "Conoïde de Plücker",
        "u*cos(v)",
        "u*sin(v)",
        "sin(2*v)",
        u_min=0.0, u_max=1.5, v_min=0.0, v_max=6.283,
        u_0=0.8, v_0=0.6,
        # Surface réglée : chaque génératrice u ↦ (u·cos v, u·sin v)
        # est une droite horizontale d'altitude sin(2v).
    ),
    _ps_preset(
        "Bouteille de Klein (immersion en 8)",
        "(2 + cos(u/2)*sin(v) - sin(u/2)*sin(2*v))*cos(u)",
        "(2 + cos(u/2)*sin(v) - sin(u/2)*sin(2*v))*sin(u)",
        "sin(u/2)*sin(v) + cos(u/2)*sin(2*v)",
        u_min=0.0, u_max=6.283, v_min=0.0, v_max=6.283,
        u_0=1.0, v_0=1.0,
        resolution_u=96, resolution_v=48,
        # Surface fermée non orientable — l'immersion « figure 8 »
        # dans R³ s'auto-intersecte nécessairement.
    ),
    _ps_preset(
        "Vase de révolution sinusoïdal",
        "(2 + 0.6*sin(2*u))*cos(v)",
        "(2 + 0.6*sin(2*u))*sin(v)",
        "u",
        u_min=-1.5, u_max=1.5, v_min=0.0, v_max=6.283,
        u_0=0.0, v_0=1.0,
        # Révolution d'un profil r(z) = 2 + 0.6·sin(2z) : lecture
        # directe du lien profil ↔ surface de révolution.
    ),

    # ----- Surfaces de Taylor osculatrices -------------------------------
    # Nappe de Taylor visible (ordre 2) dès l'ouverture : la nappe
    # osculatrice épouse la surface au point d'ancrage et s'en écarte
    # plus loin. Plan tangent masqué. Scrubber l'ordre pour voir l'effet.
    _ps_preset(
        "Tore — nappe osculatrice (ordre 2)",
        "cos(u)*(2 + cos(v))", "sin(u)*(2 + cos(v))", "sin(v)",
        u_min=0.0, u_max=6.283, v_min=0.0, v_max=6.283,
        u_0=1.0, v_0=0.5,
        resolution_u=72, resolution_v=72,
        show_tangent=False,
        show_taylor=True, taylor_order=2,
        taylor_size=2.6, taylor_resolution=28,
    ),
    _ps_preset(
        "Sphère — calotte osculatrice (ordre 2)",
        "sin(u)*cos(v)", "sin(u)*sin(v)", "cos(u)",
        u_min=0.0, u_max=3.142, v_min=0.0, v_max=6.283,
        u_0=1.2, v_0=1.0,
        show_tangent=False,
        show_taylor=True, taylor_order=2,
        taylor_size=1.6, taylor_resolution=26,
    ),
]


def reinstall_parametric_surface_builtins() -> int:
    """Write every built-in parametric-surface preset to disk."""
    from . import presets

    n = 0
    for preset in BUILTIN_PARAMETRIC_SURFACE_PRESETS:
        slug = (BUILTIN_PARAMETRIC_SURFACE_FILE_PREFIX
                + presets._slugify(preset["name"]))
        fp = presets._parametric_surface_presets_dir() / (slug + ".json")
        import json
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_parametric_surface_builtin_file(path) -> bool:
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_PARAMETRIC_SURFACE_FILE_PREFIX)


# =========================================================================== #
# Built-in 3D scalar field presets
# =========================================================================== #
# Classics from electrostatics, thermodynamics, quantum mechanics, and
# pure differential calculus.

BUILTIN_SCALAR_FIELD_3D_FILE_PREFIX = "_builtin_sf3d_"


def _sf3d_preset(name: str, expr: str, *,
                   x_min: float = -1.0, x_max: float = 1.0,
                   y_min: float = -1.0, y_max: float = 1.0,
                   z_min: float = -1.0, z_max: float = 1.0,
                   x_0: float = 0.5, y_0: float = 0.5, z_0: float = 0.5,
                   resolution_x: int = 5, resolution_y: int = 5,
                   resolution_z: int = 5,
                   marker_size: float = 0.04,
                   f_min: float = -1.0,
                   f_max: float = 1.0,
                   show_basepoint: bool = True,
                   basepoint_marker_size: float = 0.10,
                   basepoint_label_size: float = 0.16,
                   allowed_params: tuple = (),
                   params: dict | None = None) -> dict:
    """Helper to build a 3D scalar-field preset dict.

    The ``f_min`` / ``f_max`` parameters drive the colour-ramp
    normalisation: every grid sphere is shaded by f(x, y, z), with
    f_min mapped to the cold end of the ramp and f_max to the warm
    end. Choose values that bracket the *typical* range of f on the
    domain box so the colour information is informative — too wide a
    range washes out variations, too narrow saturates a lot of points
    to the extremes.
    """
    import datetime
    return {
        "schema": 1,
        "kind": "scalar_field_3d",
        "name": name,
        "name_en": _NAME_EN.get(name, name),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "formula": {
            "expr": expr,
            "x_name": "x", "y_name": "y", "z_name": "z",
            "allowed_params": list(allowed_params),
        },
        "range": {
            "x_min": float(x_min), "x_max": float(x_max),
            "y_min": float(y_min), "y_max": float(y_max),
            "z_min": float(z_min), "z_max": float(z_max),
            "x_0": float(x_0), "y_0": float(y_0), "z_0": float(z_0),
            "resolution_x": int(resolution_x),
            "resolution_y": int(resolution_y),
            "resolution_z": int(resolution_z),
            "f_min": float(f_min),
            "f_max": float(f_max),
        },
        "params": dict(params or {}),
        "markers": {"size": float(marker_size), "material_name": ""},
        # The "labels" sub-dict is left in place for back-compat with
        # snapshot/apply code that still iterates over the same keys
        # for the vector_field_3d kind. Scalar_field_3d ignores it now
        # — sphere colour replaces numeric per-point labels.
        "labels": {
            "size": 0.08,
            "offset": 0.10,
            "material_name": "",
        },
        "basepoint": {
            "visible": bool(show_basepoint),
            "marker_size": float(basepoint_marker_size),
            "label_size": float(basepoint_label_size),
            "marker_material_name": "",
            "label_material_name": "",
        },
    }


BUILTIN_SCALAR_FIELD_3D_PRESETS = [

    # ----- Polynômes simples ------------------------------------------
    _sf3d_preset(
        "Distance carrée x²+y²+z²",
        "x**2 + y**2 + z**2",
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        f_min=0.0, f_max=3.0,
    ),
    _sf3d_preset(
        "Distance euclidienne √(x²+y²+z²)",
        "sqrt(x**2 + y**2 + z**2)",
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        f_min=0.0, f_max=1.7,
    ),

    # ----- Électrostatique -------------------------------------------
    _sf3d_preset(
        "Potentiel coulombien : k/r",
        # k/r avec r = √(x²+y²+z²). Divergence à l'origine — l'utilisateur
        # doit choisir un x_0 non nul.
        "k/sqrt(x**2 + y**2 + z**2)",
        allowed_params=("k",),
        params={"k": 1.0},
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        # k=1, r=√(0.04+0.04+0.04)=0.35 → 2.9 ; r=1.73 → 0.58. Saturer
        # l'extrémité chaude à 5 pour rester lisible à proximité du
        # centre.
        f_min=0.5, f_max=5.0,
    ),
    _sf3d_preset(
        "Potentiel d'un dipôle : p·z / r³",
        # Dipôle aligné selon z : V = p·cos(θ)/r² = p·z/r³.
        "p*z/(x**2 + y**2 + z**2)**(3/2)",
        allowed_params=("p",),
        params={"p": 1.0},
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.3, y_0=0.3, z_0=0.5,
        # Antisymétrique en z, valeurs autour de [-3, 3] en pratique.
        f_min=-3.0, f_max=3.0,
    ),

    # ----- Symétrie radiale gaussienne / exponentielle ----------------
    _sf3d_preset(
        "Gaussienne 3D : exp(-(x²+y²+z²)/σ²)",
        "exp(-(x**2 + y**2 + z**2)/sigma**2)",
        allowed_params=("sigma",),
        params={"sigma": 0.5},
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.0, y_0=0.0, z_0=0.0,
        # Valeurs dans [0, 1] : 1 au centre, ~e^(-12) aux coins.
        f_min=0.0, f_max=1.0,
    ),
    _sf3d_preset(
        "Décroissance exponentielle radiale : exp(-r/λ)",
        "exp(-sqrt(x**2 + y**2 + z**2)/lambda_)",
        # lambda_ avec underscore — sinon collision avec Python keyword.
        allowed_params=("lambda_",),
        params={"lambda_": 0.5},
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        # Idem : valeurs dans [exp(-1.73/0.5), 1] ≈ [0.03, 1].
        f_min=0.0, f_max=1.0,
    ),

    # ----- Oscillateur harmonique 3D ---------------------------------
    _sf3d_preset(
        "Oscillateur harmonique 3D isotrope : ½ω²(x²+y²+z²)",
        "omega**2*(x**2 + y**2 + z**2)/2",
        allowed_params=("omega",),
        params={"omega": 1.0},
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.0, z_0=0.0,
        # ω=1 : valeurs dans [0, 3/2].
        f_min=0.0, f_max=1.5,
    ),
    _sf3d_preset(
        "Oscillateur anisotrope : ½(a·x² + b·y² + c·z²)",
        "(a*x**2 + b*y**2 + c*z**2)/2",
        allowed_params=("a", "b", "c"),
        params={"a": 1.0, "b": 2.0, "c": 3.0},
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        # a=1, b=2, c=3 : max = (1+2+3)/2 = 3 aux coins.
        f_min=0.0, f_max=3.0,
    ),

    # ----- Fonctions harmoniques (Laplacien nul) ---------------------
    _sf3d_preset(
        "Harmonique sphérique l=2, m=0 : ½·(3z² − r²)",
        # 3z² - x² - y² - z² = 2z² - x² - y². Harmonique : Δf = 0.
        "(2*z**2 - x**2 - y**2)/2",
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        # Antisymétrique : valeurs dans [-1, 1].
        f_min=-1.0, f_max=1.0,
    ),
    _sf3d_preset(
        "Champ trilinéaire x·y·z",
        "x*y*z",
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        x_0=0.5, y_0=0.5, z_0=0.5,
        # max=1 aux coins (+1,+1,+1) ou trois faces négatives, min=-1.
        f_min=-1.0, f_max=1.0,
    ),

    _sf3d_preset(
        "Onde stationnaire 3D : sin(πx)·sin(πy)·sin(πz)",
        "sin(pi*x)*sin(pi*y)*sin(pi*z)",
        x_min=-1.0, x_max=1.0, y_min=-1.0, y_max=1.0,
        z_min=-1.0, z_max=1.0,
        f_min=-1.0, f_max=1.0,
        resolution_x=7, resolution_y=7, resolution_z=7,
        # Mode propre de la boîte : plans nodaux f=0 aux entiers.
    ),
    _sf3d_preset(
        "Potentiel de Yukawa : exp(-2r)/r",
        "exp(-2*sqrt(x**2 + y**2 + z**2))/sqrt(x**2 + y**2 + z**2)",
        # Domaine légèrement décalé : la grille ne contient jamais
        # exactement l'origine (singularité 1/r évitée proprement).
        x_min=-1.04, x_max=0.96, y_min=-1.04, y_max=0.96,
        z_min=-1.04, z_max=0.96,
        x_0=0.46, y_0=0.46, z_0=0.46,
        f_min=0.0, f_max=3.0,
        # Interaction à courte portée : décroissance bien plus rapide
        # que le potentiel coulombien k/r (à comparer côte à côte).
    ),
    _sf3d_preset(
        "Fonction harmonique : x² + y² − 2z²",
        "x**2 + y**2 - 2*z**2",
        f_min=-2.0, f_max=2.0,
        # Δf = 2 + 2 − 4 = 0 : pas d'extremum intérieur (principe du
        # maximum), uniquement des points selles.
    ),
    _sf3d_preset(
        "Potentiel périodique : cos(πx)+cos(πy)+cos(πz)",
        "cos(pi*x) + cos(pi*y) + cos(pi*z)",
        f_min=-3.0, f_max=3.0,
        resolution_x=7, resolution_y=7, resolution_z=7,
    ),
    _sf3d_preset(
        "Dipôle fini : deux charges opposées en z=±0.6",
        "1/sqrt(x**2 + y**2 + (z - 0.6)**2)"
        " - 1/sqrt(x**2 + y**2 + (z + 0.6)**2)",
        f_min=-3.0, f_max=3.0,
        # Les singularités (0,0,±0.6) ne tombent sur aucun point de la
        # grille 5×5×5 de [-1,1]³ (pas de 0.5). Antisymétrie en z.
    ),
]


def reinstall_scalar_field_3d_builtins() -> int:
    """Write every 3D-scalar-field builtin preset to the user dir."""
    from . import presets

    n = 0
    for preset in BUILTIN_SCALAR_FIELD_3D_PRESETS:
        slug = (BUILTIN_SCALAR_FIELD_3D_FILE_PREFIX
                + presets._slugify(preset["name"]))
        fp = presets._scalar_field_3d_presets_dir() / (slug + ".json")
        import json
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_scalar_field_3d_builtin_file(path) -> bool:
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_SCALAR_FIELD_3D_FILE_PREFIX)


# =========================================================================== #
# Built-in 3D vector field presets
# =========================================================================== #

BUILTIN_VECTOR_FIELD_3D_FILE_PREFIX = "_builtin_vf3d_"


def _vf3d_preset(name: str, *,
                  mode: str = "explicit",
                  components=None,
                  potential: str = "",
                  x_min: float = -1.5, x_max: float = 1.5,
                  y_min: float = -1.5, y_max: float = 1.5,
                  z_min: float = -1.5, z_max: float = 1.5,
                  x_0: float = 0.5, y_0: float = 0.5, z_0: float = 0.5,
                  resolution_x: int = 4, resolution_y: int = 4,
                  resolution_z: int = 4,
                  arrow_scale: float = 0.3,
                  marker_size: float = 0.08,
                  label_size: float = 0.15,
                  label_offset: float = 0.20,
                  show_components: bool = True,
                  show_norm_label: bool = True,
                  allowed_params: tuple = (),
                  params: dict | None = None) -> dict:
    """Concise builder for a built-in vector-field preset.

    ``mode`` is either ``"explicit"`` (then ``components`` is a
    3-tuple of source strings) or ``"from_potential"`` (then
    ``potential`` is the scalar potential source string).
    """
    import datetime
    if mode == "explicit":
        if components is None or len(components) != 3:
            raise ValueError(
                f"_vf3d_preset {name!r}: explicit mode requires "
                f"a 3-tuple of components"
            )
        components_clean = [str(c) for c in components]
        potential_clean = ""
    elif mode == "from_potential":
        if not potential:
            raise ValueError(
                f"_vf3d_preset {name!r}: from_potential mode requires "
                f"a non-empty potential string"
            )
        # Components left as empty placeholders; they're derived at
        # load time from the potential. Keeping the slot present in
        # the JSON makes the schema uniform.
        components_clean = ["", "", ""]
        potential_clean = potential
    else:
        raise ValueError(f"_vf3d_preset {name!r}: unknown mode {mode!r}")

    return {
        "schema": 1,
        "kind": "vector_field_3d",
        "name": name,
        "name_en": _NAME_EN.get(name, name),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "formula": {
            "mode": mode,
            "components": components_clean,
            "potential": potential_clean,
            "x_name": "x", "y_name": "y", "z_name": "z",
            "allowed_params": list(allowed_params),
        },
        "range": {
            "x_min": float(x_min), "x_max": float(x_max),
            "y_min": float(y_min), "y_max": float(y_max),
            "z_min": float(z_min), "z_max": float(z_max),
            "x_0": float(x_0), "y_0": float(y_0), "z_0": float(z_0),
            "resolution_x": int(resolution_x),
            "resolution_y": int(resolution_y),
            "resolution_z": int(resolution_z),
        },
        "params": dict(params or {}),
        "arrow":           {"scale": float(arrow_scale), "material_name": ""},
        "marker":          {"size": float(marker_size),  "material_name": ""},
        "base_arrow":      {"material_name": ""},
        "component_arrow": {"visible": bool(show_components),
                              "material_name": ""},
        "label": {
            "visible": bool(show_norm_label),
            "size": float(label_size),
            "offset": float(label_offset),
            "material_name": "",
        },
    }


# Catalogue
# ---------
# Mix of explicit vector fields and gradient-of-potential examples,
# chosen to span the typical vector-calculus toolbox:
#
#  * Champs élémentaires : constant, radial, rotation autour d'un axe
#  * Forces centrales : Coulomb, gravitationnel
#  * Dipôles électrique et magnétique
#  * Gradients de potentiels classiques (parabolique, gaussien…)
BUILTIN_VECTOR_FIELD_3D_PRESETS = [

    # --- Champs élémentaires ----------------------------------------------
    _vf3d_preset(
        "Champ constant V = e_z",
        components=("0", "0", "1"),
        x_min=-1, x_max=1, y_min=-1, y_max=1, z_min=-1, z_max=1,
        arrow_scale=0.5,
    ),
    _vf3d_preset(
        "Champ radial V = (x, y, z) (divergence non nulle)",
        components=("x", "y", "z"),
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.5, z_max=1.5,
        arrow_scale=0.25,
    ),
    _vf3d_preset(
        "Rotation autour de Oz : V = (-y, x, 0) (rotationnel pur)",
        components=("-y", "x", "0"),
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.0, z_max=1.0,
        arrow_scale=0.3,
    ),
    _vf3d_preset(
        "Rotation autour de e_z amortie : V = (-y, x, 0)·exp(-r²)",
        components=("-y*exp(-(x**2+y**2+z**2))",
                     "x*exp(-(x**2+y**2+z**2))",
                     "0"),
        x_min=-2, x_max=2, y_min=-2, y_max=2, z_min=-1.0, z_max=1.0,
        arrow_scale=0.6,
    ),

    # --- Forces centrales (gradients de potentiel) ------------------------
    _vf3d_preset(
        "Force coulombienne : V = -∇(k/r) (= k·r/r³)",
        mode="from_potential",
        potential="-k/sqrt(x**2 + y**2 + z**2)",
        allowed_params=("k",),
        params={"k": 1.0},
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.5, z_max=1.5,
        # Singularité en 0 : on évite (x_0, y_0, z_0) = (0,0,0)
        x_0=0.5, y_0=0.3, z_0=0.4,
        arrow_scale=0.05,
    ),
    _vf3d_preset(
        "Force gravitationnelle : V = -∇(-GM/r)",
        mode="from_potential",
        potential="GM/sqrt(x**2 + y**2 + z**2)",
        allowed_params=("GM",),
        params={"GM": 1.0},
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.5, z_max=1.5,
        x_0=0.5, y_0=0.3, z_0=0.4,
        arrow_scale=0.05,
    ),

    # --- Gradients de potentiels usuels -----------------------------------
    _vf3d_preset(
        "Gradient du paraboloïde : V = ∇(x²+y²+z²) = (2x, 2y, 2z)",
        mode="from_potential",
        potential="x**2 + y**2 + z**2",
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.5, z_max=1.5,
        arrow_scale=0.15,
    ),
    _vf3d_preset(
        "Gradient d'une gaussienne 3D",
        mode="from_potential",
        potential="exp(-(x**2 + y**2 + z**2))",
        x_min=-2, x_max=2, y_min=-2, y_max=2, z_min=-2, z_max=2,
        arrow_scale=0.8,
    ),

    # --- Dipôles ----------------------------------------------------------
    _vf3d_preset(
        "Champ d'un dipôle électrique (axe e_z) — composantes explicites",
        # Formes standard du dipôle p = p·e_z :
        # E_r = (1/r³)·2p·cos θ, E_θ = (1/r³)·p·sin θ
        # En cartésiennes on peut écrire (sans constante p) :
        components=(
            "3*x*z/(x**2 + y**2 + z**2)**(5/2)",
            "3*y*z/(x**2 + y**2 + z**2)**(5/2)",
            "(2*z**2 - x**2 - y**2)/(x**2 + y**2 + z**2)**(5/2)",
        ),
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.5, z_max=1.5,
        x_0=0.4, y_0=0.3, z_0=0.5,
        arrow_scale=0.03,
    ),

    # --- Composé : hélice + radial ----------------------------------------
    _vf3d_preset(
        "Champ tournant ascendant V = (-y, x, c) (hélicoïdal)",
        components=("-y", "x", "c"),
        allowed_params=("c",),
        params={"c": 0.3},
        x_min=-1.5, x_max=1.5, y_min=-1.5, y_max=1.5, z_min=-1.0, z_max=1.0,
        arrow_scale=0.3,
    ),

    _vf3d_preset(
        "Écoulement ABC (Arnold–Beltrami–Childress)",
        components=("sin(z) + cos(y)", "sin(x) + cos(z)",
                     "sin(y) + cos(x)"),
        x_min=-3.0, x_max=3.0, y_min=-3.0, y_max=3.0,
        z_min=-3.0, z_max=3.0,
        arrow_scale=0.18,
        # A=B=C=1 : champ de Beltrami (∇×V = V) aux lignes de courant
        # chaotiques — l'exemple canonique en dynamique des fluides.
    ),
    _vf3d_preset(
        "Cisaillement simple : V = (y, 0, 0)",
        components=("y", "0", "0"),
        arrow_scale=0.3,
        # div V = 0, ∇×V = (0,0,−1) : rotation cachée dans un
        # écoulement « rectiligne » — contre-intuitif et classique.
    ),
    _vf3d_preset(
        "Point de stagnation : V = (x, y, −2z)",
        components=("x", "y", "-2*z"),
        arrow_scale=0.25,
        # div V = 1 + 1 − 2 = 0 : écoulement incompressible qui étire
        # dans le plan xy et comprime le long de z.
    ),
    _vf3d_preset(
        "Champ de Beltrami plan : V = (cos z, sin z, 0)",
        components=("cos(z)", "sin(z)", "0"),
        x_min=-1.0, x_max=1.0, y_min=-1.0, y_max=1.0,
        z_min=-3.0, z_max=3.0,
        resolution_z=6,
        arrow_scale=0.3,
        # ∇×V = V : la direction tourne avec l'altitude z (hélicité).
    ),
    _vf3d_preset(
        "Compression anisotrope : V = (a·x, b·y, c·z)",
        components=("a*x", "b*y", "c*z"),
        allowed_params=("a", "b", "c"),
        params={"a": 1.0, "b": 0.5, "c": -1.5},
        arrow_scale=0.25,
        # div V = a + b + c : ajuster les trois curseurs pour passer
        # d'une source (somme > 0) à un puits (somme < 0).
    ),
]


def reinstall_vector_field_3d_builtins() -> int:
    """Write every built-in vector-field preset to disk. Returns count."""
    from . import presets

    n = 0
    for preset in BUILTIN_VECTOR_FIELD_3D_PRESETS:
        slug = (BUILTIN_VECTOR_FIELD_3D_FILE_PREFIX
                + presets._slugify(preset["name"]))
        fp = presets._vector_field_3d_presets_dir() / (slug + ".json")
        import json
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_vector_field_3d_builtin_file(path) -> bool:
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_VECTOR_FIELD_3D_FILE_PREFIX)


# Extra curated presets bundled in v5.0.0.
# Stored as full dicts (same schema as user presets); the reinstall_*
# functions write them with the proper _builtin_* prefix on first run,
# so they ship and auto-install on every platform.
# =========================================================================== #
import json as _json

BUILTIN_PRESETS.extend(_json.loads(r'''[{"schema": 1, "name": "Oscillation amortie", "created": "2026-06-13T10:27:23", "formula": {"expr": "exp(-x/4)*sin(4*x)", "allowed_params": [], "derivative_order": 1, "taylor_order": 2}, "range": {"resolution": 256.0, "x_min": -1.0, "x_max": 10.0, "x_0": 0.0, "marker_size": 0.10000000149011612}, "params": {}, "pieces": {"f": {"thickness": 0.009999999776482582, "visible": true, "material_name": ""}, "f'": {"thickness": 0.009999999776482582, "visible": true, "material_name": ""}, "T_1": {"thickness": 0.009999999776482582, "visible": true, "material_name": ""}, "T_2": {"thickness": 0.009999999776482582, "visible": true, "material_name": ""}}, "materials": {"__marker__": ""}, "name_en": "Damped oscillation"}, {"schema": 1, "name": "Sigmoïde logistique", "created": "2026-06-13T10:27:23", "formula": {"expr": "1/(1+exp(-x))", "allowed_params": [], "derivative_order": 1, "taylor_order": 0}, "range": {"resolution": 256.0, "x_min": -6.0, "x_max": 6.0, "x_0": 0.0, "marker_size": 0.10000000149011612}, "params": {}, "pieces": {"f": {"thickness": 0.009999999776482582, "visible": true, "material_name": ""}, "f'": {"thickness": 0.009999999776482582, "visible": true, "material_name": ""}}, "materials": {"__marker__": ""}, "name_en": "Logistic sigmoid"}]'''))
BUILTIN_VECTOR_PRESETS.extend(_json.loads(r'''[{"schema": 1, "kind": "vector", "name": "Spirale conique", "created": "2026-06-13T10:27:23", "formula": {"expr": "t*cos(t)*N.x + t*sin(t)*N.y + t*N.z", "var_name": "t", "allowed_params": []}, "range": {"resolution": 256.0, "t_min": 0.0, "t_max": 6.2831854820251465, "t_0": 1.0}, "params": {}, "trace": {"thickness": 0.019999999552965164, "material_name": ""}, "arrows": {"position": {"visible": true, "material_name": ""}, "vitesse": {"visible": true, "material_name": ""}, "accélération": {"visible": true, "material_name": ""}}, "marker": {}, "name_en": "Conical spiral"}, {"schema": 1, "kind": "vector", "name": "Lissajous 3D", "created": "2026-06-13T10:27:23", "formula": {"expr": "sin(2*t)*N.x + sin(3*t)*N.y + cos(t)*N.z", "var_name": "t", "allowed_params": []}, "range": {"resolution": 256.0, "t_min": 0.0, "t_max": 6.2831854820251465, "t_0": 0.5}, "params": {}, "trace": {"thickness": 0.019999999552965164, "material_name": ""}, "arrows": {"position": {"visible": true, "material_name": ""}, "vitesse": {"visible": true, "material_name": ""}, "accélération": {"visible": true, "material_name": ""}}, "marker": {}, "name_en": "Lissajous 3D"}]'''))
BUILTIN_SURFACE_PRESETS.extend(_json.loads(r'''[{"schema": 1, "kind": "surface", "name": "Ondulation radiale", "created": "2026-06-13T10:27:23", "formula": {"expr": "cos(sqrt(x**2 + y**2))", "x_name": "x", "y_name": "y", "allowed_params": []}, "range": {"resolution_x": 64.0, "resolution_y": 64.0, "x_min": -6.0, "x_max": 6.0, "y_min": -6.0, "y_max": 6.0, "x_0": 0.5, "y_0": 0.5}, "params": {}, "surface": {"material_name": ""}, "marker": {"size": 0.15000000596046448, "material_name": ""}, "tangent": {"visible": true, "size": 1.5, "resolution": 8.0, "material_name": ""}, "name_en": "Radial ripple"}, {"schema": 1, "kind": "surface", "name": "Selle du singe", "created": "2026-06-13T10:27:23", "formula": {"expr": "x**3 - 3*x*y**2", "x_name": "x", "y_name": "y", "allowed_params": []}, "range": {"resolution_x": 64.0, "resolution_y": 64.0, "x_min": -2.0, "x_max": 2.0, "y_min": -2.0, "y_max": 2.0, "x_0": 0.5, "y_0": 0.5}, "params": {}, "surface": {"material_name": ""}, "marker": {"size": 0.15000000596046448, "material_name": ""}, "tangent": {"visible": true, "size": 1.5, "resolution": 8.0, "material_name": ""}, "name_en": "Monkey saddle"}]'''))
BUILTIN_PARAMETRIC_SURFACE_PRESETS.extend(_json.loads(r'''[{"schema": 1, "kind": "parametric_surface", "name": "Hélicoïde", "created": "2026-06-13T10:27:23", "formula": {"components": ["u*cos(v)", "u*sin(v)", "v"], "u_name": "u", "v_name": "v", "allowed_params": []}, "range": {"resolution_u": 64.0, "resolution_v": 64.0, "u_min": 0.0, "u_max": 2.0, "v_min": 0.0, "v_max": 6.2831854820251465, "u_0": 1.0, "v_0": 0.0}, "params": {}, "surface": {"material_name": ""}, "marker": {"size": 0.10000000149011612, "material_name": ""}, "tangent": {"visible": true, "size": 1.0, "resolution": 8.0, "material_name": ""}, "name_en": "Helicoid"}, {"schema": 1, "kind": "parametric_surface", "name": "Tore", "created": "2026-06-13T10:27:23", "formula": {"components": ["(cos(v) + 2)*cos(u)", "(cos(v) + 2)*sin(u)", "sin(v)"], "u_name": "u", "v_name": "v", "allowed_params": []}, "range": {"resolution_u": 64.0, "resolution_v": 64.0, "u_min": 0.0, "u_max": 6.2831854820251465, "v_min": 0.0, "v_max": 6.2831854820251465, "u_0": 0.0, "v_0": 0.0}, "params": {}, "surface": {"material_name": ""}, "marker": {"size": 0.10000000149011612, "material_name": ""}, "tangent": {"visible": true, "size": 1.0, "resolution": 8.0, "material_name": ""}, "name_en": "Torus"}]'''))
BUILTIN_SCALAR_FIELD_3D_PRESETS.extend(_json.loads(r'''[{"schema": 1, "kind": "scalar_field_3d", "name": "Onde plane diagonale", "created": "2026-06-13T10:27:23", "formula": {"expr": "sin(x + y + z)", "x_name": "x", "y_name": "y", "z_name": "z", "allowed_params": []}, "range": {"resolution_x": 5.0, "resolution_y": 5.0, "resolution_z": 5.0, "x_min": -3.0, "x_max": 3.0, "y_min": -3.0, "y_max": 3.0, "z_min": -3.0, "z_max": 3.0, "x_0": 0.0, "y_0": 0.0, "z_0": 0.0, "f_min": -1.0, "f_max": 1.0}, "params": {}, "markers": {"size": 0.03999999910593033, "material_name": "RealFn ScalarField 3D"}, "labels": {"visible": false, "stride": 2.0, "size": 0.07999999821186066, "offset": 0.10000000149011612, "decimals": 2.0, "vertical": false, "max_points": 2000.0, "material_name": "RealFn Gris"}, "basepoint": {"visible": true, "marker_size": 0.10000000149011612, "marker_material_name": "", "label_size": 0.1599999964237213, "label_offset": 0.10000000149011612, "label_material_name": ""}, "frame": {"visible": true, "thickness": 0.009999999776482582, "material_name": "RealFn Gris"}, "axes": {"visible": false, "size": 0.07000000029802322, "decimals": 1.0, "material_name": "RealFn Gris"}, "name_en": "Diagonal plane wave"}, {"schema": 1, "kind": "scalar_field_3d", "name": "Quadrique hyperbolique", "created": "2026-06-13T10:27:23", "formula": {"expr": "x**2 + y**2 - z**2", "x_name": "x", "y_name": "y", "z_name": "z", "allowed_params": []}, "range": {"resolution_x": 5.0, "resolution_y": 5.0, "resolution_z": 5.0, "x_min": -2.0, "x_max": 2.0, "y_min": -2.0, "y_max": 2.0, "z_min": -2.0, "z_max": 2.0, "x_0": 0.5, "y_0": 0.5, "z_0": 0.5, "f_min": -1.0, "f_max": 1.0}, "params": {}, "markers": {"size": 0.03999999910593033, "material_name": "RealFn ScalarField 3D"}, "labels": {"visible": false, "stride": 2.0, "size": 0.07999999821186066, "offset": 0.10000000149011612, "decimals": 2.0, "vertical": false, "max_points": 2000.0, "material_name": "RealFn Gris"}, "basepoint": {"visible": true, "marker_size": 0.10000000149011612, "marker_material_name": "", "label_size": 0.1599999964237213, "label_offset": 0.10000000149011612, "label_material_name": ""}, "frame": {"visible": true, "thickness": 0.009999999776482582, "material_name": "RealFn Gris"}, "axes": {"visible": false, "size": 0.07000000029802322, "decimals": 1.0, "material_name": "RealFn Gris"}, "name_en": "Hyperbolic quadric"}]'''))
# =========================================================================== #
# Built-in vector-bench presets
# =========================================================================== #
# Generated from the single source of truth ``bench_tree.BUILTIN_BENCHES``
# (also used by the one-click "Bancs prêts à l'emploi" buttons), so the
# preset catalogue and the quick-create buttons never drift apart. Each
# row is coloured from the RealFn palette and the parameters default to
# 0.7 so an applied bench already shows its rotation engaged.
BUILTIN_VECTOR_BENCH_FILE_PREFIX = "_builtin_bench_"

_BENCH_PALETTE = ("Bleu", "Vert", "Rouge", "Jaune", "Magenta", "Cyan",
                  "Orange", "Gris")


def _bench_builtin_dict(entry):
    """A bench_tree.BUILTIN_BENCHES entry → preset dict (user-preset schema)."""
    from . import default_materials
    rows = [(str(n), str(e)) for n, e in entry["rows"]]
    params = [s.strip() for s in entry["params"].split(",") if s.strip()]
    slots = {}
    for i, (name, _) in enumerate(rows):
        short = _BENCH_PALETTE[i % len(_BENCH_PALETTE)]
        slots[name] = {"visible": True,
                       "material_name": default_materials.MATERIAL_PREFIX + short}
    return {
        "schema": 1,
        "kind": "vector_bench",
        "name": entry["label"],
        "name_en": entry.get("label_en", entry["label"]),
        "created": "2026-06-14T00:00:00",
        "formula": {"rows": [[n, e] for n, e in rows],
                    "allowed_params": params},
        "params": {p: 0.7 for p in params},
        "slots": slots,
    }


def reinstall_vector_bench_builtins() -> int:
    """Write every built-in vector-bench preset to the user bench dir."""
    from . import presets, bench_tree
    import json
    n = 0
    for entry in bench_tree.BUILTIN_BENCHES:
        preset = _bench_builtin_dict(entry)
        slug = (BUILTIN_VECTOR_BENCH_FILE_PREFIX
                + presets._slugify(preset["name"]))
        fp = presets._vector_bench_presets_dir() / (slug + ".json")
        with fp.open("w", encoding="utf-8") as f:
            json.dump(preset, f, indent=2, ensure_ascii=False)
        n += 1
    return n


def is_vector_bench_builtin_file(path) -> bool:
    from pathlib import Path
    return Path(path).name.startswith(BUILTIN_VECTOR_BENCH_FILE_PREFIX)


BUILTIN_VECTOR_FIELD_3D_PRESETS.extend(_json.loads(r'''[{"schema": 1, "kind": "vector_field_3d", "name": "Puits de potentiel (∇ϕ)", "created": "2026-06-13T10:27:23", "formula": {"mode": "from_potential", "components": ["2*x", "2*y", "2*z"], "potential": "x**2 + y**2 + z**2", "x_name": "x", "y_name": "y", "z_name": "z", "allowed_params": []}, "range": {"resolution_x": 4.0, "resolution_y": 4.0, "resolution_z": 4.0, "x_min": -1.5, "x_max": 1.5, "y_min": -1.5, "y_max": 1.5, "z_min": -1.5, "z_max": 1.5, "x_0": 0.5, "y_0": 0.5, "z_0": 0.5}, "params": {}, "arrow": {"visible": true, "scale": 0.30000001192092896, "material_name": ""}, "marker": {"size": 0.07999999821186066, "material_name": ""}, "base_arrow": {"material_name": ""}, "component_arrow": {"visible": true, "material_name": ""}, "label": {"visible": true, "size": 0.15000000596046448, "offset": 0.20000000298023224, "material_name": ""}, "norm_labels": {"visible": false, "stride": 2.0, "size": 0.07999999821186066, "offset": 0.10000000149011612, "decimals": 2.0, "vertical": false, "max_points": 2000.0, "material_name": "RealFn Gris"}, "frame": {"visible": true, "thickness": 0.009999999776482582, "material_name": "RealFn Gris"}, "axes": {"visible": false, "size": 0.07000000029802322, "decimals": 1.0, "material_name": "RealFn Gris"}, "name_en": "Potential well (∇φ)"}, {"schema": 1, "kind": "vector_field_3d", "name": "Tourbillon ascendant", "created": "2026-06-13T10:27:23", "formula": {"mode": "explicit", "components": ["-y", "x", "0.3"], "potential": "", "x_name": "x", "y_name": "y", "z_name": "z", "allowed_params": []}, "range": {"resolution_x": 4.0, "resolution_y": 4.0, "resolution_z": 4.0, "x_min": -1.5, "x_max": 1.5, "y_min": -1.5, "y_max": 1.5, "z_min": -1.5, "z_max": 1.5, "x_0": 0.5, "y_0": 0.5, "z_0": 0.5}, "params": {}, "arrow": {"visible": true, "scale": 0.30000001192092896, "material_name": ""}, "marker": {"size": 0.07999999821186066, "material_name": ""}, "base_arrow": {"material_name": ""}, "component_arrow": {"visible": true, "material_name": ""}, "label": {"visible": true, "size": 0.15000000596046448, "offset": 0.20000000298023224, "material_name": ""}, "norm_labels": {"visible": false, "stride": 2.0, "size": 0.07999999821186066, "offset": 0.10000000149011612, "decimals": 2.0, "vertical": false, "max_points": 2000.0, "material_name": "RealFn Gris"}, "frame": {"visible": true, "thickness": 0.009999999776482582, "material_name": "RealFn Gris"}, "axes": {"visible": false, "size": 0.07000000029802322, "decimals": 1.0, "material_name": "RealFn Gris"}, "name_en": "Rising vortex"}]'''))
