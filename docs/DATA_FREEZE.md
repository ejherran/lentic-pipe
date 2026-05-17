# Data Freeze

The current detailed freeze lives at:

```text
data/freeze/DATA_FREEZE.md
```

That freeze must be regenerated after changes to source metadata, raw source
files, or download scripts. Before DVC initialization or publication, regenerate:

```bash
.venv/bin/python src/data/validate_sources.py
.venv/bin/python src/data/raw_manifest.py --reuse-existing
.venv/bin/python src/data/freeze.py --overwrite
```

The regenerated freeze should include SHA-256 signatures for:

- `data/raw/aquamatch/chla_harmonized_final.csv`
- `data/raw/aquamatch/metadata.xml`
- `data/raw/aquamatch/README.pdf`
- `data/raw/aquamatch/Data_Package_Quality_Report.mhtml`

Do not trust downstream experiment claims against a freeze that does not include
all current raw source files and source metadata files.
