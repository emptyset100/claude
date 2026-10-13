"""Composition des référentiels non galiléens.

Étant donné :
- la translation O'(t) du repère mobile R' dans R (3 expressions),
- les angles d'Euler (ψ, θ, φ) de R'/R, convention Z-Y-X intrinsèque
  (yaw-pitch-roll), donc « rotation autour de z » = ψ seul,
- la position r'(t) du point M dans R' (3 expressions),

ce module calcule symboliquement avec sympy :
    R(t)         matrice de rotation R'/R
    Ω(t)         vecteur rotation, extrait de [Ω]_× = Ṙ Rᵀ
    O'M, r_a     positions, en coordonnées de R
    v_r, v_e, v_a   composition des vitesses
    a_r, a_e, a_c, a_a   composition des accélérations (Coriolis inclus)

Tout est lambdifié (modules='math') et injecté dans
``bpy.app.driver_namespace`` sous le préfixe ``cmp_``, où les drivers
des sockets internes du wrapper de composition les retrouvent.
"""

import bpy
from mathutils import Vector

try:
    import sympy as sp
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "L'extension Vector Viewer nécessite sympy. Installez-le dans "
        "le Python de Blender :\n"
        "    <BLENDER_PYTHON> -m pip install sympy"
    ) from e

from . import _parse_helpers, modifier_inputs

# Réexports pour rétrocompat avec d'éventuels imports antérieurs.
T = _parse_helpers.T
_SYMPY_LOCALS = _parse_helpers.SYMPY_LOCALS
_parse = _parse_helpers.parse_expr


# Préfixe pour toutes les fonctions injectées dans driver_namespace
# (évite la collision avec celles du Vector Viewer simple : r_num, …).
DNS_PREFIX = "cmp_"


def _scene_dns_suffix(scene):
    """Retourne un suffixe d'identifiant Python dérivé du nom de la
    scène. Permet à plusieurs scènes de coexister avec leurs propres
    fonctions dans ``bpy.app.driver_namespace`` (les driver namespaces
    sont globaux à Blender, pas par scène).

    "Scene"        → "_scene"
    "Compare A"    → "_compare_a"
    "Scène 1"      → "_scene_1"   (slug ASCII)
    """
    import re
    import unicodedata
    if scene is None:
        return ""
    name = scene.name
    # ASCII-fold (NFKD) pour gérer les accents et caractères spéciaux.
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = ''.join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r'[^A-Za-z0-9]+', '_', ascii_name).strip('_').lower()
    return ('_' + slug) if slug else ""


def _dns_key(scene, key):
    """Préfixe complet pour la clé ``key`` dans le namespace, scoped
    à la scène ``scene``. ``cmp_O_p_scene`` par exemple."""
    return DNS_PREFIX + key + _scene_dns_suffix(scene)

# Liste des clés produites par build_composition()
DNS_KEYS = (
    'O_p', 'v_O', 'a_O',
    'OpM', 'r_a',
    'v_r', 'v_e', 'v_a',
    'a_r', 'a_e', 'a_c', 'a_a',
    'Omega',
    # Colonnes de R(t) — pour les axes du trièdre R'
    'Rcx', 'Rcy', 'Rcz',
)


def _Rz(a):
    return sp.Matrix([[sp.cos(a), -sp.sin(a), 0],
                      [sp.sin(a),  sp.cos(a), 0],
                      [0,          0,         1]])


def _Ry(a):
    return sp.Matrix([[ sp.cos(a), 0, sp.sin(a)],
                      [ 0,         1, 0        ],
                      [-sp.sin(a), 0, sp.cos(a)]])


def _Rx(a):
    return sp.Matrix([[1, 0,          0        ],
                      [0, sp.cos(a), -sp.sin(a)],
                      [0, sp.sin(a),  sp.cos(a)]])


def _cross(u, v):
    """Produit vectoriel symbolique de deux 3×1 sympy.Matrix."""
    return sp.Matrix([u[1]*v[2] - u[2]*v[1],
                      u[2]*v[0] - u[0]*v[2],
                      u[0]*v[1] - u[1]*v[0]])


def _wrap_lambda(M):
    """Transforme une 3×1 sympy.Matrix en fonction t -> mathutils.Vector."""
    fns = (sp.lambdify(T, M[0], 'math'),
           sp.lambdify(T, M[1], 'math'),
           sp.lambdify(T, M[2], 'math'))
    def f(tv):
        return Vector((float(fns[0](tv)),
                       float(fns[1](tv)),
                       float(fns[2](tv))))
    return f


