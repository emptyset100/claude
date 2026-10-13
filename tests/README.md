# Tests headless (sans interface)

Ces scripts chargent l'extension dans le module Python officiel de Blender
(`bpy` sur PyPI) et la vérifient sans ouvrir Blender.

```bash
python3.13 -m venv .venv
.venv/bin/pip install bpy==5.2.2
.venv/bin/pip install --no-deps realfn_viewer/wheels/*.whl

# Tous les presets intégrés + opérateurs + vérification numérique du compilateur
.venv/bin/python -I tests/test_presets_and_ops.py realfn_viewer          # ~3 min
.venv/bin/python -I tests/test_presets_and_ops.py realfn_viewer --quick  # sans les presets

# Dessin de tous les panneaux avec un layout simulé qui valide chaque
# layout.prop / layout.operator / icône contre la vraie API RNA
.venv/bin/python -I tests/test_panels_draw.py realfn_viewer
```

Cinématique animée (ex-Vector Viewer, sous-paquet `kinematics`) :

```bash
.venv/bin/python -I tests/test_vector_viewer.py realfn_viewer   # presets, drivers, sliders, pont F(t) → r, v, a
```

`test_panels_draw.py` couvre aussi les panneaux de cinématique.

Limite connue : en mode headless, `depsgraph_update_post` n'est jamais
appelé ; le test de synchronisation de x₀ appelle donc le handler
directement.
