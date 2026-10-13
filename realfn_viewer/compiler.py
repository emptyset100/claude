"""
Compilation of SymPy expressions into Geometry Nodes Math sub-graphs.

The compiler walks a SymPy expression tree bottom-up and emits one
``ShaderNodeMath`` or ``ShaderNodeVectorMath`` per operator, threading
sockets through ``link()`` calls. Sub-expression elimination is done by
memoising on SymPy expression identity: ``cos(x) + sin(x)*cos(x)``
emits exactly one ``COSINE`` node, not two.

Layout heuristic
----------------
Nodes are placed left-to-right along the graph: leaves (the ``x``
variable, constants, free parameters) on the left at x=-800, and each
arithmetic level pushed 200 units rightward. This isn't load-bearing —
the graph evaluates the same regardless — but it makes the result
inspectable when the user opens the node editor.

Build cost and outlining
------------------------
Every ``nodes.new`` / ``links.new`` call made from Python triggers a
full update of the *whole* node tree (Blender 4.x / 5.x), so building
one tree of N nodes costs O(N²). Measured on Blender 5.2: ~2 400 Math
nodes in a single tree take ~85 s, whereas the same nodes split into
a dozen small sub-groups take a few seconds. :func:`compile_outlined`
therefore compiles large expressions (high-order Taylor terms…) into
their own small, hidden node group (name starting with ``.``) and
instances it with a ``Group`` node. :func:`release_tree` removes an
orphaned tree together with the outlined sub-groups it owned.
"""

from __future__ import annotations

import math

import bpy

from . import sympy_parser


# --------------------------------------------------------------------------- #
# NodeBuilder: thin wrapper over the bpy node-tree API
# --------------------------------------------------------------------------- #
class NodeBuilder:
    """Convenience helpers for adding nodes and linking sockets.

    Centralises the Math / VectorMath node creation pattern: pick the
    operation enum, set up to two inputs (each can be either a NodeSocket
    or a plain float), and return the output socket. Float defaults are
    written to the socket's ``default_value`` so the compiler never has
    to allocate a ``ShaderNodeValue`` for a constant.
    """

    def __init__(self, node_tree):
        self.tree = node_tree
        self.nodes = node_tree.nodes
        self.links = node_tree.links

    def add(self, bl_idname, *, x=0, y=0, label="", **props):
        n = self.nodes.new(bl_idname)
        n.location = (x, y)
        if label:
            n.label = label
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, from_sock, to_sock):
        return self.links.new(from_sock, to_sock)

    def _to_socket(self, value, target_socket):
        """If ``value`` is already a socket, link it; if it's a float,
        write it as the target's default value. Raises if it's
        something we can't interpret."""
        if hasattr(value, "is_output"):  # NodeSocket
            self.link(value, target_socket)
            return
        try:
            target_socket.default_value = float(value)
        except (TypeError, ValueError):
            raise TypeError(
                f"Cannot wire value {value!r} of type "
                f"{type(value).__name__} into socket"
            )

    def math(self, op, a, b=None, *, x=0, y=0, label=""):
        """Add a ``ShaderNodeMath`` node with the given operation."""
        n = self.add("ShaderNodeMath", x=x, y=y, label=label)
        n.operation = op
        self._to_socket(a, n.inputs[0])
        if b is not None:
            self._to_socket(b, n.inputs[1])
        return n.outputs[0]

    def combine_xyz(self, x_in, y_in, z_in, *, x=0, y=0, label=""):
        n = self.add("ShaderNodeCombineXYZ", x=x, y=y, label=label)
        self._to_socket(x_in, n.inputs["X"])
        self._to_socket(y_in, n.inputs["Y"])
        self._to_socket(z_in, n.inputs["Z"])
        return n.outputs["Vector"]


# --------------------------------------------------------------------------- #
# SymPy → Math nodes compiler
# --------------------------------------------------------------------------- #
def _function_op_map():
    """Map SymPy class → ``ShaderNodeMath.operation`` enum value."""
    sp = sympy_parser._sympy()
    return {
        sp.sin: "SINE",
        sp.cos: "COSINE",
        sp.tan: "TANGENT",
        sp.asin: "ARCSINE",
        sp.acos: "ARCCOSINE",
        sp.atan: "ARCTANGENT",
        sp.sinh: "SINH",
        sp.cosh: "COSH",
        sp.tanh: "TANH",
        sp.exp: "EXPONENT",
        sp.Abs: "ABSOLUTE",
        sp.sign: "SIGN",
        sp.floor: "FLOOR",
        sp.ceiling: "CEIL",
        sp.frac: "FRACT",
    }


