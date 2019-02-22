from anthill.framework.conf import settings
from datetime import datetime
from tempfile import NamedTemporaryFile
from time import gmtime, strftime
import ftplib
import gzip
import os
import re
import copy


DEFAULT_DUMPS_SETTINGS = {
    'ROOT_DIR': 'dumps',
    'DUMP_PREFIX': 'db-bkp',
    'FTP_SERVER': None,
    'FTP_USER': None,
    'FTP_PASSWORD': None,
    'FTP_PATH': None
}

USER_DUMPS_SETTINGS = getattr(settings, 'SQLALCHEMY_DUMPS', {})


def _merge_dumps_settings():
    default = copy.deepcopy(DEFAULT_DUMPS_SETTINGS)
    default.update(USER_DUMPS_SETTINGS or {})
    return default


DUMPS_SETTINGS = _merge_dumps_settings()


class CommonTools:
    TIMESTAMP = strftime("%Y%m%d%H%M%S", gmtime())

    @staticmethod
    def get_timestamp(name):
        """
        Gets the timestamp from a given file name.
        :param name: (string) Name of a file generated by AlchemyDumps
        :return: (string) The backup numeric id (in case of success) or False
        """
        pattern = r'(.*)(-)(?P<timestamp>[\d]{14})(-)(.*)(.gz)'
        match = re.search(pattern, name)
        return match.group('timestamp') if match else False

    @staticmethod
    def parse_timestamp(timestamp):
        """Transforms a timestamp ID in a humanized date."""
        date_parsed = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
        return date_parsed.strftime('%b %d, %Y at %H:%M:%S')


class LocalTools(CommonTools):
    """Manage backup directory and files in local file system."""

    def __init__(self, backup_path):
        self.path = self.normalize_path(backup_path)

    @staticmethod
    def normalize_path(path):
        """
        Creates the backup directory (if needed) and returns its absolute path.
        :return: (str) Absolue path to the backup directory
        """
        if not os.path.exists(path):
            os.mkdir(path)
        return os.path.abspath(path) + os.sep

    def get_files(self):
        """List all files in the backup directory."""
        for name in os.listdir(self.path):
            is_file = os.path.isfile(os.path.join(self.path, name))
            has_timestamp = self.get_timestamp(name)
            if is_file and has_timestamp:
                yield name

    def create_file(self, name, contents):
        """
        Creates a gzip file.
        :param name: (str) Name of the file to be created (without path)
        :param contents: (bytes) Contents to be written in the file
        :return: (str) path of the created file
        """
        file_path = os.path.join(self.path, name)
        with gzip.open(file_path, 'wb') as handler:
            handler.write(contents)
        return file_path

    def read_file(self, name):
        """
        Reads the contents of a gzip file.
        :param name: (str) Name of the file to be read (without path)
        :return: (bytes) Content of the file
        """
        file_path = os.path.join(self.path, name)
        with gzip.open(file_path, 'rb') as handler:
            return handler.read()

    def delete_file(self, name):
        """
        Delete a file.
        :param name: (str) Name of the file to be deleted (without path)
        """
        os.remove(os.path.join(self.path, name))


