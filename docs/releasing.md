# Publier une version

1. `git switch main && git pull` — les versions se coupent sur `main`, une
   fois la PR fusionnée. Taguer depuis une branche de fonctionnalité
   marquerait un commit qui n'atteindra peut-être jamais `main`, et le tag
   publié pointerait dans le vide.
2. `uv run pytest` — la suite doit être verte.
3. `git status --porcelain -uno` — l'arbre doit être **propre**. Un fichier
   suivi et modifié ne se contente pas d'ajouter un suffixe : il change la
   version de base, qui devient `0.2.1.dev0+g<hash>.d20260826` au lieu du
   `0.2.0` attendu — et c'est cette version-là qui serait installée. C'est du
   vécu : lors de la mise en place de `hatch-vcs`, `uv sync` avait lui-même
   modifié `uv.lock`, ce qui a suffi. D'où l'ordre de cette procédure : arbre
   propre **avant** de taguer, jamais l'inverse. Le `-uno` ignore les fichiers
   non suivis, qui n'entrent pas dans le calcul de la version : un brouillon
   dans le répertoire ne doit pas bloquer une publication.
4. `git tag -a v0.3.0 -m "Résumé de ce que la version apporte"` — le `-a` n'est
   pas décoratif : `git push --follow-tags`, à l'étape 7, ne pousse **que** les
   tags annotés. Un `git tag v0.3.0` tapé par habitude produirait un push qui
   ne publie rien tout en signalant un succès.
5. `uv sync --reinstall-package flower` — sans quoi l'application continuera
   d'annoncer la version précédente.
6. Vérifier, avant de rendre quoi que ce soit public :
   - `uv run flower --version` doit afficher `flower 0.3.0` ;
   - `Aide → À propos de Flower` doit montrer le même numéro.
   Si l'ancienne version persiste, l'installation éditable n'a pas été
   reconstruite : `uv pip install -e . --force-reinstall`, puis revérifier.
7. `git push --follow-tags` — **en dernier**, parce que c'est la seule étape
   irréversible. Tant qu'elle n'a pas eu lieu, une erreur se rattrape en local
   avec un `git tag -d`. Après, il faut un `git push --delete origin v0.3.0`
   et un nouveau tag, visibles de tous.

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
