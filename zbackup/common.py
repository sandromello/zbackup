#!/usr/bin/python
import ldap, logging, shelve
import subprocess as sb
import xml.etree.ElementTree as ET
import os, time, sys, urllib2, ConfigParser, pwd
from datetime import datetime, timedelta
from base64 import b64encode

CONFIG_FILE_INI = '/opt/zimbra/conf/zbackup.ini'
ZIMBRA_ACCOUNT_STATUS = ['active', 'locked', 'closed', 'lockout', 'pending']

class ZBackupLockingError(Exception): pass
class ZBackupError(Exception): pass
class ZRestoreError(Exception): pass

CONTENT_TYPES = ['message', 'contact', 'appointment', 'task', 'document']

logging_levels = {
  'DEBUG' : logging.DEBUG,
  'INFO' : logging.INFO,
  'WARNING' : logging.WARNING,
  'ERROR' : logging.ERROR,
  'FATAL' : logging.FATAL
}

class ProgressUpload(object):
  def __init__(self):
    self.log = logging.getLogger(__name__)
    self._seen = 0.0
    self.future = datetime.now() + timedelta(seconds=5)

  def update(self, total, size, name):
    self._seen += size
    pct = (self._seen / total) * 100.0
    if datetime.now() > self.future:
      self.log.debug('Restoring: %s Progress: %.2f%s' % (name, pct, '%'))
      self.future = datetime.now() + timedelta(seconds=5)
    
class FileWithCallback(file):
  def __init__(self, path, mode, callback, *args):
    file.__init__(self, path, mode)
    self.seek(0, os.SEEK_END)
    self._total = self.tell()
    self.seek(0)
    self._callback = callback
    self._args = args

  def __len__(self):
    return self._total

  def read(self, size):
    data = file.read(self, size)
    self._callback(self._total, len(data), *self._args)
    return data

class ZBackupConfig(object):
  def __init__(self, metadata_config_file='/opt/zimbra/backup/zbkpdata'):
    self.metadata_config_file = metadata_config_file
    self.config = None

  @classmethod
  def get_main_config_file(cls):
    config = ConfigParser.ConfigParser()
    config.read(CONFIG_FILE_INI)
    return config

  @classmethod
  def check_pid(cls, pid):
    try:
      os.kill(pid, 0)
    except OSError:
      return False
    else:
      return True

  def __enter__(self):
    self.config = shelve.open(self.metadata_config_file, writeback=True)
    if self.config.get('pid') and self.check_pid(self.config['pid']):
      raise ZBackupLockingError('Another process is running: %s' % self.config['pid'])
    self.config['pid'] = os.getpid()
    self.config.sync()
    return self.config

  def __exit__(self, exc_type, exc_value, traceback):
    self.config['pid'] = None
    self.config.close()

class ZBackupUrl(object):
  def __init__(self, host, account, fromtime=None, totime=datetime.now(), ctypes=None):
    self.host = host
    self.account = account
    self.fromtime = fromtime
    self.totime = totime
    self.ctypes = ctypes
    self.url_parts = ''

    if self.ctypes:
      self.url_parts = '&types=%s' % self.ctypes
    
    if fromtime:
      fromtime = int(time.mktime(fromtime.timetuple())) * 1000
      totime = int(time.mktime(totime.timetuple())) * 1000

      self.url_parts += '&start=%s&end=%s' % (fromtime, totime)
    
  @property
  def url(self):
    return 'https://%s:7071/home/%s/?fmt=tgz%s&query=is:anywhere' % (self.host, self.account, self.url_parts)

