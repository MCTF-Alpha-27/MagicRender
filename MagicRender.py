import base64
import logging
import time
import glob
import json
import os
import zipfile
import cv2

from colorama import Fore, init

__author__ = "MCTF-Alpha-27"
__version__ = "1.0.0"

os.system(f"title MagicRender v{__version__} author: {__author__}")
logging.basicConfig(filename="latest.log", level=logging.DEBUG, format="[%(asctime)s] [%(levelname)s]: %(message)s", encoding="utf-8")
init(autoreset=True)

with open("latest.log", "w") as f:
    f.write("")

def log(text, level="normal"):
    if level == "normal":
        print(Fore.GREEN + text)
    elif level == "info":
        print(Fore.GREEN + "[%s] [%s]: %s" % (
            time.strftime(r"%Y-%m-%d %H:%M:%S"), "INFO", text))
        logging.info(text)
    elif level == "warning":
        print(Fore.YELLOW + "[%s] [%s]: %s" % (
            time.strftime(r"%Y-%m-%d %H:%M:%S"), "WARNING", text))
        logging.warning(text)
        print(Fore.GREEN, end="")
    elif level == "error":
        print(Fore.RED + "[%s] [%s]: %s" % (
            time.strftime(r"%Y-%m-%d %H:%M:%S"), "ERROR", text))
        logging.error(text)
        print(Fore.GREEN, end="")
    elif level == "debug":
        print(Fore.BLUE + "[%s] [%s]: %s" % (
            time.strftime(r"%Y-%m-%d %H:%M:%S"), "DEBUG", text))
        logging.debug(text)
        print(Fore.GREEN, end="")
    else:
        print("[%s] [%s]: %s" % (
            time.strftime(r"%Y-%m-%d %H:%M:%S"), level, text))
        logging.info(text)
        print(Fore.GREEN, end="")

def image_to_base64(image_path):
    """
    将32x32的图片文件转换为128x128的图片文件然后返回其Base64编码的字符串

    :param image_path: 图片文件的路径
    :return: Base64编码的字符串
    """
    img = cv2.imread(image_path)
    resized_img = cv2.resize(img, (128, 128), interpolation=cv2.INTER_AREA)
    cv2.imwrite("temp/tmp.png", resized_img)
    with open("temp/tmp.png", "rb") as f:
        base64img = base64.b64encode(f.read()).decode()
    return base64img

while True:
    mods = glob.glob("*.jar")
    for i in range(len(mods)):
        print(str(i + 1) + "." + mods[i])
    print()
    mod_index = int(input(f"检测到{len(mods)}个jar文件，请选择要进行导出的模组: "))
    try:
        mod = mods[mod_index - 1]
    except IndexError:
        print("请输入正确的模组编号")
        input("请按回车继续...")
        os.system("cls")
    else:
        break

log("解包模组文件: " + mod, "info")
with zipfile.ZipFile(mod) as f:
    mod = mod.removesuffix(".jar")
    f.extractall(f"temp/{mod}")

log("读取模组信息", "info")
with open(f"temp/{mod}/mcmod.info") as f:
    modinfo = json.load(f)[0]
log(modinfo, "info")

if modinfo["mcversion"] != "1.12.2":
    log("该程序目前仅支持导出1.12.2版本的模组，继续导出可能导致意料之外的结果", "warning")
    input("按回车以继续导出...")

log("获取法术", "info")
magics = []
count = 0
for i in glob.glob(f"temp/{mod}/assets/{modinfo["modid"]}/textures/spells/*.png"): # 获取魔法，原理是有多少魔法就一定会有多少对应的icon
    magics.append(i.split("\\")[-1].removesuffix(".png"))
    count += 1
    log("发现第" + str(count) + "项: " + i.split("\\")[-1].removesuffix(".png"), "info")

log("读取zh_cn.lang", "info")
if not os.path.exists(f"temp/{mod}/assets/{modinfo["modid"]}/lang/zh_cn.lang"):
    log(f"未检测到zh_cn.lang文件，该模组可能没有简体中文版本，请前往i18n获取zh_cn.lang后手动放入temp/{mod}/assets/{modinfo["modid"]}/lang中", "error")
zh_cn = {}
with open(f"temp/{mod}/assets/{modinfo["modid"]}/lang/zh_cn.lang", encoding="utf-8") as f: # 读取zh_cn.lang关于spell的部分并存入字典
    for i in f.readlines():
        if i.startswith("spell.") and not i.split("=")[0].endswith(".desc") and not "." in i.split("=")[0].split(":")[1]:
            zh_cn[i.split("=")[0].split(":")[1]] = i.split("=")[1].removesuffix("\n")
            log("完成键值配对: " + i.split("=")[0].split(":")[1] + "=" + i.split("=")[1].removesuffix("\n"), "info")

log("读取en_us.lang", "info")
en_us = {}
with open(f"temp/{mod}/assets/{modinfo["modid"]}/lang/en_us.lang", encoding="utf-8") as f: # 读取en_us.lang关于spell的部分并存入字典
    for i in f.readlines():
        if i.startswith("spell.") and not i.split("=")[0].endswith(".desc") and not "." in i.split("=")[0].split(":")[1]:
            en_us[i.split("=")[0].split(":")[1]] = i.split("=")[1].removesuffix("\n")
            log("完成键值配对: " + i.split("=")[0].split(":")[1] + "=" + i.split("=")[1].removesuffix("\n"), "info")

log("法术汉化程度: {:.2%}的法术具有汉化".format(len(zh_cn) / len(en_us)) + f"({len(zh_cn)}/{len(en_us)})", "info")

log("生成json信息", "info")
export = {}
exports = []
for i in magics: # 生成json信息
    if not os.path.exists(f"temp/{mod}/assets/{modinfo["modid"]}/textures/spells/{i}.png") or en_us.get(i) is None:
        continue
    export["name"] = zh_cn.get(i)
    export["englishName"] = en_us.get(i)
    if export["name"] is None: # 如果没有对应中文，将英文作为主要名称
        export["name"] = export["englishName"]
        export["englishName"] = ""
    # 以下内容为了导入格式而保留
    export["registerName"] = ""
    export["metadata"] = 0
    export["OredictList"] = "[]"
    export["CreativeTabName"] = ""
    export["type"] = "Magic"
    export["maxStackSize"] = ""
    export["maxDurability"] = 1
    # 大小图标转Base64
    with open(f"temp/{mod}/assets/{modinfo["modid"]}/textures/spells/{i}.png", "rb") as f:
        export["smallIcon"] = base64.b64encode(f.read()).decode()
    export["largeIcon"] = image_to_base64(f"temp/{mod}/assets/{modinfo["modid"]}/textures/spells/{i}.png")
    log("当前: " + export["name"], "info")
    exports.append(json.dumps(export, ensure_ascii=False) + "\n")

log("写入json信息", "info")
with open(f"{modinfo["modid"]}-{modinfo["version"]}.json", "w", encoding="utf-8") as f:
    f.writelines(exports)

log("导出完成，你现在可以删除temp文件夹", "info")
input("请按回车退出...")
