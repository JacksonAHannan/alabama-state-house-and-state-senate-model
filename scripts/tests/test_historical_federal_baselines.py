import numpy as np
from build_historical_federal_baselines import federal_office

def test_federal_office_normalizes_legacy_titles_and_districts():
    assert federal_office('US Senator')==('us_senate',None)
    assert federal_office('FOR UNITED STATES SENATOR (Vote For 1)')==('us_senate',None)
    assert federal_office('US Rep, Dist. 4')==('us_house',4)
    assert federal_office('U.S. House #5')==('us_house',5)
    assert federal_office('UNITED STATES REPRESENTATIVE  D6')==('us_house',6)
    assert federal_office('FOR UNITED STATES REPRESENTATIVE, 2ND CONGRESSIONAL DISTRICT')==('us_house',2)
    assert federal_office('State House, District 2')==(None,None)
