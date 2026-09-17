from pathlib import Path
import re

import pandas as pd


def safe_sheet_name(name: str) -> str:
    """
    Make a valid Excel sheet name.
    Excel limits sheet names to 31 characters.
    """

    name = str(name)

    # Remove characters not allowed in Excel sheet names
    name = re.sub(r'[:\\/?*\[\]]', "_", name)

    return name[:31]


def save_metadata_by_test(
    df: pd.DataFrame,
    output_file: str,
) -> None:
    """
    Save one Excel workbook with one sheet per test_psicolog.
    """

    output_path = Path(output_file)

    with pd.ExcelWriter(
        output_path,
        engine="openpyxl",
    ) as writer:

        for test_name, group in df.groupby(
            "file name",
            sort=False,
        ):

            sheet_name = safe_sheet_name(
                test_name
            )

            group.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False,
            )
