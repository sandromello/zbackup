#!/usr/bin/env python
import argparse, sys, os, signal, shelve, time
from datetime import datetime

sys.path.insert(0, '/opt/zimbra')
from zbackup.common import ZBackupRequest, ZBackupConfig, ZBackupError

BACKUP_DESTINATION = os.environ.get('ZIMBRA_HOME')
if not BACKUP_DESTINATION:
  print 'Could not find env variable ZIMBRA_HOME'
  sys.exit(1)

BACKUP_DESTINATION += '/backup'

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Zimbra Backup Query command line')
  parser.add_argument('--label', metavar='<label_backup>', help='Get metadata about a specific backup')
  parser.add_argument('--errors', help='Get identified backup errors')
  parser.add_argument('--target', metavar='<path>', help='Backup target location (default <zimbra_home>/backup)')
  
  args = parser.parse_args()

  BACKUP_DESTINATION = args.target or BACKUP_DESTINATION
  
  try:
    config = ZBackupConfig().get_main_config_file()
    config_file = config.get('main', 'metadata_config_file')
    
    # If metadata file does not exists, construct a new one based on the backup folders
    if not os.path.isfile(config_file):
      zbkpdata = shelve.open(config_file, writeback=True)
      starttime = bkp_accounts = endtime = status = ldapstatus = 'unknown'
      totalaccounts = []
      for label in os.listdir(BACKUP_DESTINATION + '/sessions'):
        if 'full' in label:
          zbkpdata.update({ 
            label : {
              'status' : 'unknown*',
              'ldapbkpstatus' : 'unknown*',
              'starttime' : 'unknown*',
              'endtime' : 'unknown*',
              'accounts' : [],
              'totalaccounts' : 0,
            }
          })
          backup_path = BACKUP_DESTINATION + '/sessions/' + label
          if os.path.isdir(backup_path):
            zbkpdata[label]['starttime'] = '%s - last modification' % time.ctime(os.path.getmtime(backup_path))
          accounts = os.listdir(backup_path + '/accounts/')
          zbkpdata[label]['accounts'] = accounts
          zbkpdata[label]['status'] = 'completed*'
          zbkpdata[label]['totalaccounts'] = len(accounts)
          if len(os.listdir(backup_path + '/ldap')) == 4:
            zbkpdata[label]['ldapbkpstatus'] = 'completed*'
      zbkpdata.close()
 
    if args.label:
      args.label = [args.label]
    else:
      args.label = os.listdir(BACKUP_DESTINATION + '/sessions')

    if args.errors:
      for label in args.label:
        print 'Label:   ', label
        print 'Status:  ', zbkpdata[label].get('status')
        for account, response in zbkpdata[label]['failaccounts']:
          print 'Account: %s Reason: %s' % (account, response.get('reason'))
        print
      sys.exit(0)

    zbkpdata = shelve.open(config_file)
    args.label.sort()

    for label in args.label:
      starttime = endtime = status = ldapstatus = 'unknown'
      totalaccounts, bkp_accounts = 0, []
      if zbkpdata.get(label):
        status = zbkpdata[label].get('status') or status
        ldapstatus = zbkpdata[label].get('ldapbkpstatus') or ldapstatus
        starttime = zbkpdata[label].get('starttime') or starttime
        endtime = zbkpdata[label].get('endtime') or endtime
        bkp_accounts = zbkpdata[label].get('accounts') or []
        totalaccounts = zbkpdata[label].get('totalaccounts') or totalaccounts

      print 'Label:   ', label
      print 'Status:  ', status
      print 'Started: ', starttime
      print 'Ended:   ', endtime
      print 'LDAP:    ', ldapstatus
      print 'Number of accounts: %s out of %s completed' % (len(bkp_accounts), totalaccounts)
      print
    zbkpdata.close()

  except Exception, e:
    print 'Error running zbackupquery: %s' % e
    sys.exit(1)