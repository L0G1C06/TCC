import boto3
import os
from botocore.config import Config

# Configura retry automático
s3_client = boto3.client(
    's3',
    config=Config(retries={'max_attempts': 10, 'mode': 'adaptive'})
)
bucket_name = 'storage-rumolog'

response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix='data/')

parquet_files = [
    obj['Key']
    for obj in response.get('Contents', [])
    if obj['Key'].endswith('.parquet')
]

def progresso(bytes_transferidos):
    print(f'  {bytes_transferidos / 1024 / 1024:.1f} MB transferidos...', end='\r')

for i, key in enumerate(parquet_files):
    local_path = os.path.join('downloads', key)
    
    # Pula arquivos já baixados
    if os.path.exists(local_path):
        print(f'[{i+1}/{len(parquet_files)}] Já existe, pulando: {key}')
        continue

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    print(f'[{i+1}/{len(parquet_files)}] Baixando: {key}')
    
    s3_client.download_file(bucket_name, key, local_path, Callback=progresso)
    print()  # nova linha após progresso

print(f'\nConcluído! {len(parquet_files)} arquivos processados.')