# ----------------------------------------------------------------------------
# Cœur : compile r/v/a (relative, entraînement, absolue, Coriolis)
# ----------------------------------------------------------------------------

def build_composition(Op_text, euler_text, rp_text):
    """Compile et lambdifie tout le jeu de fonctions pour la composition.

    Args:
        Op_text:    triplet (X0, Y0, Z0) — translation de O'.
        euler_text: triplet (ψ, θ, φ) — Euler Z-Y-X intrinsèque.
        rp_text:    triplet (x', y', z') — M dans R'.

    Returns:
        dict[str, callable] — voir DNS_KEYS pour les clés.
    """
    X0, Y0, Z0      = (_parse(s) for s in Op_text)
    psi, theta, phi = (_parse(s) for s in euler_text)
    xp, yp, zp      = (_parse(s) for s in rp_text)

    Op = sp.Matrix([X0, Y0, Z0])
    rp = sp.Matrix([xp, yp, zp])

    # R(t) = Rz(ψ) · Ry(θ) · Rx(φ)
    R = _Rz(psi) * _Ry(theta) * _Rx(phi)

    OpM = R * rp
    ra  = Op + OpM

    # Dérivées temporelles
    Op_d, Op_dd = Op.diff(T), Op.diff(T, 2)
    rp_d, rp_dd = rp.diff(T), rp.diff(T, 2)
    R_d         = R.diff(T)

    # Vitesse / accélération relatives, exprimées dans R
    vr = R * rp_d
    ar = R * rp_dd

    # Vecteur rotation : [Ω]_× = Ṙ Rᵀ (en coordonnées de R)
    Skew    = sp.simplify(R_d * R.T)
    Omega   = sp.Matrix([Skew[2, 1], Skew[0, 2], Skew[1, 0]])
    Omega_d = Omega.diff(T)

    # Composition des vitesses
    ve = Op_d + _cross(Omega, OpM)
    va = vr + ve

    # Composition des accélérations (Coriolis inclus)
    ae = Op_dd + _cross(Omega_d, OpM) + _cross(Omega, _cross(Omega, OpM))
    ac = 2 * _cross(Omega, vr)
    aa = ar + ae + ac

    # Colonnes de R(t) : axes du trièdre R' exprimés dans la base de R
    Rcx = R * sp.Matrix([1, 0, 0])
    Rcy = R * sp.Matrix([0, 1, 0])
    Rcz = R * sp.Matrix([0, 0, 1])

    return {
        'O_p':   _wrap_lambda(Op),
        'v_O':   _wrap_lambda(Op_d),
        'a_O':   _wrap_lambda(Op_dd),
        'OpM':   _wrap_lambda(OpM),
        'r_a':   _wrap_lambda(ra),
        'v_r':   _wrap_lambda(vr),
        'v_e':   _wrap_lambda(ve),
        'v_a':   _wrap_lambda(va),
        'a_r':   _wrap_lambda(ar),
        'a_e':   _wrap_lambda(ae),
        'a_c':   _wrap_lambda(ac),
        'a_a':   _wrap_lambda(aa),
        'Omega': _wrap_lambda(Omega),
        'Rcx':   _wrap_lambda(Rcx),
        'Rcy':   _wrap_lambda(Rcy),
        'Rcz':   _wrap_lambda(Rcz),
    }


# ----------------------------------------------------------------------------
# Driver namespace
# ----------------------------------------------------------------------------

def refresh_driver_namespace(props, *, scene=None):
    """Compile depuis ``props`` et place les fonctions dans
    ``bpy.app.driver_namespace`` avec préfixe ``cmp_…_<scene_slug>``.

    Le suffixe scène permet à plusieurs scènes de coexister sans que
    leurs viewers Composition ne s'écrasent les uns les autres dans le
    namespace global des drivers."""
    fns = build_composition(
        (props.X0_expr, props.Y0_expr, props.Z0_expr),
        (props.psi_expr, props.theta_expr, props.phi_expr),
        (props.xp_expr, props.yp_expr, props.zp_expr),
    )
    suffix = _scene_dns_suffix(scene)
    for key, fn in fns.items():
        bpy.app.driver_namespace[DNS_PREFIX + key + suffix] = fn


def clear_driver_namespace(*, scene=None):
    """Retire les fonctions composition de ``bpy.app.driver_namespace``
    pour la scène donnée (ou pour le suffixe vide si ``scene`` est None,
    pour rétrocompat)."""
    suffix = _scene_dns_suffix(scene)
    for k in DNS_KEYS:
        bpy.app.driver_namespace.pop(DNS_PREFIX + k + suffix, None)


# ----------------------------------------------------------------------------
# Attachement des drivers sur les sockets internes du wrapper
# ----------------------------------------------------------------------------

