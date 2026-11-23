#!/usr/bin/env python3
"""Import a Colab ZIP without executing or deserializing its embedded code/weights."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Destino já existe; importação não sobrescreve resultados')
    with zipfile.ZipFile(args.archive) as archive:
        infos = archive.infolist()
        if len({x.filename for x in infos}) != len(infos):
            raise ValueError('Entradas duplicadas no ZIP')
        if sum(x.file_size for x in infos) > 1024**3:
            raise ValueError('ZIP excede 1 GiB descompactado')
        for info in infos:
            path = PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Caminho/link não permitido no ZIP')
        manifests = [x.filename for x in infos if x.filename.endswith('/run_manifest.json')]
        if len(manifests) != 1:
            raise ValueError('Esperado exatamente um manifesto de execução')
        prefix = manifests[0][:-len('run_manifest.json')]
        manifest = json.loads(archive.read(manifests[0]))
        for section, subdir in [('artifact_sha256',''), ('adapter_files','adapter/')]:
            for name, expected in manifest[section].items():
                if PurePosixPath(name).name != name:
                    raise ValueError('Nome de artefato inválido')
                if hashlib.sha256(archive.read(prefix+subdir+name)).hexdigest() != expected:
                    raise ValueError('Hash divergente: '+name)
        args.output.mkdir(parents=True,exist_ok=False)
        for info in infos:
            if not info.filename.startswith(prefix) or info.is_dir():
                continue
            destination = args.output / info.filename[len(prefix):]
            destination.parent.mkdir(parents=True,exist_ok=True)
            with archive.open(info) as source, destination.open('xb') as target:
                shutil.copyfileobj(source,target)
    print(json.dumps({'imported_to':str(args.output),'status':manifest['status'],
        'files':len(infos),'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest()},indent=2))


if __name__ == '__main__':
    main()
