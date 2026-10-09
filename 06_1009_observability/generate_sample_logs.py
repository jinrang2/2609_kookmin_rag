"""Generate correlated synthetic logs for Filebeat and SIEM labs (no traffic sent)."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path


KST = timezone(timedelta(hours=9))
PATHS = (
    "/api/products",
    "/api/orders",
    "/api/customers",
    "/api/documents/search",
)
METHODS = ("GET", "POST")
CLIENT_IPS = (
    "1.1.1.1",
    "1.0.0.1",
    "8.8.8.8",
    "8.8.4.4",
    "9.9.9.9",
    "149.112.112.112",
    "168.126.63.1",
    "168.126.63.2",
    "208.67.220.220",
    "208.67.222.222",
)
SIEM_CLIENT_IPS = (
    "10.20.0.10",
    "10.20.0.11",
    "10.20.0.12",
    "10.20.0.13",
)
# Documentation-only addresses; these are not real attacker identities.
ATTACK_IPS = ("198.51.100.23", "203.0.113.45", "203.0.113.66", "198.51.100.99")
SCAN_PATHS = (
    "/.env",
    "/.git/config",
    "/wp-login.php",
    "/phpmyadmin/",
    "/actuator/env",
    "/actuator/heapdump",
    "/admin",
    "/backup.sql",
    "/config.yml",
    "/server-status",
)
SQL_PATHS = (
    "/api/products?id=1%20OR%201%3D1",
    "/api/documents/search?q=%27%20UNION%20SELECT%20username%2Cpassword%20FROM%20users--",
    "/api/products?id=1%3BSELECT%20SLEEP%285%29--",
)
REFERRERS = (
    "-",
    "https://portal.example.com/",
    "https://admin.example.com/orders",
    "https://partner.example.com/search",
)
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 "
    "Safari/537.36 Edg/128.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 "
    "Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S921N) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Mobile "
    "Safari/537.36",
    "curl/8.10.1",
)


@dataclass(frozen=True)
class Request:
    timestamp: datetime
    source_ip: str
    method: str
    url: str
    status: int
    response_bytes: int
    referrer: str
    user_agent: str
    scenario: str = "normal"
    category: str = "web"
    action: str = "http_request"
    user: str | None = None
    message: str = "Request completed"
    request_id: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nginx access 로그와 Spring Boot JSON 로그를 생성합니다."
    )
    parser.add_argument(
        "--count", type=int, default=1_000, help="로그별 생성 건수(공격 포함)"
    )
    parser.add_argument(
        "--scenario",
        choices=("baseline", "siem"),
        default="baseline",
        help="baseline: 기존 HTTP 실습, siem: 정상 요청과 보안 시나리오 혼합",
    )
    parser.add_argument(
        "--attack-rate",
        type=float,
        default=0.25,
        help="SIEM 모드의 공격 요청 비율(기본값: 0.25, 공격 최소 100건)",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        help="로그 종료 시각(시간대 포함 ISO 8601). 생략하면 현재 KST 시각",
    )
    parser.add_argument("--append", action="store_true", help="기존 로그 뒤에 추가")
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.05,
        help="일반 요청의 500 오류 비율(0.0~1.0, 기본값: 0.05)",
    )
    parser.add_argument(
        "--minutes", type=int, default=60, help="로그가 분포할 최근 시간 범위"
    )
    parser.add_argument("--seed", type=int, default=42, help="난수 시드")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "logs",
        help="출력 디렉터리",
    )
    args = parser.parse_args()

    if args.count <= 0:
        parser.error("--count는 1 이상이어야 합니다.")
    if not 0.0 <= args.error_rate <= 1.0:
        parser.error("--error-rate는 0.0에서 1.0 사이여야 합니다.")
    if args.minutes <= 0:
        parser.error("--minutes는 1 이상이어야 합니다.")
    if not 0.0 <= args.attack_rate <= 1.0:
        parser.error("--attack-rate는 0.0에서 1.0 사이여야 합니다.")
    if args.scenario == "siem" and round(args.count * args.attack_rate) < 100:
        parser.error(
            "SIEM 시나리오에는 공격 최소 100건이 필요합니다. --count 또는 --attack-rate를 늘리세요."
        )
    if args.end_time:
        try:
            args.end_time = datetime.fromisoformat(args.end_time)
        except ValueError:
            parser.error("--end-time은 ISO 8601 형식이어야 합니다.")
        if args.end_time.tzinfo is None:
            parser.error("--end-time에는 +09:00 같은 시간대가 필요합니다.")
        args.end_time = args.end_time.astimezone(KST)

    return args


def make_statuses(count: int, error_rate: float, rng: random.Random) -> list[int]:
    error_count = round(count * error_rate)
    statuses = [500] * error_count + [200] * (count - error_count)
    rng.shuffle(statuses)
    return statuses


def make_timestamps(
    count: int, minutes: int, rng: random.Random, end: datetime
) -> list[datetime]:
    start = end - timedelta(minutes=minutes)
    timestamps = [
        start + timedelta(seconds=rng.uniform(0, minutes * 60)) for _ in range(count)
    ]
    return sorted(timestamps)


def make_requests(args: argparse.Namespace) -> list[Request]:
    rng = random.Random(args.seed)
    end = args.end_time or datetime.now(KST).replace(microsecond=0)
    attack_count = (
        round(args.count * args.attack_rate) if args.scenario == "siem" else 0
    )
    normal_count = args.count - attack_count
    client_ips = SIEM_CLIENT_IPS if args.scenario == "siem" else CLIENT_IPS
    requests = []
    for timestamp, status in zip(
        make_timestamps(normal_count, args.minutes, rng, end),
        make_statuses(normal_count, args.error_rate, rng),
    ):
        requests.append(
            Request(
                timestamp=timestamp,
                source_ip=rng.choice(client_ips),
                method=rng.choices(METHODS, weights=(7, 3), k=1)[0],
                url=rng.choice(PATHS),
                status=status,
                response_bytes=rng.randint(500, 5_000)
                if status == 200
                else rng.randint(100, 500),
                referrer=rng.choices(REFERRERS, weights=(35, 30, 20, 15), k=1)[0],
                user_agent=rng.choices(
                    USER_AGENTS, weights=(35, 20, 15, 10, 15, 5), k=1
                )[0],
                user=rng.choice(("alice", "bob", "carol")),
                message="Request completed"
                if status == 200
                else "Internal server error",
            )
        )

    if attack_count:
        # Each group occupies <=30 seconds, inside the most recent four minutes.
        # This makes threshold/sequence demonstrations work even with --minutes 1.
        duration = min(args.minutes * 60, 240)
        attack_start = end - timedelta(seconds=duration)
        span = min(30, duration / 6)
        auth_count = attack_count // 4
        scan_count = attack_count // 5
        sql_count = attack_count * 15 // 100
        burst_count = attack_count - auth_count - scan_count - sql_count
        groups = (
            ("account_attack", auth_count),
            ("path_scan", scan_count),
            ("sql_injection", sql_count),
            ("request_burst", burst_count),
        )
        for group_index, (scenario, size) in enumerate(groups):
            for index in range(size):
                timestamp = attack_start + timedelta(
                    seconds=group_index * duration / 5 + span * index / max(size - 1, 1)
                )
                request = Request(
                    timestamp=timestamp,
                    source_ip=ATTACK_IPS[group_index],
                    method="GET",
                    url="/api/products",
                    status=200,
                    response_bytes=1200,
                    referrer="-",
                    user_agent="curl/8.10.1",
                    scenario=scenario,
                )
                if scenario == "account_attack":
                    if index < size - 3:
                        request = replace(
                            request,
                            method="POST",
                            url="/api/auth/login",
                            status=401,
                            response_bytes=180,
                            category="authentication",
                            action="login_failed",
                            user="admin",
                            message="Invalid credentials",
                        )
                    elif index == size - 3:
                        request = replace(
                            request,
                            method="POST",
                            url="/api/auth/login",
                            category="authentication",
                            action="login_success",
                            user="admin",
                            message="User logged in",
                        )
                    elif index == size - 2:
                        request = replace(
                            request,
                            url="/api/admin/settings",
                            status=403,
                            response_bytes=180,
                            action="access_denied",
                            user="admin",
                            message="Insufficient permissions",
                        )
                    else:
                        request = replace(
                            request,
                            url="/api/customers/export",
                            response_bytes=25_000_000,
                            action="customer_export",
                            user="admin",
                            message="Customer export completed",
                        )
                elif scenario == "path_scan":
                    request = replace(
                        request,
                        url=SCAN_PATHS[index % len(SCAN_PATHS)],
                        status=404,
                        response_bytes=180,
                        message="Resource not found",
                    )
                elif scenario == "sql_injection":
                    request = replace(
                        request,
                        url=SQL_PATHS[index % len(SQL_PATHS)],
                        status=403,
                        response_bytes=180,
                        user_agent="sqlmap/1.8.9",
                        action="request_blocked",
                        message="Request rejected by input validation",
                    )
                else:
                    request = replace(
                        request,
                        status=429 if index % 4 == 0 else 200,
                        user_agent="python-requests/2.32.3",
                        message="Rate limit exceeded"
                        if index % 4 == 0
                        else "Request completed",
                    )
                requests.append(request)

    requests.sort(key=lambda request: request.timestamp)
    return [
        replace(
            request,
            request_id=f"{end.strftime('%Y%m%d%H%M%S')}-{rng.getrandbits(128):032x}",
        )
        for request in requests
    ]


def generate_nginx_log(
    output_file: Path, requests: list[Request], append: bool = False
) -> int:
    with output_file.open(
        "a" if append else "w", encoding="utf-8", newline="\n"
    ) as log_file:
        for request in requests:
            # English month names are required by the Nginx parser, regardless of OS locale.
            month = (
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            )
            timestamp = request.timestamp
            nginx_time = f"{timestamp.day:02d}/{month[timestamp.month - 1]}/{timestamp.strftime('%Y:%H:%M:%S %z')}"
            line = (
                f"{request.source_ip} - - [{nginx_time}] "
                f'"{request.method} {request.url} HTTP/1.1" {request.status} {request.response_bytes} '
                f'"{request.referrer}" "{request.user_agent}"'
            )
            log_file.write(line + "\n")
    return sum(request.status == 500 for request in requests)


def generate_spring_log(
    output_file: Path, requests: list[Request], append: bool = False
) -> int:
    with output_file.open(
        "a" if append else "w", encoding="utf-8", newline="\n"
    ) as log_file:
        for request in requests:
            path, _, query = request.url.partition("?")
            event = {
                "@timestamp": request.timestamp.isoformat(timespec="milliseconds"),
                "ecs.version": "8.0.0",
                "event.kind": "event",
                "event.dataset": "spring.application",
                "event.category": [request.category],
                "event.type": [
                    "start"
                    if request.category == "authentication"
                    else "denied"
                    if request.status in (401, 403, 429)
                    else "access"
                ],
                "event.action": request.action,
                "event.outcome": "success" if request.status < 400 else "failure",
                "service.name": "shop-api",
                "host.name": "lab-app-01",
                "source.ip": request.source_ip,
                "source.address": request.source_ip,
                "destination.ip": "10.20.1.10",
                "destination.port": 8080,
                "http.request.id": request.request_id,
                "http.request.method": request.method,
                "url.original": request.url,
                "url.path": path,
                "http.response.status_code": request.status,
                "http.response.body.bytes": request.response_bytes,
                "user_agent.original": request.user_agent,
                "log.level": "ERROR"
                if request.status >= 500
                else "WARN"
                if request.status >= 400
                else "INFO",
                "message": request.message,
                "tags": ["synthetic", "filebeat-lab"],
                "labels.lab_scenario": request.scenario,
            }
            if request.user:
                event["user.name"] = request.user
            if query:
                event["url.query"] = query
            log_file.write(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            )

    return sum(request.status == 500 for request in requests)


def main() -> None:
    args = parse_args()
    nginx_file = args.output_dir / "nginx.log"
    spring_file = args.output_dir / "spring.log"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    requests = make_requests(args)
    nginx_errors = generate_nginx_log(nginx_file, requests, args.append)
    spring_errors = generate_spring_log(spring_file, requests, args.append)

    print(f"Nginx: {nginx_file} ({args.count}건, 500 오류 {nginx_errors}건)")
    print(f"Spring: {spring_file} ({args.count}건, 500 오류 {spring_errors}건)")
    for scenario, count in sorted(
        Counter(request.scenario for request in requests).items()
    ):
        print(f"  {scenario}: {count}건")


if __name__ == "__main__":
    main()
