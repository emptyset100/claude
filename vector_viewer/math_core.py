"""Couche math : parse les expressions sympy fournies par l'utilisateur
et produit les fonctions numériques r_num/v_num/a_num utilisées par les
drivers."""

from mathutils import Vector

try:
    import sympy as sp
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "L'extension Vector Viewer nécessite sympy. Installez-le dans "
        "le Python de Blender :\n"
        "    <BLENDER_PYTHON> -m pip install sympy"
    ) from e

from . import _parse_helpers

# Réexports pour rétrocompat (anciens imports). Les modules récents
# devraient importer depuis ``_parse_helpers`` directement.
T = _parse_helpers.T
_SYMPY_LOCALS = _parse_helpers.SYMPY_LOCALS
parse_expr = _parse_helpers.parse_expr


def build_kinematics(x_text, y_text, z_text):
    """Compile x(t), y(t), z(t) puis dérive vitesse et accélération.

    Retourne ``(r_num, v_num, a_num)`` où chaque fonction prend un float
    et retourne un ``mathutils.Vector``."""
    rx = parse_expr(x_text)
    ry = parse_expr(y_text)
    rz = parse_expr(z_text)

    # Dérivées (sp.diff fonctionne sur expressions ne contenant que t)
    vx, vy, vz = sp.diff(rx, T), sp.diff(ry, T), sp.diff(rz, T)
    ax, ay, az = sp.diff(vx, T), sp.diff(vy, T), sp.diff(vz, T)

    # Lambdification (modules='math' → fonctions Python pures, dépendant
    # uniquement du module math standard, donc sûres pour les drivers)
    r_fns = (sp.lambdify(T, rx, 'math'),
             sp.lambdify(T, ry, 'math'),
             sp.lambdify(T, rz, 'math'))
    v_fns = (sp.lambdify(T, vx, 'math'),
             sp.lambdify(T, vy, 'math'),
             sp.lambdify(T, vz, 'math'))
    a_fns = (sp.lambdify(T, ax, 'math'),
             sp.lambdify(T, ay, 'math'),
             sp.lambdify(T, az, 'math'))

    def _wrap(fns):
        fx, fy, fz = fns
        def _to_float(v, axis):
            """Convertit ``v`` en float, en gérant le cas où lambdify
            retourne malgré tout une expression sympy (peut arriver pour
            des constantes symboliques laissées non-évaluées, ou des cas
            limites comme oo / nan). Donne une erreur lisible plutôt que
            le ``Cannot convert expression to float`` brut de sympy."""
            try:
                return float(v)
            except TypeError:
                # Tente une évaluation numérique forcée
                try:
                    return float(sp.N(v))
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f"Composante {axis} non numérique au temps demandé "
                        f"(valeur : {v!r}). Vérifiez l'expression."
                    ) from e
        def f(tv):
            return Vector((_to_float(fx(tv), 'x'),
                           _to_float(fy(tv), 'y'),
                           _to_float(fz(tv), 'z')))
        return f

    return _wrap(r_fns), _wrap(v_fns), _wrap(a_fns)


# Note : la composition des mouvements (référentiels non galiléens) est
# traitée dans `composition.py`, qui utilise une paramétrisation par
# angles d'Euler Z-Y-X.
