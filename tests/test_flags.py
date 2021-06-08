from tomli._parser import Flags


def test_set_for_relative_key():
    flags = Flags()
    head_key = ("a", "b")
    rel_key = ("c", "d")
    flags.set_for_relative_key(head_key, rel_key, Flags.EXPLICIT_NEST)
    assert not flags.is_(("a",), flags.EXPLICIT_NEST)
    assert not flags.is_(("a", "b"), flags.EXPLICIT_NEST)
    assert flags.is_(("a", "b", "c"), flags.EXPLICIT_NEST)
    assert flags.is_(("a", "b", "c", "d"), flags.EXPLICIT_NEST)
    assert not flags.is_(("a", "b", "c", "d", "e"), flags.EXPLICIT_NEST)
