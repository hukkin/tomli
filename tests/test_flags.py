from tomli._parser import Flags


def test_set_for_relative_key():
    flags = Flags()
    head_key = ("a", "b")
    rel_key = ("c", "d")
    flags.set_for_relative_key(head_key, rel_key, Flags.EXPLICIT_NEST)
    assert not flags.has(("a",), flags.EXPLICIT_NEST)
    assert not flags.has(("a", "b"), flags.EXPLICIT_NEST)
    assert flags.has(("a", "b", "c"), flags.EXPLICIT_NEST)
    assert flags.has(("a", "b", "c", "d"), flags.EXPLICIT_NEST)
    assert not flags.has(("a", "b", "c", "d", "e"), flags.EXPLICIT_NEST)
