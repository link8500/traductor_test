"""Deduplicate immutable frozen Windows snapshots while preserving every byte.

Only snapshotted frozen-windowsNNNN folders under build/full-comics are eligible.
Mutable source/assets, screenshots, reports, personal files and Android outputs
are excluded. Shared content is marked read-only to prevent accidental in-place
changes to historical snapshots. Busy files are skipped without stopping tests.
"""
import argparse
import collections
import ctypes
import json
import os
import pathlib
import re
import stat
import time
from audit_corpus_quality import ROOT, QA, atomic, digest, read


def allocated(path):
    high=ctypes.c_ulong(0)
    api=ctypes.windll.kernel32.GetCompressedFileSizeW
    api.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
    api.restype=ctypes.c_ulong
    low=api(str(path),ctypes.byref(high))
    if low==0xffffffff and ctypes.get_last_error():raise OSError('Cannot measure allocated file size')
    return (high.value<<32)|low


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    roots=[];before={};sizes=collections.defaultdict(list)
    for folder in sorted(QA.glob('frozen-windows*')):
        match=re.fullmatch(r'frozen-windows([0-9]+)',folder.name)
        if not match or folder.is_symlink():continue
        snapshot=QA/f'windows-engine{match[1]}.json'
        if not snapshot.exists():continue
        proof=read(snapshot);assert digest(folder/'traductor.exe')==proof['binary_sha256']
        roots.append(folder.resolve());before[str(folder.relative_to(ROOT))]=digest(snapshot)
        for path in folder.rglob('*'):
            if path.is_file() and not path.is_symlink() and path.stat().st_size>=1024*1024:
                assert path.resolve().is_relative_to(folder.resolve())
                sizes[path.stat().st_size].append(path.resolve())
    groups=collections.defaultdict(list)
    for size,paths in sizes.items():
        if len(paths)<2:continue
        for path in paths:groups[digest(path)].append(path)
    duplicates={sha:paths for sha,paths in groups.items() if len(paths)>1}
    pool=(QA/'immutable-file-content').resolve()
    assert pool.is_relative_to(QA.resolve())
    saved=0;linked=[];busy=[];plan=[]
    for sha,paths in duplicates.items():
        unique={p.stat().st_ino:p for p in paths}
        possible=sum(allocated(p) for p in list(unique.values())[1:])
        plan.append(dict(sha256=sha,files=len(paths),distinct_files=len(unique),reclaimable_bytes=possible))
        if not args.apply:continue
        pool.mkdir(exist_ok=True)
        pooled=pool/sha
        assert pooled.parent==pool and all(any(p.is_relative_to(r) for r in roots) for p in paths)
        if not pooled.exists():os.link(paths[0],pooled)
        assert digest(pooled)==sha
        os.chmod(pooled,stat.S_IREAD|stat.S_IWRITE)
        try:
            for path in paths:
                assert path.resolve()==path and any(path.is_relative_to(r) for r in roots)
                if os.path.samefile(path,pooled):continue
                assert digest(path)==sha
                physical=allocated(path)
                temp=path.with_name(path.name+'.luma-dedup-link')
                assert temp.parent==path.parent and not temp.exists()
                os.link(pooled,temp)
                try:
                    # Both final absolute paths were checked against the frozen
                    # snapshot roots before this atomic single-file replacement.
                    os.chmod(path,stat.S_IREAD|stat.S_IWRITE)
                    os.replace(temp,path)
                    assert os.path.samefile(path,pooled) and digest(path)==sha
                    saved+=physical;linked.append(dict(path=str(path.relative_to(ROOT)),sha256=sha,physical_bytes_reclaimed=physical))
                except PermissionError:
                    busy.append(str(path.relative_to(ROOT)))
                    if temp.exists():temp.unlink()
        finally:
            os.chmod(pooled,stat.S_IREAD)
    for folder,snapshot_sha in before.items():
        name=pathlib.Path(folder).name.removeprefix('frozen-windows')
        proof=read(QA/f'windows-engine{name}.json')
        assert digest(QA/f'windows-engine{name}.json')==snapshot_sha
        assert digest(ROOT/folder/'traductor.exe')==proof['binary_sha256']
    value=dict(schema=1,applied=args.apply,updated_unix=time.time(),snapshot_folders=len(roots),
        duplicate_content_groups=len(duplicates),reclaimable_bytes=sum(r['reclaimable_bytes'] for r in plan),
        physical_bytes_reclaimed=saved,linked_files=linked,busy_files_skipped=busy,groups=plan,
        only_immutable_snapshot_files=True,all_snapshot_manifests_and_binaries_verified=True,
        shared_files_read_only=True,pixel_and_report_files_excluded=True,personal_files_touched=False,
        mutable_application_model_assets_touched=False)
    atomic(QA/('storage-optimization.json' if args.apply else 'storage-optimization-plan.json'),json.dumps(value,indent=2))
    print(json.dumps({k:v for k,v in value.items() if k not in ['groups','linked_files','busy_files_skipped']}|dict(linked_files=len(linked),busy_files_skipped=len(busy))),flush=True)


if __name__=='__main__':main()
