"""Deploy the pinned runtime probe without exposing signing material."""
from pathlib import Path
import json
from dotenv import load_dotenv
import os
from genlayer_py import create_client, create_account, studionet
from genlayer_py.types.transactions import TransactionStatus

load_dotenv()
client = create_client(chain=studionet, account=create_account(os.environ['DEPLOYER_PRIVATE_KEY']))
record = Path('verification/runtime-probe.json')
if record.exists():
    state = json.loads(record.read_text())
else:
    tx = client.deploy_contract(code=Path('contracts/deployable/runtime_probe.py').read_bytes(), args=[])
    state = {'network': 'studionet', 'chain_id': 61999, 'runner': '1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6', 'transaction_hash': str(tx), 'signer': client.local_account.address}
    record.write_text(json.dumps(state, indent=2))
print(json.dumps(state))
try:
    receipt = client.wait_for_transaction_receipt(state['transaction_hash'], status=TransactionStatus.FINALIZED, retries=15, interval=3000, full_transaction=True)
    state['receipt'] = receipt
    record.write_text(json.dumps(state, indent=2, default=str))
    print('Finalized runtime receipt captured; execution result:', receipt.get('consensus_data', {}).get('leader_receipt', {}).get('execution_result'))
except Exception as error:
    print('Probe pending or failed:', type(error).__name__, str(error)[:1800])
