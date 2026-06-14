import re
from datetime import datetime, timezone

LEVEL_MAP = {
    "DEBUG":    0,
    "INFO":     1,
    "WARNING":  2,
    "ERROR":    3,
    "CRITICAL": 4,
}

SERVICE_MAP = {
    "service-a": 0,
    "service-b": 1,
    "service-c": 2
}

ERROR_KEYWORDS = {
    "exception", "error", "fail", "failed",
    "timeout", "refused", "denied", "crash"
}
WARNING_KEYWORDS = {
    "warning", "warn", "slow", "high", "approaching", "memory"
}

def extract_features(parsed_log: dict) -> list[float]:
    level_encoded   = _encode_level(parsed_log.get("level", "INFO"))
    service_id      = _encode_service(parsed_log.get("service", ""))
    template_id     = _encode_template_id(parsed_log.get("template_id", 0))
    response_time   = _extract_responce_time(parsed_log.get("message", ""))
    is_error        = _is_error_message(parsed_log.get("message", ""))
    is_warning     = _is_warning_message(parsed_log.get("message", ""))
    log_length      = _encode_log_length(parsed_log.get("message", ""))
    has_numeric    = _has_numeric_values(parsed_log.get("message", ""))

    return [
        level_encoded,
        service_id,
        template_id,
        response_time,
        is_error,
        is_warning,
        log_length,
        has_numeric
    ]

def _encode_level(level: str) -> float:
    raw = LEVEL_MAP.get(level.upper(), 1)
    return raw/4.0

    
def _encode_service(service: str) -> float:
    raw = SERVICE_MAP.get(service, 0)
    return raw / max(len(SERVICE_MAP) - 1, 1)

def _encode_template_id(template_id: int) -> float:
    return min(template_id / 100.0, 1.0)

def _extract_response_time(message: str) -> float:
    patterns = [
        r"latency=(\d+)ms",
        r"duration=(\d+)ms",
        r"duration=(\d+)s",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            value = float(match.group(1))
            if "latency" in pattern:
                return min(value / 2000.0, 1.0)
            elif "ms" in pattern:
                return min(value / 2000.0, 1.0)
            else:
                return min(value / 300.0, 1.0)
    return 0.0

def _is_error_message(message: str) -> float:
    message_lower = message.lower()
    for keyword in ERROR_KEYWORDS:
        if keyword in message_lower:
            return 1.0
        
    return 0.0

def _is_warning_message(message: str) -> float:
    message_lower = message.lower()
    for keyword in WARNING_KEYWORDS:
        if keyword in message_lower:
            return 1.0
    return 0.0

def _encode_log_length(message: str) -> float:
    return min(len(message) / 200.0, 1.0)

def _has_numeric_values(message: str) -> float:
    numbers = re.findall(r'\d+', message)
    return min(len(numbers) / 10.0, 1.0)