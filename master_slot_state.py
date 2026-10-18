#!/usr/bin/env python3
"""A published daily Master slot is immutable even if a retry proposes another topic."""
from __future__ import annotations
import copy
import datetime as dt


def record_slot(record,plan):
    if record.get('date')!=plan.get('date') or record.get('kind') not in ('trending','evergreen'):return None
    kind=record['kind'];slot=record.get('slot')
    if type(slot) is int and slot in range(5):return slot
    # Legacy records had no slot. Categories are unique within each daily kind;
    # unlike topic IDs they survive a fallback/recovery topic replacement.
    category=record.get('category')
    matches=[i for i,row in enumerate(plan.get(kind,[])[:5]) if category and row.get('category')==category]
    return matches[0] if len(matches)==1 else None


def records_for_slot(plan,records,kind,slot):
    rows=[r for r in records if r.get('kind')==kind and record_slot(r,plan)==slot and r.get('url')]
    def time_key(row):
        try:return dt.datetime.fromisoformat(str(row.get('published_at','')).replace('Z','+00:00')).timestamp()
        except (ValueError,TypeError):return 0
    return sorted(rows,key=time_key)


def keeper_for_slot(plan,records,kind,slot):
    rows=records_for_slot(plan,records,kind,slot)
    return rows[0] if rows else None


def canonical_item(current,keeper,candidates=()):
    topic_id=str(keeper.get('topic_id',''))
    original=next((r for r in candidates if str(r.get('id'))==topic_id),None)
    if original:return copy.deepcopy(original)
    if str(current.get('id'))==topic_id:return copy.deepcopy(current)
    # An already-published proof is not a fresh evidence packet or demand claim.
    return {'id':topic_id,'title':keeper.get('title',''),'category':keeper.get('category',current.get('category')),
            'evergreen_category':keeper.get('evergreen_category',current.get('evergreen_category')),
            'sealed_published_url':keeper['url'],'sources':[{'name':'Verified existing Daily Yield publication','url':keeper['url']}],
            'publicationAlreadyConfirmed':True}


def seal_plan(plan,records,candidates=()):
    out=copy.deepcopy(plan)
    for kind in ('trending','evergreen'):
        for slot,current in enumerate(out.get(kind,[])[:5]):
            keeper=keeper_for_slot(plan,records,kind,slot)
            if keeper:out[kind][slot]=canonical_item(current,keeper,candidates)
    return out


def extra_records(plan,records):
    extras=[]
    for kind in ('trending','evergreen'):
        for slot in range(min(5,len(plan.get(kind,[])))):
            for row in records_for_slot(plan,records,kind,slot)[1:]:extras.append({**row,'slot':slot,'routingKey':f'master-{kind}-{slot}'})
    return extras
