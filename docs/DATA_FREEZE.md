# Data Freeze

The current detailed freeze lives at:

```text
data/freeze/DATA_FREEZE.md
```

That freeze must be regenerated after changes to source metadata, raw source
files, or download scripts. After DVC recovery on a new machine, regenerate the
local reproducibility artifacts with:

```bash
scripts/reproduce_data_workspace.sh
```

For a complete heavy rebuild from raw data, use:

```bash
scripts/reproduce_data_workspace.sh --full-rebuild
```

That mode can take hours and rewrites DVC-managed derived artifacts. The
regenerated freeze should include SHA-256 signatures for:

- `data/raw/aquamatch/chla_harmonized_final.csv`
- `data/raw/aquamatch/metadata.xml`
- `data/raw/aquamatch/README.pdf`
- `data/raw/aquamatch/Data_Package_Quality_Report.mhtml`

Do not trust downstream experiment claims against a freeze that does not include
all current raw source files and source metadata files.
