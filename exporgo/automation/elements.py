from datetime import datetime
from enum import IntEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_serializer

from ..tools import get_full_windows_user, get_windows_user_security_identifier
from ..types import Folder

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
    InteractiveToken = 3  # noqa: CCE001
    GROUP = 4
    SERVICE_ACCOUNT = 5
    INTERACTIVE_TOKEN_OR_PASSWORD = 6


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Valid Elements for Windows Task Scheduler (Triggers in Next Section)
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
    user_id: str = Field(default_factory=get_windows_user_security_identifier, serialization_alias="UserId")

    #: The logon type of the principal
    logon_type: LogonType = Field(default=LogonType.InteractiveToken, serialization_alias="LogonType")

    #: The run level of the principal
    run_level: RunLevel = Field(default=RunLevel.LeastPrivilege, serialization_alias="RunLevel")

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


class IdleSettings(BaseModel):
    """
    :cvar stop_on_idle_end: bool: stop the task when the system is no longer idle
    :cvar restart_on_idle: bool: restart the task when the system is idle
    """

    stop_on_idle_end: bool = Field(default=False, serialization_alias="StopOnIdleEnd")

    restart_on_idle: bool = Field(default=False, serialization_alias="RestartOnIdle")

    @field_serializer("stop_on_idle_end", "restart_on_idle", when_used="always")
    @classmethod
    def serialize_stop_on_idle_end(cls, value: bool) -> str:
        return str(value).lower()


class Settings(BaseModel):
    """

    :cvar multiple_instances_policy: str: policy for multiple instances of the task
    :cvar disallow_start_if_on_batteries: bool: disallow starting the task if the system is on batteries
    :cvar stop_if_going_on_batteries: bool: stop the task if the system goes on batteries
    :cvar allow_hard_terminate: bool: allow the task to be hard terminated
    :cvar start_when_available: bool: start the task when available
    :cvar run_only_if_network_available: bool: run the task only if the network is available
    :cvar idle_settings: IdleSettings: settings for the task when the system is idle
    :cvar allow_start_on_demand: bool: allow the task to be started on demand
    :cvar enabled: bool: enable the task
    :cvar hidden: bool: hide the task
    :cvar run_only_if_idle: bool: run the task only if the system is idle
    :cvar wake_to_run: bool: wake the system to run the task
    :cvar execution_time_limit: str: time limit for the task to run
    :cvar priority: int: priority of the task
    """
    multiple_instances_policy: str = Field(default="IgnoreNew", serialization_alias="MultipleInstancesPolicy")

    disallow_start_if_on_batteries: bool = Field(default=False, serialization_alias="DisallowStartIfOnBatteries")

    stop_if_going_on_batteries: bool = Field(default=True, serialization_alias="StopIfGoingOnBatteries")

    allow_hard_terminate: bool = Field(default=False, serialization_alias="AllowHardTerminate")

    start_when_available: bool = Field(default=False, serialization_alias="StartWhenAvailable")

    run_only_if_network_available: bool = Field(default=False, serialization_alias="RunOnlyIfNetworkAvailable")

    idle_settings: IdleSettings = Field(default_factory=IdleSettings, serialization_alias="IdleSettings")

    allow_start_on_demand: bool = Field(default=False, serialization_alias="AllowStartOnDemand")

    enabled: bool = Field(default=True, serialization_alias="Enabled")

    hidden: bool = Field(default=False, serialization_alias="Hidden")

    run_only_if_idle: bool = Field(default=False, serialization_alias="RunOnlyIfIdle")

    wake_to_run: bool = Field(default=False, serialization_alias="WakeToRun")

    execution_time_limit: str = Field(default="PT0S", serialization_alias="ExecutionTimeLimit")

    priority: int = Field(default=7, serialization_alias="Priority")

    @field_serializer("disallow_start_if_on_batteries",
                      "stop_if_going_on_batteries",
                      "allow_hard_terminate",
                      "start_when_available",
                      "run_only_if_network_available",
                      "allow_start_on_demand",
                      "enabled",
                      "hidden",
                      "run_only_if_idle",
                      "wake_to_run",
                      when_used="always")
    @classmethod
    def serialize_bool(cls, value: bool) -> str:
        return str(value).lower()


"""
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Valid Elements for Windows Task Scheduler (Triggers)
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
"""


class Trigger(BaseModel):
    ...  # noqa: CCE002


class LogonTrigger(Trigger):
    enabled: bool = Field(default=True, serialization_alias="Enabled")

    @field_serializer("enabled", when_used="always")
    @classmethod
    def serialize_enabled(cls, value: bool) -> str:
        return str(value).lower()
