# Publier une version

1. `uv run pytest` — la suite doit être verte.
2. `git status --porcelain` — l'arbre doit être **propre**. Un fichier
   modifié suffit à ce que la version construite porte un suffixe
   `.dYYYYMMDD`, et c'est cette version-là qui serait installée. C'est du
   vécu : lors de la mise en place de `hatch-vcs`, `uv sync` avait
   lui-même modifié `uv.lock`, ce qui a rendu l'arbre sale et fait
   apparaître ce suffixe de date au lieu du tag propre `0.2.0`. D'où
   l'ordre de cette procédure : arbre propre **avant** de taguer, jamais
   l'inverse.
3. `git tag -a v0.3.0 -m "Résumé de ce que la version apporte"`
4. `git push --follow-tags`
5. `uv sync --reinstall-package flower` — sans quoi l'application
   continuera d'annoncer la version précédente.
6. `flower --version` — doit afficher `flower 0.3.0`.

## Numérotation

- **patch** (`v0.2.1`) — correctifs seuls, aucune nouveauté visible.
- **mineur** (`v0.3.0`) — toute nouveauté fonctionnelle : un type de nœud,
  une action, une préférence.
- **majeur** (`v1.0.0`) — un jugement de maturité, pas un critère
  technique : le jour où le format `.flow` est considéré stable et l'outil
  complet. Rien n'y oblige.

Entre deux tags, la version prend une forme telle que
`0.3.1.dev4+g1a2b3c4d5` — le patch est incrémenté par défaut, sans
présumer de ce qui viendra, `dev4` compte les commits depuis le dernier
tag, et `g1a2b3c4d5` est les neuf premiers caractères du hash du commit
courant (pas les sept habituels de `git log --oneline`).

## Où vit la version

Le tag git est la seule source de vérité. `pyproject.toml` déclare
`dynamic = ["version"]` et `hatch-vcs` la dérive à la construction.
Aucun numéro n'est écrit à la main nulle part.

`flower --version` et la boîte « À propos » lisent la version de la
distribution *installée* (via `importlib.metadata`), pas celle du dépôt :
`hatch-vcs` fige le numéro de version au moment de l'installation, donc un
tag tout juste posé n'apparaît qu'une fois le paquet réinstallé — c'est
pourquoi l'étape 5 ci-dessus n'est pas facultative.
