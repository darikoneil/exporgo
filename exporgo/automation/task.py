from pydantic import BaseModel, field_serializer, Field
from .elements import RegistrationInfo, Principal, Exec

"""
////////////////////////////////////////////////////////////////////////////////////////
// Task Structure for Windows Task Scheduler
////////////////////////////////////////////////////////////////////////////////////////
"""


# noinspection HttpUrlsUsage
class Task(BaseModel):
    #: str: version of windows task schema
    _version: str = "1.1"

    #: str: windows task schema xlmns
    _xlmns: str = "http://schemas.microsoft.com/windows/2004/02/mit/task"

    registration_info: RegistrationInfo = Field(None, serialization_alias="RegistrationInfo")

    principal: Principal = Field(None, serialization_alias="Principals")

    actions: Exec = Field(None, serialization_alias="Actions")


    @field_serializer("actions", when_used="always")
    @classmethod
    def serialize_exec(cls, actions: Exec) -> dict:
        return {"Exec": actions.model_dump(by_alias=True)}

    @field_serializer("principal", when_used="always")
    @classmethod
    def serialize_principal(cls, principal: Principal) -> dict:
        return {"Principal": principal.model_dump(by_alias=True)}

