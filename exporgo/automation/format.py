from pydantic import BaseModel, Field
from os import getlogin


class RegistrationInfo(BaseModel):
    author: str = Field(getlogin(), title="Author of the task", serialization_alias="Author")
    date: str = Field(None, title="Date of the task", serialization_alias="Date")
    description: str = Field(None, title="Description of the task", serialization_alias="Description")
    documentation: str = Field(None, title="Documentation of the task", serialization_alias="Documentation")
    security: str = Field(None, title="Security descriptor of the task",
                          serialization_alias="SecurityDescriptor")
    source: str = Field(None, title="Source of the task", serialization_alias="Source")
    uri: str = Field(None, title="URI of the task", serialization_alias="URI")
    version: str = Field(None, title="Version of the task", serialization_alias="Version")


class ExecAction(BaseModel):
    arguments: str = Field(None, title="Arguments of the exec action", serialization_alias="Arguments")
    id: str = Field(None, title="ID of the exec action", serialization_alias="ID")
    path: str = Field(None, title="Path of the exec action", serialization_alias="Path")
    working_directory: str = Field(None, title="Working directory of the exec action",
                                   serialization_alias="WorkingDirectory")


class EventTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    delay: str = Field(None, title="Delay of the event trigger", serialization_alias="Delay")
    enabled: bool = Field(True, title="Enable the event trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the event trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the event trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the event trigger", serialization_alias="ID")
    repetition: str = Field(None, title="Repetition of the event trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the event trigger", serialization_alias="StartBoundary")
    subscription: str = Field(None, title="Subscription of the event trigger", serialization_alias="Subscription")
    valueQueries: str = Field(None, title="Value queries of the event trigger", serialization_alias="ValueQueries")


class TimeTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    enabled: bool = Field(True, title="Enable the time trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the time trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the time trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the time trigger", serialization_alias="ID")
    random_delay: str = Field(None, title="Random delay of the time trigger", serialization_alias="RandomDelay")
    repetition: str = Field(None, title="Repetition of the time trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the time trigger", serialization_alias="StartBoundary")


class DailyTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    days_interval: int = Field(1, title="Days interval of the daily trigger", serialization_alias="DaysInterval")
    enabled: bool = Field(True, title="Enable the daily trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the daily trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the daily trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the daily trigger", serialization_alias="ID")
    random_delay: str = Field(None, title="Random delay of the daily trigger", serialization_alias="RandomDelay")
    repetition: str = Field(None, title="Repetition of the daily trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the daily trigger", serialization_alias="StartBoundary")


class WeeklyTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    days_of_week: str = Field(None, title="Days of week of the weekly trigger", serialization_alias="DaysOfWeek")
    enabled: bool = Field(True, title="Enable the weekly trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the weekly trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the weekly trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the weekly trigger", serialization_alias="ID")
    random_delay: str = Field(None, title="Random delay of the weekly trigger", serialization_alias="RandomDelay")
    repetition: str = Field(None, title="Repetition of the weekly trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the weekly trigger", serialization_alias="StartBoundary")
    weeks_interval: int = Field(1, title="Weeks interval of the weekly trigger", serialization_alias="WeeksInterval")


class MonthlyTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    days_of_month: str = Field(None, title="Days of month of the monthly trigger", serialization_alias="DaysOfMonth")
    enabled: bool = Field(True, title="Enable the monthly trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the monthly trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the monthly trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the monthly trigger", serialization_alias="ID")
    months_of_year: str = Field(None, title="Months of year of the monthly trigger", serialization_alias="MonthsOfYear")
    random_delay: str = Field(None, title="Random delay of the monthly trigger", serialization_alias="RandomDelay")
    repetition: str = Field(None, title="Repetition of the monthly trigger", serialization_alias="Repetition")
    runs_on_last_day_of_month: bool = Field(False, title="Runs on last day of month of the monthly trigger",
                                            serialization_alias="RunsOnLastDayOfMonth")
    start_boundary: str = Field(None, title="Start boundary of the monthly trigger", serialization_alias="StartBoundary")
    months_interval: int = Field(1, title="Months interval of the monthly trigger", serialization_alias="MonthsInterval")


class IdleTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    enabled: bool = Field(True, title="Enable the idle trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the idle trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the idle trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the idle trigger", serialization_alias="ID")
    repetition: str = Field(None, title="Repetition of the idle trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the idle trigger",
                                serialization_alias="StartBoundary")


class BootTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    enabled: bool = Field(True, title="Enable the boot trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the boot trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the boot trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the boot trigger", serialization_alias="ID")
    repetition: str = Field(None, title="Repetition of the boot trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the boot trigger",
                                serialization_alias="StartBoundary")


class LogonTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    delay: str = Field(None, title="Delay of the logon trigger", serialization_alias="Delay")
    enabled: bool = Field(True, title="Enable the logon trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the logon trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the logon trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the logon trigger", serialization_alias="ID")
    repetition: str = Field(None, title="Repetition of the logon trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the logon trigger", serialization_alias="StartBoundary")


class RegistrationTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    delay: str = Field(None, title="Delay of the registration trigger", serialization_alias="Delay")
    enabled: bool = Field(True, title="Enable the registration trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the registration trigger", serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the registration trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the registration trigger", serialization_alias="ID")
    repetition: str = Field(None, title="Repetition of the registration trigger", serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the registration trigger", serialization_alias="StartBoundary")


class SessionStateChangeTrigger(BaseModel):
    #  PnYnMnDTnHnMnS
    delay: str = Field(None, title="Delay of the session state change trigger", serialization_alias="Delay")
    enabled: bool = Field(True, title="Enable the session state change trigger", serialization_alias="Enabled")
    end_boundary: str = Field(None, title="End boundary of the session state change trigger",
                              serialization_alias="EndBoundary")
    execution_time_limit: str = Field(None, title="Execution time limit of the session state change trigger",
                                      serialization_alias="ExecutionTimeLimit")
    id: str = Field(None, title="ID of the session state change trigger", serialization_alias="ID")
    repetition: str = Field(None, title="Repetition of the session state change trigger",
                            serialization_alias="Repetition")
    start_boundary: str = Field(None, title="Start boundary of the session state change trigger",
                                serialization_alias="StartBoundary")
    state_change: str = Field(None, title="State change of the session state change trigger",
                              serialization_alias="StateChange")


class Principals:
    principal: str = Field(None, title="Principal of the task", serialization_alias="Principal")
    user_id: str = Field(None, title="User ID of the task", serialization_alias="UserID")
    run_level: str = Field(None, title="Run level of the task", serialization_alias="RunLevel")


class Settings:
    ...


class Task:
    ...


class Scheduler:
    ...
