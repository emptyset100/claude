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
"""

from __future__ import annotations

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
        sp.log: "LOGARITHM",
        sp.Abs: "ABSOLUTE",
        sp.sign: "SIGN",
    }


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

        # π, e → evaluated to float (no need for a Value node).
        if expr in (sp.pi, sp.E):
            return float(expr)

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
        op_map = _function_op_map()
        for fcls, op in op_map.items():
            if isinstance(expr, fcls):
                arg = self.compile(expr.args[0])
                return self.nb.math(op, arg)

        raise ValueError(
            f"Type d'expression non supporté : "
            f"{type(expr).__name__} ({expr})"
        )

    def _fold(self, items, op):
        if not items:
            return 0.0 if op == "ADD" else 1.0
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
