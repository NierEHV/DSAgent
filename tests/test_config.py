import urllib.request, json

API='http://127.0.0.1:8000'
errors=[]

def post(section, data):
    body=json.dumps({'section':section,'data':data}).encode()
    req=urllib.request.Request(API+'/config/update',data=body,headers={'Content-Type':'application/json'})
    return json.loads(urllib.request.urlopen(req).read().decode())

def get_cfg():
    return json.loads(urllib.request.urlopen(API+'/config').read().decode())

def check(label, condition, msg):
    if not condition:
        errors.append(f'{label}: {msg}')
        return False
    return True

# 1. LLM
print('=== 1. LLM ===')
r=post('llm',{'provider':'openai','model':'gpt-4o','base_url':'https://api.openai.com/v1','max_tokens':8192,'temperature':0.5})
check('LLM update',r['status']=='updated',r)
cfg=get_cfg()
check('LLM provider',cfg['llm']['provider']=='openai',cfg['llm']['provider'])
check('LLM model',cfg['llm']['model']=='gpt-4o',cfg['llm']['model'])
check('LLM max_tokens',cfg['llm']['max_tokens']==8192,cfg['llm']['max_tokens'])
check('LLM temperature',cfg['llm']['temperature']==0.5,cfg['llm']['temperature'])
print('  Done')

# 2. Alert Rules
print('=== 2. Alert Rules ===')
r=post('alert_rules',{'inventory':{'critical_days':3,'warning_days':10,'excess_days':60},'advertising':{'acos_spike_threshold':25,'acos_spike_ratio':2.0,'budget_exhausted_pct':85,'high_performer_acos':10,'high_performer_roas':6.0},'profit':{'critical_margin':8,'warning_margin':12,'refund_rate_critical':8},'competitor':{'buy_box_lost_enabled':True,'new_seller_enabled':False}})
check('Alert update',r['status']=='updated',r)
cfg=get_cfg()
ar=cfg['alert_rules']
check('inv crit',ar['inventory']['critical_days']==3,ar['inventory']['critical_days'])
check('inv warn',ar['inventory']['warning_days']==10,ar['inventory']['warning_days'])
check('inv excess',ar['inventory']['excess_days']==60,ar['inventory']['excess_days'])
check('ad acos_thresh',ar['advertising']['acos_spike_threshold']==25,ar['advertising']['acos_spike_threshold'])
check('ad acos_ratio',ar['advertising']['acos_spike_ratio']==2.0,ar['advertising']['acos_spike_ratio'])
check('ad budget',ar['advertising']['budget_exhausted_pct']==85,ar['advertising']['budget_exhausted_pct'])
check('ad hp_acos',ar['advertising']['high_performer_acos']==10,ar['advertising']['high_performer_acos'])
check('ad hp_roas',ar['advertising']['high_performer_roas']==6.0,ar['advertising']['high_performer_roas'])
check('pr crit',ar['profit']['critical_margin']==8,ar['profit']['critical_margin'])
check('pr warn',ar['profit']['warning_margin']==12,ar['profit']['warning_margin'])
check('pr refund',ar['profit']['refund_rate_critical']==8,ar['profit']['refund_rate_critical'])
check('comp bb',ar['competitor']['buy_box_lost_enabled']==True,ar['competitor']['buy_box_lost_enabled'])
check('comp ns',ar['competitor']['new_seller_enabled']==False,ar['competitor']['new_seller_enabled'])
print('  Done')

# 3. Notify
print('=== 3. Notify ===')
r=post('notify',{'dingtalk':{'enabled':True,'webhook':'https://oapi.dingtalk.com/robot/send?access_token=test123','at_users':['@admin','@ops'],'min_severity':'warning'},'wecom':{'enabled':False,'webhook':'','min_severity':'critical'}})
check('Notify update',r['status']=='updated',r)
cfg=get_cfg()
n=cfg['notify']
check('DD enabled',n['dingtalk']['enabled']==True,n['dingtalk']['enabled'])
check('DD webhook','test123' in n['dingtalk']['webhook'],n['dingtalk']['webhook'])
check('DD at',len(n['dingtalk']['at_users'])>=2 and '@admin' in str(n['dingtalk']['at_users']),n['dingtalk']['at_users'])
check('DD sev',n['dingtalk']['min_severity']=='warning',n['dingtalk']['min_severity'])
check('WX enabled',n['wecom']['enabled']==False,n['wecom']['enabled'])
print('  Done')

# 4. Monitor
print('=== 4. Monitor ===')
r=post('monitor',{'asins':['B09TEST001','B09TEST002'],'skus':['SKU-A','SKU-B'],'keywords':['test kw','bluetooth']})
check('Monitor update',r['status']=='updated',r)
cfg=get_cfg()
m=cfg['monitor']
check('Monitor asins','B09TEST001' in str(m['asins']),m['asins'])
check('Monitor skus','SKU-A' in str(m['skus']),m['skus'])
check('Monitor kws','test kw' in str(m['keywords']),m['keywords'])
print('  Done')

