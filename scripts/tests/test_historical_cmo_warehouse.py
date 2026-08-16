from load_historical_cmo_warehouse import (LEGISLATIVE,STATEWIDE,STATEWIDE_1990,coverage,
                                           parse_1990_governor,parse_1990_statewide,parse_legislative)


def test_1990_official_workbook_has_all_legislative_districts():
    path,sheets=LEGISLATIVE[1990]
    result=parse_legislative(path,1990,sheets)
    assert result[result.chamber.eq("house")].district.nunique()==105
    assert result[result.chamber.eq("senate")].district.nunique()==35
    assert set(result.party)=={"D","R"}
    assert result.votes.ge(0).all()


def test_1990_governor_archive_has_every_county_and_both_parties():
    result=parse_1990_governor(STATEWIDE/"eagovernor1946-2010.xls")
    assert result.county.nunique()==67
    assert set(result.party)=={"D","R"}
    totals=result.groupby("party").votes.sum().to_dict()
    assert totals=={"D":582106.0,"R":633519.0}


def test_all_1990_statewide_archives_cover_every_county():
    for office,(filename,sheet) in STATEWIDE_1990.items():
        result=parse_1990_statewide(STATEWIDE/filename,office,sheet)
        assert result.county.nunique()==67


def test_cmo_eligibility_contract_starts_in_1994():
    result=coverage()
    assert result.cycle.min()==1994
    assert 1990 not in set(result.cycle)
