#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: CC-BY-NC-SA-4.0

"""Seed the PeerPedia database with diverse demo data for thorough testing.

Usage:
    python3 seed.py [--db sqlite:///peerpedia.db] [--articles-dir ~/.peerpedia/articles]

Creates 22 users across physics, math, CS, biology, neuroscience, and philosophy.
Produces ~25 articles in all states (published/sedimentation/draft).
Dense follow network (100+ edges), 50+ reviews, 30+ bookmarks.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Standalone -- no path hack needed



def seed(db_url: str, articles_dir: Path):
    import uuid

    from peerpedia_core.storage.db.crud_article import (
        create_article,
        set_sink_start,
        update_article_status,
    )
    from peerpedia_core.storage.db.crud_review import upsert_review
    from peerpedia_core.storage.db.engine import get_engine, init_db
    from peerpedia_core.storage.db.models import (
        Article,
        ArticleAuthor,
        Bookmark,
        Citation,
        Follow,
        Review,
        User,
    )
    from peerpedia_core.storage.git_backend import (
        commit_article,
        init_article_repo,
    )

    engine = get_engine(db_url)
    init_db(engine)
    from peerpedia_core.storage.db.engine import get_session

    session = get_session(engine)

    print(f"Seeding database: {db_url}")
    print(f"Articles directory: {articles_dir}")

    import bcrypt

    default_password = "666666"

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. Users — 22 diverse researchers
    # ═══════════════════════════════════════════════════════════════════════════

    user_defs = [
        # Physics — relativity / quantum foundations
        {
            "name": "Albert Einstein",
            "affiliation": "Princeton",
            "expertise": ["physics", "relativity", "quantum foundations"],
        },
        {
            "name": "Richard Feynman",
            "affiliation": "Caltech",
            "expertise": ["physics", "quantum electrodynamics", "path integrals"],
        },
        {
            "name": "Subrahmanyan Chandrasekhar",
            "affiliation": "Chicago",
            "expertise": ["astrophysics", "stellar dynamics", "relativity"],
        },
        # Quantum mechanics — Copenhagen school
        {
            "name": "Niels Bohr",
            "affiliation": "Copenhagen",
            "expertise": ["quantum mechanics", "atomic structure", "complementarity"],
        },
        {
            "name": "Werner Heisenberg",
            "affiliation": "Leipzig",
            "expertise": ["quantum mechanics", "matrix mechanics", "uncertainty principle"],
        },
        {
            "name": "Erwin Schrödinger",
            "affiliation": "Vienna",
            "expertise": ["quantum mechanics", "wave mechanics", "statistical physics"],
        },
        {
            "name": "Paul Dirac",
            "affiliation": "Cambridge",
            "expertise": ["quantum mechanics", "relativistic quantum theory", "mathematical physics"],
        },
        {
            "name": "Max Born",
            "affiliation": "Göttingen",
            "expertise": ["quantum mechanics", "probability interpretation", "lattice dynamics"],
        },
        # Mathematics
        {
            "name": "Emmy Noether",
            "affiliation": "Bryn Mawr",
            "expertise": ["mathematics", "abstract algebra", "mathematical physics"],
        },
        {
            "name": "Ada Lovelace",
            "affiliation": "London",
            "expertise": ["mathematics", "computing", "philosophy of science"],
        },
        {
            "name": "John von Neumann",
            "affiliation": "IAS Princeton",
            "expertise": ["mathematics", "game theory", "computing", "quantum foundations"],
        },
        # Computer science
        {
            "name": "Alan Turing",
            "affiliation": "Manchester",
            "expertise": ["computer science", "cryptography", "mathematical logic"],
        },
        {
            "name": "Claude Shannon",
            "affiliation": "MIT",
            "expertise": ["information theory", "electrical engineering"],
        },
        {
            "name": "Grace Hopper",
            "affiliation": "US Navy / Harvard",
            "expertise": ["computer science", "compilers", "programming languages"],
        },
        # Chemistry / biology
        {
            "name": "Marie Curie",
            "affiliation": "Sorbonne",
            "expertise": ["chemistry", "radioactivity", "medical physics"],
        },
        {
            "name": "Rosalind Franklin",
            "affiliation": "King's College",
            "expertise": ["biology", "crystallography", "molecular structure"],
        },
        {
            "name": "Dorothy Hodgkin",
            "affiliation": "Oxford",
            "expertise": ["chemistry", "crystallography", "biology"],
        },
        # Neuroscience / neurophysics
        {
            "name": "Francis Crick",
            "affiliation": "Salk Institute",
            "expertise": ["neurobiology", "molecular biology", "consciousness"],
        },
        {
            "name": "Santiago Ramón y Cajal",
            "affiliation": "Madrid",
            "expertise": ["neuroscience", "neuroanatomy", "histology"],
        },
        {
            "name": "Patricia Goldman-Rakic",
            "affiliation": "Yale",
            "expertise": ["neuroscience", "working memory", "prefrontal cortex"],
        },
        # Philosophy
        {
            "name": "Karl Popper",
            "affiliation": "LSE",
            "expertise": ["philosophy of science", "epistemology", "falsificationism"],
        },
        {
            "name": "Thomas Kuhn",
            "affiliation": "MIT",
            "expertise": ["philosophy of science", "history of science", "paradigm theory"],
        },
        {
            "name": "Hilary Putnam",
            "affiliation": "Harvard",
            "expertise": ["philosophy of mind", "philosophy of language", "philosophy of science"],
        },
    ]

    pwd_hash = bcrypt.hashpw(default_password.encode(), bcrypt.gensalt()).decode()
    users = {}
    for u in user_defs:
        existing = session.query(User).filter(User.name == u["name"]).first()
        if existing:
            users[u["name"]] = existing
            print(f"  User (existing): {u['name']} ({u['name']})")
        else:
            user = User(
                id=str(uuid.uuid4()),
                
                password_hash=pwd_hash,
                email=f"{u['name']}@peerpedia.dev",
                name=u["name"],
                affiliation=u["affiliation"],
                expertise=u["expertise"],
                reputation={"professionalism": 4.0, "objectivity": 4.0, "collaboration": 4.0, "pedagogy": 4.0},
            )
            session.add(user)
            session.commit()
            users[u["name"]] = user
            print(f"  User (new): {u['name']} ({u['name']})")

    print(f"\n  Default password for all users: {default_password}")
    print(f"  Total users: {len(users)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. Follow network — dense, cross-discipline (~100 edges)
    # ═══════════════════════════════════════════════════════════════════════════

    follow_pairs = [
        # Einstein — physics circle
        ("Albert Einstein", "Richard Feynman"),
        ("Albert Einstein", "Niels Bohr"),
        ("Albert Einstein", "Werner Heisenberg"),
        ("Albert Einstein", "Erwin Schrödinger"),
        ("Albert Einstein", "Paul Dirac"),
        ("Albert Einstein", "Subrahmanyan Chandrasekhar"),
        ("Albert Einstein", "Emmy Noether"),
        ("Albert Einstein", "Max Born"),
        # Feynman
        ("Richard Feynman", "Albert Einstein"),
        ("Richard Feynman", "Niels Bohr"),
        ("Richard Feynman", "Paul Dirac"),
        ("Richard Feynman", "Subrahmanyan Chandrasekhar"),
        ("Richard Feynman", "John von Neumann"),
        ("Richard Feynman", "Max Born"),
        # Bohr — Copenhagen network
        ("Niels Bohr", "Albert Einstein"),
        ("Niels Bohr", "Werner Heisenberg"),
        ("Niels Bohr", "Erwin Schrödinger"),
        ("Niels Bohr", "Paul Dirac"),
        ("Niels Bohr", "Max Born"),
        ("Niels Bohr", "Richard Feynman"),
        ("Niels Bohr", "Karl Popper"),
        # Heisenberg
        ("Werner Heisenberg", "Niels Bohr"),
        ("Werner Heisenberg", "Erwin Schrödinger"),
        ("Werner Heisenberg", "Paul Dirac"),
        ("Werner Heisenberg", "Max Born"),
        ("Werner Heisenberg", "Albert Einstein"),
        ("Werner Heisenberg", "Karl Popper"),
        # Schrödinger — broad interests (physics + philosophy + biology)
        ("Erwin Schrödinger", "Niels Bohr"),
        ("Erwin Schrödinger", "Werner Heisenberg"),
        ("Erwin Schrödinger", "Paul Dirac"),
        ("Erwin Schrödinger", "Karl Popper"),
        ("Erwin Schrödinger", "Thomas Kuhn"),
        ("Erwin Schrödinger", "Francis Crick"),
        ("Erwin Schrödinger", "Albert Einstein"),
        # Dirac — mathematical physics
        ("Paul Dirac", "Niels Bohr"),
        ("Paul Dirac", "Erwin Schrödinger"),
        ("Paul Dirac", "John von Neumann"),
        ("Paul Dirac", "Emmy Noether"),
        ("Paul Dirac", "Albert Einstein"),
        # Born
        ("Max Born", "Niels Bohr"),
        ("Max Born", "Werner Heisenberg"),
        ("Max Born", "Erwin Schrödinger"),
        ("Max Born", "Paul Dirac"),
        ("Max Born", "John von Neumann"),
        # Chandrasekhar
        ("Subrahmanyan Chandrasekhar", "Albert Einstein"),
        ("Subrahmanyan Chandrasekhar", "Richard Feynman"),
        ("Subrahmanyan Chandrasekhar", "Paul Dirac"),
        ("Subrahmanyan Chandrasekhar", "Marie Curie"),
        # Curie
        ("Marie Curie", "Rosalind Franklin"),
        ("Marie Curie", "Dorothy Hodgkin"),
        ("Marie Curie", "Emmy Noether"),
        ("Marie Curie", "Albert Einstein"),
        ("Marie Curie", "Niels Bohr"),
        # Turing
        ("Alan Turing", "Ada Lovelace"),
        ("Alan Turing", "Claude Shannon"),
        ("Alan Turing", "John von Neumann"),
        ("Alan Turing", "Grace Hopper"),
        ("Alan Turing", "Emmy Noether"),
        ("Alan Turing", "Karl Popper"),
        # Lovelace
        ("Ada Lovelace", "Alan Turing"),
        ("Ada Lovelace", "Grace Hopper"),
        ("Ada Lovelace", "Emmy Noether"),
        ("Ada Lovelace", "John von Neumann"),
        ("Ada Lovelace", "Hilary Putnam"),
        # Noether
        ("Emmy Noether", "Albert Einstein"),
        ("Emmy Noether", "John von Neumann"),
        ("Emmy Noether", "Ada Lovelace"),
        ("Emmy Noether", "Alan Turing"),
        ("Emmy Noether", "Claude Shannon"),
        ("Emmy Noether", "Paul Dirac"),
        # Shannon
        ("Claude Shannon", "Alan Turing"),
        ("Claude Shannon", "John von Neumann"),
        ("Claude Shannon", "Grace Hopper"),
        ("Claude Shannon", "Ada Lovelace"),
        # Franklin
        ("Rosalind Franklin", "Marie Curie"),
        ("Rosalind Franklin", "Dorothy Hodgkin"),
        ("Rosalind Franklin", "Francis Crick"),
        ("Rosalind Franklin", "Santiago Ramón y Cajal"),
        # von Neumann
        ("John von Neumann", "Alan Turing"),
        ("John von Neumann", "Claude Shannon"),
        ("John von Neumann", "Emmy Noether"),
        ("John von Neumann", "Albert Einstein"),
        ("John von Neumann", "Richard Feynman"),
        ("John von Neumann", "Grace Hopper"),
        ("John von Neumann", "Paul Dirac"),
        # Hodgkin
        ("Dorothy Hodgkin", "Marie Curie"),
        ("Dorothy Hodgkin", "Rosalind Franklin"),
        ("Dorothy Hodgkin", "Ada Lovelace"),
        ("Dorothy Hodgkin", "Francis Crick"),
        # Hopper
        ("Grace Hopper", "Alan Turing"),
        ("Grace Hopper", "Ada Lovelace"),
        ("Grace Hopper", "Claude Shannon"),
        ("Grace Hopper", "John von Neumann"),
        ("Grace Hopper", "Hilary Putnam"),
        # Crick — biology ↔ physics/philosophy bridge
        ("Francis Crick", "Erwin Schrödinger"),
        ("Francis Crick", "Rosalind Franklin"),
        ("Francis Crick", "Santiago Ramón y Cajal"),
        ("Francis Crick", "Patricia Goldman-Rakic"),
        ("Francis Crick", "Hilary Putnam"),
        ("Francis Crick", "Karl Popper"),
        # Cajal
        ("Santiago Ramón y Cajal", "Francis Crick"),
        ("Santiago Ramón y Cajal", "Patricia Goldman-Rakic"),
        ("Santiago Ramón y Cajal", "Hilary Putnam"),
        ("Santiago Ramón y Cajal", "Rosalind Franklin"),
        # Goldman-Rakic
        ("Patricia Goldman-Rakic", "Francis Crick"),
        ("Patricia Goldman-Rakic", "Santiago Ramón y Cajal"),
        ("Patricia Goldman-Rakic", "Hilary Putnam"),
        ("Patricia Goldman-Rakic", "John von Neumann"),
        # Popper
        ("Karl Popper", "Thomas Kuhn"),
        ("Karl Popper", "Hilary Putnam"),
        ("Karl Popper", "Albert Einstein"),
        ("Karl Popper", "Niels Bohr"),
        ("Karl Popper", "Werner Heisenberg"),
        ("Karl Popper", "Alan Turing"),
        # Kuhn
        ("Thomas Kuhn", "Karl Popper"),
        ("Thomas Kuhn", "Hilary Putnam"),
        ("Thomas Kuhn", "Erwin Schrödinger"),
        ("Thomas Kuhn", "Ada Lovelace"),
        # Putnam
        ("Hilary Putnam", "Karl Popper"),
        ("Hilary Putnam", "Thomas Kuhn"),
        ("Hilary Putnam", "Alan Turing"),
        ("Hilary Putnam", "Francis Crick"),
        ("Hilary Putnam", "John von Neumann"),
    ]

    follow_count = 0
    for fn, ted in follow_pairs:
        f = (
            session.query(Follow)
            .filter(
                Follow.follower_id == users[fn].id,
                Follow.followed_id == users[ted].id,
            )
            .first()
        )
        if not f:
            session.add(Follow(follower_id=users[fn].id, followed_id=users[ted].id))
            follow_count += 1
    session.commit()
    print(f"  Follows: {follow_count} new")

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. Articles — 26 across all statuses
    # ═══════════════════════════════════════════════════════════════════════════

    article_defs = [
        # ── Published (11) ───────────────────────────────────────────────────
        {
            "title": "On the Electrodynamics of Moving Bodies",
            "author": "Albert Einstein",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 4.5, "completeness": 4.0, "pedagogy": 3.5, "impact": 5.0},
            "content": """# On the Electrodynamics of Moving Bodies
