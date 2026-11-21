import base64
import json
import logging
import os
import shutil
import sys
import time
import tomllib
import traceback
import zipfile
from pathlib import Path

import cv2
import numpy as np
from colorama import Fore, init

__author__ = "MCTF-Alpha-27"
__version__ = "1.1.1"

BASE_DIR = Path(sys.argv[0]).resolve().parent
LOG_FILE = BASE_DIR / "latest.log"
TEMP_DIR = BASE_DIR / "temp"

LEVEL_COLORS = {
    "info": Fore.GREEN,
    "warning": Fore.YELLOW,
    "error": Fore.RED,
    "debug": Fore.BLUE,
    "exception": Fore.RED,
}

LOG_METHODS = {
    "info": logging.info,
    "warning": logging.warning,
    "error": logging.error,
    "debug": logging.debug,
    "exception": logging.exception,
}


def setup():
    if os.name == "nt":
        os.system(f"title MagicRender v{__version__} author: {__author__}")
    logging.basicConfig(
        filename=LOG_FILE,
        filemode="w",
        level=logging.DEBUG,
        format="[%(asctime)s] [%(levelname)s]: %(message)s",
        encoding="utf-8",
    )
    init(autoreset=True)


def log(text, level="normal"):
    if level == "normal":
        print(Fore.GREEN + str(text))
        return
    level = level.lower()
    color = LEVEL_COLORS.get(level, Fore.GREEN)
    timestamp = time.strftime(r"%Y-%m-%d %H:%M:%S")
    print(color + f"[{timestamp}] [{level.upper()}]: {text}")
    if level == "exception":
        detail = traceback.format_exc()
        if detail.strip() and detail.strip() != "NoneType: None":
            print(Fore.RED + detail, end="")
    LOG_METHODS.get(level, logging.info)(text)


def read_input(prompt=""):
    """读取输入；标准输入被关闭时直接退出，避免 EOFError 崩溃。"""
    try:
        return input(prompt)
    except EOFError:
        print()
        log("未检测到标准输入，程序退出", "error")
        sys.exit(1)


def pause(prompt="请按回车继续..."):
    try:
        input(prompt)
    except EOFError:
        pass


def clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        print("\033[2J\033[H", end="")


def first_existing(*paths):
    for path in paths:
        if path.exists():
            return path
    return None


