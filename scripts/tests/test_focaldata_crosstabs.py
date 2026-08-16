import pandas as pd

from extract_focaldata_votehub_crosstabs import extract_table


def test_extract_focaldata_banner_combines_education_counts():
    f = pd.DataFrame(index=range(13), columns=range(12), dtype=object)
    f.iloc[0, 0] = "House generic ballot by BANNER"
    labels = ["Total", "White", "Black or African American", "Hispanic", "Asian",
              "Other / multiple races", "Did not graduate high school", "High school graduate",
              "Some college, no degree", "Associate's degree (2-year)",
              "Bachelor's degree (4-year)", "Graduate or professional degree"]
    f.iloc[2, :] = labels
    f.iloc[3, 0], f.iloc[5, 0], f.iloc[7, 0], f.iloc[9, 0] = (
        "The Democratic Party candidate", "The Republican Party candidate", "Column n", "Column Population")
    f.iloc[4, :] = 40; f.iloc[6, :] = 50; f.iloc[7, :] = 100; f.iloc[9, :] = 100
    f.iloc[3, :] = ["The Democratic Party candidate"] + [0.4] * 11
    f.iloc[5, :] = ["The Republican Party candidate"] + [0.5] * 11
    # Restore response labels overwritten in column zero while retaining numeric Total in column one.
    f.iloc[3, 0] = "The Democratic Party candidate"; f.iloc[3, 1:] = 0.4
    f.iloc[5, 0] = "The Republican Party candidate"; f.iloc[5, 1:] = 0.5
    # Use a separate Total column, matching real workbooks where col 0 is row label.
    f = pd.concat([pd.Series([None] * len(f), name="row"), f], axis=1)
    f.iloc[0, 0] = "House generic ballot by BANNER"; f.iloc[0, 1] = None
    f.iloc[2, 1:] = labels
    f.iloc[3, 0] = "The Democratic Party candidate"; f.iloc[3, 1:] = 0.4
    f.iloc[4, 1:] = 40
    f.iloc[5, 0] = "The Republican Party candidate"; f.iloc[5, 1:] = 0.5
    f.iloc[6, 1:] = 50
    f.iloc[7, 0] = "Column n"; f.iloc[7, 1:] = 100
    f.iloc[9, 0] = "Column Population"; f.iloc[9, 1:] = 100
    out = extract_table(f, "poll", "https://source")
    assert len(out) == 10
    assert out.loc[out.group.eq("focaldata_hs_or_less"), "cell_base"].iloc[0] == 200
    assert out.loc[out.group.eq("white"), "dem_pct"].iloc[0] == 40