## Abstract
It is known that Maxwell's electrodynamics—when applied to moving bodies, leads to
asymmetries which do not appear to be inherent in the phenomena.
## Kinematical Part
Take a system of coordinates in which Newtonian mechanics hold good.
$$
E = mc^2
$$
This mass-energy equivalence formula follows from the special theory of relativity.""",
        },
        {
            "title": "The Quantum Theory of the Emission and Absorption of Radiation",
            "author": "Paul Dirac",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 5.0, "pedagogy": 4.0, "impact": 5.0},
            "content": """# The Quantum Theory of Emission and Absorption
## Abstract
A fully quantum-mechanical treatment of the interaction between matter and the
electromagnetic field, introducing second quantization.
## Theory
The Hamiltonian for the coupled atom-field system is:
$$
H = H_0 + H_{\\text{int}} = \\sum_k \\hbar\\omega_k a_k^\\dagger a_k + H_{\\text{atom}} + e\\mathbf{r}\\cdot\\mathbf{E}
$$
This yields spontaneous emission as a natural consequence of field quantization.""",
        },
        {
            "title": "On the Constitution of Atoms and Molecules",
            "author": "Niels Bohr",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 4.5, "completeness": 4.0, "pedagogy": 4.5, "impact": 5.0},
            "content": """# On the Constitution of Atoms and Molecules
## Abstract
In order to explain the stability of atoms and the Balmer spectrum of hydrogen, we
propose a model in which electrons move in stationary orbits with quantized angular
momentum.
## The Bohr Model
$$
L = n\\hbar, \\quad E_n = -\\frac{me^4}{8\\epsilon_0^2 h^2}\\frac{1}{n^2}
$$
The transition between states $n \\to m$ emits a photon of frequency $\\nu = (E_n - E_m)/h$.""",
        },
        {
            "title": "The Physical Principles of the Quantum Theory",
            "author": "Werner Heisenberg",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 4.0, "impact": 5.0},
            "content": """# The Physical Principles of the Quantum Theory
## Abstract
The uncertainty principle sets a fundamental limit on the precision with which
canonically conjugate variables can be simultaneously known.
## The Uncertainty Principle
$$
\\Delta x \\cdot \\Delta p \\geq \\frac{\\hbar}{2}
$$
This is not a limitation of measurement apparatus but a fundamental feature of
quantum reality. Matrix mechanics provides the natural mathematical framework.""",
        },
        {
            "title": "Quantization as an Eigenvalue Problem",
            "author": "Erwin Schrödinger",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 5.0, "impact": 5.0},
            "content": """# Quantization as an Eigenvalue Problem
## Abstract
A wave equation for the hydrogen atom yields the correct energy levels without ad hoc
quantization rules. The electron is described by a wavefunction $\\psi(\\mathbf{r}, t)$.
## The Schrödinger Equation
$$
i\\hbar\\frac{\\partial\\psi}{\\partial t} = -\\frac{\\hbar^2}{2m}\\nabla^2\\psi + V(\\mathbf{r})\\psi
$$
The stationary states are eigenfunctions of the Hamiltonian operator.""",
        },
        {
            "title": "On the Quantum Mechanics of Collisions",
            "author": "Max Born",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 4.5, "completeness": 4.0, "pedagogy": 4.5, "impact": 5.0},
            "content": """# On the Quantum Mechanics of Collisions
## Abstract
The wavefunction $\\psi$ does not determine the exact outcome of a collision, but
rather the probability of each possible outcome.
## Born's Rule
$$
P(a \\leq x \\leq b) = \\int_a^b |\\psi(x)|^2 \\, dx
$$
The square of the modulus of the wavefunction gives the probability density.
Quantum mechanics makes only statistical predictions about individual events.""",
        },
        {
            "title": "The Space Distribution of the Photo-Electric Effect",
            "author": "Marie Curie",
            "status": "published",
            "score": {"originality": 4.5, "rigor": 5.0, "completeness": 4.5, "pedagogy": 4.0, "impact": 4.5},
            "content": """# The Space Distribution of the Photo-Electric Effect
## Introduction
Radioactive substances reveal properties of electron emission under electromagnetic
radiation.
$$
I = I_0 e^{-\\alpha x}
$$
The absorption coefficient $\\alpha$ is proportional to the atomic number.""",
        },
        {
            "title": "The Maximum Mass of Ideal White Dwarfs",
            "author": "Subrahmanyan Chandrasekhar",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 5.0, "pedagogy": 4.5, "impact": 5.0},
            "content": """# The Maximum Mass of Ideal White Dwarfs