class ZBackupRequest(object):
  def __init__(self, 
    target, 
    bkp_location,
    host='localhost', 
    ctypes=None,
    debug=False,
    localconfig='/opt/zimbra/conf/localconfig.xml'
  ):

    if not pwd.getpwuid( os.getuid() ).pw_name == 'zimbra':
      raise ZBackupError("Must be run as 'zimbra' user")
    try:
      self.config = ZBackupConfig().get_main_config_file()

      self.log = logging.getLogger(__name__)      
      self.log.setLevel(logging_levels[self.config.get('main', 'logging_level')])

      handler = logging.FileHandler(self.config.get('main', 'logging_file'))
      handler.setLevel(logging_levels[self.config.get('main', 'logging_level')])

      formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
      handler.setFormatter(formatter)

      if debug:
        # Log to stdout and file!
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        self.log.addHandler(ch)
        
      self.log.addHandler(handler)

    except Exception, e:
      raise ZBackupError('Error doing initial config: %s' % e)

    self.cred = self.get_ldap_credentials(localconfig)
    self.target = target
    self.bkp_location = bkp_location
    self.bkp_session_location = self.bkp_location + '/sessions'
    self.host = host
    self.ctypes = ctypes

  def run_backup(self, status_list, fromtime=None, totime=datetime.now(), sync=True):
    if not os.path.isdir(self.bkp_location):
      raise ZBackupError('Backup path does not exists: %s' % self.bkp_location)

    sessions_path = self.bkp_location + '/sessions'
    if not os.path.isdir(sessions_path):
      os.makedirs(sessions_path)

    label = self.new_label()
    label_path = '%s/%s' % (self.bkp_session_location, label)
    print label

    target_accounts = {}
    if self.target == 'all':
      for account in self.get_all_accounts(status_list):
        target_accounts[account] = ZBackupUrl(self.host, account, fromtime, ctypes=self.ctypes)
    elif not self.target == 'ldap':
      for account in self.target.split(','):
        target_accounts[account] = ZBackupUrl(self.host, account, fromtime, totime, self.ctypes)
        if not self.is_valid_account(account):
          self.log.error('Account not found: %s' % account)
          raise ZBackupError('Account not found: %s' % account)

    if not sync:
      if os.fork():
        sys.exit()

    if not os.path.isdir(label_path):
      os.makedirs(label_path)

    with ZBackupConfig(self.config.get('main', 'metadata_config_file')) as cfg:
      self.log.info('Starting backup...')
      cfg[label] = {'starttime' : datetime.now(), 'accounts' : [], 'failaccounts' : {}}
      try:
        self.start_ldap_backup(label_path)
      except Exception, e:
        self.log.error('Failed to backup LDAP')
        self.log.exception(e)
        return
      cfg[label]['ldapbkpstatus'] = 'completed'
      self.log.info('Ldap Backup Completed: %s' % label)
      
      # STOP! backup only ldap
      if self.target == 'ldap':
        cfg[label]['endtime'] = datetime.now()
        self.log.info('END')
        return

      self.log.info('Backing up accounts...')
      cfg[label]['totalaccounts'] = len(target_accounts)
      cfg[label]['status'] = 'running'
      for account, zurl in target_accounts.items():
        cfg.sync()
        try:
          self.log.info('Starting backing up account: %s' % account)
          self.log.debug('URL: %s' % zurl.url)

          result = self.start_download(zurl.url,
            self.config.get('main', 'admin_user'), 
            self.config.get('main', 'admin_password'), 
            account, 
            label_path
          )
          self.log.info('Backup Completed: %s Size: %s' % (account, result))
          cfg[label]['accounts'].append(account)
        except Exception, e:
          self.log.warning('Failed to backup account: %s' % account)
          self.log.exception(e)
          cfg[label]['failaccounts'][account] = {'reason' : str(e)}
      cfg[label]['endtime'] = str(datetime.now())
      status = 'completed'
      if len(cfg[label]['failaccounts']) > 0:
        status += ' with errors!'
      cfg[label]['status'] = status

      self.log.info('SUCCESS backing up %s account(s)' % len(cfg[label]['accounts']))
      self.log.info('FAIL backing up %s account(s)' % len(cfg[label]['failaccounts']))

  def run_restore(self, label, dest_account, resolve='ignore', dest_folder='', sync=True):
    if not os.path.isdir(self.bkp_location):
      raise ZBackupError('Backup path does not exists: %s' % self.bkp_location)

    self.log.info('Resolve duplicates: %s' % resolve)
    self.log.info('Content to restore: %s' % self.ctypes)

    accounts_path = self.bkp_location + '/sessions/%s/accounts' % label
    url_parts = ''
    if self.ctypes:
      url_parts = '&types=%s' % self.ctypes

    if resolve == 'ignore':
      resolve = ''
    else:
      resolve = '&resolve=%s' % resolve

    url = 'https://%s:7071/home/%s%s?fmt=tgz%s%s' % (self.host, dest_account, dest_folder, url_parts, resolve)
    self.log.debug('URL: %s' % url)

    account_path = '%s/%s.tgz' % (accounts_path, self.target)
    self.log.debug('File path: %s' % account_path)

    if not os.path.isfile(account_path):
      raise ZRestoreError('Could not find account path: %s' % account_path)

    if not sync:
      if os.fork():
        print 'Restore started on background!'
        sys.exit()

    filesize = os.stat(account_path).st_size / 1024 / 1024
    self.log.info('Starting restore: %s into account %s. Backup Size: %s MB' % (self.target, dest_account, filesize))
    if self.target == dest_account:
      self.log.warning('Restoring to the same account could duplicate or reset the content')

    try:
      self.start_upload(
        url,
        self.config.get('main', 'admin_user'),
        self.config.get('main', 'admin_password'),
        self.target,
        account_path
      )
      self.log.info('Restore completed for account %s' % dest_account)
    except Exception, e:
      self.log.error('Error restoring account: %s' % dest_account)
      self.log.exception(e)
      raise e

  def start_download(self, url, admin_user, admin_password, account, label_path):
    userAndPass = b64encode(b"%s:%s" % (admin_user, admin_password)).decode("ascii")
    
    file_name = '%s/accounts/%s.tgz' % (label_path, account)
    if not os.path.isdir(label_path + '/accounts'):
      os.makedirs(label_path + '/accounts')
    file_size_dl, block_sz = (0, 8192)
    future = datetime.now() + timedelta(seconds=10)

    request = urllib2.Request(url, headers={ 'Authorization' : 'Basic %s' %  userAndPass })
    u = urllib2.urlopen(request)
    f = open(file_name, 'wb')
    while True:
      buffer = u.read(block_sz)
      if not buffer:
        break

      file_size_dl += len(buffer)
      f.write(buffer)
      if datetime.now() > future:
        self.log.debug('Account: %s, progress: %s MB' % (account, float(file_size_dl) / 1024 / 1024))
        future = datetime.now() + timedelta(seconds=10)

    f.close()
    return float(file_size_dl) / 1024 / 1024

  def start_upload(self, url, admin_user, admin_password, account_name, account_path):
    userAndPass = b64encode(b"%s:%s" % (admin_user, admin_password)).decode("ascii")
    headers = { 
      'Content-Type' : 'application/x-www-form-urlencoded', 
      'Connection' : 'keep-alive', 
      'Authorization' : 'Basic %s' %  userAndPass 
    }
    progress = ProgressUpload()
    stream = FileWithCallback(account_path, 'rb', progress.update, account_name)
    request = urllib2.Request(url, data=stream, headers=headers)
    urllib2.urlopen(request)

  def start_ldap_backup(self, label_path):
    label_path = label_path + '/ldap/'
    self.zmslapcat(label_path)
    self.log.debug('LDAP BACKUP SUCCESS: %s' % label_path)
    # Ldap Config
    self.zmslapcat(label_path, '-c')
    self.log.debug('LDAP BACKUP CONFIG SUCCESS: %s' % label_path)

    try:
      # Access log
      self.zmslapcat(label_path, '-a')
    except Exception, e:
      self.log.warning('Could not backup access log configuration, probally does not exists!')

  def zmslapcat(self, label_path, arg=None):
    slapcat = '/opt/zimbra/libexec/zmslapcat'
    if arg:
      proc = sb.Popen([slapcat, arg, label_path], stdout=sb.PIPE, stderr=sb.PIPE)
    else:
      proc = sb.Popen([slapcat, label_path], stdout=sb.PIPE, stderr=sb.PIPE)

    result = ''.join(proc.communicate())
    if proc.returncode == 1:
      raise IOError('Error subprocessing: %s' % result)

  def is_valid_account(self, account):
    query = '(&(objectClass=zimbraAccount)(&(zimbraMailDeliveryAddress=%s))\
      (!(zimbraIsSystemResource=TRUE))(!(objectClass=zimbraCalendarResource)))' % account
    attrs = ['zimbraMailDeliveryAddress']
    match = None
    for dn, entry in self.ldap_query(query, attrs):
      match = entry['zimbraMailDeliveryAddress'][0]
      break
    return match == account

  def build_search_query(self, status_list):
    query = '(&(objectClass=zimbraAccount)%s(!(zimbraIsSystemResource=TRUE))(!(objectClass=zimbraCalendarResource)))'
    status_query = ''
    for s in status_list:
      status_query += '(|(zimbraAccountStatus=%s)' % s.strip()
    
    for s in status_list:
      status_query += ')'
    return query % status_query

  def get_all_accounts(self, status_list):
    query = self.build_search_query(status_list)
    self.log.debug(query)
    #query = '(&(objectClass=zimbraAccount)(!(zimbraIsSystemResource=TRUE))(!(objectClass=zimbraCalendarResource)))'
    attrs = ['zimbraMailDeliveryAddress']
    accounts = []
    for dn, entry in self.ldap_query(query, attrs):
      accounts.append(entry['zimbraMailDeliveryAddress'][0])  
    return accounts

  def new_label(self):
    return 'full-%s.%s' % (datetime.strftime(datetime.now(), '%Y%m%d'), datetime.strftime(datetime.now(), '%H%M%S.%f'))

  def ldap_query(self, query, attrs):
    """ Query Ldap for results
    :param query: Str containing the ldap query. Example: (&(objectClass=zimbraDistributionList))
    :param attrs: List containing the attributes to return """
    try:
      ldp = ldap.initialize(self.cred['ldap_url'])
      ldp.simple_bind_s(self.cred['zimbra_ldap_userdn'], self.cred['zimbra_ldap_password'])
      return ldp.search_s('', ldap.SCOPE_SUBTREE, query, attrs)
    except Exception, e:
      raise ZBackupError('Error querying to ldap. Error: %s' % e)

  @classmethod
  def get_ldap_credentials(cls, localconfig_file):
    """ Get Ldap credentials from Zimbra config file: localconfig.xml
    Expected output: {'zimbra_ldap_password': '<passwd>', 'ldap_url': '<ldap_uri>', 'zimbra_ldap_userdn': '<userdn>'} """
    tree = ET.parse(localconfig_file)
    root = tree.getroot()
    
    ldap_data = dict()
    try:
      for key in root.findall('key'):
        if key.attrib['name'] in ['ldap_url', 'zimbra_ldap_password', 'zimbra_ldap_userdn']:
          ldap_data[key.attrib['name']] = key.find('value').text
    except AttributeError, ex:
      raise LocalConfigParseError('Error getting ldap credentials in %s: %s ' % (localconfig_file, ex))
    if not ldap_data:
      raise LocalConfigParseError('Ldap credentials empty')

    return ldap_data

if __name__ == '__main__':
  zbr = ZBackupRequest('admin@c403775bc8c8', '/opt/zimbra/backup')
  zbr.run()