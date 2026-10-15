"""Check the request contract used by Kibana's per-alert webhook action."""

import json
import unittest

from fastapi.testclient import TestClient

from soar_app import app


class SoarAppTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.payload = {
            "alert_id": "connector-test-001",
            "rule_id": "manual-test",
            "rule_name": "Webhook 연결 테스트",
            "severity": "low",
            "action_time": "manual-test",
        }

    def test_health_and_documented_request_fields(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(self.client.get("/docs").status_code, 200)
        schema = self.client.get("/openapi.json").json()
        fields = schema["components"]["schemas"]["SiemAlert"]["required"]
        self.assertEqual(set(fields), set(self.payload))

    def test_connector_body_and_korean_logging(self):
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            response = self.client.post("/webhook/siem", json=self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "received": True, "alert_id": "connector-test-001",
        })
        self.assertIn("Webhook 연결 테스트", logs.output[0])

    def test_rule_action_body_and_extra_fields(self):
        self.payload.update(
            alert_id="actual-alert-001",
            severity="high",
            action_time="2026-10-13T03:00:00.000Z",
            source={"ip": "198.51.100.23"},
        )
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            response = self.client.post("/webhook/siem", json=self.payload)
        self.assertEqual(response.status_code, 200)
        logged_payload = json.loads(logs.records[0].getMessage().split("\n", 1)[1])
        self.assertEqual(logged_payload, self.payload)
        self.assertEqual(response.json()["alert_id"], "actual-alert-001")

    def test_invalid_body_is_rejected_before_handler(self):
        invalid_bodies = [
            {},
            {**self.payload, "alert_id": "   "},
            {**self.payload, "severity": "unknown"},
            {**self.payload, "rule_id": 123},
            [self.payload],
        ]
        for body in invalid_bodies:
            with self.subTest(body=body), self.assertNoLogs("uvicorn.error"):
                self.assertEqual(
                    self.client.post("/webhook/siem", json=body).status_code, 422,
                )
        response = self.client.post(
            "/webhook/siem", content="{", headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
