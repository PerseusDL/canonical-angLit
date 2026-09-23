Canonical - Ang Literature
=========

This will be the base repo for all text and annotation data published in the PDL

## Beowulf

`data/anon/beowulf` contains Klaeber's 1922 Old English edition, Garnett's
1912 English translation, and Klaeber's line commentary.  The related
Old English–English glossary is a separately citable work in
`data/anon/klaeber_glossary`.

The checked-in TEI is regenerated from the legacy Perseus TEI P4 sources with:

```bash
python3 tools/import_klaeber.py --source-dir /path/to/legacy/Beowulf
```

The importer expands obsolete DTD entities to Unicode and numbers every line
of the Old English edition.  `klaeber.glossary.xml` is the selected glossary
source; the `-test` variant differs principally by replacing literal thorn
characters with legacy entity references.

Tufts University holds the overall copyright to the Perseus Digital Library; the materials therein 
(including all texts, translations, images, descriptions, drawings, etc.) are provided for the 
personal use of students, scholars, and the public. 

Materials within the Perseus DL have varying copyright status: please contact the project for more information 
about a specific component or object.  Copyright is protected by the copyright laws of the United States and 
the Universal Copyright Convention. 

Unless otherwise indicated, all contents of this repository are licensed under a 
Creative Commons Attribution-ShareAlike 3.0 United States License. You must  offer Perseus
any modifications you make. Perseus provides credit for all accepted changes.

# Installing on exist-db

- Install `ant`
- Run `ant` at the root of this repository.
- In the package manager of your existDB install, select your .xar file and upload it.
- You have now the Perseus Canonical Ang Lit installed in your repository.
