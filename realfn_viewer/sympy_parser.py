"""
SymPy parsing with a strict safety filter.

``sympy.parsing.sympy_parser.parse_expr`` ultimately calls ``eval`` on
the user's string. Passing untrusted input directly is therefore
equivalent to running ``eval(user_input)`` — naïve probes confirm that
``__import__('os').system(...)`` executes successfully.

Two complementary layers of defence here:

1. **AST whitelist** (the load-bearing one): ``_validate_ast`` walks
   the Python AST of the input *before* SymPy sees it, accepting only
   arithmetic-expression node types plus a fixed set of mathematical
   function calls. Any unknown node type, any identifier starting
   with ``_``, any indirect call (``foo.bar()``), or any keyword
   argument is rejected.

2. **Sandboxed eval namespace**: even if a malicious construct slipped
   past the AST check, ``parse_expr`` is invoked with
   ``global_dict={"__builtins__": {}}`` so that ``__import__``,
   ``open``, ``exec``, … are simply not in scope.

The two layers are independently sufficient against every concrete
attack I've tried; we keep both because a future refactor of one
shouldn't silently regress the other.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


# --------------------------------------------------------------------------- #
# Lazy SymPy import
# --------------------------------------------------------------------------- #
# SymPy ships as bundled wheels under ``wheels/``. Blender's extension
# loader unpacks them and prepends sys.path automatically when the
# extension is enabled — we just need to *use* the resulting import.
# We import lazily so the addon load doesn't pay the SymPy cost up
# front, and so that running this module under a stub bpy (for tests)
# doesn't fail on a missing SymPy.
_SYMPY = [None]


def _sympy():
    if _SYMPY[0] is None:
        try:
            import sympy as sp  # noqa: F401
        except ImportError:
            # Outside Blender: fall back to importing from the bundled
            # wheels directly so unit tests can exercise the module.
            here = Path(__file__).parent / "wheels"
            for whl in sorted(here.glob("*.whl")):
                if str(whl) not in sys.path:
                    sys.path.insert(0, str(whl))
            import sympy as sp  # noqa: F401
        _SYMPY[0] = sp
    return _SYMPY[0]


# --------------------------------------------------------------------------- #
# AST whitelist
# --------------------------------------------------------------------------- #
# Functions the user is allowed to call. Anything else (open, exec,
# __import__, getattr, …) raises a ValueError during validation.
_ALLOWED_FUNCTIONS = frozenset({
    "sin", "cos", "tan",
    "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh",
    "asinh", "acosh", "atanh",
    "exp", "log", "ln",
    "sqrt", "Abs", "abs", "sign",
    "Heaviside",  # useful for piecewise-flat functions
    # Rounding / modulo / extrema — compiled to the matching Math-node
    # operations (FLOOR, CEIL, FRACT, FLOORED_MODULO, MINIMUM, MAXIMUM).
    "floor", "ceil", "ceiling", "frac", "Mod", "mod",
    "Min", "Max", "min", "max",
})

# Vector / Mathutils helper functions. These take numeric tuples (and/or
# scalars) and return either a scalar or a tuple. They are added to the
# *call* whitelist so the AST validator lets ``cross((1,0,0),(0,1,0))``
# through — but note that **no new AST node type is enabled**: tuples
# (``ast.Tuple``/``ast.List``) were already allowed, and these are still
# plain ``f(...)`` calls with no attribute access, subscript, or method
# call. The security posture (AST whitelist + sandboxed ``parse_expr``)
# is therefore unchanged.
#
# Numerics: when every argument is a constant tuple, the geometric
# helpers evaluate through Blender's **mathutils** API (``Vector.dot``,
# ``.cross``, ``.length``, ``.normalized``, ``.angle``, ``.project``,
# ``Quaternion`` axis-angle, ``Vector.slerp``) so results match Blender's
# own conventions. When an argument carries a free symbol (``x``, ``t``,
# ``u``, ``v``…) the symbol-friendly helpers fall back to a pure-SymPy
# expression so the formula still compiles to a live Geometry-Nodes
# subgraph. ``rotate`` / ``slerp`` are mathutils-only (constant args).
_VECTOR_HELPER_FUNCTIONS = frozenset({
    "vec",
    "dot", "cross", "vlen", "norm", "vdist", "vangle", "angle",
    "normalize", "unit", "proj", "comp", "lerp", "clamp",
    "rot_x", "rot_y", "rot_z", "rotate", "slerp",
    # Matrices & Euler. NB: sympy ``Matrix`` uses ``*`` for the matrix
    # product (already an allowed AST operator), so ``eul(...) * v`` and
    # ``A * B`` work without enabling the ``@`` (MatMult) node — the
    # security posture is unchanged.
    "mat", "eye", "identity", "diag", "scalemat",
    "rmx", "rmy", "rmz", "rotmat", "eul",
    "eul_xyz", "eul_xzy", "eul_yxz", "eul_yzx", "eul_zxy", "eul_zyx",
    "transpose", "det", "inv", "trace",
    # Quaternions (w, x, y, z) — mathutils convention. Symbolic-capable,
    # including a symbolic slerp.
    "quat", "quat_axis", "qaxis", "qmul", "qconj", "qnorm",
    "qnormalize", "qunit", "qrotate", "qmat", "quat_to_mat", "qslerp",
})

_ALLOWED_FUNCTIONS = _ALLOWED_FUNCTIONS | _VECTOR_HELPER_FUNCTIONS

# AST node types accepted anywhere in the expression. This excludes
# Attribute (no ``foo.bar``), Subscript (no ``foo[0]``), Lambda,
# generator/list/dict/set comprehensions, and everything else that
# could reach outside the arithmetic sandbox.
_ALLOWED_NODES = (
    ast.Expression, ast.Load,
    ast.Constant,
    ast.Name,
    ast.BinOp, ast.UnaryOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.FloorDiv,
    ast.USub, ast.UAdd,
    ast.Call,
    ast.Tuple, ast.List,
)

# Vector-mode extension: when ``allow_frame_attr=True``, ``_validate_ast``
# accepts ``<Name>.x|y|z`` syntax used by :mod:`sympy.physics.vector` to
# reference the basis vectors of a reference frame (typically ``N.x``).
# This is the *only* attribute access we let through — everything else
# (``foo.bar``, dotted method calls, dunder lookups) stays banned.
_FRAME_AXIS_ATTRS = frozenset({"x", "y", "z"})


def _validate_ast(source: str, *,
                   allow_frame_attr: bool = False,
                   frame_name: str = "N") -> None:
    """Raise :class:`ValueError` if ``source`` contains anything outside
    a safe arithmetic-expression subset.

    When ``allow_frame_attr`` is True, accesses of the form
    ``<frame_name>.x``, ``<frame_name>.y``, ``<frame_name>.z`` are
    additionally allowed — used for the vector-function parser that
    needs to see ``N.x`` etc. in the user's input.
    """
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Syntaxe invalide : {e.msg}") from None

    # Build the expanded allowed-nodes tuple inline so the common path
    # (scalar mode) pays nothing for the vector hook.
    allowed_nodes = _ALLOWED_NODES
    if allow_frame_attr:
        allowed_nodes = _ALLOWED_NODES + (ast.Attribute,)

    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise ValueError(
                f"Construction interdite : {type(node).__name__}"
            )
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise ValueError(
                    f"Identifiant interdit : {node.id!r}"
                )
        elif isinstance(node, ast.Attribute):
            # We're in vector mode (otherwise the isinstance above
            # would have failed). The *only* allowed form is
            # ``<frame_name>.<axis>`` where axis ∈ {x, y, z}.
            if not (isinstance(node.value, ast.Name)
                    and node.value.id == frame_name
                    and node.attr in _FRAME_AXIS_ATTRS):
                raise ValueError(
                    f"Accès d'attribut interdit : seuls "
                    f"{frame_name}.x, {frame_name}.y, {frame_name}.z "
                    f"sont autorisés ({type(node.value).__name__}."
                    f"{node.attr} rejeté)"
                )
        elif isinstance(node, ast.Call):
            if node.keywords:
                raise ValueError(
                    "Arguments nommés non autorisés"
                )
            if not isinstance(node.func, ast.Name):
                raise ValueError(
                    "Seuls les appels de la forme f(...) sont autorisés"
                )
            if node.func.id not in _ALLOWED_FUNCTIONS:
                raise ValueError(
                    f"Fonction non autorisée : {node.func.id!r}. "
                    f"Autorisées : {', '.join(sorted(_ALLOWED_FUNCTIONS))}"
                )
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float, complex)):
                raise ValueError(
                    f"Littéral non numérique interdit : "
                    f"{type(node.value).__name__}"
                )


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Vector / Mathutils helpers
# --------------------------------------------------------------------------- #
# Built once and cached. Every helper accepts SymPy / Python numbers and
# returns SymPy objects (scalars) or Python tuples of SymPy objects
# (vectors), so they compose: ``vlen(cross(a, b))`` works, and
# ``comp(v, i)`` bridges a vector result back to a scalar usable in a
# normal ``f(x)`` formula without needing subscript syntax.
_HELPERS = [None]


def _vector_helpers() -> dict:
    if _HELPERS[0] is not None:
        return _HELPERS[0]

    sp = _sympy()
    try:
        import mathutils as _mu  # Blender-only; absent in bare unit tests.
    except Exception:
        _mu = None

    def _is_vec(a):
        # sympy Matrix iterates via __getitem__ (no __iter__ attribute),
        # so test MatrixBase explicitly.
        if isinstance(a, (tuple, list, sp.MatrixBase)):
            return True
        return (hasattr(a, "__iter__")
                and not isinstance(a, (str, bytes))
                and not isinstance(a, sp.Expr))

    def _vec(a):
        """Coerce ``a`` to a non-empty list of SymPy scalar expressions."""
        if not _is_vec(a):
            raise ValueError(
                "argument vectoriel attendu, par ex. (1, 2, 3)"
            )
        comps = [sp.sympify(e) for e in a]
        if not comps:
            raise ValueError("vecteur vide")
        return comps

    def _scalar(e):
        v = sp.sympify(e)
        if _is_vec(v):
            raise ValueError("scalaire attendu, vecteur reçu")
        return v

    def _const(e):
        """Return ``float(e)`` or raise if ``e`` is not constant."""
        v = sp.sympify(e)
        if getattr(v, "free_symbols", set()):
            raise ValueError("argument constant requis (aucune variable libre)")
        return float(v)

    def _mu_vec(comps):
        """mathutils.Vector of ``comps`` iff all constant & mathutils present,
        else ``None`` (→ caller uses the SymPy path)."""
        if _mu is None:
            return None
        try:
            vals = [float(c) for c in comps]
        except (TypeError, ValueError):
            return None
        return _mu.Vector(vals)

    def _M(seq):
        """Pack a sequence of scalars into a column ``sympy.Matrix``.

        Vector-valued helpers return a ``Matrix`` (not a Python tuple) so
        that ``+``, ``-`` and scalar ``*`` compose naturally inside an
        expression (``a + cross(a, b)``, ``2*a``) — Python tuples would
        concatenate/repeat instead. ``Matrix`` is still iterable, so
        ``comp``/``vlen``/``dot`` consume it transparently, and it is not
        a ``sympy.Expr`` so the scalar-field guard still rejects a bare
        vector result."""
        return sp.Matrix([sp.sympify(s) for s in seq])

    def vec(*comps):
        """Explicit vector constructor: ``vec(1, 0, 0)`` or ``vec(x, y, z)``.
        2 components are accepted (z defaults to 0)."""
        if len(comps) == 1 and _is_vec(comps[0]):
            comps = tuple(comps[0])
        if len(comps) == 2:
            comps = comps + (sp.Integer(0),)
        if len(comps) != 3:
            raise ValueError("vec : 2 ou 3 composantes attendues")
        return _M(comps)

    # ---- scalar-valued -----------------------------------------------------
    def dot(a, b):
        va, vb = _vec(a), _vec(b)
        if len(va) != len(vb):
            raise ValueError("dot : dimensions différentes")
        ma, mb = _mu_vec(va), _mu_vec(vb)
        if ma is not None and mb is not None:
            return sp.Float(ma.dot(mb))
        return sum((x * y for x, y in zip(va, vb)), sp.Integer(0))

    def vlen(a):
        va = _vec(a)
        m = _mu_vec(va)
        if m is not None:
            return sp.Float(m.length)
        return sp.sqrt(sum((x * x for x in va), sp.Integer(0)))
    norm = vlen

    def vdist(a, b):
        va, vb = _vec(a), _vec(b)
        if len(va) != len(vb):
            raise ValueError("vdist : dimensions différentes")
        ma, mb = _mu_vec(va), _mu_vec(vb)
        if ma is not None and mb is not None:
            return sp.Float((ma - mb).length)
        return sp.sqrt(sum(((x - y) ** 2 for x, y in zip(va, vb)), sp.Integer(0)))

    def vangle(a, b):
        va, vb = _vec(a), _vec(b)
        ma, mb = _mu_vec(va), _mu_vec(vb)
        if ma is not None and mb is not None:
            return sp.Float(ma.angle(mb))
        return sp.acos(dot(va, vb) / (vlen(va) * vlen(vb)))
    angle = vangle

    def comp(a, i):
        va = _vec(a)
        idx = int(_const(i))
        try:
            return va[idx]
        except IndexError:
            raise ValueError(
                f"comp : indice {idx} hors limites (vecteur de "
                f"dimension {len(va)})"
            ) from None

    def clamp(v, lo, hi):
        return sp.Min(sp.Max(_scalar(v), _scalar(lo)), _scalar(hi))

    # ---- vector-valued (tuple out) ----------------------------------------
    def cross(a, b):
        va, vb = _vec(a), _vec(b)
        if len(va) != 3 or len(vb) != 3:
            raise ValueError("cross : deux vecteurs 3D requis")
        ma, mb = _mu_vec(va), _mu_vec(vb)
        if ma is not None and mb is not None:
            return _M(sp.Float(c) for c in ma.cross(mb))
        return _M((va[1] * vb[2] - va[2] * vb[1],
                   va[2] * vb[0] - va[0] * vb[2],
                   va[0] * vb[1] - va[1] * vb[0]))

    def normalize(a):
        va = _vec(a)
        m = _mu_vec(va)
        if m is not None:
            return _M(sp.Float(c) for c in m.normalized())
        n = vlen(va)
        return _M(x / n for x in va)
    unit = normalize

    def proj(a, b):
        va, vb = _vec(a), _vec(b)
        ma, mb = _mu_vec(va), _mu_vec(vb)
        if ma is not None and mb is not None:
            return _M(sp.Float(c) for c in ma.project(mb))
        s = dot(va, vb) / dot(vb, vb)
        return _M(s * y for y in vb)

    def lerp(a, b, t):
        ts = _scalar(t)
        if _is_vec(a) or _is_vec(b):
            va, vb = _vec(a), _vec(b)
            if len(va) != len(vb):
                raise ValueError("lerp : dimensions différentes")
            return _M(x + (y - x) * ts for x, y in zip(va, vb))
        sa, sb = _scalar(a), _scalar(b)
        return sa + (sb - sa) * ts

    # ---- symbolic-capable axis rotations (radians, right-handed) ----------
    def _vec3(a):
        va = _vec(a)
        if len(va) != 3:
            raise ValueError("vecteur 3D requis")
        return va

    def rot_x(a, ang):
        x, y, z = _vec3(a)
        c, s = sp.cos(_scalar(ang)), sp.sin(_scalar(ang))
        return _M((x, y * c - z * s, y * s + z * c))

    def rot_y(a, ang):
        x, y, z = _vec3(a)
        c, s = sp.cos(_scalar(ang)), sp.sin(_scalar(ang))
        return _M((x * c + z * s, y, -x * s + z * c))

    def rot_z(a, ang):
        x, y, z = _vec3(a)
        c, s = sp.cos(_scalar(ang)), sp.sin(_scalar(ang))
        return _M((x * c - y * s, x * s + y * c, z))

    def rotate(a, axis, ang):
        """Rotate vector ``a`` around ``axis`` by ``ang`` (radians).

        Symbolic-capable via Rodrigues' formula, so the angle can be a
        live parameter — this is what makes the rotation explorer work.
        When every argument is constant *and* mathutils is available we
        take the fast numeric path (``Quaternion`` axis-angle) for
        Blender-consistent floats."""
        va, ax = _vec3(a), _vec3(axis)
        th = _scalar(ang)
        mv, mx = _mu_vec(va), _mu_vec(ax)
        if (mv is not None and mx is not None
                and not getattr(th, "free_symbols", set())):
            q = _mu.Quaternion(mx, float(th))
            r = mv.copy()
            r.rotate(q)
            return _M(sp.Float(c) for c in r)
        # Rodrigues: v·cosθ + (k×v)·sinθ + k·(k·v)·(1−cosθ),  k = axis/‖axis‖
        n = sp.sqrt(sum((e * e for e in ax), sp.Integer(0)))
        k = [e / n for e in ax]
        kxv = (k[1] * va[2] - k[2] * va[1],
               k[2] * va[0] - k[0] * va[2],
               k[0] * va[1] - k[1] * va[0])
        kdv = sum((ki * vi for ki, vi in zip(k, va)), sp.Integer(0))
        c, s = sp.cos(th), sp.sin(th)
        return _M(va[i] * c + kxv[i] * s + k[i] * kdv * (1 - c)
                  for i in range(3))

    # ---- mathutils-only (constant args) -----------------------------------
    def slerp(a, b, t):
        if _mu is None:
            raise ValueError("slerp : mathutils indisponible hors de Blender")
        v1 = _mu.Vector([_const(c) for c in _vec(a)])
        v2 = _mu.Vector([_const(c) for c in _vec(b)])
        return _M(sp.Float(c) for c in v1.slerp(v2, _const(t)))

    # ---- matrices & Euler -------------------------------------------------
    def _asmat(a):
        if isinstance(a, sp.MatrixBase):
            return a
        raise ValueError("matrice attendue (par ex. mat((1,0,0),(0,1,0),(0,0,1)))")

    def mat(*rows):
        """Build a matrix from row vectors: ``mat((1,0,0),(0,1,0),(0,0,1))``.
        Also accepts a single list of rows."""
        if len(rows) == 1 and _is_vec(rows[0]) and all(_is_vec(r) for r in rows[0]):
            rows = tuple(rows[0])
        data = [[sp.sympify(e) for e in _vec(r)] for r in rows]
        width = len(data[0])
        if any(len(r) != width for r in data):
            raise ValueError("mat : lignes de longueurs différentes")
        return sp.Matrix(data)

    def eye(n=3):
        return sp.eye(int(sp.sympify(n)))
    identity = eye

    def diag(*vals):
        if len(vals) == 1 and _is_vec(vals[0]):
            vals = tuple(vals[0])
        return sp.diag(*[sp.sympify(v) for v in vals])

    def scalemat(sx, sy, sz):
        return sp.diag(_scalar(sx), _scalar(sy), _scalar(sz))

    def rmx(a):
        c, s = sp.cos(_scalar(a)), sp.sin(_scalar(a))
        return sp.Matrix([[1, 0, 0], [0, c, -s], [0, s, c]])

    def rmy(a):
        c, s = sp.cos(_scalar(a)), sp.sin(_scalar(a))
        return sp.Matrix([[c, 0, s], [0, 1, 0], [-s, 0, c]])

    def rmz(a):
        c, s = sp.cos(_scalar(a)), sp.sin(_scalar(a))
        return sp.Matrix([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    def rotmat(axis, ang):
        """3×3 rotation matrix about ``axis`` by ``ang`` (Rodrigues).
        Symbolic-capable; mathutils ``Matrix.Rotation`` fast-path when
        constant."""
        ax = _vec3(axis)
        th = _scalar(ang)
        mx = _mu_vec(ax)
        if (mx is not None and _mu is not None
                and not getattr(th, "free_symbols", set())):
            M = _mu.Matrix.Rotation(float(th), 3, mx)
            return sp.Matrix([[sp.Float(M[i][j]) for j in range(3)]
                              for i in range(3)])
        n = sp.sqrt(sum((e * e for e in ax), sp.Integer(0)))
        k = [e / n for e in ax]
        K = sp.Matrix([[0, -k[2], k[1]],
                       [k[2], 0, -k[0]],
                       [-k[1], k[0], 0]])
        c, s = sp.cos(th), sp.sin(th)
        return sp.eye(3) + s * K + (1 - c) * (K * K)

    def _eul_order(order, rx, ry, rz):
        """Rotation matrix from Euler angles (rx, ry, rz) in a given axis
        ``order`` (e.g. ``"XYZ"``, ``"ZYX"``).

        Convention matches Blender's ``mathutils.Euler``: ``rx``/``ry``/``rz``
        are always the rotations about X/Y/Z; ``order`` is the sequence in
        which they are *applied* (first letter applied first). The matrix
        is therefore the reverse product — ``order = c1c2c3`` →
        ``R = R[c3]·R[c2]·R[c1]``. Constant args take the mathutils
        fast-path for an exact match."""
        a, b, c = _scalar(rx), _scalar(ry), _scalar(rz)
        if (_mu is not None and not any(getattr(v, "free_symbols", set())
                                        for v in (a, b, c))):
            M = _mu.Euler((float(a), float(b), float(c)), order).to_matrix()
            return sp.Matrix([[sp.Float(M[i][j]) for j in range(3)]
                              for i in range(3)])
        rof = {"X": rmx(a), "Y": rmy(b), "Z": rmz(c)}
        c1, c2, c3 = order
        return rof[c3] * rof[c2] * rof[c1]

    def eul_xyz(rx, ry, rz): return _eul_order("XYZ", rx, ry, rz)
    def eul_xzy(rx, ry, rz): return _eul_order("XZY", rx, ry, rz)
    def eul_yxz(rx, ry, rz): return _eul_order("YXZ", rx, ry, rz)
    def eul_yzx(rx, ry, rz): return _eul_order("YZX", rx, ry, rz)
    def eul_zxy(rx, ry, rz): return _eul_order("ZXY", rx, ry, rz)
    def eul_zyx(rx, ry, rz): return _eul_order("ZYX", rx, ry, rz)
    eul = eul_xyz  # default order, matches Blender

    def transpose(a):
        return _asmat(a).T

    def det(a):
        return _asmat(a).det()

    def inv(a):
        return _asmat(a).inv()

    def trace(a):
        return _asmat(a).trace()

    # ---- quaternions (w, x, y, z) — mathutils convention -----------------
    def _quat(q):
        items = _vec(q)
        if len(items) != 4:
            raise ValueError("quaternion (w, x, y, z) attendu")
        return items

    def quat(w, x, y, z):
        return _M((w, x, y, z))

    def quat_axis(axis, ang):
        """Unit quaternion of a rotation by ``ang`` about ``axis``
        (mathutils ``Quaternion(axis, angle)`` convention)."""
        ax = _vec3(axis)
        n = sp.sqrt(sum((e * e for e in ax), sp.Integer(0)))
        k = [e / n for e in ax]
        h = _scalar(ang) / 2
        s = sp.sin(h)
        return _M((sp.cos(h), k[0] * s, k[1] * s, k[2] * s))
    qaxis = quat_axis

    def qconj(q):
        w, x, y, z = _quat(q)
        return _M((w, -x, -y, -z))

    def qnorm(q):
        return sp.sqrt(sum((e * e for e in _quat(q)), sp.Integer(0)))

    def qnormalize(q):
        n = qnorm(q)
        return _M(e / n for e in _quat(q))
    qunit = qnormalize

    def qmul(q1, q2):
        """Hamilton product q1·q2 (same order as mathutils ``q1 @ q2``)."""
        w1, x1, y1, z1 = _quat(q1)
        w2, x2, y2, z2 = _quat(q2)
        return _M((
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ))

    def qmat(q):
        """Quaternion → 3×3 rotation matrix (normalised first)."""
        w, x, y, z = _quat(qnormalize(q))
        return sp.Matrix([
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ])
    quat_to_mat = qmat

    def qrotate(q, v):
        """Rotate vector ``v`` by quaternion ``q`` → 3-vector (bench row)."""
        return qmat(q) * _M(_vec3(v))

    def qslerp(q1, q2, t):
        """Symbolic spherical-linear interpolation between quaternions;
        ``t`` may be a live parameter."""
        a = _quat(qnormalize(q1))
        b = _quat(qnormalize(q2))
        d = sum((ai * bi for ai, bi in zip(a, b)), sp.Integer(0))
        # Shorter-arc flip, decidable only for concrete endpoints.
        if getattr(d, "is_number", False) and bool(d < 0):
            b = [-bi for bi in b]
            d = -d
        om = sp.acos(d)
        s = sp.sin(om)
        ts = _scalar(t)
        return _M((sp.sin((1 - ts) * om) / s) * ai
                  + (sp.sin(ts * om) / s) * bi
                  for ai, bi in zip(a, b))

    _HELPERS[0] = {
        "vec": vec,
        "mat": mat, "eye": eye, "identity": identity, "diag": diag,
        "scalemat": scalemat, "rmx": rmx, "rmy": rmy, "rmz": rmz,
        "rotmat": rotmat, "eul": eul,
        "eul_xyz": eul_xyz, "eul_xzy": eul_xzy, "eul_yxz": eul_yxz,
        "eul_yzx": eul_yzx, "eul_zxy": eul_zxy, "eul_zyx": eul_zyx,
        "transpose": transpose, "det": det, "inv": inv, "trace": trace,
        "quat": quat, "quat_axis": quat_axis, "qaxis": qaxis,
        "qmul": qmul, "qconj": qconj, "qnorm": qnorm,
        "qnormalize": qnormalize, "qunit": qunit, "qrotate": qrotate,
        "qmat": qmat, "quat_to_mat": quat_to_mat, "qslerp": qslerp,
        "dot": dot, "cross": cross, "vlen": vlen, "norm": norm,
        "vdist": vdist, "vangle": vangle, "angle": angle,
        "normalize": normalize, "unit": unit, "proj": proj,
        "comp": comp, "lerp": lerp, "clamp": clamp,
        "rot_x": rot_x, "rot_y": rot_y, "rot_z": rot_z,
        "rotate": rotate, "slerp": slerp,
    }
    return _HELPERS[0]


def _reject_non_scalar(expr):
    """Raise a friendly error if ``expr`` is a vector/tuple rather than a
    scalar SymPy expression (e.g. the user typed ``cross(a, b)`` at the
    top level of a scalar formula). Numbers and symbolic scalars are
    ``sympy.Expr`` and pass through untouched."""
    sp = _sympy()
    if isinstance(expr, sp.MatrixBase) or not isinstance(expr, sp.Expr):
        raise ValueError(
            "Résultat vectoriel dans un champ scalaire. Extrais une "
            "composante avec comp(v, i) — par ex. comp(cross(a, b), 2) — "
            "ou compose avec un helper scalaire (vlen, dot, …)."
        )
    return expr


def _base_math_locals() -> dict:
    """Math functions + constants + vector/Mathutils helpers, *without*
    any free variable. Shared by :func:`_safe_locals` (which adds the
    integration variable) and :func:`_bench_locals` (which adds declared
    parameters and prior named vectors)."""
    sp = _sympy()
    aliases = {
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
        "atan2": sp.atan2,
        "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
        "asinh": sp.asinh, "acosh": sp.acosh, "atanh": sp.atanh,
        "exp": sp.exp, "log": sp.log, "ln": sp.log,
        "sqrt": sp.sqrt,
        "Abs": sp.Abs, "abs": sp.Abs, "sign": sp.sign,
        "Heaviside": sp.Heaviside,
        "floor": sp.floor, "ceil": sp.ceiling, "ceiling": sp.ceiling,
        "frac": sp.frac, "Mod": sp.Mod, "mod": sp.Mod,
        "Min": sp.Min, "Max": sp.Max, "min": sp.Min, "max": sp.Max,
        "pi": sp.pi, "E": sp.E,
    }
    # Vector / Mathutils helpers (shared by every parser variant, since
    # the 2D/3D and vector locals all build on this dict).
    aliases.update(_vector_helpers())
    return aliases


def _safe_locals(var_name: str) -> dict:
    aliases = _base_math_locals()
    sp = _sympy()
    aliases[var_name] = sp.Symbol(var_name, real=True)
    return aliases


def _safe_globals() -> dict:
    """Globals dict for ``parse_expr``: SymPy's internal helpers
    (``Integer``, ``Symbol``, ``Float``, …) need to be in scope because
    SymPy's tokeniser transforms ``2`` into ``Integer(2)`` and similar.
    But we explicitly blank out ``__builtins__`` so ``__import__``,
    ``open``, ``eval``, … are unreachable even if the AST check missed
    something."""
    sp = _sympy()
    return {
        # Whitelist of SymPy classes/functions the tokeniser may
        # reference internally.
        "Integer": sp.Integer,
        "Float": sp.Float,
        "Rational": sp.Rational,
        "Symbol": sp.Symbol,
        "Pow": sp.Pow,
        # Hard wall: no Python builtins at all.
        "__builtins__": {},
    }


def parse_expression(source: str, var_name: str = "x"):
    """Parse ``source`` into a SymPy expression after full safety check.

    Raises :class:`ValueError` if the expression contains anything
    outside the safe arithmetic subset.
    """
    source = source.strip()
    if not source:
        raise ValueError("Expression vide")
    _validate_ast(source)
    sp = _sympy()
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
    )
    try:
        expr = parse_expr(
            source,
            local_dict=_safe_locals(var_name),
            global_dict=_safe_globals(),
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, AttributeError, NameError) as e:
        raise ValueError(f"Parsing impossible : {e}") from None
    return _reject_non_scalar(expr)


# --------------------------------------------------------------------------- #
# Vector-mode parser
# --------------------------------------------------------------------------- #
# A vector function of one real variable is parsed as a
# ``sympy.physics.vector.Vector`` expressed in the basis of a fixed
# reference frame ``N``. The user types things like::
#
#     t*N.x + sin(t)*N.y + cos(t)*N.z
#     exp(-t)*sin(t)*N.x + exp(-t)*cos(t)*N.y + t*N.z
#
# After parsing we project onto each axis with ``v.dot(N.x)`` and friends
# to recover a triplet of SymPy scalars ``(Fx, Fy, Fz)`` that the
# compiler can lower to Geometry Nodes the same way it lowers a single
# scalar formula.

_VECTOR_FRAME_NAME = "N"


def _vector_safe_locals(var_name: str) -> dict:
    """Build the locals dict for parse_expr in vector mode.

    On top of the scalar locals (math functions, the integration
    variable as a real symbol), we expose:

    * ``N`` — a :class:`sympy.physics.vector.ReferenceFrame` instance.
      The AST validator has already ensured the user can only reach
      its ``.x``, ``.y``, ``.z`` attributes, which are the basis
      vectors.
    """
    sp = _sympy()
    aliases = dict(_safe_locals(var_name))
    # Lazy import: ``sympy.physics.vector`` pulls in extra modules
    # we don't need for scalar parsing.
    from sympy.physics.vector import ReferenceFrame
    aliases[_VECTOR_FRAME_NAME] = ReferenceFrame(_VECTOR_FRAME_NAME)
    return aliases


def parse_vector_expression(source: str, var_name: str = "t"):
    """Parse a vector-valued expression and return its component triplet.

    The input must use the fixed reference frame ``N``: for example
    ``t*N.x + sin(t)*N.y + cos(t)*N.z`` for a helix.

    Returns
    -------
    tuple of three SymPy expressions
        The components ``(Fx, Fy, Fz)`` extracted by projection onto
        ``N.x``, ``N.y``, ``N.z`` respectively. Each component is a
        plain scalar SymPy expression — the same shape the regular
        scalar compiler already knows how to lower to Geometry Nodes
        Math sub-graphs.

    Raises
    ------
    ValueError
        If the input is empty, syntactically invalid, contains
        disallowed nodes, or evaluates to something other than a
        ``sympy.physics.vector.Vector``.
    """
    source = source.strip()
    if not source:
        raise ValueError("Expression vectorielle vide")

    _validate_ast(source, allow_frame_attr=True,
                   frame_name=_VECTOR_FRAME_NAME)

    sp = _sympy()
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
    )
    locals_ = _vector_safe_locals(var_name)
    N = locals_[_VECTOR_FRAME_NAME]
    try:
        expr = parse_expr(
            source,
            local_dict=locals_,
            global_dict=_safe_globals(),
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, AttributeError, NameError) as e:
        raise ValueError(f"Parsing impossible : {e}") from None

    # Validate that the result is actually a Vector. A user typing a
    # pure scalar like ``cos(t)`` would get a SymPy expression back
    # from ``parse_expr`` — we reject that with a clear message
    # rather than letting the projection step crash later.
    from sympy.physics.vector import Vector
    if not isinstance(expr, Vector):
        # SymPy's zero is special — ``0*N.x`` simplifies to a scalar
        # zero, not a zero Vector. Treat it as the zero vector to be
        # tolerant of degenerate inputs.
        if expr == 0:
            return (sp.S.Zero, sp.S.Zero, sp.S.Zero)
        raise ValueError(
            f"L'expression doit être un vecteur (combinaison de "
            f"{_VECTOR_FRAME_NAME}.x, {_VECTOR_FRAME_NAME}.y, "
            f"{_VECTOR_FRAME_NAME}.z). "
            f"Type obtenu : {type(expr).__name__}"
        )

    # Project onto each axis. ``dot`` returns a SymPy scalar.
    fx = expr.dot(N.x)
    fy = expr.dot(N.y)
    fz = expr.dot(N.z)
    return (fx, fy, fz)


def vector_diff(components, var_name: str = "t"):
    """Return the component-wise time derivative of a vector function.

    Convenience wrapper that lets callers compute ``F'(t)`` directly
    on the triplet returned by :func:`parse_vector_expression`. Each
    component is differentiated independently — equivalent to
    ``Vector.diff(t, N)`` followed by re-projection, but cheaper since
    we already have the scalars.
    """
    sp = _sympy()
    t = sp.Symbol(var_name, real=True)
    return tuple(sp.diff(c, t) for c in components)


# --------------------------------------------------------------------------- #
# Surface parsers (2 variables)
# --------------------------------------------------------------------------- #
# Two flavours of surfaces:
#
#   * explicit  z = f(x, y)
#       — one scalar expression in two variables; the surface is a
#         graph in the plane XY.
#
#   * parametric (x(u, v), y(u, v), z(u, v))
#       — three scalar expressions in two variables; supports
#         self-intersecting / folded surfaces (sphere, torus, …).
#
# Both reuse the scalar safety machinery (AST whitelist, sandboxed
# parse_expr). The only twist is exposing *two* free variables to the
# locals dict instead of one.


def _safe_locals_2d(x_name: str, y_name: str) -> dict:
    """Locals dict for a 2-variable expression.

    Identical to :func:`_safe_locals` except two symbols rather than
    one are registered as real-valued. Both names must be distinct —
    we don't try to be clever about ``x_name == y_name``; the caller
    is expected to validate that.
    """
    aliases = dict(_safe_locals(x_name))
    sp = _sympy()
    aliases[y_name] = sp.Symbol(y_name, real=True)
    return aliases


def parse_surface_expression(source: str,
                              x_name: str = "x",
                              y_name: str = "y"):
    """Parse a 2-variable scalar expression ``z = f(x, y)``.

    Returns a SymPy expression with two free symbols (``x``, ``y`` by
    default) — plus any free parameters the user declared. Same safety
    pipeline as :func:`parse_expression`: AST whitelist, sandboxed
    ``parse_expr``, no Python builtins, no attribute access.
    """
    source = source.strip()
    if not source:
        raise ValueError("Expression de surface vide")
    if x_name == y_name:
        raise ValueError(
            f"x_name et y_name doivent être distincts (reçus tous deux {x_name!r})"
        )
    _validate_ast(source)
    sp = _sympy()
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
    )
    try:
        expr = parse_expr(
            source,
            local_dict=_safe_locals_2d(x_name, y_name),
            global_dict=_safe_globals(),
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, AttributeError, NameError) as e:
        raise ValueError(f"Parsing impossible : {e}") from None
    return _reject_non_scalar(expr)


def surface_gradient(expr, x_name: str = "x", y_name: str = "y"):
    """Return the partial derivatives ``(∂f/∂x, ∂f/∂y)`` of a scalar
    field, as a pair of SymPy expressions.

    Useful for displaying the gradient at the basepoint and for
    constructing the tangent plane (whose two basis vectors are
    ``(1, 0, ∂f/∂x)`` and ``(0, 1, ∂f/∂y)`` at the point of contact).
    """
    sp = _sympy()
    x = sp.Symbol(x_name, real=True)
    y = sp.Symbol(y_name, real=True)
    return (sp.diff(expr, x), sp.diff(expr, y))


def parse_parametric_surface_components(components_source,
                                          u_name: str = "u",
                                          v_name: str = "v"):
    """Parse three scalar expressions making up a parametric surface
    ``(x(u, v), y(u, v), z(u, v))``.

    ``components_source`` is a triplet of strings — one per axis. We
    parse each independently with two free variables ``(u, v)``, so the
    three expressions can share or differ in their parameter usage
    freely.

    Returns a triplet of SymPy expressions matching the input.
    """
    if len(components_source) != 3:
        raise ValueError(
            f"3 expressions attendues (x(u,v), y(u,v), z(u,v)), "
            f"{len(components_source)} reçues"
        )
    if u_name == v_name:
        raise ValueError(
            f"u_name et v_name doivent être distincts (reçus {u_name!r})"
        )
    parsed = []
    for axis_name, source in zip(("x", "y", "z"), components_source):
        try:
            expr = parse_surface_expression(source, u_name, v_name)
        except ValueError as e:
            # Re-raise with a clearer message identifying which axis
            # the failure happened on — without this the user gets
            # ``Parsing impossible : ...`` with no clue which of the
            # three boxes contains the typo.
            raise ValueError(
                f"Composante {axis_name}({u_name}, {v_name}) : {e}"
            ) from None
        parsed.append(expr)
    return tuple(parsed)


def parametric_surface_partial_derivatives(components,
                                            u_name: str = "u",
                                            v_name: str = "v"):
    """Return ``(∂F/∂u, ∂F/∂v)`` of a parametric surface, each as a
    triplet of SymPy expressions (one per axis).

    For the tangent plane visualisation we need both partial
    derivatives — they span the plane at the contact point.
    """
    sp = _sympy()
    u = sp.Symbol(u_name, real=True)
    v = sp.Symbol(v_name, real=True)
    d_u = tuple(sp.diff(c, u) for c in components)
    d_v = tuple(sp.diff(c, v) for c in components)
    return (d_u, d_v)


# --------------------------------------------------------------------------- #
# 3D scalar field parser
# --------------------------------------------------------------------------- #
# Scalar field f: R^3 -> R, used for visualising electrostatic potentials,
# temperature fields, density distributions, anything that assigns a single
# real value to each point of 3-space.


def _safe_locals_3d(x_name: str, y_name: str, z_name: str) -> dict:
    """Locals dict for a 3-variable expression.

    Extension of :func:`_safe_locals_2d` to three coordinate symbols.
    The caller is expected to pass three distinct names; we validate
    this explicitly because a typo like ``z_name = "x"`` would silently
    collapse the field to a 2-variable one with no warning.
    """
    aliases = dict(_safe_locals_2d(x_name, y_name))
    sp = _sympy()
    aliases[z_name] = sp.Symbol(z_name, real=True)
    return aliases


def parse_scalar_field_3d_expression(source: str,
                                       x_name: str = "x",
                                       y_name: str = "y",
                                       z_name: str = "z"):
    """Parse a 3-variable scalar expression ``f(x, y, z)``.

    Returns a SymPy expression with three free coordinate symbols
    (plus any free parameters declared by the user). Reuses the same
    AST safety pipeline as the 1D / 2D parsers — no Python builtins,
    no attribute access, only the whitelisted SymPy functions.

    Distinct ``x_name``, ``y_name``, ``z_name`` are required;
    duplicates raise ``ValueError`` rather than silently collapsing
    dimensions.
    """
    source = source.strip()
    if not source:
        raise ValueError("Expression de champ scalaire vide")
    if len({x_name, y_name, z_name}) != 3:
        raise ValueError(
            f"x_name, y_name, z_name doivent être distincts "
            f"(reçus {x_name!r}, {y_name!r}, {z_name!r})"
        )
    _validate_ast(source)
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
    )
    try:
        expr = parse_expr(
            source,
            local_dict=_safe_locals_3d(x_name, y_name, z_name),
            global_dict=_safe_globals(),
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, AttributeError, NameError) as e:
        raise ValueError(f"Parsing impossible : {e}") from None
    return _reject_non_scalar(expr)


def scalar_field_3d_gradient(expr,
                              x_name: str = "x",
                              y_name: str = "y",
                              z_name: str = "z"):
    """Return ``(∂f/∂x, ∂f/∂y, ∂f/∂z)`` of a 3D scalar field.

    The 3D analogue of :func:`surface_gradient`. Used to display the
    gradient at the basepoint (a vector pointing in the direction of
    steepest ascent) and, eventually, to drive vector-field
    visualisations like the gradient field of a scalar potential.
    """
    sp = _sympy()
    x = sp.Symbol(x_name, real=True)
    y = sp.Symbol(y_name, real=True)
    z = sp.Symbol(z_name, real=True)
    return (sp.diff(expr, x), sp.diff(expr, y), sp.diff(expr, z))


def parse_vector_field_3d_components(components_source,
                                       x_name: str = "x",
                                       y_name: str = "y",
                                       z_name: str = "z"):
    """Parse three scalar expressions making up a 3D vector field
    ``V(x, y, z) = (V_x(x,y,z), V_y(x,y,z), V_z(x,y,z))``.

    Symmetric to :func:`parse_parametric_surface_components` but with
    *three* free coordinate variables instead of two. Each component
    is parsed independently with the same AST safety pipeline as the
    scalar parsers, then we collect free symbols across all three to
    expose to the caller as the "free parameters" set.

    Returns the triplet of SymPy expressions (unlike the parametric
    surface parser which silently returns just the components, we
    keep the contract symmetric).
    """
    if len(components_source) != 3:
        raise ValueError(
            f"3 expressions attendues (V_x, V_y, V_z), "
            f"{len(components_source)} reçues"
        )
    if len({x_name, y_name, z_name}) != 3:
        raise ValueError(
            f"x_name, y_name, z_name doivent être distincts "
            f"(reçus {x_name!r}, {y_name!r}, {z_name!r})"
        )
    parsed = []
    for axis_name, source in zip(("V_x", "V_y", "V_z"), components_source):
        try:
            expr = parse_scalar_field_3d_expression(
                source, x_name, y_name, z_name,
            )
        except ValueError as e:
            raise ValueError(
                f"Composante {axis_name}({x_name}, {y_name}, {z_name}) : {e}"
            ) from None
        parsed.append(expr)
    return tuple(parsed)


def vector_field_3d_divergence(components,
                                 x_name: str = "x",
                                 y_name: str = "y",
                                 z_name: str = "z"):
    """Return the divergence ∂V_x/∂x + ∂V_y/∂y + ∂V_z/∂z of a 3D
    vector field.

    A scalar function of (x, y, z). Stored in the tree metadata for
    panel display — useful for physical intuition (incompressibility
    of a flow = zero divergence; sources/sinks visible from the sign).
    """
    sp = _sympy()
    x = sp.Symbol(x_name, real=True)
    y = sp.Symbol(y_name, real=True)
    z = sp.Symbol(z_name, real=True)
    return sp.diff(components[0], x) + sp.diff(components[1], y) + sp.diff(components[2], z)


# --------------------------------------------------------------------------- #
# Vector bench parser
# --------------------------------------------------------------------------- #
# The "banc de vecteurs" lets the user declare several named vectors and
# explore vector algebra / rotations interactively. Each row is a vector
# expression in a shared set of scalar *parameters* (e.g. ``theta``),
# which become live modifier sliders. A row may reference vectors defined
# in earlier rows by name (so ``v3 = cross(v1, v2)`` works), enabling
# genuine vector-calculus exploration. Rotations use the symbol-friendly
# ``rotate`` / ``rot_z`` helpers so a parameter angle animates live.


def _bench_locals(allowed_params, prior=None) -> dict:
    """Locals for a bench row: math + helpers + ``vec`` + declared scalar
    parameters (as real Symbols) + previously-defined vectors (as
    ``sympy.Matrix`` values, keyed by name)."""
    sp = _sympy()
    d = _base_math_locals()
    for p in allowed_params:
        d[p] = sp.Symbol(p, real=True)
    if prior:
        d.update(prior)
    return d


def _as_three(expr):
    """Normalise a parsed bench result to a list of 3 scalar SymPy exprs.

    Accepts a ``sympy.Matrix`` (what ``vec`` and the vector helpers
    return), a Python tuple/list, or a ``sympy.Tuple`` literal. A
    2-vector is padded with ``z = 0``. A bare scalar raises a friendly
    error pointing at ``vec(...)``."""
    sp = _sympy()
    if isinstance(expr, sp.MatrixBase):
        items = list(expr)
    elif isinstance(expr, (tuple, list)):
        items = list(expr)
    elif isinstance(expr, sp.Tuple):
        items = list(expr)
    else:
        raise ValueError(
            "L'expression doit être un vecteur — par ex. vec(1, 0, 0), "
            "cross(a, b) ou rotate(v, axe, θ). Scalaire reçu."
        )
    if len(items) == 2:
        items = items + [sp.Integer(0)]
    if len(items) != 3:
        raise ValueError(
            f"Vecteur 3D attendu, dimension {len(items)} reçue"
        )
    return [sp.sympify(c) for c in items]


def parse_bench_vector(source: str, *, allowed_params=(), prior=None):
    """Parse one bench-row vector expression → triplet ``(Fx, Fy, Fz)``.

    ``allowed_params`` are the declared scalar slider names; any free
    symbol outside that set raises. ``prior`` maps already-defined row
    names to their ``sympy.Matrix`` value so later rows can reference
    them. Same AST safety pipeline as every other parser (whitelist +
    sandboxed ``parse_expr``)."""
    source = source.strip()
    if not source:
        raise ValueError("Expression vectorielle vide")
    _validate_ast(source)
    sp = _sympy()
    from sympy.parsing.sympy_parser import (
        parse_expr, standard_transformations,
    )
    try:
        expr = parse_expr(
            source,
            local_dict=_bench_locals(allowed_params, prior),
            global_dict=_safe_globals(),
            transformations=standard_transformations,
            evaluate=True,
        )
    except (SyntaxError, TypeError, AttributeError, NameError) as e:
        raise ValueError(f"Parsing impossible : {e}") from None

    comps = _as_three(expr)
    allowed = set(allowed_params)
    for axis, c in zip(("x", "y", "z"), comps):
        if not isinstance(c, sp.Expr):
            raise ValueError(
                f"Composante {axis} non scalaire ({type(c).__name__})"
            )
        bad = sorted(s.name for s in c.free_symbols if s.name not in allowed)
        if bad:
            raise ValueError(
                f"Symboles non déclarés : {', '.join(bad)}. "
                f"Ajoutez-les aux paramètres."
            )
    return tuple(comps)


def vector_field_3d_curl(components,
                           x_name: str = "x",
                           y_name: str = "y",
                           z_name: str = "z"):
    """Return the curl ∇×V of a 3D vector field, as a triplet of
    SymPy expressions.

    Curl identifies rotational components. Two pedagogical uses:

    * A field is *conservative* (= gradient of some potential) iff
      its curl is identically zero. Useful as a quick sanity check
      when the user toggles "from potential" mode and back.

    * Visual intuition for rotational flows: a non-zero curl points
      along the axis of local rotation.

    Curl formula:
        (curl V)_x = ∂V_z/∂y - ∂V_y/∂z
        (curl V)_y = ∂V_x/∂z - ∂V_z/∂x
        (curl V)_z = ∂V_y/∂x - ∂V_x/∂y
    """
    sp = _sympy()
    x = sp.Symbol(x_name, real=True)
    y = sp.Symbol(y_name, real=True)
    z = sp.Symbol(z_name, real=True)
    Vx, Vy, Vz = components
    return (
        sp.diff(Vz, y) - sp.diff(Vy, z),
        sp.diff(Vx, z) - sp.diff(Vz, x),
        sp.diff(Vy, x) - sp.diff(Vx, y),
    )
