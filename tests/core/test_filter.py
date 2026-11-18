

def test_a_range_filter_has_the_base_attributes():
    from flim.core.filter import RangeFilter

    assert RangeFilter("x", 0, 1).get_description() == ""  # set, no AttributeError
    assert RangeFilter(params={"name": "x"}).get_description() == ""
    # stored parameters without `selected` are applied, as the conversions read them
    assert RangeFilter(params={"name": "x"}).is_selected()
    assert not RangeFilter("x").is_selected()  # a new filter is off