def _binary_op_map():
    """Two-argument SymPy functions with a direct Math-node equivalent.

    ``atan2(y, x)`` maps to ``ARCTAN2`` whose inputs are (A=y, B=x);
    SymPy's ``Mod`` follows the sign of the divisor, which is exactly
    ``FLOORED_MODULO``."""
    sp = sympy_parser._sympy()
    return {
        sp.atan2: "ARCTAN2",
        sp.Mod: "FLOORED_MODULO",
    }


def _derivative_ignoring_steps(d):
    """Evaluate ``d`` (a SymPy ``Derivative``) treating floor/ceiling as
    locally constant — their derivative is 0 everywhere but at the jumps,
    which a sampled curve can't show anyway. frac and Mod are first
    rewritten through floor, so d/dx frac(x) = 1 and so on."""
    sp = sympy_parser._sympy()
    inner = d.expr
    inner = inner.replace(sp.frac, lambda a: a - sp.floor(a))
    inner = inner.replace(sp.Mod, lambda a, b: a - b * sp.floor(a / b))
    inner = inner.replace(sp.ceiling, lambda a: -sp.floor(-a))
    frozen = {f: sp.Dummy() for f in inner.atoms(sp.floor)}
    res = sp.diff(inner.xreplace(frozen), *d.variable_count)
    return res.xreplace({v: k for k, v in frozen.items()})


