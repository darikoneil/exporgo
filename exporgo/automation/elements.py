from datetime import datetime
from enum import IntEnum
from pathlib import Path
from pydantic import BaseModel, Field, field_serializer
from ..types import Folder
from ..tools import get_full_windows_user

"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// WINDOWS ENUMERATIONS
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class RunLevel(IntEnum):
    LeastPrivilege = 0
    HighestAvailable = 1


class LogonType(IntEnum):
    NONE = 0
    PASSWORD = 1
    S4U = 2
    InteractiveToken = 3
    GROUP = 4
    SERVICE_ACCOUNT = 5
    INTERACTIVE_TOKEN_OR_PASSWORD = 6


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Valid Elements for Windows Task Scheduler
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


# The following classes are used to define the elements of a Windows Task Scheduler task.
# The classes are used to define the structure of the XML file that is used to create a task.
# These are not complete, but they should be sufficient for the majority of users.
# The fields are named for user clarity and are not necessarily the same as the Windows Task Scheduler field names.
# The serialization aliases are used to match the field names to the names used in the Windows Task Scheduler.


class RegistrationInfo(BaseModel):
    #: The date the task was created
    date: str = Field(default_factory=lambda: str(datetime.now().isoformat()), serialization_alias="Date")

    #: The author of the task
    author: str = Field(default_factory=get_full_windows_user, serialization_alias="Author")

    #: The description of the task
    description: str = Field(default="Task to Execute", serialization_alias="Description")

    #: The name of the task
    name: str = Field(default="Exporgo Task", serialization_alias="URI")

    @field_serializer("name", when_used="always")
    @classmethod
    def serialize_name(cls, value: str) -> str:
        return "\\" + value


class Principal(BaseModel):
    #: The user ID of the principal
    user_id: str = Field(default_factory=get_full_windows_user, serialization_alias="UserID")

    #: The logon type of the principal
    logon_type: LogonType = Field(default=LogonType.InteractiveToken, serialization_alias="LogonType")

    #: The run level of the principal
    run_level: RunLevel = Field(default=RunLevel.HighestAvailable, serialization_alias="RunLevel")

    @field_serializer("logon_type", when_used="always")
    @classmethod
    def serialize_logon_type(cls, value: LogonType) -> str:
        return value.name

    @field_serializer("run_level", when_used="always")
    @classmethod
    def serialize_run_level(cls, value: RunLevel) -> str:
        return value.name


class Exec(BaseModel):
    command: str = Field(default="cmd.exe", serialization_alias="Command")
    arguments: str = Field(default="/c echo Hello World", serialization_alias="Arguments")
    working_directory: Folder = Field(default_factory=Path.cwd, serialization_alias="WorkingDirectory")

    @field_serializer("working_directory", when_used="always")
    @classmethod
    def serialize_working_directory(cls, value: Folder) -> str:
        return str(value)


class Trigger(BaseModel):
    ...


class LogonTrigger(Trigger):
    enabled: bool = Field(default=True, serialization_alias="Enabled")

    @field_serializer("enabled", when_used="always")
    @classmethod
    def serialize_enabled(cls, value: bool) -> str:
        return str(value).lower()
