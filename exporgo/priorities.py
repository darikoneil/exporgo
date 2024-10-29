from enum import Enum


class Priority(Enum):
    CRITICAL = 0
    HIGH = 1
    ABOVE_NORMAL = 2
    NORMAL = 3
    BELOW_NORMAL = 4
    LOW = 5
    IDLE = 6
