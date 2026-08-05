import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from exporter import HTMLExporter
from models import NewsItem


class ExporterSecurityTests(TestCase):
    def test_report_drops_script_urls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = HTMLExporter(temp_dir, "tenant-test")
            exporter.generate([
                NewsItem(
                    id="one",
                    title="Unsafe",
                    url="javascript:alert(1)",
                    source="feed",
                    source_type="rss",
                    tags=["test"],
                )
            ], datetime.now(timezone.utc))
            report = Path(temp_dir, "html", "tenant-test", "latest", "current.html").read_text()
            self.assertNotIn("javascript:", report)

