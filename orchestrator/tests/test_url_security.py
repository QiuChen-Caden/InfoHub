import socket
from unittest import TestCase
from unittest.mock import patch

from url_security import (
    UnsafeUrlError,
    validate_http_url_syntax,
    validate_public_http_url,
    validate_rsshub_route,
)


class UrlSecurityTests(TestCase):
    def test_rejects_private_and_non_http_urls(self):
        for url in (
            "http://127.0.0.1/feed",
            "http://10.1.2.3/feed",
            "http://localhost/feed",
            "file:///etc/passwd",
        ):
            with self.assertRaises(UnsafeUrlError):
                validate_http_url_syntax(url)

    @patch("url_security.socket.getaddrinfo")
    def test_rejects_dns_name_resolving_to_private_ip(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443)),
        ]
        with self.assertRaises(UnsafeUrlError):
            validate_public_http_url("https://example.com/hook")

    @patch("url_security.socket.getaddrinfo")
    def test_accepts_public_dns_result(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]
        self.assertEqual(
            validate_public_http_url("https://example.com/hook"),
            "https://example.com/hook",
        )

    def test_rsshub_route_allowlist(self):
        self.assertEqual(validate_rsshub_route("/zhihu/hot"), "/zhihu/hot")
        with self.assertRaises(UnsafeUrlError):
            validate_rsshub_route("/proxy/http://127.0.0.1")

