# -*- coding: utf-8 -*-
"""Начисление вознаграждения за выполненное задание + реферальные уровни."""
from database import BalanceRepository, ReferralRepository, UserRepository


async def grant_task_completion_rewards(session, attempt_user_id: int, task) -> float:
    """
    Зачисляет исполнителю цену задания и реферальные комиссии (20% / 5%).
    Возвращает сумму основного вознаграждения (float).
    """
    user_repo = UserRepository(session)
    bal_repo = BalanceRepository(session)
    ref_repo = ReferralRepository(session)
    amount = float(task.price)
    await user_repo.add_balance(attempt_user_id, amount)
    await bal_repo.add_operation(attempt_user_id, amount, "task_reward", f"Задание {task.id}")

    ref1_id = await ref_repo.get_referrer_for_referee(attempt_user_id)
    if ref1_id and ref1_id != attempt_user_id:
        comm1 = amount * 0.20
        await user_repo.add_balance(ref1_id, comm1)
        await bal_repo.add_operation(
            ref1_id, comm1, "referral_commission_l1", f"Комиссия за реферала (задание {task.id})"
        )

        ref2_id = await ref_repo.get_referrer_for_referee(ref1_id)
        if ref2_id and ref2_id != ref1_id and ref2_id != attempt_user_id:
            comm2 = amount * 0.05
            await user_repo.add_balance(ref2_id, comm2)
            await bal_repo.add_operation(
                ref2_id, comm2, "referral_commission_l2", f"Комиссия за реферала 2 уровня (задание {task.id})"
            )

    return amount
