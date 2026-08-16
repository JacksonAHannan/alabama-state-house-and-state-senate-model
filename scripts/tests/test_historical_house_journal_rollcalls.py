from extract_historical_house_journal_rollcalls import member_names,parse_document

def test_member_names_handles_speaker_representatives_and_and():
    assert member_names('Mr. Speaker, Representatives Allen, Baker and Black (L).')==['SPEAKER','Allen','Baker','Black (L)']

def test_parse_document_validates_named_tallies_and_bill_context():
    text=('\n<<<PAGE 1>>>\nHB96 MOTION TO REREFER TABLED\nThe motion was tabled.\n'
          'Yeas 3; Nays 2; Abstains 1.\nYea:\nRepresentatives Allen, Baker and Black (L).\n - 3\n'
          'Nay:\nRepresentatives Clark and Dean.\n - 2\nAbstain:\nRepresentative Evans.\n - 1\n')
    rollcalls,votes=parse_document(text,'1998_RegularSession','Day1','example.pdf')
    assert rollcalls[0]['count_valid'] is True
    assert rollcalls[0]['bill_type']=='HB' and rollcalls[0]['bill_number']==96
    assert len(votes)==6
