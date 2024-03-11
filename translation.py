import time
import re
import os
import json
import requests
from PyQt5.QtWidgets import QInputDialog, QMessageBox

BAIDU_URL = 'https://aip.baidubce.com/rpc/2.0/mt/texttrans/v1'

def validate_key(key, length):
    return bool(re.match(r'^[A-Za-z0-9]{' + str(length) + r'}$', key))

def get_translation_keys():
    key_file = 'translationkey.txt'
    if os.path.exists(key_file):
        with open(key_file, 'r') as file:
            lines = file.readlines()
            if len(lines) >= 2:
                ak = lines[0].strip().split(" = ")[1].strip("'\" ")
                sk = lines[1].strip().split(" = ")[1].strip("'\" ")
                if validate_key(ak, 24) and validate_key(sk, 32):
                    return ak, sk
    # 使用PyQt5的QInputDialog获取AK和SK
    ak, ok = QInputDialog.getText(None, "AK", "请输入AK (看帮助获取):")
    if ok and validate_key(ak, 24):
        sk, ok = QInputDialog.getText(None, "SK", "请输入SK (看帮助获取):")
        if ok and validate_key(sk, 32):
            with open(key_file, 'w') as file:
                file.write(f"AK = '{ak}'\nSK = '{sk}'")
            return ak, sk
    QMessageBox.warning(None, "错误", "AK或SK无效，请检查输入。")
    return None, None

def get_token():
    ak, sk = get_translation_keys()
    if ak is None or sk is None:
        return ""
    try:
        url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={ak}&client_secret={sk}"
        response = requests.post(url)
        response_json = response.json()
        if 'access_token' in response_json:
            return response_json['access_token']
        else:
            print("Error: ", response_json)
            return ""
    except requests.RequestException as e:
        print(f"网络请求异常: {e}")
        return ""

def read_subtitle_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    return content

def translate_text(text, token, to_lang, include_original=True, progress_callback=None):
    translations = []
    lines = text.split('\n')
    total_lines = len(lines)
    for i in range(0, total_lines, 4):
        # 更新进度的回调
        if progress_callback:
            progress_callback(int((i / total_lines) * 100))
        # 检查是否有足够的行
        if i + 2 >= len(lines):
            break
        # 第一行和第二行直接添加到结果中
        translations.append(lines[i])
        translations.append(lines[i+1])
        # 第三行进行翻译
        paragraph = lines[i+2]
        data = {}
        data['q'] = paragraph
        data['from'] = 'auto'
        data['to'] = to_lang
        data['termIds'] = ''

        headers = {'Content-Type': 'application/json'}
        url = BAIDU_URL + '?access_token=' + token
        response = requests.post(url, data=json.dumps(data), headers=headers)
        response_json = response.json()
        if 'result' in response_json and 'trans_result' in response_json['result']:
            translation = response_json['result']['trans_result'][0]['dst']
        else:
            print("Error: ", response_json)
            translation = ""
        # 根据用户选择添加翻译和/或原文
        translations.append(translation)
        if include_original:
            translations.append(paragraph)
        # 添加空行
        translations.append('')
        # 添加延迟
        time.sleep(0.1)
    # 确保在结束时进度是100%
    if progress_callback:
        progress_callback(100)

    return '\n'.join(translations)

def write_subtitle_file(translation, file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(translation)