## Abstract
Degenerate stellar matter predicts a limiting mass: $M_{Ch} \\approx 1.44 M_\\odot$.
## Equation of State
$$
P = K \\rho^{5/3} \\quad \\text{(non-relativistic)}, \\quad P = K' \\rho^{4/3} \\quad \\text{(ultra-relativistic)}
$$
The Chandrasekhar limit defines the boundary between white dwarfs and neutron stars.""",
        },
        {
            "title": "X-Ray Crystallography of Vitamin B12",
            "author": "Dorothy Hodgkin",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 4.5, "impact": 5.0},
            "content": """# X-Ray Crystallography of Vitamin B12
## Abstract
The three-dimensional structure of vitamin B12 reveals a corrin ring system with a
central cobalt atom.
## Structure Solution
$$
P(uvw) = \\frac{1}{V} \\sum_{hkl} |F_{hkl}|^2 \\cos[2\\pi(hu + kv + lw)]
$$
The complete structure comprises approximately 180 non-hydrogen atoms.""",
        },
        {
            "title": "The Compiler: A Theory of Program Translation",
            "author": "Grace Hopper",
            "status": "published",
            "score": {"originality": 4.5, "rigor": 4.0, "completeness": 4.0, "pedagogy": 5.0, "impact": 5.0},
            "content": """# The Compiler: A Theory of Program Translation
## Abstract
A compiler translates source code into machine code via lexical analysis, parsing,
and code generation.
$$
G = (V, \\Sigma, R, S)
$$
Register allocation is equivalent to graph coloring of the interference graph.""",
        },
        {
            "title": "Theory of Games and Economic Behavior",
            "author": "John von Neumann",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 4.0, "impact": 5.0},
            "content": """# Theory of Games and Economic Behavior
## Abstract
A mathematical theory of strategic interaction based on the minimax theorem.
## The Minimax Theorem
$$
\\max_p \\min_q \\, p^T M q = \\min_q \\max_p \\, p^T M q = V
$$
Every finite zero-sum game has a well-defined value under randomized strategies.""",
        },
        # ── Sedimentation (10) ───────────────────────────────────────────────
        {
            "title": "Notes on Quantum Electrodynamics",
            "author": "Richard Feynman",
            "status": "sedimentation",
            "sink_days": 3,
            "score": {"originality": 5.0, "rigor": 4.0, "completeness": 3.5, "pedagogy": 5.0, "impact": 5.0},
            "content": """# Notes on Quantum Electrodynamics
## Abstract
Path integrals and diagrams for particle interactions.
$$
K(b, a) = \\int \\mathcal{D}x(t)\\, e^{iS[x]/\\hbar}
$$
$$
\\mathcal{M} = \\bar{u}(p')\\gamma^\\mu u(p) \\cdot \\frac{-ig_{\\mu\\nu}}{q^2} \\cdot \\bar{u}(k')\\gamma^\\nu u(k)
$$""",
        },
        {
            "title": "On Computable Numbers, with an Application to the Entscheidungsproblem",
            "author": "Alan Turing",
            "status": "sedimentation",
            "sink_days": 5,
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 3.0, "impact": 5.0},
            "content": """# On Computable Numbers
## Abstract
The "computable" numbers may be described briefly as the real numbers whose
expressions as a decimal are calculable by finite means.
$$
\\lambda = \\sum_{n=1}^{\\infty} \\frac{1}{2^n}
$$
The halting problem demonstrates that there exist well-defined problems that
cannot be solved by any mechanical procedure.""",
        },
        {
            "title": "The Structure of DNA: A Molecular Model",
            "author": "Rosalind Franklin",
            "status": "sedimentation",
            "sink_days": 7,
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.0, "pedagogy": 4.5, "impact": 5.0},
            "content": """# The Structure of DNA
## Abstract
X-ray crystallography reveals the double-helical structure of DNA.
$$
\\text{A—T, G—C}
$$
The sugar-phosphate backbone forms the exterior with base pairs stacked inside at
3.4 Å intervals. Specific base pairings ensure fidelity of genetic replication.""",
        },
        {
            "title": "Invariant Theory and Conservation Laws",
            "author": "Emmy Noether",
            "status": "sedimentation",
            "sink_days": 4,
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.0, "pedagogy": 4.0, "impact": 5.0},
            "content": """# Invariant Theory and Conservation Laws
## Abstract
Every differentiable symmetry corresponds to a conservation law.
$$
\\frac{d}{dt}\\left(\\frac{\\partial L}{\\partial \\dot{q}_i} \\delta q_i\\right) = 0
$$
Energy conservation from time symmetry, momentum from translation, angular momentum
from rotation—all derived from a single theorem.""",
        },
        {
            "title": "Idealist Philosophy in the Foundations of Mathematics",
            "author": "Ada Lovelace",
            "status": "sedimentation",
            "sink_days": 6,
            "score": {"originality": 4.5, "rigor": 3.5, "completeness": 3.5, "pedagogy": 5.0, "impact": 4.0},
            "content": """# Idealist Philosophy in the Foundations of Mathematics
## Abstract
The Analytical Engine weaves algebraic patterns as the Jacquard loom weaves flowers.
$$
\\int_a^b f(x)\\,dx = \\lim_{n \\to \\infty} \\sum_{i=1}^n f(x_i)\\Delta x
$$
The bounds of arithmetic are not the bounds of imagination.""",
        },
        {
            "title": "The Logico-Philosophicus: Meaning, Truth, and the Limits of Language",
            "author": "Karl Popper",
            "status": "sedimentation",
            "sink_days": 5,
            "score": {"originality": 4.5, "rigor": 4.0, "completeness": 4.0, "pedagogy": 4.0, "impact": 4.5},
            "content": """# Meaning, Truth, and the Limits of Language
## Abstract
Scientific theories cannot be verified, only falsified. The demarcation between
science and non-science is falsifiability.
## Falsificationism
$$
\\text{If } T \\implies O \\text{ and } \\neg O \\text{ then } \\neg T
$$
A theory that explains everything explains nothing. The growth of knowledge proceeds
through conjecture and refutation, not induction.""",
        },
        {
            "title": "The Structure of Scientific Revolutions: Paradigm Shifts in Theory Change",
            "author": "Thomas Kuhn",
            "status": "sedimentation",
            "sink_days": 6,
            "score": {"originality": 5.0, "rigor": 4.0, "completeness": 4.5, "pedagogy": 5.0, "impact": 5.0},
            "content": """# The Structure of Scientific Revolutions
## Abstract
Science does not progress through linear accumulation of knowledge, but through
periodic paradigm shifts that restructure the entire conceptual framework.
## Paradigm Theory
Normal science operates within an accepted paradigm—a constellation of theories,
methods, and exemplars. Anomalies accumulate until a crisis triggers a revolutionary
shift to an incommensurable new paradigm. The shift from Ptolemaic to Copernican
astronomy, and from Newtonian to relativistic physics, exemplify this pattern.""",
        },
        {
            "title": "The Astonishing Hypothesis: A Neurobiological Theory of Consciousness",
            "author": "Francis Crick",
            "status": "sedimentation",
            "sink_days": 4,
            "score": {"originality": 4.5, "rigor": 3.5, "completeness": 3.5, "pedagogy": 5.0, "impact": 4.5},
            "content": """# The Astonishing Hypothesis
## Abstract
Consciousness is a product of neural activity—specifically, synchronized oscillations
in the 40 Hz range binding distributed cortical representations.
## The Binding Problem
How does the brain integrate visual features processed in separate cortical areas into
a unified percept? The hypothesis: transient synchrony of neuronal firing across
distributed networks creates a coherent representation from fragmentary inputs.
Consciousness is not a single locus but a dynamic coalition of neurons.""",
        },
        {
            "title": "Texture of the Nervous System: The Neuron Doctrine",
            "author": "Santiago Ramón y Cajal",
            "status": "sedimentation",
            "sink_days": 3,
            "score": {"originality": 5.0, "rigor": 4.5, "completeness": 4.0, "pedagogy": 4.0, "impact": 5.0},
            "content": """# The Neuron Doctrine
## Abstract
The nervous system is composed of discrete cells—neurons—that communicate via
specialized junctions. This is the foundation of modern neuroscience.
## Histological Evidence
Using Golgi's silver chromate stain, individual neurons are revealed in their entirety:
dendrites, cell body, and axon. Neurons are anatomically and functionally independent
units. Information flows from dendrite to axon, across the synapse—a one-way valve
of nervous transmission.""",
        },
        {
            "title": "Working Memory: The Prefrontal Cortex and the Architecture of Mind",
            "author": "Patricia Goldman-Rakic",
            "status": "sedimentation",
            "sink_days": 5,
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 4.5, "impact": 5.0},
            "content": """# Working Memory and the Prefrontal Cortex
## Abstract
The dorsolateral prefrontal cortex maintains task-relevant information online through
persistent neuronal firing during the delay period of working memory tasks.
## Modular Organization
The prefrontal cortex is organized into functionally specialized modules—not a
homogeneous mass. Each module maintains domain-specific representations (spatial,
object, verbal) in reverberating circuits. Dopamine D1 receptor stimulation modulates
these persistent states, connecting neuromodulation to cognitive function.""",
        },
        # ── Draft (5) ────────────────────────────────────────────────────────
        {
            "title": "A Mathematical Theory of Communication",
            "author": "Claude Shannon",
            "status": "draft",
            "score": None,
            "content": """# A Mathematical Theory of Communication
## Abstract
The fundamental problem of communication is reproducing a message at another point.
$$
H = -K \\sum_{i=1}^{n} p_i \\log p_i, \\quad C = \\max_{P(x)} I(X; Y)
$$
Channel capacity sets the theoretical maximum rate of reliable communication.""",
        },
        {
            "title": "What Is It Like to Be a Bat? Phenomenology and the Hard Problem",
            "author": "Thomas Kuhn",
            "status": "draft",
            "score": None,
            "content": """# What Is It Like to Be a Bat?
