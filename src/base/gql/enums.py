from enum import Enum
import strawberry


@strawberry.enum
class ClockEventType(Enum):
    CLOCK_IN = "ClockIn"
    CLOCK_OUT = "ClockOut"
    BREAK_START = "BreakStart"
    BREAK_END = "BreakEnd"


@strawberry.enum
class TEMPLATE_SOURCE_OBJECT_TYPE(Enum):
    AWARD = "Award"
    POSITION = "Position"
    WORKSITE = "Worksite"


@strawberry.enum
class TEMPLATE_SOURCE_EVENT(Enum):
    CLOCK_IN = "ClockIn"
    CLOCK_OUT = "ClockOut"
    BREAK_START = "BreakStart"
    BREAK_END = "BreakEnd"


@strawberry.enum
class TRANSACTION_TYPE(Enum):
    APPROVED_TIMESHEET = "ApprovedTimesheet"
    VACANCY_QUOTE = "VacancyQuote"


@strawberry.enum
class NOTIFICATION_EVENT_TYPE(Enum):
    NOTIFICATION = "Notification"
    TASK = "Task"
    DOCUMENT = "Document"
    INVOICE = "Invoice"
    TIMESHEET = "Timesheet"
    SHIFT_CONFIRMATION = "ShiftConfirmation"
    CHAT = "Chat"
    CHAT_TYPING = "ChatTyping"
    PARSE_CV_COMPLETED = "ParseCVCompleted"