# 5. Scheduler
print('=== 5. Scheduler ===')
r=post('scheduler',{'interval_minutes':10,'enabled_agents':['inventory','competitor'],'working_hours_only':True,'working_hours_start':'08:00','working_hours_end':'20:00','auto_approve_low_risk':False})
check('Sched update',r['status']=='updated',r)
cfg=get_cfg()
s=cfg['scheduler']
check('Sched interval',s['interval_minutes']==10,s['interval_minutes'])
check('Sched agents','inventory' in str(s['enabled_agents']),s['enabled_agents'])
check('Sched wh',s['working_hours_only']==True,s['working_hours_only'])
check('Sched start',s['working_hours_start']=='08:00',s['working_hours_start'])
check('Sched auto',s['auto_approve_low_risk']==False,s['auto_approve_low_risk'])
print('  Done')

# 6. Storage
print('=== 6. Storage ===')
r=post('storage',{'raw_retention_days':14,'snapshot_retention_days':180})
check('Storage update',r['status']=='updated',r)
cfg=get_cfg()
check('Storage raw',cfg['storage']['raw_retention_days']==14,cfg['storage']['raw_retention_days'])
check('Storage snap',cfg['storage']['snapshot_retention_days']==180,cfg['storage']['snapshot_retention_days'])
print('  Done')

# 7. UI
print('=== 7. UI ===')
r=post('ui',{'theme':'light','refresh_interval_seconds':60,'language':'en'})
check('UI update',r['status']=='updated',r)
cfg=get_cfg()
check('UI theme',cfg['ui']['theme']=='light',cfg['ui']['theme'])
check('UI refresh',cfg['ui']['refresh_interval_seconds']==60,cfg['ui']['refresh_interval_seconds'])
check('UI lang',cfg['ui']['language']=='en',cfg['ui']['language'])
print('  Done')

# 8. Datasource
print('=== 8. Datasource ===')
r=post('datasource',{'name':'sellersprite','url':'https://mcp.sellersprite.com/sse','secret_key':'test_key_ss_new','enabled':True})
check('DS update',r['status']=='updated',r)
cfg=get_cfg()
target=[d for d in cfg['datasources'] if d['name']=='sellersprite']
check('DS found',len(target)>0,'not found')
if target:
    check('DS key',target[0].get('secret_key')=='test_key_ss_new',target[0].get('secret_key'))
    check('DS enabled',target[0].get('enabled')==True,target[0].get('enabled'))
print('  Done')

# 9. System / Mock
print('=== 9. System ===')
r=post('system',{'mock_mode':False,'interval_minutes':8})
check('Sys update',r['status']=='updated',r)
cfg=get_cfg()
check('Sys mock',cfg['mock_mode']==False,cfg['mock_mode'])
check('Sys interval',cfg['scheduler']['interval_minutes']==8,cfg['scheduler']['interval_minutes'])
print('  Done')

print()
if errors:
    print(f'=== {len(errors)} ERRORS ===')
    for e in errors: print(f'  FAIL: {e}')
else:
    print('=== ALL 9 SECTIONS PASSED ===')

# Restore
print()
print('Restoring defaults...')
post('alert_rules',{'inventory':{'critical_days':7,'warning_days':14,'excess_days':90},'advertising':{'acos_spike_threshold':30,'acos_spike_ratio':1.5,'budget_exhausted_pct':90,'high_performer_acos':15,'high_performer_roas':5.0},'profit':{'critical_margin':10,'warning_margin':15,'refund_rate_critical':10},'competitor':{'buy_box_lost_enabled':True,'new_seller_enabled':True}})
post('scheduler',{'interval_minutes':5,'enabled_agents':['inventory','advertising','competitor','profit'],'working_hours_only':False,'auto_approve_low_risk':True})
post('monitor',{'asins':['B09XYZ0001','B07DEF5678','B08ABC1234','B05GHI9012'],'skus':['SKU-BT001-BLK','SKU-BT001-WHT','SKU-SPK001','SKU-CHG001','SKU-CHG002','SKU-LMP001','SKU-BTL001','SKU-BTL002'],'keywords':['bluetooth earbuds','usb c charger','portable speaker','wireless headphones']})
post('storage',{'raw_retention_days':7,'snapshot_retention_days':90})
post('ui',{'theme':'dark','refresh_interval_seconds':300,'language':'zh'})
post('system',{'mock_mode':True,'interval_minutes':5})
post('llm',{'provider':'deepseek','model':'deepseek-chat','base_url':'https://api.deepseek.com/v1','max_tokens':4096,'temperature':0.3})
post('notify',{'dingtalk':{'enabled':False,'webhook':'','at_users':[],'min_severity':'warning'},'wecom':{'enabled':False,'webhook':'','min_severity':'critical'}})
post('datasource',{'name':'sellersprite','url':'https://mcp.sellersprite.com/sse','secret_key':'','enabled':True})
print('Done.')
