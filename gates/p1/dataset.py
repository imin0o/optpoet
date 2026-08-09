"""P1 完了ゲートで使う固定資産の定義（12 画像と入力文）。

12 画像の URL・SHA-256・バイト長は docs/environment/validation-dataset.md 4 章の写しで、
第三者が同一バイトで受入判定を再現できるようにする（P0-G03 / P1-G01）。入力文は Phase 1
が AI を使わないため、権利の明確な既存テキスト（青空文庫の著作権消滅作品）を使う
（requirements.md 121 行「適法に利用できる既存テキスト」）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
IMAGE_DIR = ASSETS / "images"
TEXT_DIR = ASSETS / "text"

USER_AGENT = "optpoet-p1-gate/0.1 (local validation asset fetch)"


@dataclass(frozen=True, slots=True)
class ImageAsset:
    slot: str
    category: str
    url: str
    sha256: str
    size: int

    @property
    def path(self) -> Path:
        return IMAGE_DIR / f"{self.slot}.jpg"


IMAGES: tuple[ImageAsset, ...] = (
    ImageAsset(
        "portrait-1",
        "portrait",
        "https://upload.wikimedia.org/wikipedia/commons/e/e7/Boy_Face_from_Venezuela.jpg",
        "e11be19f72949f9fe445b32077a63911ca065c09097477318ab9c75600ffd321",
        10_864_429,
    ),
    ImageAsset(
        "portrait-2",
        "portrait",
        "https://upload.wikimedia.org/wikipedia/commons/3/31/"
        "My_niece_Julia_full_face%2C_by_Julia_Margaret_Cameron.jpg",
        "1a28914be1038939c2018274df3883f40ca4e68dbb05db5ea8ee2064972f8849",
        3_680_047,
    ),
    ImageAsset(
        "portrait-3",
        "portrait",
        "https://upload.wikimedia.org/wikipedia/commons/6/6b/"
        "David_R._Allen_Assistant_Manager_for_Safety_and_Technical_Services_"
        "Department_of_Energy_Oak_Ridge_Office_%289364899021%29.jpg",
        "9388025bfe04a1fa359ef4838880715669c01a2b9f96f6d1a21d8b5e2f89a3c7",
        982_789,
    ),
    ImageAsset(
        "landscape-1",
        "landscape",
        "https://upload.wikimedia.org/wikipedia/commons/c/cb/"
        "Utah_Dunes_Landscape_-_West_Desert_District.jpg",
        "08786cf02088576bf95df9c7b941c8a358c6843e1702d3fe37c19597328ad589",
        5_356_067,
    ),
    ImageAsset(
        "landscape-2",
        "landscape",
        "https://upload.wikimedia.org/wikipedia/commons/f/fb/"
        "Foggy_landscape_in_My%C5%A5a%2C_Hvo%C5%BE%C4%8Fany%2C_Central_Bohemia_"
        "%2851867697891%29.jpg",
        "f6fa73b7b0e8de6e891d954f44770e485b412c398b7a52cbc26cb0a7937a688a",
        1_344_244,
    ),
    ImageAsset(
        "landscape-3",
        "landscape",
        "https://upload.wikimedia.org/wikipedia/commons/0/04/Foggy_sunrise_%2853068259930%29.jpg",
        "10e874dcffe302c3c094e937cbb49ace69169dfe4c48c618656b5631b7476c26",
        19_378_010,
    ),
    ImageAsset(
        "architecture-1",
        "architecture",
        "https://upload.wikimedia.org/wikipedia/commons/2/23/"
        "Canterbury_Cathedral_Tower_Ceiling.jpg",
        "2fa5572b9f06aac9363e3320e7dd6108104923906291979bf520bacd20fbe7cc",
        22_095_050,
    ),
    ImageAsset(
        "architecture-2",
        "architecture",
        "https://upload.wikimedia.org/wikipedia/commons/a/af/Chester_Cathedral_Nave.jpg",
        "142cd1b4123caa934f28189d933bbbf2f4d5734895eafe0533a3b19311137c37",
        23_452_409,
    ),
    ImageAsset(
        "architecture-3",
        "architecture",
        "https://upload.wikimedia.org/wikipedia/commons/8/83/Brick_Wall_Building.jpg",
        "56828f87c71df6e872b65d1bb8a950e7ab8393104f657b095dcfe24647a463ff",
        33_219_917,
    ),
    ImageAsset(
        "still-life-1",
        "still-life",
        "https://upload.wikimedia.org/wikipedia/commons/1/1e/Gorgonzola_and_a_pear.jpg",
        "8a8f5fa4793bb73f2ab86dbe5b2fb0317e99a4e09f81d351234babff6a4bde51",
        156_957,
    ),
    ImageAsset(
        "still-life-2",
        "still-life",
        "https://upload.wikimedia.org/wikipedia/commons/f/ff/Apples_garlic_cloves_still_life.jpg",
        "80e57776f3db2789ea79c0f30ce88e14aa8357e353a389290525ab4c6b847b2e",
        193_271,
    ),
    ImageAsset(
        "still-life-3",
        "still-life",
        "https://upload.wikimedia.org/wikipedia/commons/9/93/Still_life_fruit.jpg",
        "c247ba0261482698ffc33decfe80958ce75e824610e915d7cce2ef48d9dbe7eb",
        111_552,
    ),
)


OVERSIZED = ImageAsset(
    "oversized",
    "architecture",
    "https://upload.wikimedia.org/wikipedia/commons/f/f6/St_Marys_Cathedral_Nave_Edinburgh.jpg",
    "3f604c97fedfb30399327842dc86ecbdc937ef209806fb888b019931197debac",
    35_110_649,
)
"""50MP 超（8686x5790 = 50,291,940 px）の原本。AC-06 の上限超過ケース用で 12 枚には含めない
（OI-005 / validation-dataset.md 4.2）。"""


@dataclass(frozen=True, slots=True)
class TextAsset:
    """入力文の出所。原本 zip のハッシュで取得元を固定する。"""

    name: str
    title: str
    author: str
    url: str
    sha256: str

    @property
    def archive(self) -> Path:
        return TEXT_DIR / f"{self.name}.zip"

    @property
    def path(self) -> Path:
        return TEXT_DIR / f"{self.name}.txt"


# 夏目漱石『こころ』（1914 年、著作権消滅）。青空文庫のルビ付きテキスト zip。
TEXT = TextAsset(
    name="kokoro",
    title="こころ",
    author="夏目漱石",
    url="https://www.aozora.gr.jp/cards/000148/files/773_ruby_5968.zip",
    sha256="c55d7bf6c7cc5bd960ce291949f38cae9ba6a672a6142c3b9e1a9f5a159fa4c4",
)

TEXT_BODY_SHA256 = "8a75c39986da9f1b7ba31d238f18f08307e6d515d9c771a7cda23a7467584766"
"""`clean_aozora()` 後の本文（UTF-8 / LF）のハッシュ。整形規則を変えたら更新する。"""