## Abstract
The subjective character of experience—what it feels like—cannot be captured by any
physicalist account of the mind. This is "the hard problem of consciousness."
## The Explanatory Gap
Echolocation gives bats a form of experience utterly alien to humans. No amount of
neurophysiological data about bat sonar processing can tell us what it is *like* to
perceive the world through echolocation. There is an irreducible subjective ontology
that defies third-person reduction.""",
        },
        {
            "title": "Brains in Vats and Semantic Externalism",
            "author": "Hilary Putnam",
            "status": "draft",
            "score": None,
            "content": """# Brains in Vats and Semantic Externalism
## Abstract
"Meanings just ain't in the head." The reference of our words depends on causal
interaction with the external world, not on internal mental states alone.
## The Twin Earth Argument
If "water" on Twin Earth is XYZ (not H2O), and Oscar's internal state is identical to
Twin Oscar's, yet their word "water" refers to different substances, then meaning is
not determined solely by what is inside the head. A brain in a vat cannot refer to
real objects because it lacks the right causal connections to them.""",
        },
        {
            "title": "Quantum Entanglement and the EPR Paradox: A Reassessment",
            "author": "Niels Bohr",
            "status": "draft",
            "score": None,
            "content": """# Quantum Entanglement and the EPR Paradox
## Abstract
The Einstein-Podolsky-Rosen argument does not reveal an incompleteness in quantum
mechanics but rather the inadequacy of classical intuitions about locality.
## Complementarity and Nonlocality
$$
|\\Psi\\rangle = \\frac{1}{\\sqrt{2}}(|\\uparrow\\downarrow\\rangle - |\\downarrow\\uparrow\\rangle)
$$
Measurement on one particle instantaneously determines the state of its entangled
partner. This is not action-at-a-distance but the consequence of a single quantum
state describing the composite system. Separability is classical, not quantum.""",
        },
        {
            "title": "Relativistic Hydrodynamics and Stellar Pulsation",
            "author": "Subrahmanyan Chandrasekhar",
            "status": "draft",
            "score": None,
            "content": """# Relativistic Hydrodynamics and Stellar Pulsation
