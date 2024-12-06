# noinspection PyPep8Naming
from xml.etree.ElementTree import Element, SubElement
from pydantic import BaseModel, field_serializer, Field
from .elements import LogonTrigger, Trigger, RegistrationInfo, Principal, Exec
from typing import Sequence

"""
////////////////////////////////////////////////////////////////////////////////////////
// Task Structure for Windows Task Scheduler
////////////////////////////////////////////////////////////////////////////////////////
"""


# noinspection HttpUrlsUsage
class Task(BaseModel):
    """
    :cvar version: str: version of windows task schema
    :cvar xmlns: str: windows task schema xlmns
    :cvar registration_info: RegistrationInfo: registration information for the task
    :cvar principal: Principal: principal information for the task
    :cvar actions: Exec: actions to be performed by the task
    :cvar triggers: Trigger | Sequence[Trigger]: triggers for the task

    """
    #: str: version of windows task schema
    version: str = Field("1.2")

    #: str: windows task schema xlmns
    xmlns: str = Field("http://schemas.microsoft.com/windows/2004/02/mit/task")

    registration_info: RegistrationInfo = Field(None, serialization_alias="RegistrationInfo")

    principal: Principal = Field(None, serialization_alias="Principals")

    actions: Exec = Field(None, serialization_alias="Actions")

    triggers: Trigger | Sequence[Trigger] = Field(None, serialization_alias="Triggers")

    @classmethod
    def field_to_xml(cls, field, value, root):
        if isinstance(value, dict):
            primary_element = SubElement(root, field)

            # ------------------------------------------
            # ugh, this is annoying
            if field=="Actions":
                primary_element.attrib["Context"] = "Author"
            elif field=="Principal":
                primary_element.attrib["id"] = "Author"
            # ------------------------------------------

            for key, value in value.items():
                cls.field_to_xml(key, value, primary_element)
        else:
            SubElement(root, field).text = str(value)

    def model_dump_xml(self) -> Element:
        # Don't worry too much about the attributes being out of order, but I am ordered the sub-elements in the order
        # they appear in the reference documentation.
        fields = self.model_dump(by_alias=True)
        _ = fields.pop("version")
        _ = fields.pop("xmlns")
        root = Element("Task", version=self.version, xmlns=self.xmlns)
        for field, serialized in fields.items():
            self.field_to_xml(field, serialized, root)
        return root

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
