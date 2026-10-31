# Documentation localization

This documentation uses Sphinx gettext catalogs. We keep doc translations in
`doc/locale/` so they stay separate from the app UI translations in `src/`.

## Update POT and PO files

We use one pattern for doc translations:

1. Regenerate the gettext templates with `make gettext`.
2. Merge those template changes into every existing `doc/locale/*/LC_MESSAGES/*.po`
   file with `msgmerge`.

```bash
cd doc
make gettext

find locale -path '*/LC_MESSAGES/*.po' -print0 | while IFS= read -r -d '' po; do
  pot="locale/$(basename "${po%.po}").pot"
  [ -f "$pot" ] || continue
  msgmerge --update --no-fuzzy-matching "$po" "$pot"
done
```

This updates each existing PO file in place and disables fuzzy matching during
the merge.

## Validate PO files

After updating or importing doc translations, validate all doc PO files with:

```bash
cd doc
python3 ../src/language/test_translations.py --docs
```

This checks PO syntax with `msgfmt`, verifies Python-style placeholders still
match the source strings, and ensures Sphinx substitution tokens such as
`|icon_echo|` are not dropped or added accidentally.

Translator note: do not translate Sphinx substitution tokens like
`|icon_echo|`. Keep the `|...|` text unchanged in `msgid`/`msgstr`.

## Build localized docs

```bash
cd doc
make html SPHINXOPTS="-D language=<lang> -D ga4_measurement_id=G-XXXX"
```

Sphinx will load PO files from `doc/locale/` via `locale_dirs` in `doc/conf.py`.

## Create language translations for openshot.org website

```bash
  cd doc
  make html SPHINXOPTS="-D ga4_measurement_id=G-W2VHM9Y8QH"

 # languages from locale folders
  langs=$(find locale -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

  mkdir -p _build/html
  for lang in $langs; do
    rm -rf "_build/html/$lang"
    # Share images/CSS, while retaining each language's search and UI scripts.
    OPENSHOT_SHARED_ASSETS=1 sphinx-build -b html -D language="$lang" -D ga4_measurement_id=G-W2VHM9Y8QH . "_build/html/$lang"

  done
```

## Create PDF translations for openshot.org website

```bash
  # languages from locale folders
  langs=$(find locale -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)

  # Install XeLaTeX plus Noto, Noto CJK, and DejaVu fonts before building.

  # Build English PDF and copy into the root html folder
  make latexpdf BUILDDIR="_build/pdf/en"
  cp -f "_build/pdf/en/latex/OpenShotVideoEditor.pdf" "_build/html/OpenShotVideoEditor.pdf"

  # Build translated PDFs and copy into html folders
  for lang in $langs; do
    builddir="_build/pdf/$lang"
    make latexpdf SPHINXOPTS="-D language=$lang" BUILDDIR="$builddir"
    cp -f "$builddir/latex/OpenShotVideoEditor.pdf" "_build/html/$lang/OpenShotVideoEditor.pdf"
  done
```