class SymPyCompiler:
    """Lower a SymPy expression to a Geometry Nodes Math sub-graph.

    Parameters
    ----------
    nb : :class:`NodeBuilder`
        Active builder bound to the destination node tree.
    var_sockets : dict[str, NodeSocket]
        Maps each free symbol name (``"x"``, ``"a"``, …) to the source
        socket whose value resolves it. Constants like π and e are
        emitted inline as floats.
    """

    def __init__(self, nb: NodeBuilder, var_sockets: dict):
        self.nb = nb
        self.var_sockets = dict(var_sockets)
        self._cache: dict = {}

    def compile(self, expr):
        """Return either a NodeSocket or a plain float."""
        if expr in self._cache:
            return self._cache[expr]
        out = self._compile(expr)
        self._cache[expr] = out
        return out

    def _compile(self, expr):
        sp = sympy_parser._sympy()

        # Plain numeric literal → float (NodeBuilder.math handles it).
        if expr.is_Number:
            return float(expr)

        # Any closed-form constant (π, e, sqrt(2)/3, log(5), cos(1)…) →
        # folded to a single float instead of a chain of Math nodes.
        # Typical source: Taylor coefficients ``f⁽ⁿ⁾(x₀)/n!`` once x₀
        # is numeric, or constants produced by differentiation.
        if not expr.free_symbols:
            try:
                val = complex(expr.evalf())
            except (TypeError, ValueError):
                val = None
            if val is not None and abs(val.imag) < 1e-12:
                return float(val.real)

        # Symbol → matching socket.
        if expr.is_Symbol:
            name = expr.name
            if name in self.var_sockets:
                return self.var_sockets[name]
            raise ValueError(f"Symbole inattendu : {name!r}")

        # Addition: left-fold pairwise.
        if expr.is_Add:
            return self._fold([self.compile(a) for a in expr.args], "ADD")

        # Multiplication: recognise Mul(-1, X) as unary negation for a
        # slightly smaller graph.
        if expr.is_Mul:
            args = list(expr.args)
            if len(args) == 2 and args[0] == sp.S.NegativeOne:
                inner = self.compile(args[1])
                return self.nb.math("MULTIPLY", inner, -1.0)
            return self._fold(
                [self.compile(a) for a in args], "MULTIPLY"
            )

        # Power: special-case small integer exponents, sqrt and 1/x for
        # numerical stability and graph compactness.
        if expr.is_Pow:
            base, exponent = expr.args
            return self._compile_pow(base, exponent)

        # Function application.
        # Natural log: the Math node's LOGARITHM is log_B(A) with B (the
        # second input) defaulting to 0.5 — B must be set to e, or
        # ``log(x)`` silently becomes log₀.₅(x) = −log₂(x).
        if isinstance(expr, sp.log):
            return self.nb.math("LOGARITHM", self.compile(expr.args[0]),
                                math.e)

        op_map = _function_op_map()
        for fcls, op in op_map.items():
            if isinstance(expr, fcls):
                arg = self.compile(expr.args[0])
                return self.nb.math(op, arg)

        for fcls, op in _binary_op_map().items():
            if isinstance(expr, fcls):
                a = self.compile(expr.args[0])
                b = self.compile(expr.args[1])
                return self.nb.math(op, a, b)

        # Min / Max (n-ary, e.g. from ``clamp``) → pairwise fold.
        if isinstance(expr, sp.Min):
            return self._fold([self.compile(a) for a in expr.args],
                              "MINIMUM")
        if isinstance(expr, sp.Max):
            return self._fold([self.compile(a) for a in expr.args],
                              "MAXIMUM")

        # Heaviside(x) = (sign(x) + 1) / 2 — matches SymPy's H(0) = 1/2.
        if isinstance(expr, sp.Heaviside):
            s_ = self.nb.math("SIGN", self.compile(expr.args[0]))
            half = self.nb.math("MULTIPLY", s_, 0.5)
            return self.nb.math("ADD", half, 0.5)

        # DiracDelta appears when differentiating Heaviside / sign /
        # Abs. It is zero everywhere except on a null set, which is all
        # a sampled curve can show.
        if isinstance(expr, sp.DiracDelta):
            return 0.0

        # Unevaluated derivatives of step-like functions (floor, frac,
        # Mod, ceiling) — SymPy leaves ``Derivative(floor(x), x)``
        # as is. Away from the jumps floor/ceiling are locally constant,
        # so differentiate with them frozen.
        if isinstance(expr, sp.Derivative):
            return self.compile(_derivative_ignoring_steps(expr))
        if isinstance(expr, sp.Subs):
            inner = expr.expr
            if isinstance(inner, sp.Derivative):
                inner = _derivative_ignoring_steps(inner)
            return self.compile(
                inner.xreplace(dict(zip(expr.variables, expr.point))))

        # Inverse hyperbolic functions have no Math-node operation:
        # rewrite through their logarithmic closed form.
        if isinstance(expr, (sp.asinh, sp.acosh, sp.atanh)):
            return self.compile(expr.rewrite(sp.log))

        raise ValueError(
            f"Type d'expression non supporté : "
            f"{type(expr).__name__} ({expr})"
        )

    def _fold(self, items, op):
        if not items:
            return 0.0 if op == "ADD" else 1.0
        # Pre-combine the plain-float operands so constants cost at most
        # one input slot instead of one Math node each.
        if op in ("ADD", "MULTIPLY"):
            consts = [it for it in items if isinstance(it, float)]
            if len(consts) > 1:
                acc = 0.0 if op == "ADD" else 1.0
                for c in consts:
                    acc = acc + c if op == "ADD" else acc * c
                items = [it for it in items if not isinstance(it, float)]
                items.append(acc)
        if len(items) == 1:
            return items[0]
        result = self.nb.math(op, items[0], items[1])
        for it in items[2:]:
            result = self.nb.math(op, result, it)
        return result

    def _compile_pow(self, base, exponent):
        sp = sympy_parser._sympy()
        base_s = self.compile(base)
        if exponent == 2:
            return self.nb.math("MULTIPLY", base_s, base_s)
        if exponent == 3:
            sq = self.nb.math("MULTIPLY", base_s, base_s)
            return self.nb.math("MULTIPLY", sq, base_s)
        if exponent == sp.Rational(1, 2):
            return self.nb.math("SQRT", base_s)
        if exponent == -1:
            return self.nb.math("DIVIDE", 1.0, base_s)
        if exponent == -2:
            sq = self.nb.math("MULTIPLY", base_s, base_s)
            return self.nb.math("DIVIDE", 1.0, sq)
        # Generic case.
        exp_s = self.compile(exponent)
        return self.nb.math("POWER", base_s, exp_s)


# --------------------------------------------------------------------------- #
# Vector compilation helper
# --------------------------------------------------------------------------- #
def compile_vector_components(nb: NodeBuilder, components, var_sockets,
                                *, x=0, y=0, label="F"):
    """Compile a SymPy component triplet ``(Fx, Fy, Fz)`` into a single
    ``Vector`` socket via ``CombineXYZ``.

    A single :class:`SymPyCompiler` is shared across the three
    components so any common sub-expression appears only once in the
    resulting node graph. For instance,
    ``(cos(t)*t, sin(t)*t, t)`` emits exactly one ``COSINE`` node, one
    ``SINE`` node, and the multiplications by ``t`` share their
    operand socket.

    Parameters
    ----------
    nb : :class:`NodeBuilder`
        Active builder bound to the destination node tree.
    components : tuple of SymPy expressions
        The three scalar components of the vector function.
    var_sockets : dict[str, NodeSocket]
        Symbol-to-socket mapping for free variables (the integration
        variable ``t`` and any user-declared parameters).
    x, y : int
        Approximate location to place the ``CombineXYZ`` node — the
        compiler arranges the upstream math nodes to its left.
    label : str
        Cosmetic label for the produced ``CombineXYZ`` node.

    Returns
    -------
    NodeSocket
        The output socket of the ``CombineXYZ``, carrying a
        ``NodeSocketVector`` that can be wired wherever a vector
        socket is needed.
    """
    if len(components) != 3:
        raise ValueError(
            f"compile_vector_components: 3 composantes attendues, "
            f"{len(components)} reçues"
        )
    compiler = SymPyCompiler(nb, var_sockets)
    fx_sock = compiler.compile(components[0])
    fy_sock = compiler.compile(components[1])
    fz_sock = compiler.compile(components[2])
    return nb.combine_xyz(fx_sock, fy_sock, fz_sock,
                          label=label, x=x, y=y)


