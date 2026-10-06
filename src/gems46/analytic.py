"""Metric algebra that needs no data at all.

In the sparse regime the official index collapses to a two-term budget

    DTI = T / (0.2 * N + 0.8 * |G|)                        (A)

with ``T`` the weighted credit, ``N`` the number of emitted unit-mass dot pixels
and ``|G|`` the scored truth mass.  (A) follows from
``DTI = TPw / (TPw + alpha*FPw + beta*FNw)`` with ``FNw = |G| - TPw`` and
``FPw = N - TPw`` -- both exact identities when no two dots are the best cover
of the same truth pixel, which is the regime a thin dotted raster targets.)

(A) is worth having because it bounds what is *possible*:

    max_N DTI  =  |G| / (0.2*|G| + 0.8*|G|) = 1        (perfect T = |G|, N = |G|)
    DTI  <=  |G| / (0.2*N + 0.8*|G|)   for every N    (since T <= |G|)

The second line is a hard, data-free ceiling: **no submission with N dots can
score above |G| / (0.2N + 0.8|G|)**, whatever model produced it.  It converts an
assumed truth mass into an upper bound on how many dots any competitive file may
carry, which is exactly the constraint a catalogue-truth surrogate cannot see.
"""

from __future__ import annotations


def max_possible_index(n_dots: float, g_mass: float) -> float:
    """Hard ceiling |G| / (0.2 N + 0.8 |G|) -- perfect placement."""
    return g_mass / (0.2 * n_dots + 0.8 * g_mass)


def index_at(n_dots: float, credit: float, g_mass: float) -> float:
    """(A) evaluated at a measured credit."""
    return credit / (0.2 * n_dots + 0.8 * g_mass)


def max_dots_for_target(target: float, g_mass: float) -> float:
    """Largest dot count whose *perfect-placement* ceiling still reaches ``target``."""
    if target >= 1.0:
        return float("inf")
    need = g_mass / target
    return max(0.0, (need - 0.8 * g_mass) / 0.2)


def credit_needed(n_dots: float, g_mass: float, target: float) -> float:
    """Credit required at ``n_dots`` to reach ``target`` under (A)."""
    return target * (0.2 * n_dots + 0.8 * g_mass)
