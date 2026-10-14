#!/usr/bin/env python3
"""Delete one proven duplicate Tumblr post and remove only its tracker row."""
import argparse,json
from pathlib import Path
from tumblr_publisher import API,TUMBLR_BLOG,auth,refresh_access,request,verify_account

TRACKER=Path('tumblr_tracker.json')

def main():
 p=argparse.ArgumentParser();p.add_argument('--post-id',required=True);p.add_argument('--url',required=True);a=p.parse_args()
 data=json.loads(TRACKER.read_text());matches=[x for x in data.get('published',[]) if x.get('url')==a.url]
 if len(matches)<2:raise RuntimeError('refusing cleanup: tracker does not prove a duplicate destination')
 target=[x for x in matches if str(x.get('tumblr_post_id'))==a.post_id]
 if len(target)!=1:raise RuntimeError('refusing cleanup: requested post is not exactly one tracked duplicate')
 token=refresh_access();verify_account(token)
 request('DELETE',f'{API}/blog/{TUMBLR_BLOG}/post/delete',headers=auth(token),params={'id':a.post_id},retries=2)
 data['published']=[x for x in data.get('published',[]) if str(x.get('tumblr_post_id'))!=a.post_id]
 TRACKER.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'status':'PASS','deleted_tumblr_post_id':a.post_id,'destination':a.url}))
if __name__=='__main__':main()
