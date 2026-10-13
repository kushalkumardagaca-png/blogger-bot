#!/usr/bin/env python3
"""Balanced Daily Yield reader-availability release plan (IST).

Twenty-one daily publications are spaced exactly one hour apart from 02:15
through 22:15 IST. The sole overnight quiet period is exactly four hours. Desk
order still follows the global audience day; Master slots fill the former gaps.
"""
from __future__ import annotations
import datetime as dt,time
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')
NEWS_LIVE={
 'asia-pacific':'02:15','china':'03:15','india':'06:15','russia':'09:15',
 'markets':'11:15','europe':'12:15','economy':'13:15','americas':'17:15',
 'companies':'18:15','global':'19:15','banking':'20:15',
}
MASTER_LIVE={
 ('trending',0):'04:15',('evergreen',0):'05:15',
 ('trending',1):'07:15',('evergreen',1):'08:15',
 ('trending',2):'10:15',('evergreen',2):'14:15',
 ('trending',3):'15:15',('evergreen',3):'16:15',
 ('trending',4):'21:15',('evergreen',4):'22:15',
}
# Reader-readiness reference windows remain 45 minutes after release.
PEAKS={k:v for k,v in {
 'asia-pacific':'03:00','china':'04:00','india':'07:00','russia':'10:00',
 'markets':'12:00','europe':'13:00','economy':'14:00','americas':'18:00',
 'companies':'19:00','global':'20:00','banking':'21:00'}.items()}

def release_datetime(value,reference=None):
 now=(reference or dt.datetime.now(IST)).astimezone(IST);hh,mm=map(int,value.split(':'))
 return now.replace(hour=hh,minute=mm,second=0,microsecond=0)

def wait_for_release(value,dry=False):
 if dry:return 0
 target=release_datetime(value);seconds=(target-dt.datetime.now(IST)).total_seconds()
 if seconds>0:
  print(f'Precision release waiting {round(seconds)} seconds for {target.isoformat()}',flush=True);time.sleep(seconds)
 lateness=(dt.datetime.now(IST)-target).total_seconds()
 if lateness>300:print(f'::warning::Release started {round(lateness)} seconds late; publishing immediately.',flush=True)
 return lateness
