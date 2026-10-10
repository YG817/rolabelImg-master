def test_startup(window):
    assert window.formatCombo.currentIndex() == 0
    assert not window.usingPascalVocFormat