class RemoteTools(CommonTools):
    """Manage backup files in a remote file system via FTP."""

    def __init__(self, ftp):
        """Receives a Python FTP class instance"""
        self.ftp = ftp
        self.path = self.normalize_path()

    def normalize_path(self):
        """Add missing slash to the end of the FTP url to be used in stdout."""
        url = 'ftp://{}{}'.format(self.ftp.host, self.ftp.pwd())
        return url if url.endswith('/') else url + '/'

    def get_files(self):
        """List all files in the backup directory."""
        files = self.ftp.nlst()
        for name in files:
            if self.get_timestamp(name):
                yield name

    def create_file(self, name, contents):
        """
        Creates a gzip file.
        :param name: (str) Name of the file to be created (without path)
        :param contents: (bytes) Contents to be written in the file
        :return: (str) path of the created file
        """
        # write a tmp file
        tmp = NamedTemporaryFile()
        with gzip.open(tmp.name, 'wb') as handler:
            handler.write(contents)

        # send it to the FTP server
        self.ftp.storbinary('STOR {}'.format(name), open(tmp.name, 'rb'))
        return '{}{}'.format(self.path, name)

    def read_file(self, name):
        """
        Reads the contents of a gzip file.
        :param name: (str) Name of the file to be read (without path)
        :return: (bytes) Content of the file
        """
        tmp = NamedTemporaryFile()
        with open(tmp.name, 'wb') as handler:
            self.ftp.retrbinary('RETR {}'.format(name), handler.write)
        with gzip.open(tmp.name, 'rb') as handler:
            return handler.read()

    def delete_file(self, name):
        """
        Delete a file.
        :param name: (str) Name of the file to be deleted (without path)
        """
        self.ftp.delete(name)


class Backup:
    def __init__(self):
        """
        Bridge backups to local file system or to FTP server according to env
        vars set to allow FTP usage (see connect method).
        """
        self.ftp = self.ftp_connect()
        self.dir = DUMPS_SETTINGS['ROOT_DIR']
        self.prefix = DUMPS_SETTINGS['DUMP_PREFIX']
        self.files = None
        self.target = self.get_target()

    def ftp_connect(self):
        """
        Tries to connect to FTP server according to settings.
        :return: Python FTP class instance or False
        """
        server = DUMPS_SETTINGS['ALCHEMYDUMPS_FTP_SERVER']
        user = DUMPS_SETTINGS['ALCHEMYDUMPS_FTP_USER']
        password = DUMPS_SETTINGS['ALCHEMYDUMPS_FTP_PASSWORD']
        path = DUMPS_SETTINGS['ALCHEMYDUMPS_FTP_PATH']
        if server and user:
            try:
                ftp = ftplib.FTP(server, user, password)
                return self.ftp_change_path(ftp, path)
            except ftplib.error_perm:
                print("==> Couldn't connect to " + server)
                return False
        return False

    @staticmethod
    def ftp_change_path(ftp, path):
        """
        Changes path at FTP server.
        :param ftp: Python FTP class instance
        :param path: (str) Path at the FTP server
        :return: Python FTP class instance or False
        """
        change_path = ftp.cwd(path)
        if not change_path.startswith('250 '):
            print("==> Path doesn't exist: " + path)
            ftp.quit()
            return False
        return ftp

    def close_ftp(self):
        if self.ftp:
            self.ftp.quit()

    def get_target(self):
        """Returns the object to manage backup files (Local or Remote)."""
        return RemoteTools(self.ftp) if self.ftp else LocalTools(self.dir)

    def get_timestamps(self):
        """
        Gets the different existing timestamp numeric IDs.
        :return: (list) Existing timestamps in backup directory
        """
        if not self.files:
            self.files = tuple(self.target.get_files())

        different_timestamps = list()
        for name in self.files:
            timestamp = self.target.get_timestamp(name)
            if timestamp and timestamp not in different_timestamps:
                different_timestamps.append(timestamp)
        return different_timestamps

    def by_timestamp(self, timestamp):
        """
        Gets the list of all backup files with a given timestamp.
        :param timestamp: (str) Timestamp to be used as filter
        :return: (list) The list of backup file names matching the timestamp
        """
        if not self.files:
            self.files = tuple(self.target.get_files())

        for name in self.files:
            if timestamp == self.target.get_timestamp(name):
                yield name

    def valid(self, timestamp):
        """Check backup files for the given timestamp."""
        if timestamp and timestamp in self.get_timestamps():
            return True
        print('==> Invalid id. Use "history" to list existing downloads')
        return False

    def get_name(self, class_name, timestamp=None):
        """
        Gets a backup file name given the timestamp and the name of the
        SQLAlchemy mapped class.
        """
        timestamp = timestamp or self.target.TIMESTAMP
        return '{}-{}-{}.gz'.format(self.prefix, timestamp, class_name)