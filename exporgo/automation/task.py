# noinspection PyPep8Naming
from xml.etree import ElementTree as ET

from pydantic import BaseModel, field_serializer, Field
from .elements import LogonTrigger, RegistrationInfo, Principal, Exec

"""
////////////////////////////////////////////////////////////////////////////////////////
// Task Structure for Windows Task Scheduler
////////////////////////////////////////////////////////////////////////////////////////
"""


# noinspection HttpUrlsUsage
class Task(BaseModel):
    #: str: version of windows task schema
    version: str = Field("1.1")

    #: str: windows task schema xlmns
    xmlns: str = Field("http://schemas.microsoft.com/windows/2004/02/mit/task")

    registration_info: RegistrationInfo = Field(None, serialization_alias="RegistrationInfo")

    principal: Principal = Field(None, serialization_alias="Principals")

    actions: Exec = Field(None, serialization_alias="Actions")

    triggers: LogonTrigger = Field(None, serialization_alias="Triggers")

    @field_serializer("actions", when_used="always")
    @classmethod
    def serialize_actions(cls, actions: Exec) -> dict:
        return {"Exec": actions.model_dump(by_alias=True)}

    @field_serializer("principal", when_used="always")
    @classmethod
    def serialize_principal(cls, principal: Principal) -> dict:
        return {"Principal": principal.model_dump(by_alias=True)}

    @field_serializer("registration_info", when_used="always")
    @classmethod
    def serialize_registration_info(cls, registration_info: RegistrationInfo) -> dict:
        return {**registration_info.model_dump(by_alias=True)}

    @field_serializer("triggers", when_used="always")
    @classmethod
    def serialize_triggers(cls, triggers: LogonTrigger) -> dict:
        return {"LogonTrigger": triggers.model_dump(by_alias=True)}

    @classmethod
    def __to_xml__(cls, task: "Task") -> ET.Element:
        serialized_task = task.model_dump(by_alias=True)
        version = serialized_task.pop("version")
        xmlns = serialized_task.pop("xmlns")
        root = ET.Element("Task", version=version, xmlns=xmlns)
        reg = ET.SubElement(root, "RegistrationInfo")
        for key, value in serialized_task.pop("RegistrationInfo").items():
            ET.SubElement(reg, key).text = value
        for key, value in serialized_task.items():
            sub0 = ET.SubElement(root, key)
            for inner_key, inner_value in value.items():
                if isinstance(inner_value, dict):
                    sub1 = ET.SubElement(sub0, inner_key)
                    for k, v in inner_value.items():
                        ET.SubElement(sub1, k).text = v
                else:
                    ET.SubElement(root, inner_key).text = inner_value
        return root