# Noms des nodes dans le wrapper de composition (cf. composition_nodegroups.py)
ARROW_NODE_NAMES = (
    "OOp", "OpM", "OM",           # position context
    "vr",  "ve",  "va",           # composition des vitesses
    "ar",  "ae",  "ac",  "aa",    # composition des accélérations
    "Omega",                      # vecteur rotation instantanée
)

# Noms des axes du trièdre R' (le trièdre R est statique, défini au build)
RP_TRIPOD_NODE_NAMES = ("Rp_x", "Rp_y", "Rp_z")


def _socket_identifier(wrapper_tree, socket_name):
    """Identifiant interne stable d'un socket d'interface, pour
    référence dans les expressions de driver. ``None`` si introuvable."""
    for item in wrapper_tree.interface.items_tree:
        if (getattr(item, 'in_out', None) == 'INPUT'
                and getattr(item, 'name', None) == socket_name):
            return item.identifier
    return None


def _add_modifier_var(driver, var_name, host_obj, modifier_name, socket_id):
    """Ajoute à ``driver`` une variable ``var_name`` lisant
    ``host_obj.modifiers[modifier_name][socket_id]``."""
    var = driver.variables.new()
    var.name = var_name
    var.type = 'SINGLE_PROP'
    target = var.targets[0]
    target.id_type = 'OBJECT'
    target.id = host_obj
    mod = host_obj.modifiers.get(modifier_name) if host_obj else None
    if mod is not None:
        # Blender 5.2 : ``…properties.inputs.Socket_N.value`` ; avant :
        # ``…["Socket_N"]`` (voir modifier_inputs).
        target.data_path = modifier_inputs.input_data_path(mod, socket_id)
    else:
        target.data_path = f'modifiers["{modifier_name}"]["{socket_id}"]'


