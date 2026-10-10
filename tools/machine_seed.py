"""Create a NoCloud ISO with the SDK's pycdlib, outside the IDE runtime."""
import io,json,sys
import pycdlib


def main():
    payload=sys.stdin.buffer.read(80001)
    if len(payload)>80000:raise ValueError('Machine seed is too large')
    files=json.loads(payload)
    if not isinstance(files,dict) or len(files)>8:raise ValueError('Invalid machine seed')
    iso=pycdlib.PyCdlib();iso.new(interchange_level=3,vol_ident='CIDATA',joliet=3,rock_ridge='1.09')
    try:
        for index,(name,content) in enumerate(files.items()):
            if name not in ('user-data','meta-data','network-config') or not isinstance(content,str):raise ValueError('Invalid seed file')
            raw=content.encode('utf-8')
            iso.add_fp(io.BytesIO(raw),len(raw),iso_path=f'/SEED{index}.;1',joliet_path='/'+name,rr_name=name)
        iso.write(sys.argv[1])
    finally:iso.close()

if __name__=='__main__':main()
