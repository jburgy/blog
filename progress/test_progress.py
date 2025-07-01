from progress import Progress

def test_progress(capfd):
    root = Progress()
    node = root.start("making orange juice", 5)
    for _ in range(5):
        node.completeOne()

    node.end()
    root.end()

    assert capfd.readouterr().out == ""