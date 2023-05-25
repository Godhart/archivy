import os
import sys
import shutil
import subprocess
import re
from pathlib import Path


WORDCONV = os.environ.get("WORDCONV_PATH", r"C:\Program Files\Microsoft Office\root\Office16\Wordconv.exe")


def doc_fix_path(path):
    f_path = Path(path).parent / Path(path).stem
    f_path = re.sub(r"[^\wА-Яа-я-\\/]", "_", str(f_path))
    f_path = f_path + Path(path).suffix.lower()
    return f_path


def import_doc(src_root, src_path, dst_root):
    src = Path(src_path)
    dst = Path(dst_root) / doc_fix_path(src.relative_to(Path(src_root)))

    if not src.is_file():
        return None

    os.makedirs(dst.parent, exist_ok=True)
    if src.suffix == ".doc":
        dst = dst.parent / (dst.stem + ".docx")
        if dst.exists():
            if dst.is_file():
                dst.unlink()
            else:
                return False
        subprocess.run([WORDCONV, "-oice", "-nme", src, dst])
        return dst

    if src.suffix == ".txt":
        dst = dst.parent / (dst.stem + ".md")
        if dst.exists():
            if dst.is_file():
                dst.unlink()
            else:
                return False
        if True:
            for enc in ("windows-1251", "utf-8"):
                try:
                    with open(src, "r", encoding=enc) as f:
                        data = f.read()
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write(data)
                    return dst
                except Exception as e:
                    pass
            # Fallback in case of failure - just copy
        dst = Path(dst_root) / doc_fix_path(src.relative_to(Path(src_root)))

    # TODO: .url

    if dst.exists():
        if dst.is_file():
            dst.unlink()
        else:
            return False
    shutil.copy2(src, dst)
    return dst


def import_docs(src_root, dst_root):
    for src_path in Path(src_root).glob("**/*"):
        res = import_doc(src_root, src_path, dst_root)
        if res is False:
            print(f"[FAILED]: '{src_path}'")
        elif res is not None:
            print(f"[SUCCESS]: '{src_path}' => '{res}'")


def docs_stat(docs_root):
    extensions = {}
    for src_path in Path(docs_root).glob("**/*"):
        if not src_path.is_file():
            continue
        ext = src_path.suffix
        if ext not in extensions:
            extensions[ext] = 0
        extensions[ext] += 1

    print("="*80)
    for k in sorted(extensions.keys()):
        print(f"{k}: {extensions[k]}")

    print("="*80)
    for k in sorted(extensions.keys(), reverse=True, key=lambda x: extensions[x]):
        print(f"{k}: {extensions[k]}")


def docs_fix_names(docs_root):
    for root, dirs, files in os.walk(docs_root):
        root_p = Path(root)
        for objs in (files, dirs):
            for objn in objs:
                objr = doc_fix_path(objn)
                if objr != objn:
                    Path(root_p / objn).rename(root_p / objr)
        for _, dirs, _ in os.walk(root_p):
            for dn in dirs:
                docs_fix_names(root_p / dn)
            break
        break

if __name__ == "__main__":
    if len(sys.argv > 2):
        if sys.argv[1] not in ("", "-"):
            import_docs(sys.argv[1], sys.argv[2])
        docs_stat(sys.argv[2])
    # docs_fix_names(sys.argv[2])
