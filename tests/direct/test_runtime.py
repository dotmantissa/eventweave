from conftest import OWNER

def test_pinned_runtime_and_storage_probes(chain):
    runtime=chain.deploy('runtime_probe.py');value=chain.call(runtime,'get_runtime');assert value['owner'].lower()==OWNER;assert value['runner']=='1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6'
    storage=chain.deploy('storage_probe.py');assert chain.call(storage,'get_state')['count']==0
