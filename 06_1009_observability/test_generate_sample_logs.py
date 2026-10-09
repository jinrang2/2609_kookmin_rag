"""Regression checks for correlated requests and SIEM demonstration patterns."""

import argparse
import json
import re
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import generate_sample_logs as generator


class SampleLogsTest(unittest.TestCase):
    def args(self, **overrides):
        values = dict(count=1000, error_rate=0.05, minutes=60, seed=42,
                      scenario="siem", attack_rate=0.25,
                      end_time=datetime(2026, 10, 7, 23, 0, tzinfo=generator.KST))
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_counts_errors_timing_and_reproducibility(self):
        args = self.args()
        requests = generator.make_requests(args)
        self.assertEqual(len(requests), args.count)
        self.assertEqual(requests, generator.make_requests(args))
        self.assertEqual(Counter(r.scenario for r in requests),
                         dict(normal=750, account_attack=62, path_scan=50,
                              sql_injection=37, request_burst=101))
        self.assertEqual(sum(r.status == 500 for r in requests), round(750 * 0.05))
        self.assertEqual(len({r.request_id for r in requests}), args.count)
        self.assertEqual(requests, sorted(requests, key=lambda r: r.timestamp))
        for request in requests:
            self.assertLessEqual(request.timestamp, args.end_time)
            self.assertGreaterEqual(request.timestamp, args.end_time - timedelta(minutes=60))
            if request.scenario != "normal":
                self.assertGreaterEqual(request.timestamp, args.end_time - timedelta(minutes=4))

    def test_baseline_and_error_rate_extremes(self):
        for rate in (0, 0.05, 1):
            requests = generator.make_requests(self.args(scenario="baseline", count=101, error_rate=rate))
            self.assertEqual(len(requests), 101)
            self.assertEqual(sum(r.status == 500 for r in requests), round(101 * rate))
            self.assertEqual({r.scenario for r in requests}, {"normal"})
            self.assertTrue(all(r.source_ip in generator.CLIENT_IPS for r in requests))

    def test_minimum_attack_budget_still_supports_detections(self):
        for total, rate in ((100, 1), (400, 0.25), (1001, 0.25)):
            requests = generator.make_requests(self.args(count=total, attack_rate=rate, minutes=1))
            self.assertEqual(len(requests), total)
            groups = {name: [r for r in requests if r.scenario == name]
                      for name in ("account_attack", "path_scan", "sql_injection", "request_burst")}
            self.assertGreaterEqual(sum(r.action == "login_failed" for r in groups["account_attack"]), 10)
            self.assertGreaterEqual(len(groups["path_scan"]), 10)
            self.assertGreaterEqual(len({r.url for r in groups["path_scan"]}), 5)
            self.assertGreaterEqual(len(groups["request_burst"]), 40)
            for group in groups.values():
                self.assertLessEqual(group[-1].timestamp - group[0].timestamp, timedelta(seconds=30))

    def test_failed_login_success_and_export_share_identity_in_order(self):
        attack = [r for r in generator.make_requests(self.args()) if r.scenario == "account_attack"]
        self.assertEqual({(r.source_ip, r.user) for r in attack}, {("198.51.100.23", "admin")})
        self.assertTrue(all(r.status == 401 for r in attack[:-3]))
        self.assertEqual([r.action for r in attack[-3:]],
                         ["login_success", "access_denied", "customer_export"])
        self.assertLess(attack[-4].timestamp, attack[-3].timestamp)
        self.assertLess(attack[-3].timestamp, attack[-1].timestamp)
        self.assertGreaterEqual(attack[-1].response_bytes, 10_000_000)

    def test_rendered_files_correlate_and_queries_stay_in_query_field(self):
        requests = generator.make_requests(self.args())
        pattern = re.compile(r'^(\S+) - - \[([^\]]+)\] "(\S+) (\S+) HTTP/1.1" (\d+) (\d+) "([^"]*)" "([^"]*)"$')
        with tempfile.TemporaryDirectory() as directory:
            nginx_file, spring_file = Path(directory) / "nginx.log", Path(directory) / "spring.log"
            generator.generate_nginx_log(nginx_file, requests)
            generator.generate_spring_log(spring_file, requests)
            nginx = nginx_file.read_text(encoding="utf-8").splitlines()
            spring = [json.loads(line) for line in spring_file.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(nginx), len(spring))
            for line, event in zip(nginx, spring):
                match = pattern.fullmatch(line)
                self.assertIsNotNone(match)
                ip, time, method, url, status, size, _, ua = match.groups()
                self.assertEqual(ip, event["source.ip"])
                self.assertEqual(method, event["http.request.method"])
                self.assertEqual(url, event["url.original"])
                self.assertEqual(int(status), event["http.response.status_code"])
                self.assertEqual(int(size), event["http.response.body.bytes"])
                self.assertEqual(ua, event["user_agent.original"])
                self.assertEqual(datetime.strptime(time, "%d/%b/%Y:%H:%M:%S %z"),
                                 datetime.fromisoformat(event["@timestamp"]).replace(microsecond=0))
                self.assertNotIn("?", event["url.path"])
                if "?" in url:
                    self.assertEqual(url.partition("?")[2], event["url.query"])
                self.assertEqual(event["event.outcome"], "success" if int(status) < 400 else "failure")

    def test_append_keeps_existing_records(self):
        requests = generator.make_requests(self.args(count=10, scenario="baseline"))
        with tempfile.TemporaryDirectory() as directory:
            for writer, name in ((generator.generate_nginx_log, "nginx.log"),
                                 (generator.generate_spring_log, "spring.log")):
                path = Path(directory) / name
                writer(path, requests)
                original = path.read_bytes()
                writer(path, requests, append=True)
                self.assertEqual(path.read_bytes(), original + original)

    def test_cli_rejects_invalid_rates_counts_and_naive_time(self):
        for flags in (("--count", "0"), ("--minutes", "0"),
                      ("--error-rate", "1.1"), ("--attack-rate", "-0.1"),
                      ("--scenario", "siem", "--count", "100"),
                      ("--end-time", "invalid"), ("--end-time", "2026-10-07T23:00:00")):
            with self.subTest(flags=flags), patch("sys.argv", ["generator", *flags]), \
                 patch("sys.stderr"), self.assertRaises(SystemExit) as error:
                generator.parse_args()
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
