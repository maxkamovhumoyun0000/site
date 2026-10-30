# Student channel gate and bot shutdown

Journeys: students can use the app without joining a Telegram channel; the
channel gate can later be re-enabled; production activation leaves the
Student, Teacher and Support bots stopped.

`python3 tests/test_student_bot_switch.py`: three isolated tests passed. The
same tests failed before the fix: the backend ignored `FORCE_SUBSCRIBE=false`,
the bot attempted a Telegram membership request, and activation included the
Student bot. `bash -n scripts/activate_production_release.sh` also passed.

These checks do not measure coverage or test a logged-in mobile app, Telegram,
or a production deployment. The service states must be checked separately.
