from datetime import datetime
from enum import IntEnum
from os import getlogin

from pydantic import BaseModel, Field, field_serializer

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
    INTERACTIVE_TOKEN = 3
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
    author: str = Field(default_factory=getlogin, serialization_alias="Author")

    #: The description of the task
    description: str = Field(default="Task to Execute", serialization_alias="Description")

    #: The name of the task
    name: str = Field(default="Exporgo Task", serialization_alias="URI")


class Principals(BaseModel):
    #: The user ID of the principal
    user_id: str = Field(default_factory=getlogin, serialization_alias="UserID")

    #: The logon type of the principal
    logon_type: LogonType = Field(default=LogonType.INTERACTIVE_TOKEN, serialization_alias="LogonType")

    #: The run level of the principal
    run_level: RunLevel = Field(default=RunLevel.HighestAvailable, serialization_alias="RunLevel")

    @field_serializer("logon_type", when_used="always")
    def serialize_logon_type(self, value):
        return {"LogonType": value.name}

    @field_serializer("run_level", when_used="always")
    def serialize_run_level(self, value):
        return {"RunLevel": value.name}
