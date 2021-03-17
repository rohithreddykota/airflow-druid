"""
### HTTP operator and sensor to look for data and post to druid
"""
from airflow import DAG, macros
from airflow.operators import SimpleHttpOperator, HttpSensor, PythonOperator
from airflow.macros import ds_format
from datetime import datetime, timedelta
import json
import requests

seven_days_ago = datetime.combine(datetime.today() - timedelta(7),
                                  datetime.min.time())


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': seven_days_ago,
    'email': ['airflow@airflow.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG('druid-ingest-covid', default_args=default_args)

dag.doc_md = __doc__

check_data = HttpSensor(
    task_id='covid-data-check',
    conn_id='http_default',
    endpoint='{{ macros.ds_format(ds, "%Y-%m-%d", "%d-%m-%Y") }}.csv',
    params={},
    response_check=lambda response: True if response.status_code == 200 else False,
    poke_interval=5,
    dag=dag)

def post_task(ds):
    endpoint = macros.ds_format(ds, "%Y-%m-%d", "%d-%m-%Y") + '.csv'
    http_conn_host = 'https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports/'
    url = http_conn_host + endpoint

    with open('spec.json') as f:
        druid_spec = json.load(f)

    druid_spec['spec']['ioConfig']['inputSource']['uris'] = [ url ]

    headers = {'Content-Type': 'application/json'}
    druid_endpoint = 'http://coordinator:8081/druid/indexer/v1/task'
    data = json.dumps(druid_spec)

    response = requests.post(url=druid_endpoint, data=data, headers=headers)
    if response.status_code == 200:
        print(response._content)
    else:
        raise

druid_ingest = PythonOperator(
    task_id='druid-ingest',
    python_callable=post_task,
    op_args=['{{ ds }}'],
    dag=dag
    )




check_data >> druid_ingest
