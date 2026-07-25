# P0-016 形態素解析器スパイク
#
# 目的: SudachiPy / fugashi(MeCab) / Janome の 3 候補を参照 PC の Python 3.14 で
#       実際に動かし、(1) バージョン・辞書、(2) 通常文の分割、(3) 未知語(OOV)挙動、
#       (4) 分割粒度の違い を実測する。用途は Phase 2 の「草稿を文・文節・形態素へ
#       分解」(P2-023 / requirements.md)。
#
# 実行: 隔離 venv に sudachipy sudachidict-core janome fugashi unidic-lite を導入して実行。
#   python morphology_spike.py            # 人間可読の要約
#   python morphology_spike.py --json     # 生データ(JSON)

import json
import sys

# 通常文 + 未知語(造語・新語・混在)を含む検証文
NORMAL = "私は東京都に住んでいる。"
OOV = "ヴェゾルグ現象がフワモコに作用し、ぴえん超えてぱおんになった。"


def probe_sudachi():
    from sudachipy import dictionary, tokenizer
    import sudachipy
    tk = dictionary.Dictionary().create()
    modes = {
        "A": tokenizer.Tokenizer.SplitMode.A,
        "B": tokenizer.Tokenizer.SplitMode.B,
        "C": tokenizer.Tokenizer.SplitMode.C,
    }

    def toks(text, mode):
        return [
            {"surface": m.surface(), "pos": m.part_of_speech()[0],
             "normalized": m.normalized_form(), "oov": m.is_oov()}
            for m in tk.tokenize(text, modes[mode])
        ]

    return {
        "name": "SudachiPy + SudachiDict-core",
        "version": sudachipy.__version__,
        "dict": "SudachiDict-core 20260723",
        "license_engine": "Apache-2.0",
        "license_dict": "Apache-2.0 (UniDic + NEologd 等を再構成)",
        "normal": toks(NORMAL, "C"),
        "oov": {m: toks(OOV, m) for m in modes},
    }


def probe_fugashi():
    import fugashi
    from importlib.metadata import version as _v
    tagger = fugashi.Tagger()  # unidic-lite

    def toks(text):
        out = []
        for w in tagger(text):
            f = w.feature
            out.append({
                "surface": w.surface,
                "pos": getattr(f, "pos1", None),
                "lemma": getattr(f, "lemma", None),
                "oov": bool(getattr(w, "is_unk", False)),  # MeCab の未知語ノード判定
            })
        return out

    return {
        "name": "fugashi(MeCab) + unidic-lite",
        "version": _v("fugashi"),
        "dict": "unidic-lite 1.0.8",
        "license_engine": "MeCab: GPL/LGPL/BSD トライライセンス, fugashi: MIT",
        "license_dict": "unidic-lite: BSD-3-Clause 相当(UniDic)",
        "normal": toks(NORMAL),
        "oov": {"default": toks(OOV)},
    }


def probe_janome():
    from janome.tokenizer import Tokenizer
    import janome
    tk = Tokenizer()

    def toks(text):
        out = []
        for t in tk.tokenize(text):
            ps = t.part_of_speech.split(",")
            out.append({
                "surface": t.surface,
                "pos": ps[0],
                "base": t.base_form,
                # ipadic の未知語は読み(reading)が付与されず '*' になる
                "oov": t.reading == "*",
            })
        return out

    return {
        "name": "Janome",
        "version": janome.__version__,
        "dict": "内蔵 mecab-ipadic-2.7.0 (同梱)",
        "license_engine": "Janome: Apache-2.0",
        "license_dict": "ipadic: 修正BSD/GPL/LGPL 選択可(同梱)",
        "normal": toks(NORMAL),
        "oov": {"default": toks(OOV)},
    }


def line(t):
    parts = [t["surface"]]
    if t.get("pos"):
        parts.append(t["pos"])
    if t.get("oov"):
        parts.append("★OOV")
    return "/".join(parts)


def main():
    results = []
    for fn in (probe_sudachi, probe_fugashi, probe_janome):
        try:
            results.append(fn())
        except Exception as e:  # 導入失敗も記録
            results.append({"name": fn.__name__, "error": f"{type(e).__name__}: {e}"})

    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for r in results:
        print("=" * 72)
        if "error" in r:
            print(r["name"], "ERROR:", r["error"])
            continue
        print(f"# {r['name']}  (v{r['version']})")
        print(f"  辞書   : {r['dict']}")
        print(f"  ライセンス(エンジン): {r['license_engine']}")
        print(f"  ライセンス(辞書)   : {r['license_dict']}")
        print(f"  通常文 : {NORMAL}")
        print("    " + "  ".join(line(t) for t in r["normal"]))
        print(f"  未知語文: {OOV}")
        for mode, ts in r["oov"].items():
            n_oov = sum(1 for t in ts if t.get("oov"))
            print(f"    [mode {mode}] OOV {n_oov}件 / {len(ts)}トークン")
            print("      " + "  ".join(line(t) for t in ts))


if __name__ == "__main__":
    main()