# --------------------------------------------------------------------------- #
# Outlining: compile big expressions into their own small node group
# --------------------------------------------------------------------------- #
OUTLINED_PROP = "rfn_outlined"

# Below this SymPy operation count an expression is compiled inline (it
# then shares sub-expressions with the rest of the tree). Above it, the
# expression goes to its own sub-group so no single tree grows large.
OUTLINE_MIN_OPS = 40
# A sum larger than this is split: each summand becomes its own group.
OUTLINE_SPLIT_OPS = 300


def _count_ops(expr) -> int:
    try:
        return int(expr.count_ops())
    except Exception:
        return 0


def compile_outlined(nb: NodeBuilder, compiler: SymPyCompiler, expr, *,
                     name: str, x=0, y=0, label=""):
    """Compile ``expr`` like ``compiler.compile`` would, but in a hidden
    sub node group when the expression is large.

    Returns a socket (or a float for constants), exactly like
    :meth:`SymPyCompiler.compile`. ``compiler.var_sockets`` provides the
    sockets wired into the sub-group's inputs, one per free symbol.
    """
    n_ops = _count_ops(expr)
    if n_ops < OUTLINE_MIN_OPS or not expr.free_symbols:
        return compiler.compile(expr)

    # Huge sums: one group per summand keeps every tree small.
    if expr.is_Add and n_ops > OUTLINE_SPLIT_OPS:
        parts = [compile_outlined(nb, compiler, a, name=f"{name}.{i}",
                                  x=x, y=y - 40 * i, label=label)
                 for i, a in enumerate(expr.args)]
        return compiler._fold(parts, "ADD")

    syms = sorted(expr.free_symbols, key=lambda s_: s_.name)
    for s_ in syms:
        if s_.name not in compiler.var_sockets:
            raise ValueError(f"Symbole inattendu : {s_.name!r}")

    sub = bpy.data.node_groups.new("." + name, "GeometryNodeTree")
    sub[OUTLINED_PROP] = True
    for s_ in syms:
        sub.interface.new_socket(s_.name, in_out="INPUT",
                                 socket_type="NodeSocketFloat")
    sub.interface.new_socket("Value", in_out="OUTPUT",
                             socket_type="NodeSocketFloat")
    snb = NodeBuilder(sub)
    gin = snb.add("NodeGroupInput", x=-1200, y=0)
    gout = snb.add("NodeGroupOutput", x=600, y=0)
    inner = SymPyCompiler(snb, {s_.name: gin.outputs[i]
                                for i, s_ in enumerate(syms)})
    snb._to_socket(inner.compile(expr), gout.inputs[0])

    node = nb.add("GeometryNodeGroup", x=x, y=y, label=label or name)
    node.node_tree = sub
    for i, s_ in enumerate(syms):
        nb._to_socket(compiler.var_sockets[s_.name], node.inputs[i])
    return node.outputs[0]


def _outlined_children(nt):
    out = []
    for n in nt.nodes:
        sub = getattr(n, "node_tree", None)
        if sub is not None and sub.get(OUTLINED_PROP):
            out.append(sub)
    return out


def release_tree(old, keep=None) -> None:
    """Remove the RealFn tree ``old`` if nothing uses it any more, plus
    the outlined sub-groups that only it referenced.

    Called wherever a modifier gets a freshly rebuilt tree, so repeated
    edits don't pile up orphaned node groups in the .blend.
    """
    if old is None or old is keep:
        return
    try:
        if old.users != 0:
            return
        children = _outlined_children(old)
        bpy.data.node_groups.remove(old)
    except (ReferenceError, RuntimeError):
        return
    for sub in children:
        try:
            if sub.users == 0:
                bpy.data.node_groups.remove(sub)
        except (ReferenceError, RuntimeError):
            pass
