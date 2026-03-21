from dotenv import load_dotenv

load_dotenv()

from box_data import box_id, box_name  # noqa: E402
from application.use_cases.execute_booking import ExecuteBookingUseCase  # noqa: E402
from application.use_cases.remove_booking import RemoveBookingUseCase  # noqa: E402
from application.use_cases.schedule_booking import ScheduleBookingUseCase  # noqa: E402
from infrastructure.aimharder.client_factory import AimHarderClientFactory  # noqa: E402
from infrastructure.persistence.json_repository import JsonRepository  # noqa: E402
from infrastructure.scheduling.apscheduler import APSchedulerAdapter  # noqa: E402
from infrastructure.telegram.bot import TelegramBot  # noqa: E402
from infrastructure.telegram.group_notifier import TelegramGroupNotifier  # noqa: E402
from infrastructure.telegram.user_notifier import TelegramUserNotifier  # noqa: E402


def bootstrap():
    json_repo = JsonRepository()
    factory = AimHarderClientFactory(box_id=box_id, box_name=box_name)

    telegram_bot = TelegramBot(user_repo=json_repo)
    user_notifier = TelegramUserNotifier(send_fn=telegram_bot.send_message)
    group_notifier = TelegramGroupNotifier()

    execute_uc = ExecuteBookingUseCase(
        json_repo, json_repo, factory, user_notifier, group_notifier
    )
    apscheduler = APSchedulerAdapter(on_job_execute=execute_uc.execute)
    schedule_uc = ScheduleBookingUseCase(json_repo, json_repo, apscheduler, factory)
    remove_uc = RemoveBookingUseCase(json_repo, apscheduler)

    telegram_bot.set_use_cases(schedule_uc, remove_uc)

    # Startup recovery: re-schedule persisted booking goals
    for user in json_repo.get_all_users():
        for goal in user.booking_goals:
            schedule_uc.execute(
                user_id=goal.user_id,
                booking_date=goal.booking_date,
                class_name=goal.name,
            )

    apscheduler.start()

    return {
        "json_repo": json_repo,
        "factory": factory,
        "telegram_bot": telegram_bot,
        "execute_uc": execute_uc,
        "apscheduler": apscheduler,
        "schedule_uc": schedule_uc,
        "remove_uc": remove_uc,
    }


if __name__ == "__main__":
    app = bootstrap()
    app["telegram_bot"].run()
