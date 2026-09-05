from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    SUPPORT_ENGINEER = "SUPPORT_ENGINEER"
    ADMIN = "ADMIN"
