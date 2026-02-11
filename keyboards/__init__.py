# -*- coding: utf-8 -*-
from .user import (
    kb_next_training,
    kb_after_training,
    kb_take_task,
    kb_sent_for_review,
    kb_copy_text,
)
from .admin import (
    kb_admin_main,
    kb_admin_back,
    kb_task_approve_reject,
    kb_task_paid,
    kb_links_manage,
    kb_edit_training_step,
)

__all__ = [
    "kb_next_training",
    "kb_after_training",
    "kb_take_task",
    "kb_sent_for_review",
    "kb_copy_text",
    "kb_admin_main",
    "kb_admin_back",
    "kb_task_approve_reject",
    "kb_task_paid",
    "kb_links_manage",
    "kb_edit_training_step",
]
