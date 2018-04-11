from anthill.framework.core.management import Command, Option, Manager
from anthill.framework.db import db


class DiscoveryCommand(Command):
    help = 'Some help text here.'
    name = None

    option_list = (
        Option('-f', '--foo', dest='foo', default=None,
               help='some help text here'),
    )

    def run(self, *args, **kwargs):
        print('Discovery command here')


class DiscoveryManager(Manager):
    name = None


manager = DiscoveryManager(usage='Some help text here.')


@manager.option('-f', '--foo', dest='foo', default=None,
                help="some help text here")
def foo(*args, **kwargs):
    print('Discovery command here')
