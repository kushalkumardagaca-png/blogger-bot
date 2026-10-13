#!/usr/bin/env python3
"""Audience-aligned Daily Yield release plan (IST).

Regional News retains its logical local-reader sequence and Master Articles fill
the intervening global-demand windows. Daytime gaps stay at 30–90 minutes; the
sole overnight quiet period is six hours from 22:15 through 04:15 IST.
"""
from __future__ import annotations
import datetime as dt,time
from zoneinfo import ZoneInfo
IST=ZoneInfo('Asia/Kolkata')
NEWS_LIVE={
 'asia-pacific':'04:15','china':'05:15','india':'07:15','russia':'10:15',
 'markets':'12:15','europe':'12:45','economy':'13:15','americas':'17:15',
 'companies':'17:45','global':'18:15','banking':'18:45',
}
MASTER_LIVE={
 ('trending',0):'06:15',('evergreen',0):'08:15',
 ('trending',1):'09:15',('evergreen',1):'11:15',
 ('trending',2):'14:15',('evergreen',2):'15:15',
 ('trending',3):'16:15',('evergreen',3):'19:45',
 ('trending',4):'20:45',('evergreen',4):'22:15',
}
# Regional News remains 45 minutes before the intended local-reader window.
PEAKS={k:v for k,v in {
 'asia-pacific':'05:00','china':'06:00','india':'08:00','russia':'11:00',
 'markets':'13:00','europe':'13:30','economy':'14:00','americas':'18:00',
 'companies':'18:30','global':'19:00','banking':'19:30'}.items()}

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
