"""Helpers de parsing sympy partagés entre ``math_core`` (Vector Viewer
simple) et ``composition`` (Composition).

Tous les deux ont besoin :
    - du même namespace ``_SYMPY_LOCALS`` (mêmes fonctions exposées)
    - de la même validation : seul ``t`` est autorisé comme symbole libre,
      et toutes les fonctions appliquées doivent être des fonctions sympy
      connues (pas des AppliedUndef issues d'un identifiant inconnu).

Cette validation au parse est essentielle parce que ``sp.sympify`` accepte
silencieusement tout identifiant absent de ``locals`` en le transformant
en symbole libre ou en AppliedUndef. Sans validation, une faute de frappe
(``cs(t)``), un nom de paramètre (``omega``, ``r0``) ou même une ligne
vide passent le parse, sont lambdifiés sans erreur, et plantent au
premier appel runtime du driver avec ``TypeError: Cannot convert
expression to float`` — totalement illisible.
"""

import sympy as sp


# Symbole temps universel — partagé entre math_core et composition.
T = sp.Symbol('t', real=True)


# Namespace exposé à ``sp.sympify``. Toute fonction/constante manquante
# ici doit être ajoutée explicitement par les deux modules consommateurs
# en propageant l'addition dans ``_SYMPY_LOCALS``.
SYMPY_LOCALS = {
    't': T,
    'pi': sp.pi, 'E': sp.E, 'e': sp.E,
    'cos': sp.cos, 'sin': sp.sin, 'tan': sp.tan,
    'cot': sp.cot, 'sec': sp.sec, 'csc': sp.csc,
    'acos': sp.acos, 'asin': sp.asin, 'atan': sp.atan, 'atan2': sp.atan2,
    'exp': sp.exp, 'log': sp.log, 'ln': sp.log, 'sqrt': sp.sqrt,
    'sinh': sp.sinh, 'cosh': sp.cosh, 'tanh': sp.tanh,
    'Abs': sp.Abs, 'abs': sp.Abs,
}


def parse_expr(text):
    """Parse une chaîne en expression sympy. Lève ``ValueError`` si
    l'expression est vide, syntaxiquement invalide, contient un symbole
    libre autre que ``t``, ou utilise une fonction inconnue.

    Le message d'erreur nomme l'identifiant fautif et liste les
    fonctions/constantes acceptées — feedback actionnable pour
    l'utilisateur.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Expression vide.")
    try:
        expr = sp.sympify(text, locals=SYMPY_LOCALS)
    except (sp.SympifyError, SyntaxError, TypeError, AttributeError,
            ValueError) as e:
        raise ValueError(f"Expression invalide « {text} » : {e}") from e

    # Validation : seul ``t`` autorisé comme symbole libre, et toutes
    # les fonctions appliquées doivent être des fonctions sympy connues.
    free = expr.free_symbols
    extras = free - {T}
    unknown_funcs = {f.func for f in expr.atoms(sp.Function)
                      if isinstance(f, sp.core.function.AppliedUndef)}

    if extras or unknown_funcs:
        bad_names = sorted({str(s) for s in extras}
                            | {str(f) for f in unknown_funcs})
        accepted = ", ".join(sorted(k for k in SYMPY_LOCALS if k != 't'))
        raise ValueError(
            f"Expression « {text} » : identifiant inconnu "
            f"{', '.join(repr(n) for n in bad_names)}. "
            f"Seul « t » est accepté comme variable. "
            f"Fonctions/constantes disponibles : {accepted}."
        )
    return expr
