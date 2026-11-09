"""Fetch one matched B-format measurement, using bounded ZIP byte ranges."""
import io
import json
import hashlib
import urllib.request
import zipfile
from pathlib import Path


class RemoteZip(io.RawIOBase):
    def __init__(self,url):
        self.url=url; self.position=0
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=15) as response:
            self.size=int(response.headers['Content-Length'])
    def seekable(self): return True
    def tell(self): return self.position
    def seek(self,offset,whence=0):
        self.position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset
        return self.position
    def read(self,size=-1):
        size=self.size-self.position if size<0 else min(size,self.size-self.position)
        if not size: return b''
        if not 0<size<=2_000_000: raise ValueError('Archive range exceeds download bound')
        request=urllib.request.Request(self.url,headers={'Range':f'bytes={self.position}-{self.position+size-1}'})
        with urllib.request.urlopen(request,timeout=20) as response:
            if response.status!=206 or not response.headers.get('Content-Range','').startswith(f'bytes {self.position}-'):
                raise ValueError('Server did not honor requested byte range')
            result=response.read(size)
        if len(result)!=size: raise ValueError('Incomplete archive range')
        self.position+=len(result)
        return result


def main():
    root=Path('artifacts/gs_baseline_research/hall');root.mkdir(parents=True,exist_ok=True)
    records=[]
    for channel in 'WXY':
        url=f'https://isophonics.net/files/irs/greathall{channel}.zip'
        member=f'{channel}/{channel}x06y06.wav'
        target=root/f'great_hall_{channel}.wav'
        if not target.exists():
            with zipfile.ZipFile(RemoteZip(url)) as archive:
                license_text=archive.read('LICENSE').decode()
                (root/'LICENSE.txt').write_text(license_text)
                payload=archive.read(member)
                if not payload.startswith(b'RIFF'): raise ValueError('Expected WAV measurement')
                target.write_bytes(payload)
        records.append({'url':url,'member':member,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
        print(f'Fetched {member}',flush=True)
    (root/'provenance.json').write_text(json.dumps(records,indent=2))
    print((root/'LICENSE.txt').read_text())


if __name__=='__main__':main()
