"""Typed failures from the mtkclient facade."""
import pytest

from mtk_gui.backend import stdio_bridge
from mtk_gui.backend.mtk_wrapper import MtkOperationError, mtk_operation


def test_systemexit_becomes_a_typed_error():
    with pytest.raises(MtkOperationError) as excinfo:
        with mtk_operation("Erase partitions"):
            raise SystemExit(2)
    err = excinfo.value
    assert err.operation == "Erase partitions"
    assert err.exit_code == 2
    assert "Erase partitions failed" in str(err)
    assert "exited with 2" in str(err)


def test_error_quotes_the_output_that_explained_the_failure():
    """The reason was never lost, only unread: mtkclient printed it."""
    stream = stdio_bridge.BufferedTextStream()
    stream.write("Status: DA upload failed, wrong loader\n")

    with pytest.raises(MtkOperationError) as excinfo:
        with mtk_operation("Write partitions"):
            raise SystemExit(1)

    text = str(excinfo.value)
    assert "Last output before the failure" in text
    assert "wrong loader" in text, "the explanation must reach the user"


def test_success_passes_through_untouched():
    with mtk_operation("Read flash"):
        value = 123
    assert value == 123


def test_other_exceptions_are_not_swallowed():
    with pytest.raises(ValueError, match="distinct"):
        with mtk_operation("Read flash"):
            raise ValueError("distinct")


def test_no_exit_code_is_omitted_from_the_message():
    with pytest.raises(MtkOperationError) as excinfo:
        with mtk_operation("Reset device"):
            raise SystemExit(0)
    assert "exited with" not in str(excinfo.value)
