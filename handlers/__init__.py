# -*- coding: utf-8 -*-
from .user import router as user_router
from .admin import router as admin_router
from .manager import router as manager_router
from .staff_settings import router as staff_settings_router

__all__ = ["user_router", "admin_router", "manager_router", "staff_settings_router"]
