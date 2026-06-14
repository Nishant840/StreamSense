from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Union

class LogEvent(BaseModel):
    service:        str
    timestamp:      str
    level:          str
    message:        str
    template:       Optional[str] = None
    template_id:    Union[int, str, None] = None
    anomaly_score:  float
    is_anomaly:     bool

class AnomalyResponse(BaseModel):
    id:             int
    service:        str
    timestamp:      str
    level:          str
    message:        str
    template:       Optional[str] = None
    template_id:    Union[int, str, None] = None
    anomaly_score:  float
    created_at:     datetime

class ServiceStatus(BaseModel):
    service:        str
    status:         str
    anomaly_rate:  float
    last_anomaly:   Optional[str] = None

class WebSocketMessage(BaseModel):
    type:           str
    service:        str
    timestamp:      str
    level:          str
    message:        str
    anomaly_score:  float
    is_anomaly:     bool
    template:       Optional[str] = None
    template_id:    Union[int, str, None] = None