# manage.py

import os
import subprocess

COV = None
if os.environ.get('FLASK_COVERAGE'):
    import coverage

    COV = coverage.coverage(branch=True, include='app/*', config_file=os.path.join(os.curdir, '.coveragerc'))
    COV.start()

from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell, Command

from app import create_app, db
from app.models import Users, Agencies, Requests, Responses, Events, Reasons, Roles

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)


class Celery(Command):
    """
    Start Celery
    """

    # TODO: autoreload and background options?
    # http://stackoverflow.com/questions/21666229/celery-auto-reload-on-any-changes
    # http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html

    def run(self):
        subprocess.call(['celery', 'worker', '-A', 'celery_worker.celery', '--loglevel=info'])


def make_shell_context():
    return dict(
        app=app,
        db=db,
        Users=Users,
        Agencies=Agencies,
        Requests=Requests,
        Responses=Responses,
        Events=Events,
        Reasons=Reasons,
        Roles=Roles
    )


manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command("db", MigrateCommand)
manager.add_command("celery", Celery())


@manager.option("-t", "--test-name", help="Specify tests (file, class, or specific test)", dest='test_name')
@manager.option("-c", "--coverage", help="Run coverage analysis for tests", dest='coverage')
def test(coverage=False, test_name=None):
    """Run the unit tests."""
    if coverage and not os.environ.get('FLASK_COVERAGE'):
        import sys
        os.environ['FLASK_COVERAGE'] = '1'
        os.execvp(sys.executable, [sys.executable] + sys.argv)
    import unittest
    if not test_name:
        tests = unittest.TestLoader().discover('tests', pattern='*.py')
    else:
        tests = unittest.TestLoader().loadTestsFromName('tests.' + test_name)
    unittest.TextTestRunner(verbosity=2).run(tests)

    if COV:
        COV.stop()
        COV.save()
        print('Coverage Summary:')
        COV.report()
        COV.html_report()
        COV.xml_report()


@manager.command
def profile(length=25, profile_dir=None):
    """Start the application under the code profiler."""
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
                                      profile_dir=profile_dir)
    app.run()


@manager.command
def deploy():
    """Run deployment tasks."""
    from flask_migrate import upgrade
    from app.models import Roles, Agencies, Reasons

    # migrate database to latest revision
    upgrade()

    # pre-populate
    list(map(lambda x: x.populate(), (
        Roles,
        Agencies,
        Reasons
    )))

    es_recreate()
    create_users()


@manager.command
def es_recreate():
    """Recreate elasticsearch index and request docs."""
    from app.search.utils import recreate
    recreate()


@manager.command
def create_search_set():
    """Create a number of requests for test purposes."""
    from tests.lib.tools import create_requests_search_set
    from app.constants.user_type_auth import PUBLIC_USER_TYPES
    import random

    users = random.sample(PUBLIC_USER_TYPES, 2)
    for i in range(len(users)):
        users[i] = Users.query.filter_by(auth_user_type=users[i]).first()

    create_requests_search_set(users[0], users[1])


@manager.command
def create_users():
    """Create a user from each of the allowed auth_user_types."""
    from app.constants.user_type_auth import PUBLIC_USER_TYPES, AGENCY_USER
    types = [type for type in PUBLIC_USER_TYPES]
    types.append(AGENCY_USER)

    from tests.lib.tools import create_user
    for type in types:
        user = create_user(type)
        print("Created User: {guid} - {name} ({email})".format(guid=user.guid, name=user.name, email=user.email))


#
# @manager.option("-a", "--agency", help="Create agency user.", action="store_true", dest='agency')
# def create_user(agency=False):
#     from tests.lib.tools import create_user
#     from app.constants.user_type_auth import AGENCY_USER
#     if agency:
#         user = create_user(AGENCY_USER)
#     else:
#         user = create_user()
#     print(user, "created.")


if __name__ == "__main__":
    manager.run()
