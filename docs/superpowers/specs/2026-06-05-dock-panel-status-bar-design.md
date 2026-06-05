# Design — DockPanel & Status Bar

**Date:** 2026-06-05  
**Contexte:** Refonte de la barre latérale droite et déplacement des infos du nœud sélectionné vers une status bar.

---

## Objectif

- Supprimer l'`InfoPanel` (infos du nœud sélectionné dans la barre latérale droite).
- Afficher ces infos dans une status bar en bas de la fenêtre principale.
- Transformer la barre latérale droite en `DockPanel` : un conteneur dans lequel l'utilisateur peut "docker" des éditeurs de nœuds.

---

## 1. Status bar

`QMainWindow` expose nativement `statusBar()`. Deux zones coexistent :

### Zone permanente (gauche)
- Un `QLabel` ajouté via `statusBar().addWidget(label)`.
- Mis à jour à chaque sélection de nœud : format `type · nom · actif` (ex. `noop · mon_noeud · actif`).
- Quand aucun nœud n'est sélectionné : label vide ou `"Aucun nœud sélectionné"`.
- Mis à jour dans `MainWindow._on_node_selected()` et `MainWindow._on_node_updated()`.

### Messages passagers (droite)
- `statusBar().showMessage("Fichier sauvegardé", 3000)` — disparaît après 3 secondes.
- Utilisé pour : sauvegarde fichier, suppression de nœud, et toute action notable.

---

## 2. DockPanel (remplace InfoPanel)

### Fichiers
- `src/flower/ui/info_panel.py` → renommé `src/flower/ui/dock_panel.py`
- Classe `InfoPanel` → `DockPanel`
- Nouvelle classe `DockEntry` dans le même fichier `dock_panel.py`

### Structure du DockPanel
```
DockPanel (QWidget)
└── QScrollArea
    └── QWidget (container)
        └── QVBoxLayout
            ├── DockEntry (node A)
            ├── DockEntry (node B)
            └── stretch
```

- Attribut interne : `_entries: dict[str, DockEntry]` indexé par `node_id`.

### API publique du DockPanel
```python
def dock(self, node_id: str, node: Node, form: NodeForm) -> None
    # Crée un DockEntry et ajoute le form comme body.

def undock(self, node_id: str) -> NodeForm
    # Retire le DockEntry, retourne le NodeForm pour reparentage.

def remove(self, node_id: str) -> None
    # Retire et détruit le DockEntry (fermeture sans undock).

def clear(self) -> None
    # Retire et détruit toutes les entrées (appelé sur nouveau fichier / ouverture).
```

### Signaux du DockPanel
```python
undock_requested = Signal(str)   # node_id
close_requested  = Signal(str)   # node_id
name_changed     = Signal(str, str)  # node_id, new_name
```

### Structure d'un DockEntry
```
┌─────────────────────────────────────────────┐
│ ▼  [nom_noeud_____________]  [↗ undock] [✕] │  ← header (QHBoxLayout)
├─────────────────────────────────────────────┤
│                                             │
│   NodeForm                                  │  ← body (collapsible)
│                                             │
└─────────────────────────────────────────────┘
```

- **▼/▶** (`QPushButton`) : toggle collapse/expand — masque/affiche le body (`NodeForm`).
- **nom du nœud** (`QLineEdit`) : éditable, émet `name_changed` à `editingFinished`.
- **↗ undock** (`QPushButton`) : émet un signal interne `undock_requested(node_id)` ; `DockPanel` le relaie via son propre signal du même nom.
- **✕ fermer** (`QPushButton`) : émet un signal interne `close_requested(node_id)` ; `DockPanel` le relaie de même.

---

## 3. EditorWindow — ajout du bouton Dock

- Nouveau bouton **"Dock"** dans la barre de boutons de l'`EditorWindow`.
- Nouveau signal : `dock_requested = Signal(str)  # node_id`
- Nouvelle méthode : `extract_form() -> NodeForm` — retire le `NodeForm` du layout sans le détruire.

### Séquence "Dock"
1. L'utilisateur clique "Dock" dans `EditorWindow`.
2. `EditorWindow` émet `dock_requested(node_id)`.
3. `MainWindow._on_dock_requested(node_id)` :
   a. Appelle `win.extract_form()` → récupère le `NodeForm`.
   b. Ferme l'`EditorWindow`.
   c. Appelle `self._dock_panel.dock(node_id, node, form)`.

### Séquence "Undock"
1. L'utilisateur clique ↗ dans le `DockEntry`.
2. `DockPanel` émet `undock_requested(node_id)`.
3. `MainWindow._on_undock_requested(node_id)` :
   a. Appelle `self._dock_panel.undock(node_id)` → récupère le `NodeForm`.
   b. Crée un `EditorWindow` en lui passant le `NodeForm` existant.
   c. Affiche la fenêtre flottante.

---

## 4. Changements dans MainWindow

### Suppressions
- `self._info = InfoPanel()` et tout usage de `self._info`.
- Import de `InfoPanel`.
- `self._info.edit_requested.connect(...)` dans `_connect_signals`.
- `self._info.clear()` dans `_delete_selected_node`.
- `self._info.show_node(node)` dans `_on_node_selected` et `_on_node_updated`.

### Ajouts
- `self._dock_panel = DockPanel()` (prend la place dans le splitter).
- `self._status_node_label = QLabel()` ajouté à `statusBar()`.
- Connexions : `_dock_panel.undock_requested`, `_dock_panel.close_requested`, `_dock_panel.name_changed`.
- `showMessage(...)` dans `_save_file` et `_delete_selected_node`.

### Nouveaux handlers
```python
def _on_dock_requested(self, node_id: str) -> None
def _on_undock_requested(self, node_id: str) -> None
def _on_dock_close_requested(self, node_id: str) -> None
def _on_name_changed(self, node_id: str, new_name: str) -> None
    # Met à jour node.name, appelle mark_dirty() et _canvas.refresh_layout().
```

`_open_editor` doit connecter `win.dock_requested.connect(self._on_dock_requested)`.

### Réinitialisation lors de l'ouverture d'un nouveau fichier
`_new_file` et `_open_file` appellent `self._dock_panel.clear()` (nouvelle méthode publique sur `DockPanel` qui retire et détruit toutes les entrées) en plus de `_close_all_editors`.

---

## Fichiers modifiés

| Fichier | Action |
|---|---|
| `ui/info_panel.py` | Renommé → `ui/dock_panel.py` (contenu remplacé) |
| `ui/main_window.py` | Mise à jour imports, splitter, signaux, handlers |
| `ui/editor/editor_window.py` | Ajout bouton Dock, signal `dock_requested`, méthode `extract_form()` |

---

## Ce qui ne change pas

- `NodeForm` (`ui/editor/node_form.py`) : aucune modification.
- `GraphCanvas`, `ToolBar`, `EdgeItem`, `NodeItem` : non touchés.
- Logique de sauvegarde/chargement fichier : non touchée.
