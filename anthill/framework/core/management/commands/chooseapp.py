from anthill.framework.core.management.commands.base import Command, Option


class ApplicationChooser(Command):
    help = description = 'Choose application for administration.'

    def get_options(self):
        options = (
            Option('-n', '--name', dest='name', required=True, help='Name of the application.'),
        )
        return options

    def run(self, *args, **kwargs):
        pass