def choose_mod():
    print(Fore.YELLOW + "[警告] 导出前请确保模组文件名称不包含中文、空格，否则可能导致程序无法运行\n")
    mods = sorted(BASE_DIR.glob("*.jar"))
    if not mods:
        log(f"未在 {BASE_DIR} 找到任何 jar 文件", "error")
        pause()
        sys.exit(1)

    while True:
        for i, mod in enumerate(mods, 1):
            print(f"{i}.{mod.name}")
        print()

        raw = read_input(f"检测到{len(mods)}个jar文件，请选择要进行导出的模组: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(mods):
            return mods[int(raw) - 1]

        print("请输入正确的模组编号")
        pause()
        clear_screen()


def extract_mod(jar_path):
    jar_name = jar_path.stem
    extract_dir = TEMP_DIR / jar_name

    log("解包模组文件: " + jar_path.name, "info")

    # 已存在解包结果时让用户决定，避免覆盖手动放入的汉化文件
    if extract_dir.is_dir() and any(extract_dir.iterdir()):
        print(Fore.YELLOW + f"检测到已解包的目录: {extract_dir}")
        choice = read_input(
            "是否重新解包？重新解包会删除该目录下的所有文件（包括你手动放入的汉化文件）。\n"
            "输入 y 重新解包，直接回车沿用现有文件: "
        ).strip().lower()
        if choice not in ("y", "yes"):
            log("沿用现有解包文件，跳过解包", "info")
            return extract_dir
        log("正在重新解包，旧文件将被清除", "info")
        shutil.rmtree(extract_dir)

    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(jar_path) as zf:
        zf.extractall(extract_dir)

    return extract_dir


def read_manifest_version(extract_dir):
    manifest = extract_dir / "META-INF" / "MANIFEST.MF"
    if not manifest.exists():
        return None
    with open(manifest, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.lower().startswith("implementation-version:"):
                return line.split(":", 1)[1].strip()
    return None


def read_mod_info(extract_dir):
    log("读取模组信息", "info")

    mcmod = extract_dir / "mcmod.info"
    toml_file = extract_dir / "META-INF" / "mods.toml"

    if mcmod.exists():
        with open(mcmod, encoding="utf-8") as f:
            data = json.load(f)
        info = data[0] if isinstance(data, list) else data
        if not isinstance(info, dict):
            raise ValueError("mcmod.info 格式无法识别")
        modid = info.get("modid") or info["mods"][0]["modId"]
        version = info.get("version") or info["mods"][0]["version"]
    elif toml_file.exists():
        with open(toml_file, "rb") as f:
            info = tomllib.load(f)
        mod_entry = info["mods"][0]
        modid = mod_entry["modId"]
        version = mod_entry["version"]
    else:
        raise FileNotFoundError("未找到 mcmod.info 或 META-INF/mods.toml")

    log(info, "info")

    if not version or "${" in str(version):
        version = read_manifest_version(extract_dir) or version

    return modid, str(version)


def find_magics(extract_dir, modid):
    log("获取法术图标", "info")

    spells_dir = extract_dir / "assets" / modid / "textures" / "spells"
    if not spells_dir.is_dir():
        raise FileNotFoundError(f"未找到法术图标目录: {spells_dir}")

    magics = []
    for i, png in enumerate(sorted(spells_dir.glob("*.png")), 1):
        name = png.stem
        magics.append(name)
        log(f"发现第{i}项: {name}", "info")

    return magics, spells_dir


def read_lang(lang_file, magics):
    """读取 .lang 或 .json 中与 magics 对应的法术名称。"""
    result = {}
    magic_set = set(magics)

    if lang_file.suffix == ".lang":
        with open(lang_file, encoding="utf-8-sig") as f:
            for line in f:
                line = line.rstrip("\r\n")
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if not key.startswith("spell.") or key.endswith(".desc"):
                    continue
                name = key.split(":")[-1]
                if "." in name:
                    continue
                if name in magic_set:
                    result[name] = value
                    log(f"完成键值配对: {name}={value}", "info")
                else:
                    log(f"{name}未发现对应键值，已被筛除", "info")
    else:
        with open(lang_file, encoding="utf-8-sig") as f:
            data = json.load(f)
        for key, value in data.items():
            if not key.startswith("spell.") or key.endswith(".desc"):
                continue
            name = key.split(".")[-1]
            if name in magic_set:
                result[name] = value
                log(f"完成键值配对: {name}={value}", "info")
            else:
                log(f"{name}未发现对应键值，已被筛除", "info")

    return result


def wait_for_zh_cn(lang_dir):
    candidates = (lang_dir / "zh_cn.lang", lang_dir / "zh_cn.json")
    found = first_existing(*candidates)
    if found is not None:
        return found

    log(
        f"未检测到汉化文件，该模组可能没有简体中文版本。建议先前往 i18n 获取汉化文件后手动放入 {lang_dir}",
        "warning",
    )
    while True:
        choice = read_input(
            "若你已放入汉化文件，请按回车继续；若你确认 i18n 也不存在汉化文件，请输入 none 跳过汉化文件读取: "
        ).strip().lower()
        found = first_existing(*candidates)
        if found is not None:
            return found
        if choice == "none":
            return None
        log("仍未检测到汉化文件，请放入后重试", "warning")


def load_translations(extract_dir, modid, magics):
    lang_dir = extract_dir / "assets" / modid / "lang"

    log("读取zh_cn", "info")
    zh_cn = {}
    zh_file = wait_for_zh_cn(lang_dir)
    if zh_file is None:
        log("已跳过汉化文件读取", "info")
    else:
        zh_cn = read_lang(zh_file, magics)

    log("读取en_us", "info")
    en_file = first_existing(lang_dir / "en_us.lang", lang_dir / "en_us.json")
    if en_file is None:
        raise FileNotFoundError(f"未找到英文语言文件: {lang_dir}")
    en_us = read_lang(en_file, magics)

    if en_us:
        log(
            "法术汉化程度: {:.2%}的法术具有汉化({}/{})".format(
                len(zh_cn) / len(en_us), len(zh_cn), len(en_us)
            ),
            "info",
        )
    else:
        log("未读取到英文名称，跳过汉化程度统计", "warning")

    return zh_cn, en_us


def image_bytes_to_base64(data):
    """把图片字节放大到 128x128 后返回 PNG 的 Base64（保留透明通道）。"""
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("无法解码图片")
    # 像素画放大使用最近邻，避免边缘被插值糊掉
    resized = cv2.resize(img, (128, 128), interpolation=cv2.INTER_NEAREST)
    ok, buf = cv2.imencode(".png", resized)
    if not ok:
        raise ValueError("PNG 编码失败")
    return base64.b64encode(buf.tobytes()).decode()


def build_records(magics, zh_cn, en_us, modid, spells_dir):
    exports = []
    for name in magics:
        english = en_us.get(name)
        if english is None:
            log(f"图标 {name}.png 没有对应的英文名称(spell.*)，已跳过", "warning")
            continue

        png_path = spells_dir / f"{name}.png"
        try:
            data = png_path.read_bytes()
            large_icon = image_bytes_to_base64(data)
        except Exception:
            log(f"图片处理失败，已跳过: {png_path.name}", "exception")
            continue

        chinese = zh_cn.get(name)
        # 每个记录都用新字典，避免复用同一个对象
        record = {
            "name": chinese if chinese is not None else english,
            "englishName": english if chinese is not None else "",
            "registerName": f"{modid}:{name}",  # 法术注册名
            "metadata": 0,
            "OredictList": "[]",
            "CreativeTabName": "",
            "type": "Magic",
            "maxStackSize": "",
            "maxDurability": 1,
            "smallIcon": base64.b64encode(data).decode(),
            "largeIcon": large_icon,
        }
        log("当前: " + record["name"], "info")
        exports.append(json.dumps(record, ensure_ascii=False) + "\n")

    return exports


def main():
    setup()

    jar_path = choose_mod()

    try:
        extract_dir = extract_mod(jar_path)
    except Exception:
        log("解包失败，请查看日志", "exception")
        pause()
        sys.exit(1)

    try:
        modid, modversion = read_mod_info(extract_dir)
    except Exception:
        log("读取模组信息失败，请查看日志", "exception")
        pause()
        sys.exit(1)

    try:
        magics, spells_dir = find_magics(extract_dir, modid)
        zh_cn, en_us = load_translations(extract_dir, modid, magics)
    except Exception:
        log("导出失败，请查看日志", "exception")
        pause()
        sys.exit(1)

    try:
        exports = build_records(magics, zh_cn, en_us, modid, spells_dir)
    except Exception:
        log("生成json失败，请查看日志", "exception")
        pause()
        sys.exit(1)

    log("写入json信息", "info")
    log(f"共发现 {len(magics)} 个图标，成功导出 {len(exports)} 项", "info")
    output = BASE_DIR / f"{modid}-{modversion}.json"
    with open(output, "w", encoding="utf-8") as f:
        f.writelines(exports)

    log(f"导出完成: {output}", "info")
    log("你现在可以删除temp文件夹", "info")
    pause("请按回车退出...")


if __name__ == "__main__":
    main()