def attach_socket_drivers(wrapper_tree, *, fps, t0, host_name,
                          modifier_name, scene=None,
                          scale_v=1.0, scale_a=1.0,
                          scale_omega=1.0, axis_length=1.0):
    """Écrit les drivers Python sur les sockets ``inputs[0]`` (origine)
    et ``inputs[1]`` (extrémité) des nodes-flèches du wrapper.

    Les échelles ``scale_v``, ``scale_a`` et ``scale_omega`` sont lues en
    LIVE via des variables de driver (``sv``, ``sa``, ``so``) pointant
    sur les sockets exposés du modifier — modifier les sliders
    « Échelle v/a/Ω » dans le panneau actualise les flèches sans rebuild.

    Câblage :
    - OO'  : 0 → O'(t)
    - O'M  : O'(t) → r_a(t)
    - OM   : 0 → r_a(t)   (= OO' + O'M, ferme le triangle des positions)
    - 7 vecteurs cinématiques (vr, ve, va, ar, ae, ac, aa) ancrés à M(t)
    - Ω    : O'(t) → O'(t) + so·Ω(t) (axe instantané de R'/R)
    - 3 axes du trièdre R' (Rp_x, Rp_y, Rp_z) : O'(t) → O'(t) + L·R(t)·ê_i

    Le trièdre R (axes ê_x, ê_y, ê_z à l'origine) est statique et géré
    par ``composition_nodegroups.composition_wrapper_node_group``.

    Args:
        host_name, modifier_name: nécessaires pour cibler les sockets
            du modifier dans les variables de driver.
        scene: scène courante, utilisée pour suffixer les noms de
            fonctions dans ``driver_namespace`` (permet à plusieurs
            scènes de coexister sans collision).
        scale_v, scale_a, scale_omega: valeurs initiales écrites dans
            le modifier au moment du build (le slider du panneau les
            mettra à jour ensuite en live).
        axis_length: utilisé en CONSTANTE LITTÉRALE pour le trièdre R'.
    """
    time = f"(frame/{fps} + {t0})"
    # Préfixe complet incluant le suffixe scène : les drivers
    # référenceront ``cmp_O_p_<scene>(...)`` qui sera trouvé dans le
    # namespace populé par ``refresh_driver_namespace(scene=scene)``.
    P    = DNS_PREFIX
    suffix = _scene_dns_suffix(scene)
    L    = float(axis_length)

    # ── Pré-écriture des valeurs initiales sur le modifier ──────────
    sv_id = _socket_identifier(wrapper_tree, "Échelle v")
    sa_id = _socket_identifier(wrapper_tree, "Échelle a")
    so_id = _socket_identifier(wrapper_tree, "Échelle Ω")
    if not (sv_id and sa_id and so_id):
        raise RuntimeError(
            "Sockets d'échelle introuvables sur le wrapper composition — "
            "le wrapper doit avoir été reconstruit avec la version "
            "courante de composition_wrapper_node_group."
        )
    host_obj = bpy.data.objects.get(host_name)
    if host_obj is not None and modifier_name in host_obj.modifiers:
        mod = host_obj.modifiers[modifier_name]
        # No-op si le modifier n'expose pas encore ces sockets.
        modifier_inputs.set_value(mod, sv_id, float(scale_v))
        modifier_inputs.set_value(mod, sa_id, float(scale_a))
        modifier_inputs.set_value(mod, so_id, float(scale_omega))

    # ── Helpers d'expression de driver ──────────────────────────────
    def f(name):
        """Composantes [a=0,1,2] de la fonction préfixée ``name``."""
        return [f"{P}{name}{suffix}({time})[{a}]" for a in range(3)]

    def add(orig, ext):
        return [f"({orig[a]}) + ({ext[a]})" for a in range(3)]

    def scaled(name, var):
        """Composantes ``var * func(time)``, où ``var`` est un nom de
        variable de driver (``sv``, ``sa``, ``so``) ou un littéral."""
        return [f"{var}*({P}{name}{suffix}({time})[{a}])" for a in range(3)]

    # Plans : (node_name, sock_idx, exprs, set_of_vars_needed)
    # set_of_vars_needed ⊆ {"sv", "sa", "so"} indique quelles variables
    # de driver doivent être ajoutées (Blender warne si on déclare des
    # variables non utilisées).
    plans = [
        # Positions : pas d'échelle
        ("OOp", 0, ["0", "0", "0"], set()),
        ("OOp", 1, f("O_p"),         set()),
        ("OpM", 0, f("O_p"),         set()),
        ("OpM", 1, f("r_a"),         set()),
        ("OM",  0, ["0", "0", "0"], set()),
        ("OM",  1, f("r_a"),         set()),

        # Vitesses : sv
        ("vr",  0, f("r_a"),                                 set()),
        ("vr",  1, add(f("r_a"), scaled("v_r", "sv")),     {"sv"}),
        ("ve",  0, f("r_a"),                                 set()),
        ("ve",  1, add(f("r_a"), scaled("v_e", "sv")),     {"sv"}),
        ("va",  0, f("r_a"),                                 set()),
        ("va",  1, add(f("r_a"), scaled("v_a", "sv")),     {"sv"}),

        # Accélérations : sa
        ("ar",  0, f("r_a"),                                 set()),
        ("ar",  1, add(f("r_a"), scaled("a_r", "sa")),     {"sa"}),
        ("ae",  0, f("r_a"),                                 set()),
        ("ae",  1, add(f("r_a"), scaled("a_e", "sa")),     {"sa"}),
        ("ac",  0, f("r_a"),                                 set()),
        ("ac",  1, add(f("r_a"), scaled("a_c", "sa")),     {"sa"}),
        ("aa",  0, f("r_a"),                                 set()),
        ("aa",  1, add(f("r_a"), scaled("a_a", "sa")),     {"sa"}),

        # Rotation instantanée : so
        ("Omega", 0, f("O_p"),                               set()),
        ("Omega", 1, add(f("O_p"), scaled("Omega", "so")), {"so"}),

        # Trièdre R' : axis_length comme littéral (statique)
        ("Rp_x", 0, f("O_p"),                                set()),
        ("Rp_x", 1, add(f("O_p"), scaled("Rcx", str(L))),  set()),
        ("Rp_y", 0, f("O_p"),                                set()),
        ("Rp_y", 1, add(f("O_p"), scaled("Rcy", str(L))),  set()),
        ("Rp_z", 0, f("O_p"),                                set()),
        ("Rp_z", 1, add(f("O_p"), scaled("Rcz", str(L))),  set()),
    ]

    var_to_socket = {"sv": sv_id, "sa": sa_id, "so": so_id}

    for node_name, sock_idx, exprs, vars_needed in plans:
        if node_name not in wrapper_tree.nodes:
            print(f"[VectorComp] Node introuvable : {node_name}")
            continue
        sock = wrapper_tree.nodes[node_name].inputs[sock_idx]

        try:
            sock.driver_remove("default_value")
        except Exception:
            pass

        fcurves = sock.driver_add("default_value")
        for fc, expr in zip(fcurves, exprs):
            drv = fc.driver
            drv.type = 'SCRIPTED'
            drv.expression = expr
            for var_name in vars_needed:
                _add_modifier_var(drv, var_name, host_obj, modifier_name,
                                   var_to_socket[var_name])
