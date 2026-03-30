"""Tests for trace_viewer.storage.ring_buffer module."""

from trace_viewer.storage.ring_buffer import KeywordCapture, RingBuffer


class TestKeywordCapture:
    """Test KeywordCapture dataclass."""

    def test_create_minimal(self):
        capture = KeywordCapture(index=1, name="Open Browser", folder="/tmp/001")
        assert capture.index == 1
        assert capture.name == "Open Browser"
        assert capture.folder == "/tmp/001"
        assert capture.screenshot is None
        assert capture.variables is None
        assert capture.console_logs is None
        assert capture.dom is None
        assert capture.network is None

    def test_create_full(self):
        capture = KeywordCapture(
            index=1,
            name="Click",
            folder="/tmp/001",
            metadata={"status": "PASS"},
            screenshot=b"png_data",
            variables={"scalar": {"FOO": "bar"}},
            console_logs=[{"level": "INFO", "message": "test"}],
            dom="<html></html>",
            network=[{"url": "https://example.com"}],
        )
        assert capture.screenshot == b"png_data"
        assert capture.variables["scalar"]["FOO"] == "bar"
        assert len(capture.console_logs) == 1
        assert capture.dom == "<html></html>"
        assert len(capture.network) == 1


class TestRingBuffer:
    """Test RingBuffer behavior."""

    def test_empty_buffer(self):
        buf = RingBuffer(maxlen=5)
        assert len(buf) == 0
        assert buf.maxlen == 5
        assert not buf.is_full
        assert buf.flush_all() == []

    def test_push_and_len(self):
        buf = RingBuffer(maxlen=5)
        buf.push(KeywordCapture(index=1, name="kw1", folder="/tmp/1"))
        assert len(buf) == 1
        buf.push(KeywordCapture(index=2, name="kw2", folder="/tmp/2"))
        assert len(buf) == 2

    def test_maxlen_eviction(self):
        buf = RingBuffer(maxlen=3)
        for i in range(5):
            buf.push(KeywordCapture(index=i, name=f"kw{i}", folder=f"/tmp/{i}"))
        assert len(buf) == 3
        assert buf.is_full
        captures = buf.flush_all()
        assert [c.index for c in captures] == [2, 3, 4]

    def test_flush_all_clears(self):
        buf = RingBuffer(maxlen=5)
        buf.push(KeywordCapture(index=1, name="kw1", folder="/tmp/1"))
        captures = buf.flush_all()
        assert len(captures) == 1
        assert len(buf) == 0

    def test_clear(self):
        buf = RingBuffer(maxlen=5)
        buf.push(KeywordCapture(index=1, name="kw1", folder="/tmp/1"))
        buf.push(KeywordCapture(index=2, name="kw2", folder="/tmp/2"))
        buf.clear()
        assert len(buf) == 0

    def test_flush_preserves_order(self):
        buf = RingBuffer(maxlen=10)
        for i in range(5):
            buf.push(KeywordCapture(index=i, name=f"kw{i}", folder=f"/tmp/{i}"))
        captures = buf.flush_all()
        assert [c.index for c in captures] == [0, 1, 2, 3, 4]

    def test_default_maxlen(self):
        buf = RingBuffer()
        assert buf.maxlen == 10

    def test_is_full(self):
        buf = RingBuffer(maxlen=2)
        assert not buf.is_full
        buf.push(KeywordCapture(index=1, name="kw1", folder="/tmp/1"))
        assert not buf.is_full
        buf.push(KeywordCapture(index=2, name="kw2", folder="/tmp/2"))
        assert buf.is_full
