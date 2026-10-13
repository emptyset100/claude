# Regénérer le PDF du guide

```bash
pandoc GUIDE_ENSEIGNANT.md -s --section-divs --toc --toc-depth=3 \
  --css docs/guide_style.css -o guide.html
chromium --headless --no-pdf-header-footer --print-to-pdf=GUIDE_ENSEIGNANT.pdf guide.html
```
