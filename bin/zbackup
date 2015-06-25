#!/usr/bin/env python
import argparse, sys, os, signal, shelve
from datetime import datetime
from traceback import format_exc

sys.path.insert(0, '/opt/zimbra')
from zbackup.common import ZBackupRequest, ZBackupConfig, CONTENT_TYPES

BACKUP_DESTINATION = os.environ.get('ZIMBRA_HOME')
if not BACKUP_DESTINATION:
  print 'Could not find env variable ZIMBRA_HOME'
  sys.exit(1)

BACKUP_DESTINATION += '/backup'

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Zimbra Backup line command')
  parser.add_argument('--ctypes', metavar='<message,content,appointment,task,document>',
    help='which content to backup: message,contact,appointment,task,document. Default: all')
  parser.add_argument('-f', metavar='<account|all>',
    help='Start a full backup from all or a specific one: all or account@domain.tld')
  parser.add_argument('--sync', action='store_true', help='Runs backup synchronously.')
  parser.add_argument('--fromtime', metavar='<ymdhms>',
    help='Backup from a specific time. Format: YearMonthDayHourMinuteSeconds. E.g.: 20150320160000')
  parser.add_argument('--debug', action='store_true', help='Turn on debuging')
  parser.add_argument('--ldap', action='store_true', help='Runs a full backup only for LDAP')
  parser.add_argument('--abort', metavar='<label>', help='Abort backup job.')
  parser.add_argument('--target', help='Backup target location (default <zimbra_home>/backup)')
  
  args = parser.parse_args()

  debug, ctypes, fromtime = (False, None, None)
  if args.ctypes:
    if [ctype for ctype in args.ctypes.split(',') if ctype not in CONTENT_TYPES]:
      print 'Content Type error. Accept only: %s' % ','.join(CONTENT_TYPES)
      print parser.print_help()
      sys.exit(1)

  BACKUP_DESTINATION = args.target or BACKUP_DESTINATION
  
  if args.fromtime:
    try:
      fromtime = datetime.strptime(args.fromtime, '%Y%m%d%H%M%S')
    except Exception, e:
      print 'Wrong datetime format identified: %s' % e
      sys.exit(1)

  if args.debug:
    debug = True
  if args.abort:
    label = args.abort
    config = ZBackupConfig().get_main_config_file()
    zbkpdata = shelve.open(config.get('main', 'metadata_config_file'), writeback=True)
    if zbkpdata.get('pid') and ZBackupConfig.check_pid(zbkpdata.get('pid')):
      if not zbkpdata.get(label):
        print 'Label does not exists'
        sys.exit(0)
      zbkpdata[label]['status'] = 'aborted'
      if not zbkpdata[label].get('ldapbkpstatus'):
        zbkpdata[label]['ldapbkpstatus'] = 'aborted'

      zbkpdata[label]['endtime'] = datetime.now()
      print 'Killing process %s...' % zbkpdata.get('pid')
      os.kill(zbkpdata['pid'], signal.SIGQUIT)
      print 'Done!'
      zbkpdata['pid'] = None

    else:
      print 'Cannot find any running backup process'
    zbkpdata.close()
    sys.exit(0)

  if args.ldap:
    args.f = 'ldap'

  try:
    zcr = ZBackupRequest(args.f, BACKUP_DESTINATION, debug=debug, ctypes=args.ctypes)
    zcr.run_backup(fromtime=fromtime, sync=args.sync)
  except Exception, e:
    if args.sync:
      print 'Error running backup: %s' % e
    if args.debug:
      print format_exc()
    sys.exit(1)