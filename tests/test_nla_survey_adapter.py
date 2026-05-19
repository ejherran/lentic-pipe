from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.data.adapters.nla_survey import COMBINED_USECOLS, build_observations


REPO_ROOT = Path(__file__).resolve().parents[1]


def _variables_config() -> dict:
    with (REPO_ROOT / "configs/variables.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {column: "NA" for column in COMBINED_USECOLS}
    row.update(
        {
            "PUBLICATION_DATE": "6/3/2022",
            "UNIQUE_ID": "NLA_NV-10109",
            "UID": "2010177",
            "SITE_ID": "NLA17_NV-10018",
            "VISIT_NO": 1,
            "IND_DOMAIN": "CORE",
            "DSGN_CYCLE": 2017,
            "PSTL_CODE": "NV",
            "AG_ECO9": "XER",
            "AG_ECO3": "WMTNS",
            "EPA_REG": "Region_09",
            "LAT_DD83": 39.54188,
            "LON_DD83": -119.7789,
            "LAKE_ORGN": "MAN_MADE",
            "TNT_CAT": "Target",
            "CHLA_COND": "Good",
            "DIS_O2_CLS": "High (>=5 ppm)",
            "PTL_COND": "Poor",
            "NTL_COND": "Poor",
            "TROPHIC_STATE": "Mesotrophic",
            "CHLA_MDL": 0.39,
            "CHLA_NARS_FLAG": "NA",
            "CHLA_RESULT": 5.19,
            "DO_SURF": 6.366,
            "NTL_MDL": 0.003,
            "NTL_NARS_FLAG": "NA",
            "NTL_RESULT": 1.343,
            "PTL_MDL": 1.2,
            "PTL_NARS_FLAG": "NA",
            "PTL_RESULT": 92.325,
        }
    )
    row.update(overrides)
    return row


def test_nla_survey_adapter_converts_combined_population_estimate_file(tmp_path: Path) -> None:
    raw_dir = tmp_path / "nla"
    raw_dir.mkdir()
    relative_path = Path("2022/nla2007-2022_data_forpopestimates_indexvisits_probsites_0.csv")
    raw_path = raw_dir / relative_path
    raw_path.parent.mkdir()
    pd.DataFrame([_row(UID=2020238, UNIQUE_ID="NLA_AZ-10100", SITE_ID="NLA22_AZ-10009", DSGN_CYCLE=2022)]).to_csv(
        raw_path,
        index=False,
    )
    sample_grid = raw_dir / "2022/nla2022_sample_grid.csv"
    pd.DataFrame(
        [
            {
                "UID": 2020238,
                "SITE_ID": "NLA22_AZ-10009",
                "VISIT_NO": 1,
                "UNIQUE_ID": "NLA_AZ-10100",
                "DATE_COL": "5/9/2022",
            }
        ]
    ).to_csv(sample_grid, index=False)
    sampled_lake_2007 = raw_dir / "2007/NLA2007_SampledLakeInformation_20091113.csv"
    sampled_lake_2007.parent.mkdir()
    pd.DataFrame(columns=["SITE_ID", "VISIT_NO", "DATE_COL"]).to_csv(sampled_lake_2007, index=False)

    frame = build_observations(
        {
            "raw_path": raw_dir.as_posix(),
            "format": {
                "main_files": {"combined_population_estimates": relative_path.as_posix()},
                "date_files": {
                    "sample_grid_2022": "2022/nla2022_sample_grid.csv",
                    "sampled_lake_information_2007": "2007/NLA2007_SampledLakeInformation_20091113.csv",
                },
            },
        },
        _variables_config(),
    )

    assert len(frame) == 4
    assert sorted(frame["variable_canonical"].tolist()) == ["DO_mgL", "TN_ugL", "TP_ugL", "chlorophyll_a_ugL"]
    assert frame["source_id"].unique().tolist() == ["nla"]
    assert frame["site_id"].unique().tolist() == ["nla:NLA_AZ-10100"]
    assert frame["year_month"].unique().tolist() == ["2022-05"]

    tn = frame[frame["variable_canonical"] == "TN_ugL"].iloc[0]
    assert tn["value_canonical"] == pytest.approx(1343.0)
    assert tn["conversion"] == "multiply_1000"

    chla = frame[frame["variable_canonical"] == "chlorophyll_a_ugL"].iloc[0]
    flags = json.loads(str(chla["flags_json"]))
    assert flags["sample_date_policy"] == "exact_date_col_joined"
    assert flags["sample_date_raw"] == "5/9/2022"


def test_nla_survey_adapter_uses_nominal_month_when_exact_date_is_unavailable(tmp_path: Path) -> None:
    raw_dir = tmp_path / "nla"
    raw_dir.mkdir()
    relative_path = Path("2022/nla2007-2022_data_forpopestimates_indexvisits_probsites_0.csv")
    raw_path = raw_dir / relative_path
    raw_path.parent.mkdir()
    pd.DataFrame([_row()]).to_csv(raw_path, index=False)
    sample_grid = raw_dir / "2022/nla2022_sample_grid.csv"
    pd.DataFrame(columns=["UID", "SITE_ID", "VISIT_NO", "DATE_COL"]).to_csv(sample_grid, index=False)
    sampled_lake_2007 = raw_dir / "2007/NLA2007_SampledLakeInformation_20091113.csv"
    sampled_lake_2007.parent.mkdir()
    pd.DataFrame(columns=["SITE_ID", "VISIT_NO", "DATE_COL"]).to_csv(sampled_lake_2007, index=False)

    frame = build_observations(
        {
            "raw_path": raw_dir.as_posix(),
            "format": {
                "main_files": {"combined_population_estimates": relative_path.as_posix()},
                "date_files": {
                    "sample_grid_2022": "2022/nla2022_sample_grid.csv",
                    "sampled_lake_information_2007": "2007/NLA2007_SampledLakeInformation_20091113.csv",
                },
            },
        },
        _variables_config(),
    )

    assert frame["year_month"].unique().tolist() == ["2017-07"]
    flags = json.loads(str(frame.iloc[0]["flags_json"]))
    assert flags["sample_date_policy"] == "survey_year_nominal_month"


def test_nla_survey_adapter_uses_2007_site_metadata_when_available(tmp_path: Path) -> None:
    raw_dir = tmp_path / "nla"
    raw_dir.mkdir()
    relative_path = Path("2022/nla2007-2022_data_forpopestimates_indexvisits_probsites_0.csv")
    raw_path = raw_dir / relative_path
    raw_path.parent.mkdir()
    pd.DataFrame(
        [
            _row(
                UID=2007468,
                UNIQUE_ID="NLA_MT-10001",
                SITE_ID="NLA06608-0001",
                VISIT_NO=1,
                DSGN_CYCLE=2007,
            )
        ]
    ).to_csv(raw_path, index=False)
    sample_grid = raw_dir / "2022/nla2022_sample_grid.csv"
    pd.DataFrame(columns=["UID", "SITE_ID", "VISIT_NO", "DATE_COL"]).to_csv(sample_grid, index=False)
    sampled_lake_2007 = raw_dir / "2007/NLA2007_SampledLakeInformation_20091113.csv"
    sampled_lake_2007.parent.mkdir()
    pd.DataFrame(
        [
            {
                "SITE_ID": "NLA06608-0001",
                "VISIT_NO": 1,
                "DATE_COL": "7/31/2007",
                "NHDNAME": "Wurdeman, Lake",
                "LAKENAME": "Lake Wurdeman",
                "HUC_8": "03050201",
                "REACHCODE": "10010001000311",
                "COM_ID": "9301511",
            }
        ]
    ).to_csv(sampled_lake_2007, index=False)

    frame = build_observations(
        {
            "raw_path": raw_dir.as_posix(),
            "format": {
                "main_files": {"combined_population_estimates": relative_path.as_posix()},
                "date_files": {
                    "sample_grid_2022": "2022/nla2022_sample_grid.csv",
                    "sampled_lake_information_2007": "2007/NLA2007_SampledLakeInformation_20091113.csv",
                },
            },
        },
        _variables_config(),
    )

    assert frame["site_name"].dropna().unique().tolist() == ["Lake Wurdeman"]
    assert frame["year_month"].unique().tolist() == ["2007-07"]
    flags = json.loads(str(frame.iloc[0]["flags_json"]))
    assert flags["lake_name_field"] == "Lake Wurdeman"
    assert flags["lake_name_nhd"] == "Wurdeman, Lake"
    assert flags["huc_8"] == "03050201"
    assert flags["com_id"] == "9301511"