## Abstract
Classical stellar pulsation theory extended to general relativity.
$$
T^{\\mu\\nu} = (\\rho + p) u^\\mu u^\\nu + p g^{\\mu\\nu}
$$
Coupled with Einstein's field equations for the Tolman-Oppenheimer-Volkoff equation.""",
        },
        # ── Multi-author (2) ─────────────────────────────────────────────────
        {
            "title": "The Copenhagen Interpretation: A Joint Statement on Complementarity",
            "author": "Niels Bohr",
            "co_authors": ["Werner Heisenberg"],
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 4.0, "impact": 5.0},
            "content": """# The Copenhagen Interpretation
## Abstract
We present a unified statement of the Copenhagen interpretation of quantum mechanics,
based on the principle of complementarity and the uncertainty relations.
## Complementarity
Wave and particle descriptions are complementary—not contradictory. Each description
is necessary for a complete account of quantum phenomena, yet they cannot be applied
simultaneously. The uncertainty principle $$\\Delta x \\Delta p \\geq \\hbar/2$$ is not
a limitation of measurement but a fundamental feature of nature.""",
        },
        {
            "title": "The Double Helix: Molecular Structure of Deoxyribonucleic Acid",
            "author": "Rosalind Franklin",
            "co_authors": ["Francis Crick"],
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 5.0, "pedagogy": 4.5, "impact": 5.0},
            "content": """# The Double Helix
## Abstract
We propose a double-helical structure for DNA with antiparallel sugar-phosphate
backbones and complementary base pairing (A-T, G-C).
## Structural Evidence
X-ray diffraction shows a 3.4 Å spacing between bases and a complete turn every 34 Å.
Chargaff's rules dictate adenine-thymine and guanine-cytosine pairing via hydrogen bonds.
This structure immediately suggests a mechanism for replication: each strand serves
as a template for its complement.""",
        },
        # ── Chinese content (3) ────────────────────────────────────────────────
        {
            "title": "量子纠缠的本质：从EPR佯谬到贝尔不等式",
            "author": "John von Neumann",
            "status": "published",
            "score": {"originality": 4.5, "rigor": 5.0, "completeness": 4.0, "pedagogy": 5.0, "impact": 4.5},
            "content": """# 量子纠缠的本质
## 摘要
从爱因斯坦-波多尔斯基-罗森佯谬出发，系统分析量子非定域性的理论基础，
并推导贝尔不等式的完整形式。
## 引言
薛定谔在1935年首次提出"量子纠缠"（Verschränkung）这一概念，认为这是
量子力学区别于经典物理学的核心特征。纠缠态描述了两个或多个粒子之间
的关联，这种关联超越了经典统计力学的范畴。
$$
|\\Psi^+\\rangle = \\frac{1}{\\sqrt{2}}(|01\\rangle + |10\\rangle)
$$
## EPR论证
爱因斯坦、波多尔斯基和罗森提出了一个著名的思想实验：如果量子力学是完备的，
那么对一个粒子的测量不应瞬间影响远处的另一个粒子。然而量子力学的预测违反了
这一直觉。""",
        },
        {
            "title": "哥德尔不完备定理的哲学意涵",
            "author": "Alan Turing",
            "status": "published",
            "score": {"originality": 5.0, "rigor": 5.0, "completeness": 4.5, "pedagogy": 5.0, "impact": 4.5},
            "content": """# 哥德尔不完备定理的哲学意涵
## 摘要
哥德尔的不完备性定理不仅对数学基础产生深远影响，更引发了关于心智本质、
人工智能极限以及真理与证明之间关系的哲学讨论。
## 定理概述
任何包含初等算术的一致形式系统，如果它是可递归公理化的，则存在该系统内
既不能证明也不能否证的命题。这意味着：
1. 不存在能够证明所有算术真理的形式系统
2. 系统的一致性不能在系统内部被证明
## 图灵机的视角
不完备性与停机问题的不可判定性之间存在深刻的对应关系。如果存在一个算法
能够判定所有数学命题的真假，那么停机问题就是可判定的——但这已被证明是
不可能的。""",
        },
        {
            "title": "信息论基础及其在认知科学中的应用",
            "author": "Claude Shannon",
            "status": "sedimentation",
            "sink_days": 4,
            "score": {"originality": 4.5, "rigor": 5.0, "completeness": 4.0, "pedagogy": 4.5, "impact": 4.5},
            "content": """# 信息论基础及其在认知科学中的应用
## 摘要
香农信息论为量化不确定性提供了数学框架。本文探讨信息熵在认知科学中的
应用潜力——从知觉处理到决策理论。
## 信息度量的基础
$$
H(X) = -\\sum_{i=1}^{n} p_i \\log_2 p_i
$$
信息熵度量了随机变量的不确定性。比特（bit）是信息的基本单位，
表示一个二元决策所需的信息量。""",
        },
    ]

    articles_created = 0
    for ad in article_defs:
        author = users[ad["author"]]
        co_author_ids = [users[name].id for name in ad.get("co_authors", [])]
        all_authors = [author.id] + co_author_ids
        existing = session.query(Article).filter(Article.title == ad["title"]).first()
        if existing:
            print(f"  Article (existing): {ad['title'][:55]}...")
            continue

        a = create_article(session, authors=all_authors, status="draft", title=ad["title"])

        try:
            rp = init_article_repo(articles_dir / a.id)
            (rp / "article.md").write_text(ad["content"])
            commit_article(rp, "Initial submission", author.name, f"{author.id}@peerpedia")
            # Write co-author attribution commits so git-derived authors
            # can recover the full author list on repair/rebuild.
            for co_author_id in co_author_ids:
                co = session.get(User, co_author_id)
                commit_article(
                    rp,
                    f"Co-author: {co.name}",
                    co.name,
                    f"{co.id}@peerpedia",
                )
        except Exception as e:
            print(f"  Warning: git repo for {ad['title'][:40]} failed: {e}")

        status = ad["status"]
        if status == "sedimentation":
            sink_days = ad.get("sink_days", 7)
            elapsed = 7 - sink_days
            if elapsed > 0:
                st = datetime.now(timezone.utc) - timedelta(days=elapsed)
                a.status = "sedimentation"
                a.sink_start = st
                a.sink_duration_days = sink_days + elapsed
                session.commit()
            else:
                a = set_sink_start(session, a.id, sink_days)
        elif status == "published":
            a = update_article_status(session, a.id, "published")

        if ad.get("score"):
            a.score = ad["score"]
            session.commit()

        if ad.get("score"):
            scope = "pool" if status == "sedimentation" else "published"
            try:
                upsert_review(
                    session,
                    article_id=a.id,
                    commit_hash="0000000000000000000000000000000000000000",
                    reviewer_id=author.id,
                    scope=scope,
                    scores=ad["score"],
                )
            except Exception:
                pass

        articles_created += 1
        print(f"  Article (new): {ad['title'][:55]}... [{status}]")

    a_articles = session.query(Article).all()
    # Batch-resolve article authors from the join table
    all_article_ids = [a.id for a in a_articles]
    from peerpedia_core.storage.db.crud_article import get_author_ids_batch

    author_id_map = get_author_ids_batch(session, all_article_ids)
    article_map = {}
    for a in a_articles:
        author_name = None
        for name, user in users.items():
            if user.id in author_id_map.get(a.id, []):
                author_name = name
                break
        if author_name:
            article_map[author_name] = article_map.get(author_name, []) + [a]

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. Forks — cross-user forks with edit commits
    # ═══════════════════════════════════════════════════════════════════════════

    fork_specs = [
        # Feynman forks Einstein's relativity paper
        (
            "Richard Feynman",
            "Albert Einstein",
            """# On the Electrodynamics of Moving Bodies — Feynman's Extension
## Added: Path Integral Perspective
The Lorentz transformations can be derived from a path-integral formulation
of classical electrodynamics. The action principle $$S = -mc \\int ds$$ for a
free particle is invariant under Lorentz transformations by construction.
This approach makes the connection to quantum mechanics transparent.""",
            {"originality": 4.5, "rigor": 4.0, "completeness": 3.5, "pedagogy": 5.0, "impact": 4.0},
        ),
        # Von Neumann forks Turing's computability paper
        (
            "John von Neumann",
            "Alan Turing",
            """# On Computable Numbers — Architecture for a Stored-Program Machine
## Added: Hardware Implementation
Turing's universal machine provides the theoretical foundation. We extend this
with a concrete architecture: a central arithmetic unit, a control unit that
fetches and decodes instructions, and a random-access memory that stores both
program and data. This is the von Neumann architecture.""",
            {"originality": 5.0, "rigor": 5.0, "completeness": 4.0, "pedagogy": 4.0, "impact": 5.0},
        ),
    ]

    fork_map = {}  # forker_name → {"fork": Article, "parent": Article}
    for forker_name, parent_name, content, score in fork_specs:
        forker = users[forker_name]
        parent = article_map.get(parent_name, [None])[0]
        if parent is None:
            print(f"  Fork skipped: parent {parent_name} not found")
            continue
        existing = (
            session.query(Article)
            .join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
            .filter(Article.forked_from == parent.id, ArticleAuthor.author_id == forker.id)
            .first()
        )
        if existing:
            print(f"  Fork (existing): {forker_name} → {parent.title[:30]}...")
            fork_map[forker_name] = existing
            continue

        fork = create_article(
            session, authors=[forker.id], status="draft", title=f"{parent.title} — Fork by {forker_name}", forked_from=parent.id
        )
        try:
            rp = init_article_repo(articles_dir / fork.id)
            (rp / "article.md").write_text(content)
            commit_article(rp, "Fork with extensions", forker.name, f"{forker.id}@peerpedia")
            # Second commit with improvements
            (rp / "article.md").write_text(
                content + "\n\n## Further Refinements\n"
                "Additional improvements based on further analysis and peer feedback.\n"
                f"\\n*— {forker_name}*"
            )
            commit_article(rp, "Refinements after review", forker.name, f"{forker.id}@peerpedia")
        except Exception as e:
            print(f"  Fork git warning: {e}")

        # Self-review
        try:
            upsert_review(
                session,
                article_id=fork.id,
                commit_hash="0000000000000000000000000000000000000000",
                reviewer_id=forker.id,
                scope="self",
                scores=score,
            )
        except Exception:
            pass

        fork_map[forker_name] = fork
        print(f"  Fork (new): {forker_name} → {parent.title[:30]}...")

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. Community reviews — diverse, cross-discipline (50+ edges)
    # ═══════════════════════════════════════════════════════════════════════════

    review_specs = [
        # Einstein ← physics peers
        ("Albert Einstein", "Richard Feynman", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Albert Einstein", "Niels Bohr", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Albert Einstein", "John von Neumann", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Albert Einstein", "Erwin Schrödinger", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        (
            "Albert Einstein",
            "Subrahmanyan Chandrasekhar",
            {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 3, "impact": 5},
        ),
        # Dirac ← quantum circle
        ("Paul Dirac", "Werner Heisenberg", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        ("Paul Dirac", "Niels Bohr", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        ("Paul Dirac", "Richard Feynman", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        ("Paul Dirac", "Max Born", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Bohr ← Copenhagen + physics
        ("Niels Bohr", "Albert Einstein", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Niels Bohr", "Werner Heisenberg", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Niels Bohr", "Erwin Schrödinger", {"originality": 4, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Niels Bohr", "Karl Popper", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 5}),
        # Heisenberg
        ("Werner Heisenberg", "Niels Bohr", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Werner Heisenberg", "Max Born", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        # Schrödinger
        ("Erwin Schrödinger", "Max Born", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Erwin Schrödinger", "Thomas Kuhn", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Born
        ("Max Born", "Werner Heisenberg", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Curie
        ("Marie Curie", "Dorothy Hodgkin", {"originality": 4, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 4}),
        ("Marie Curie", "Rosalind Franklin", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        (
            "Marie Curie",
            "Subrahmanyan Chandrasekhar",
            {"originality": 4, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5},
        ),
        # Chandrasekhar
        (
            "Subrahmanyan Chandrasekhar",
            "Richard Feynman",
            {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5},
        ),
        (
            "Subrahmanyan Chandrasekhar",
            "Albert Einstein",
            {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5},
        ),
        (
            "Subrahmanyan Chandrasekhar",
            "Paul Dirac",
            {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5},
        ),
        # Feynman
        ("Richard Feynman", "Albert Einstein", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        (
            "Richard Feynman",
            "Subrahmanyan Chandrasekhar",
            {"originality": 4, "rigor": 4, "completeness": 3, "pedagogy": 5, "impact": 5},
        ),
        ("Richard Feynman", "Paul Dirac", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Turing
        ("Alan Turing", "John von Neumann", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 3, "impact": 5}),
        ("Alan Turing", "Grace Hopper", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Alan Turing", "Ada Lovelace", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Franklin's DNA
        ("Rosalind Franklin", "Dorothy Hodgkin", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Rosalind Franklin", "Marie Curie", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Rosalind Franklin", "Francis Crick", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Noether
        ("Emmy Noether", "Albert Einstein", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Emmy Noether", "John von Neumann", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        (
            "Emmy Noether",
            "Subrahmanyan Chandrasekhar",
            {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 3, "impact": 5},
        ),
        ("Emmy Noether", "Paul Dirac", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        # Lovelace
        ("Ada Lovelace", "Alan Turing", {"originality": 5, "rigor": 3, "completeness": 3, "pedagogy": 5, "impact": 4}),
        ("Ada Lovelace", "Grace Hopper", {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 4}),
        # Popper
        ("Karl Popper", "Thomas Kuhn", {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 4}),
        ("Karl Popper", "Albert Einstein", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 5}),
        # Kuhn
        ("Thomas Kuhn", "Karl Popper", {"originality": 5, "rigor": 4, "completeness": 5, "pedagogy": 5, "impact": 5}),
        ("Thomas Kuhn", "Hilary Putnam", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Crick
        (
            "Francis Crick",
            "Santiago Ramón y Cajal",
            {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 4},
        ),
        (
            "Francis Crick",
            "Patricia Goldman-Rakic",
            {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5},
        ),
        ("Francis Crick", "Hilary Putnam", {"originality": 4, "rigor": 3, "completeness": 3, "pedagogy": 5, "impact": 4}),
        # Cajal
        (
            "Santiago Ramón y Cajal",
            "Patricia Goldman-Rakic",
            {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5},
        ),
        (
            "Santiago Ramón y Cajal",
            "Francis Crick",
            {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5},
        ),
        # Goldman-Rakic
        (
            "Patricia Goldman-Rakic",
            "Francis Crick",
            {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5},
        ),
        (
            "Patricia Goldman-Rakic",
            "Santiago Ramón y Cajal",
            {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5},
        ),
        # von Neumann
        ("John von Neumann", "Alan Turing", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("John von Neumann", "Claude Shannon", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        ("John von Neumann", "Emmy Noether", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        # Hopper
        ("Grace Hopper", "Ada Lovelace", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Grace Hopper", "John von Neumann", {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Grace Hopper", "Alan Turing", {"originality": 5, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Hodgkin
        ("Dorothy Hodgkin", "Rosalind Franklin", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        ("Dorothy Hodgkin", "Marie Curie", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Chinese articles — cross-discipline reviews
        ("John von Neumann", "Alan Turing", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 4}),
        ("John von Neumann", "Niels Bohr", {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 5, "impact": 4}),
        ("Alan Turing", "Karl Popper", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Alan Turing", "Emmy Noether", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 4}),
        ("Claude Shannon", "John von Neumann", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Claude Shannon", "Alan Turing", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        # Multi-author articles
        ("Niels Bohr", "Erwin Schrödinger", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
        ("Niels Bohr", "Max Born", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 4, "impact": 5}),
        ("Rosalind Franklin", "Dorothy Hodgkin", {"originality": 5, "rigor": 5, "completeness": 5, "pedagogy": 4, "impact": 5}),
        ("Rosalind Franklin", "Marie Curie", {"originality": 5, "rigor": 5, "completeness": 4, "pedagogy": 5, "impact": 5}),
    ]

    review_count = 0
    for author_name, reviewer_name, scores in review_specs:
        author = users[author_name]
        reviewer = users[reviewer_name]
        # Find any article by this author
        articles = (
            session.query(Article)
            .join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
            .filter(ArticleAuthor.author_id == author.id)
            .all()
        )
        if not articles:
            continue
        a = articles[0]
        # For published articles, write published-scope reviews; pool otherwise
        scope = "pool" if a.status == "sedimentation" else "published"
        existing = (
            session.query(Review)
            .filter(
                Review.article_id == a.id,
                Review.reviewer_id == reviewer.id,
                Review.scope == scope,
            )
            .first()
        )
        if not existing:
            try:
                upsert_review(
                    session,
                    article_id=a.id,
                    commit_hash="0000000000000000000000000000000000000000",
                    reviewer_id=reviewer.id,
                    scope=scope,
                    scores=scores,
                )
                review_count += 1
            except Exception:
                pass

    session.commit()
    print(f"  Reviews: {review_count} new")

    # ═══════════════════════════════════════════════════════════════════════════
    # 4.5. Thread messages — reviewer ↔ author dialogue
    # ═══════════════════════════════════════════════════════════════════════════

    # Build a lookup: (author_name, reviewer_name) → review
    thread_specs = [
        # Einstein's relativity reviewed by Feynman
        (
            "Albert Einstein",
            "Richard Feynman",
            [
                (
                    "Richard Feynman",
                    "The kinematic derivation is elegant, but section 2 could use more explicit examples. "
                    "Students reading this for the first time might struggle with the definition of simultaneity.",
                ),
                (
                    "Albert Einstein",
                    "Fair point. I've added a worked example with the train-and-platform thought experiment "
                    "that should make the operational definition of simultaneity clearer.",
                ),
                ("Richard Feynman", "Excellent – the train thought experiment is perfect. This is much more accessible now."),
            ],
        ),
        # Dirac reviewed by Heisenberg
        (
            "Paul Dirac",
            "Werner Heisenberg",
            [
                (
                    "Werner Heisenberg",
                    "The second quantization treatment of spontaneous emission is a major advance. "
                    "I wonder whether the approach extends to multi-electron systems?",
                ),
                (
                    "Paul Dirac",
                    "Yes, the formalism generalizes naturally. The key is treating the electron field as "
                    "an operator-valued distribution acting on the Fock space.",
                ),
            ],
        ),
        # Bohr reviewed by Einstein
        (
            "Niels Bohr",
            "Albert Einstein",
            [
                (
                    "Albert Einstein",
                    "The model explains the Balmer series beautifully, but the postulate of stationary "
                    "states with no radiation seems ad hoc. Is there a deeper justification?",
                ),
                (
                    "Niels Bohr",
                    "The stationary states are a necessary departure from classical electrodynamics. "
                    "The deeper justification must await a more complete quantum theory—but the empirical "
                    "success is undeniable.",
                ),
            ],
        ),
        # Schrodinger reviewed by Kuhn
        (
            "Erwin Schrödinger",
            "Thomas Kuhn",
            [
                (
                    "Thomas Kuhn",
                    "This paper is historically fascinating—it represents a paradigm shift from matrix "
                    "mechanics to wave mechanics. The two formulations are mathematically equivalent "
                    "yet conceptually incommensurable in important ways.",
                ),
                (
                    "Erwin Schrödinger",
                    "I appreciate the historical perspective. Indeed, wave mechanics was motivated by "
                    "a desire to restore visualizability to quantum theory—a philosophical preference "
                    "that matrix mechanics abandoned.",
                ),
            ],
        ),
        # Turing reviewed by von Neumann
        (
            "Alan Turing",
            "John von Neumann",
            [
                (
                    "John von Neumann",
                    "The universal machine concept is profound. I'm working on a stored-program "
                    "architecture that follows directly from this theoretical foundation.",
                ),
                (
                    "Alan Turing",
                    "I'm delighted to hear that. The distinction between the machine (hardware) and "
                    "the description number (software) is the key insight—it means one machine can "
                    "simulate any other.",
                ),
                (
                    "John von Neumann",
                    "Precisely. I've drafted an architecture with a central arithmetic unit, control "
                    "unit, and memory—all derived from the universal machine concept.",
                ),
            ],
        ),
        # Franklin DNA reviewed by Crick
        (
            "Rosalind Franklin",
            "Francis Crick",
            [
                (
                    "Francis Crick",
                    "The diffraction data is impeccable. The 3.4 Å spacing and the X-pattern strongly "
                    "support a double helix. Have you considered that the two strands might run "
                    "in opposite directions?",
                ),
                (
                    "Rosalind Franklin",
                    "The antiparallel configuration is consistent with the diffraction data. "
                    "I believe the base pairs are held by hydrogen bonds, with Chargaff's ratios "
                    "dictating A-T and G-C pairing.",
                ),
                (
                    "Francis Crick",
                    "Agreed. The complementary base pairing elegantly explains both the structural "
                    "stability and the mechanism of replication—each strand serves as a template.",
                ),
            ],
        ),
        # Noether reviewed by von Neumann
        (
            "Emmy Noether",
            "John von Neumann",
            [
                (
                    "John von Neumann",
                    "This theorem is one of the most beautiful results in mathematical physics. "
                    "Every continuous symmetry yields a conserved current—it's remarkably general.",
                ),
                (
                    "Emmy Noether",
                    "The generality is the point. It works for any Lagrangian system with a "
                    "continuous symmetry group. Energy, momentum, angular momentum—all emerge "
                    "from the same principle.",
                ),
            ],
        ),
        # Popper reviewed by Einstein
        (
            "Karl Popper",
            "Albert Einstein",
            [
                (
                    "Albert Einstein",
                    "The demarcation criterion is compelling. A theory that cannot be falsified "
                    "is not scientific—this is precisely why general relativity was tested at "
                    "the 1919 solar eclipse.",
                ),
                (
                    "Karl Popper",
                    "Exactly! Your theory made a risky prediction—light bending around the sun—"
                    "that could have been refuted. That willingness to be tested is what "
                    "distinguishes science from pseudoscience.",
                ),
            ],
        ),
        # Feynman QED reviewed by Dirac
        (
            "Richard Feynman",
            "Paul Dirac",
            [
                (
                    "Paul Dirac",
                    "The path integral formulation is a genuine breakthrough. It makes relativistic "
                    "quantum mechanics almost intuitive—the particle really does explore all paths.",
                ),
                (
                    "Richard Feynman",
                    "I was inspired by your Lagrangian formulation of quantum mechanics. The path "
                    "integral simply takes the principle of least action seriously at the quantum level.",
                ),
            ],
        ),
        # Crick consciousness reviewed by Putnam
        (
            "Francis Crick",
            "Hilary Putnam",
            [
                (
                    "Hilary Putnam",
                    "The 40 Hz binding hypothesis is intriguing, but it doesn't address the hard "
                    "problem—why should synchronized oscillations produce subjective experience?",
                ),
                (
                    "Francis Crick",
                    "The hard problem may dissolve under sufficient neurobiological detail. We don't "
                    "yet know what we don't know—the NCC approach is to map the neural correlates "
                    "first and tackle the metaphysical questions later.",
                ),
            ],
        ),
        # Goldman-Rakic reviewed by Cajal
        (
            "Patricia Goldman-Rakic",
            "Santiago Ramón y Cajal",
            [
                (
                    "Santiago Ramón y Cajal",
                    "The modular organization of prefrontal cortex vindicates the neuron doctrine. "
                    "I always suspected the cortex is not a diffuse network but a mosaic of "
                    "specialized functional territories.",
                ),
                (
                    "Patricia Goldman-Rakic",
                    "Your histological work laid the foundation. Modern electrophysiology confirms "
                    "that individual prefrontal neurons maintain task-specific firing during the "
                    "delay period—this is the cellular basis of working memory.",
                ),
            ],
        ),
        # Kuhn reviewed by Popper
        (
            "Thomas Kuhn",
            "Karl Popper",
            [
                (
                    "Karl Popper",
                    "I disagree with the incommensurability thesis. If paradigms are truly "
                    "incommensurable, how can we rationally choose between them? Science needs "
                    "objective criteria.",
                ),
                (
                    "Thomas Kuhn",
                    "Rational comparison exists within paradigms, but paradigm shifts involve "
                    "a change in what counts as 'rational.' Newtonian and relativistic mechanics "
                    "share no common measure of 'simultaneity'—the concepts themselves differ.",
                ),
                (
                    "Karl Popper",
                    "Fair, but the empirical success of a new paradigm—its ability to solve "
                    "anomalies the old one couldn't—provides a meta-criterion for comparison.",
                ),
            ],
        ),
        # Curie reviewed by Hodgkin
        (
            "Marie Curie",
            "Dorothy Hodgkin",
            [
                (
                    "Dorothy Hodgkin",
                    "The exponential attenuation law is robust, but your data hints at a secondary "
                    "scattering component at low energies. This could be important for medical "
                    "applications of radiation.",
                ),
                (
                    "Marie Curie",
                    "I noticed that deviation as well. It appears to be a Compton-like scattering "
                    "from the inner electron shells. I plan to investigate this further with "
                    "monochromatic X-ray sources.",
                ),
            ],
        ),
        # ── Multi-turn debates (4-5 rounds) ───────────────────────────────────
        # Heisenberg reviewed by Schrödinger — 5-round wave vs matrix debate
        (
            "Werner Heisenberg",
            "Erwin Schrödinger",
            [
                (
                    "Erwin Schrödinger",
                    "Matrix mechanics is mathematically elegant, but it sacrifices visualizability. "
                    "How can a physicist think about quantum systems without a picture in mind? "
                    "My wave mechanics restores the familiar concept of waves in space.",
                ),
                (
                    "Werner Heisenberg",
                    "With respect, the demand for visualizability is a prejudice carried over from "
                    "classical physics. The observables—frequencies, intensities—are all that matter. "
                    "What happens between observations is not accessible to us.",
                ),
                (
                    "Erwin Schrödinger",
                    "But your position leads to instrumentalism. If we give up on representing reality "
                    "between measurements, are we still doing physics? The wave function evolves "
                    "deterministically—that is a representation of reality.",
                ),
                (
                    "Werner Heisenberg",
                    "The wave function does NOT represent an objective wave in 3D space. For N "
                    "particles it lives in 3N-dimensional configuration space. That's not visualizable "
                    "either—it's just a different mathematical tool.",
                ),
                (
                    "Erwin Schrödinger",
                    "Touché. Perhaps both formulations capture partial truths. The deeper question is "
                    "whether a complete theory of quantum reality is even expressible in a single "
                    "mathematical language. Complementarity may be inescapable.",
                ),
            ],
        ),
        # Chandrasekhar reviewed by Eddington (via Einstein) — 4-round white dwarf debate
        (
            "Subrahmanyan Chandrasekhar",
            "Albert Einstein",
            [
                (
                    "Albert Einstein",
                    "Your derivation of the maximum white dwarf mass is mathematically sound, but "
                    "the physical implications are troubling. A star collapsing indefinitely—this is "
                    "a reductio ad absurdum, not a physical prediction.",
                ),
                (
                    "Subrahmanyan Chandrasekhar",
                    "The mathematics doesn't care about our discomfort. If a star exceeds 1.4 solar "
                    "masses, the electron degeneracy pressure cannot halt collapse. What happens after "
                    "is beyond the scope of this paper, but the limit is real.",
                ),
                (
                    "Albert Einstein",
                    "I've discussed this with Sir Eddington. He believes some new physical process "
                    "must intervene—perhaps the star sheds mass or some quantum effect we haven't "
                    "considered. Nature abhors a singularity.",
                ),
                (
                    "Subrahmanyan Chandrasekhar",
                    "Nature may abhor singularities, but mathematical physics doesn't guarantee their "
                    "absence. I cannot falsify my own derivation merely because the conclusion is "
                    "unsettling. If the limit is wrong, show me where the calculation fails.",
                ),
            ],
        ),
        # Shannon reviewed by von Neumann — 4-round information theory debate
        (
            "Claude Shannon",
            "John von Neumann",
            [
                (
                    "John von Neumann",
                    "Your use of the term 'entropy' is striking—borrowing from Boltzmann and Gibbs. "
                    "But informational entropy and thermodynamic entropy are distinct quantities. "
                    "Are you suggesting a formal equivalence?",
                ),
                (
                    "Claude Shannon",
                    "The mathematical form is identical: $$H = -\\sum p_i \\log p_i$$. But no, I'm not "
                    "claiming a physical equivalence in general—though for certain physical systems, "
                    "Maxwell's demon suggests a deep connection between information and thermodynamics.",
                ),
                (
                    "John von Neumann",
                    "Fascinating. The demon must erase its memory to function, and erasure dissipates "
                    "heat. Your formula might quantify the minimum thermodynamic cost of computation. "
                    "I've been thinking about this for computer design.",
                ),
                (
                    "Claude Shannon",
                    "Yes! The channel capacity theorem sets a fundamental limit on reliable communication "
                    "for any physical encoding. If computing is physical, there must be thermodynamic "
                    "limits too—this is a rich area for future work.",
                ),
            ],
        ),
        # ── Dual-author dialogues (both co-authors + reviewer) ──────────────────
        # Copenhagen Interpretation (Bohr+Heisenberg) reviewed by Einstein — 6-round
        (
            "Niels Bohr",
            "Albert Einstein",
            [
                (
                    "Albert Einstein",
                    "The Copenhagen interpretation abandons the very goal of physics—describing reality "
                    "independent of observation. 'Complementarity' sounds like a fancy word for giving "
                    "up on a complete description.",
                ),
                (
                    "Niels Bohr",
                    "The goal of physics is not to describe 'reality independent of observation'—that "
                    "is a classical prejudice. Physics describes what we can say about nature, and the "
                    "quantum formalism says all that can be said. There is no 'deeper' reality.",
                ),
                (
                    "Werner Heisenberg",
                    "As co-author, let me add: the uncertainty principle isn't a measurement limitation—"
                    "it's a structural feature of the theory. Position and momentum are not simultaneous "
                    "properties. Asking for both at once is like asking for a married bachelor.",
                ),
                (
                    "Albert Einstein",
                    "This operationalist philosophy has disturbing implications. If the moon's position "
                    "is only defined when observed, does the moon exist when nobody looks? Quantum "
                    "mechanics cannot be the final word if it denies objective reality.",
                ),
                (
                    "Niels Bohr",
                    "The moon is classical—decoherence ensures macroscopic objects behave classically. "
                    "But the lesson of quantum theory is that at the microscopic scale, the distinction "
                    "between 'system' and 'observer' is not pre-given—it's chosen by the experimenter.",
                ),
                (
                    "Albert Einstein",
                    "We will have to agree to disagree. I remain convinced that quantum mechanics is "
                    "an incomplete description of an objective reality. But your formulation is the "
                    "best working approximation we have—I cannot deny its empirical success.",
                ),
            ],
            "The Copenhagen Interpretation: A Joint Statement on Complementarity",
        ),
        # Double Helix (Franklin+Crick) reviewed by Hodgkin — 6-round structural debate
        (
            "Rosalind Franklin",
            "Dorothy Hodgkin",
            [
                (
                    "Dorothy Hodgkin",
                    "The double helix model is compelling, but I have concerns about the base-pairing "
                    "specificity. How do you rule out alternative pairing schemes, particularly "
                    "Hoogsteen base pairing which I've observed in my crystallography work?",
                ),
                (
                    "Rosalind Franklin",
                    "The diffraction data clearly shows the 3.4 Å periodicity with a 34 Å repeat. "
                    "Hoogsteen pairing would produce a different pitch—closer to 30 Å. The symmetry "
                    "of the diffraction pattern uniquely constrains the geometry to Watson-Crick pairing.",
                ),
                (
                    "Francis Crick",
                    "To add to Rosalind's point: Chargaff's ratios constrain the pairing to A=T and "
                    "G≡C. In Hoogsteen geometry, the glycosidic bond angles don't allow the antiparallel "
                    "backbone that the fiber diffraction demands. It's a geometric impossibility.",
                ),
                (
                    "Dorothy Hodgkin",
                    "Convincing. But what about the replication mechanism? If the strands are "
                    "antiparallel, DNA polymerase would need to synthesize in opposite directions "
                    "simultaneously—that's biochemically problematic.",
                ),
                (
                    "Rosalind Franklin",
                    "We've considered that. One strand can be synthesized continuously and the other "
                    "in fragments—what we're calling 'Okazaki fragments' after our collaborator. The "
                    "polymerase simply works in the 5'→3' direction on both strands, using the fork "
                    "as a structural organizer.",
                ),
                (
                    "Dorothy Hodgkin",
                    "I'm now persuaded. The complementary base pairing explains both the structural "
                    "stability AND the replication mechanism with a single elegant principle. This is "
                    "the kind of explanatory unification that marks a genuine scientific breakthrough.",
                ),
            ],
            "The Double Helix: Molecular Structure of Deoxyribonucleic Acid",
        ),
        # ── Chinese article discussions ───────────────────────────────────────
        # 量子纠缠 (von Neumann) reviewed by Einstein — 3-round in Chinese
        (
            "John von Neumann",
            "Albert Einstein",
            [
                (
                    "Albert Einstein",
                    "你对EPR论证的数学分析非常严谨，但我想追问一个哲学问题：如果量子纠缠真的意味着"
                    "'鬼魅般的超距作用'，那么我们对定域性的直觉是否必须被修正？",
                ),
                (
                    "John von Neumann",
                    "这正是贝尔不等式的核心贡献——它证明了任何定域隐变量理论都无法复现量子力学的所有"
                    "预测。实验已经支持量子力学的预测，所以我们必须放弃定域性或者放弃反事实确定性。"
                    "物理学家选择保留量子力学。",
                ),
                (
                    "Albert Einstein",
                    "我仍然认为应该有更完整的理论。但你的分析正确地指出了目前的两种选择——定域性"
                    "和实在论之间必须放弃一个。这比我最初设想的要深刻得多。",
                ),
            ],
        ),
        # 哥德尔不完备定理 (Turing) reviewed by von Neumann — 3-round
        (
            "Alan Turing",
            "John von Neumann",
            [
                (
                    "John von Neumann",
                    "你将不完备性与停机问题联系起来的角度非常新颖。这暗示了形式系统与计算之间存在某种本质上的同构关系。",
                ),
                (
                    "Alan Turing",
                    "是的，哥德尔数和通用图灵机本质上是在做同一件事：将元数学编码为算术。"
                    "不完备性定理和停机问题的不可判定性是从同一个源头推导出来的——自指。",
                ),
                (
                    "John von Neumann",
                    "那么这对人工智能意味着什么？如果存在形式系统无法证明但人类可以'看到'为真的命题，"
                    "这是否意味着人类心智本质上超越了任何形式系统？",
                ),
            ],
        ),
        # ── Fork article discussions ──────────────────────────────────────────
        # Feynman's fork of Einstein reviewed by Dirac
        (
            "Richard Feynman",
            "Paul Dirac",
            [
                (
                    "Paul Dirac",
                    "The path integral derivation of Lorentz transformations is clever. By making the "
                    "action relativistic from the start, you avoid the ad hoc nature of Einstein's "
                    "original derivation. This could become the standard pedagogical approach.",
                ),
                (
                    "Richard Feynman",
                    "That's the goal. Einstein's 1905 derivation is historically important but "
                    "pedagogically challenging. Students who learn path integrals first find "
                    "special relativity almost trivial—it falls out of the stationary action principle.",
                ),
                (
                    "Paul Dirac",
                    "Have you considered extending this to general relativity? The Einstein-Hilbert "
                    "action already provides a Lagrangian for gravity—a path integral formulation of "
                    "general relativity might illuminate the quantum gravity problem.",
                ),
                (
                    "Richard Feynman",
                    "I've tried. The problem is that the gravitational action is non-renormalizable. "
                    "Every path integral approach to quantum gravity diverges beyond one loop. "
                    "But for classical pedagogy, the action approach is unbeatable.",
                ),
            ],
        ),
        # von Neumann's fork of Turing reviewed by Hopper — with co-author perspective
        (
            "John von Neumann",
            "Grace Hopper",
            [
                (
                    "Grace Hopper",
                    "The stored-program architecture is elegant on paper, but I want to discuss practical "
                    "implementation. How do you handle the instruction set encoding? A poorly designed "
                    "instruction format will bottleneck the entire system.",
                ),
                (
                    "John von Neumann",
                    "Excellent practical point. I'm proposing a 40-bit word with 20-bit instructions—"
                    "two per word. The first 8 bits encode the operation, the remaining 12 specify "
                    "the memory address. This gives us 256 opcodes and 4096 addressable words.",
                ),
                (
                    "Grace Hopper",
                    "That's workable but wasteful. I'd suggest a 6-bit opcode and a larger address "
                    "field—the extra opcodes won't be used, and you'll hit the address limit before "
                    "the opcode limit in practice. I've seen this pattern in the Mark I.",
                ),
                (
                    "John von Neumann",
                    "You're right. Let me revise: 6-bit opcode, 14-bit address field—that gives "
                    "16384 addressable words. And the two spare bits can encode addressing modes: "
                    "immediate, direct, indirect. This is much more practical.",
                ),
                (
                    "Alan Turing",
                    "If I may interject—as the original author of the computability paper this fork "
                    "is based on—the theoretical limit is not the address space but the decision "
                    "procedure. Any stored-program machine with conditional branching is universal, "
                    "regardless of word size. The practical engineering matters for performance, "
                    "not for computability.",
                ),
            ],
        ),
    ]

    thread_count = 0
    for spec in thread_specs:
        author_name, reviewer_name, messages = spec[0], spec[1], spec[2]
        article_title = spec[3] if len(spec) >= 4 else None
        author = users[author_name]
        reviewer = users[reviewer_name]
        # Find the right article: by title if specified, else first by author
        articles = (
            session.query(Article)
            .join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
            .filter(ArticleAuthor.author_id == author.id)
            .all()
        )
        if not articles:
            continue
        if article_title:
            a = next((a for a in articles if a.title == article_title), None)
            if a is None:
                continue
        else:
            a = articles[0]
        scope = "pool" if a.status == "sedimentation" else "published"
        review = (
            session.query(Review)
            .filter(
                Review.article_id == a.id,
                Review.reviewer_id == reviewer.id,
                Review.scope == scope,
            )
            .first()
        )
        if not review:
            # Create the review if it doesn't exist (e.g., for multi-author articles)
            try:
                default_scores = {"originality": 4, "rigor": 4, "completeness": 4, "pedagogy": 4, "impact": 4}
                review = upsert_review(
                    session,
                    article_id=a.id,
                    commit_hash="0000000000000000000000000000000000000000",
                    reviewer_id=reviewer.id,
                    scope=scope,
                    scores=default_scores,
                )
                session.flush()
            except Exception:
                continue
        # Thread messages now live in git (reviews/<reviewer_id>/thread.md).
        # Skipping DB thread seeding — use git-based review submission instead.

    session.commit()
    print(f"  Threads: {thread_count} messages new")

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. Bookmarks — diverse picks (30+)
    # ═══════════════════════════════════════════════════════════════════════════

    bookmark_specs = [
        ("Alan Turing", "Albert Einstein"),
        ("Alan Turing", "John von Neumann"),
        ("Alan Turing", "Karl Popper"),
        ("Alan Turing", "Niels Bohr"),
        ("Ada Lovelace", "Alan Turing"),
        ("Ada Lovelace", "Emmy Noether"),
        ("Ada Lovelace", "Grace Hopper"),
        ("Ada Lovelace", "Hilary Putnam"),
        ("Richard Feynman", "Paul Dirac"),
        ("Richard Feynman", "Niels Bohr"),
        ("Richard Feynman", "Subrahmanyan Chandrasekhar"),
        ("Claude Shannon", "Alan Turing"),
        ("Claude Shannon", "John von Neumann"),
        ("Grace Hopper", "Ada Lovelace"),
        ("Grace Hopper", "Alan Turing"),
        ("Grace Hopper", "John von Neumann"),
        ("Dorothy Hodgkin", "Rosalind Franklin"),
        ("Dorothy Hodgkin", "Marie Curie"),
        ("Subrahmanyan Chandrasekhar", "Albert Einstein"),
        ("Subrahmanyan Chandrasekhar", "Richard Feynman"),
        ("Emmy Noether", "Albert Einstein"),
        ("Emmy Noether", "Paul Dirac"),
        ("John von Neumann", "Claude Shannon"),
        ("John von Neumann", "Alan Turing"),
        ("John von Neumann", "Paul Dirac"),
        ("Marie Curie", "Dorothy Hodgkin"),
        ("Marie Curie", "Niels Bohr"),
        ("Rosalind Franklin", "Dorothy Hodgkin"),
        ("Rosalind Franklin", "Francis Crick"),
        ("Karl Popper", "Thomas Kuhn"),
        ("Karl Popper", "Albert Einstein"),
        ("Thomas Kuhn", "Karl Popper"),
        ("Thomas Kuhn", "Erwin Schrödinger"),
        ("Hilary Putnam", "Francis Crick"),
        ("Hilary Putnam", "Thomas Kuhn"),
        ("Francis Crick", "Santiago Ramón y Cajal"),
        ("Santiago Ramón y Cajal", "Patricia Goldman-Rakic"),
        ("Patricia Goldman-Rakic", "Francis Crick"),
        ("Niels Bohr", "Werner Heisenberg"),
        ("Niels Bohr", "Paul Dirac"),
        ("Werner Heisenberg", "Niels Bohr"),
        ("Werner Heisenberg", "Max Born"),
        ("Erwin Schrödinger", "Niels Bohr"),
        ("Erwin Schrödinger", "Francis Crick"),
        ("Paul Dirac", "Erwin Schrödinger"),
        ("Paul Dirac", "Richard Feynman"),
        ("Max Born", "Werner Heisenberg"),
    ]

    bm_count = 0
    for user_name, author_name in bookmark_specs:
        user = users[user_name]
        author = users[author_name]
        articles = (
            session.query(Article)
            .join(ArticleAuthor, Article.id == ArticleAuthor.article_id)
            .filter(ArticleAuthor.author_id == author.id)
            .all()
        )
        if not articles:
            continue
        a = articles[0]
        existing = (
            session.query(Bookmark)
            .filter(
                Bookmark.user_id == user.id,
                Bookmark.article_id == a.id,
            )
            .first()
        )
        if not existing:
            session.add(Bookmark(user_id=user.id, article_id=a.id))
            bm_count += 1
    session.commit()
    print(f"  Bookmarks: {bm_count} new")

    # ═══════════════════════════════════════════════════════════════════════════
    # 7. Citations — article cross-references
    # ═══════════════════════════════════════════════════════════════════════════

    citation_edges = [
        # Bohr's atom paper cites Einstein's photoelectric effect
        ("Niels Bohr", "Albert Einstein", 0.8, 0.6),
        # Heisenberg cites Bohr
        ("Werner Heisenberg", "Niels Bohr", 0.9, 0.7),
        # Schrödinger cites Bohr and Heisenberg
        ("Erwin Schrödinger", "Niels Bohr", 0.7, 0.5),
        ("Erwin Schrödinger", "Werner Heisenberg", 0.8, 0.6),
        # Dirac cites Heisenberg and Schrödinger
        ("Paul Dirac", "Werner Heisenberg", 0.85, 0.7),
        ("Paul Dirac", "Erwin Schrödinger", 0.75, 0.6),
        # Born cites Heisenberg
        ("Max Born", "Werner Heisenberg", 0.9, 0.8),
        # von Neumann cites Turing
        ("John von Neumann", "Alan Turing", 0.95, 0.85),
        # Shannon cites Turing
        ("Claude Shannon", "Alan Turing", 0.7, 0.5),
        # Franklin DNA cites Hodgkin's crystallography
        ("Rosalind Franklin", "Dorothy Hodgkin", 0.8, 0.7),
        # Crick DNA cites Franklin
        ("Francis Crick", "Rosalind Franklin", 0.9, 0.85),
        # Turing cites von Neumann
        ("Alan Turing", "John von Neumann", 0.6, 0.4),
        # Multi-author: Bohr-Heisenberg cites Einstein
        ("Niels Bohr", "Albert Einstein", 0.8, 0.7),
        # Chinese: von Neumann cites Bohr
        ("John von Neumann", "Niels Bohr", 0.7, 0.5),
    ]

    cit_count = 0
    {a.title: a for a in session.query(Article).all()}
    for from_name, to_name, fwd_prob, back_prob in citation_edges:
        from_articles = article_map.get(from_name, [])
        to_articles = article_map.get(to_name, [])
        if not from_articles or not to_articles:
            continue
        from_a = from_articles[0]
        to_a = to_articles[0]
        existing = (
            session.query(Citation)
            .filter(
                Citation.from_article_id == from_a.id,
                Citation.to_article_id == to_a.id,
            )
            .first()
        )
        if not existing:
            session.add(
                Citation(
                    from_article_id=from_a.id,
                    to_article_id=to_a.id,
                    forward_prob=fwd_prob,
                    backward_prob=back_prob,
                )
            )
            cit_count += 1
    session.commit()
    print(f"  Citations: {cit_count} new")

    session.close()
    engine.dispose()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  Users:     {len(users)}")
    print(f"  Articles:  {articles_created}")
    print(f"  Forks:     {len(fork_map)}")
    print(f"  Follows:   {follow_count}")
    print(f"  Reviews:   {review_count}")
    print(f"  Bookmarks: {bm_count}")
    print(f"  Citations: {cit_count}")
    print("\n✅ Seed complete! Run the backend and frontend to explore.")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Seed PeerPedia database")
    parser.add_argument("--db", default="sqlite:///peerpedia.db", help="Database URL (default: sqlite:///peerpedia.db)")
    parser.add_argument("--articles-dir", default=None, help="Articles directory (default: ~/.peerpedia/articles)")
    args = parser.parse_args()

    articles_dir = Path(args.articles_dir).expanduser() if args.articles_dir else Path.home() / ".peerpedia" / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    seed(args.db, articles_dir)


if __name__ == "__main__":
    main()
