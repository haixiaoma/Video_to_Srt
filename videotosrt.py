#导入所需的库和模块：音频处理库，json处理库，数学库，多进程库，操作系统接口库，子进程管理库，wave音频文件读写库，base64编码解码库，时间库，文件复制与删除库，进度条库，格式转换器，url请求库等
import audioop
import json
import math
import multiprocessing
import subprocess
import wave
import base64
import time
import shutil
from PyQt5.QtWidgets import QInputDialog, QMessageBox
from formatters import FORMATTERS
from urllib.request import urlopen
from urllib.request import Request
from urllib.error import URLError
from urllib.parse import urlencode
timer = time.perf_counter
import tkinter as tk
from tkinter import simpledialog
import os
import re

class InputDialog(simpledialog.Dialog):
    def __init__(self, parent, title, prompt):
        self.prompt = prompt
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text=self.prompt).grid(row=0)
        self.entry = tk.Entry(master)
        self.entry.grid(row=0, column=1)
        return self.entry

    def apply(self):
        self.result = self.entry.get()

def ask_string(title, prompt, parent):
    d = InputDialog(parent, title, prompt)
    return d.result

def validate_api_key(api_key):
    return bool(re.match(r'^[A-Za-z0-9]{24}$', api_key))

def validate_secret_key(secret_key):
    return bool(re.match(r'^[A-Za-z0-9]{32}$', secret_key))

def get_api_keys():
    api_key_file = 'apikey.txt'
    if os.path.exists(api_key_file):
        with open(api_key_file, 'r') as file:
            lines = file.readlines()
            if len(lines) >= 2:
                api_key = lines[0].strip().split(" = ")[1].strip("' ")
                secret_key = lines[1].strip().split(" = ")[1].strip("' ")
                if validate_api_key(api_key) and validate_secret_key(secret_key):
                    return api_key, secret_key

    # 使用PyQt5的QInputDialog获取API_KEY和SECRET_KEY
    api_key, ok = QInputDialog.getText(None, "API_KEY", "请输入API_KEY (看帮助获取):")
    if ok and validate_api_key(api_key):
        secret_key, ok = QInputDialog.getText(None, "SECRET_KEY", "请输入SECRET_KEY (看帮助获取):")
        if ok and validate_secret_key(secret_key):
            with open(api_key_file, 'w') as file:
                file.write(f"API_KEY = '{api_key}'\nSECRET_KEY = '{secret_key}'")
            return api_key, secret_key
        else:
            QMessageBox.warning(None, "警告", "未输入SECRET_KEY或格式不正确，操作将被取消。")
    else:
        QMessageBox.warning(None, "警告", "未输入API_KEY或格式不正确，操作将被取消。")
    return None, None

#定义which函数，用于检查指定程序是否在系统路径中存在并可执行
def which(program):
    def is_exe(file_path):
        return os.path.isfile(file_path) and os.access(file_path, os.X_OK)
    fpath, _ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file
    return None


# 定义函数extract_audio，该函数使用ffmpeg命令行工具从给定的视频文件中提取音频，并将其保存为wav格式。
def extract_audio(filepath, channels=1, rate=16000):
    if not os.path.isfile(filepath):
        print("The given file does not exist: {}".format(filepath))
        raise Exception("Invalid filepath: {}".format(filepath))
    # 在当前目录下创建一个名为'temp'的临时文件夹，如果不存在的话
    if not os.path.exists('temp'):
        os.mkdir('temp')
    filename = (os.path.split(filepath)[-1])[:-3] + 'wav'
    tempname = os.path.join(os.getcwd(), 'temp', filename)

    ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg-6.0-essentials_build', 'bin', 'ffmpeg')
    # 使用完整路径的ffmpeg
    command = [ffmpeg_path, "-y", "-i", filepath, "-ac", str(channels), "-ar", str(rate), "-loglevel", "error",
               tempname]
    use_shell = True if os.name == "nt" else False
    subprocess.check_output(command, stdin=open(os.devnull), shell=use_shell)

    return tempname, rate

#定义percentile函数，用于计算数组的百分位数
def percentile(arr, percent):
    arr = sorted(arr)
    k = (len(arr) - 1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c: return arr[int(k)]
    d0 = arr[int(f)] * (c - k)
    d1 = arr[int(c)] * (k - f)
    return d0 + d1

#定义find_speech_regions函数，用于找出音频文件中的语音区域。
#解释：该函数首先读取音频文件，然后计算每个帧的能量，根据能量确定是否为静音，然后根据静音情况划分语音区域
def find_speech_regions(filename, frame_width=4096, min_region_size=0.5, max_region_size=6):
    # 打开音频文件
    reader = wave.open(filename)
    # 获取音频文件的一些参数
    sample_width = reader.getsampwidth()
    rate = reader.getframerate()
    n_channels = reader.getnchannels()
    # 计算每个帧的时长
    chunk_duration = float(frame_width) / rate
    # 计算总帧数
    n_chunks = int(math.ceil(reader.getnframes() * 1.0 / frame_width))
    # 初始化能量列表
    energies = []
    # 遍历每个帧，计算其能量并添加到能量列表中
    for i in range(n_chunks):
        chunk = reader.readframes(frame_width)
        energies.append(audioop.rms(chunk, sample_width * n_channels))
    # 计算能量阈值，低于此阈值的帧被认为是静音
    threshold = percentile(energies, 0.2)
    # 初始化已经过去的时间
    elapsed_time = 0
    # 初始化语音区域列表
    regions = []
    # 初始化当前语音区域的开始时间
    region_start = None
    # 初始化语音区域编号
    num = 0
    # 遍历每个帧的能量
    for energy in energies:
        # 判断当前帧是否为静音
        is_silence = energy <= threshold
        # 判断当前语音区域的时长是否超过最大时长
        max_exceeded = region_start and elapsed_time - region_start >= max_region_size
        # 如果当前语音区域的时长超过最大时长或者当前帧为静音，并且存在正在记录的语音区域，则结束当前语音区域的记录
        if (max_exceeded or is_silence) and region_start:
            # 如果当前语音区域的时长大于等于最小时长，则将其添加到语音区域列表中
            if elapsed_time - region_start >= min_region_size:
                num = num + 1
                regions.append((region_start, elapsed_time, num))
                region_start = None
        # 如果没有正在记录的语音区域，并且当前帧不是静音，则开始记录新的语音区
        elif (not region_start) and (not is_silence):
            region_start = elapsed_time
        # 更新已经过去的时间
        elapsed_time += chunk_duration
    # 返回语音区域列表
    return regions

# 定义WAVConverter类，用于将音频文件切割为多个小片段，每个片段包含一个语音区域
class WAVConverter(object):
    def __init__(self, source_path, include_before=0.25, include_after=0.25):
        self.source_path = source_path
        self.include_before = include_before
        self.include_after = include_after

    def __call__(self, region):
        try:
            start, end, num = region
            start = max(0, start - self.include_before)
            end += self.include_after
            tempname = os.path.join(os.getcwd(), 'temp', 'temp' + str(num) + '.wav')

            ffmpeg_path = os.path.join(os.getcwd(), 'ffmpeg-6.0-essentials_build', 'bin', 'ffmpeg')

            # 使用完整路径的ffmpeg
            command = [ffmpeg_path, "-ss", str(start), "-t", str(end - start),
                       "-y", "-i", self.source_path,
                       "-loglevel", "error", tempname]

            use_shell = True if os.name == "nt" else False
            subprocess.check_output(command, stdin=open(os.devnull), shell=use_shell)
            return tempname
        except KeyboardInterrupt:
            return 1

#定义SpeechRecognizer类，用于调用百度语音识别API将音频片段转化为文字。
#过程：该类首先获取API的token，然后对音频文件进行base64编码，最后发送POST请求到百度语音识别API，获取识别结果，之前用百度语音极速版失败可能是因为没有进行编码转换。
class SpeechRecognizer(object):
    # 初始化SpeechRecognizer类，设置API密钥、音频参数、重试次数，并获取API token
    def __init__(self, api_key, secret_key, rate, audioformat, dev_pid, retries=3):
        self.api_key = api_key
        self.secret_key = secret_key
        self.rate = rate
        self.format = audioformat
        self.dev_pid = dev_pid  #1537表示识别普通话，1737表示英语
        self.cuid = '123456PYTHON'
        self.asr_url = 'http://vop.baidu.com/server_api'
        self.token_url = 'http://openapi.baidu.com/oauth/2.0/token'
        self.scope = 'audio_voice_assistant_get'  # 若授权认证返回值中没有此字符串，那么表示用户应用中没有开通asr功能，需要到网页端开通
        self.retries = retries
        self.token = self.fetch_token()

    # 获取API token，用于后续的语音识别请求
    def fetch_token(self):
        params = {'grant_type': 'client_credentials',
                  'client_id': self.api_key,
                  'client_secret': self.secret_key}
        post_data = urlencode(params)
        post_data = post_data.encode('utf-8')
        req = Request(self.token_url, post_data)
        try:
            f = urlopen(req)
            result_str = f.read()
        except URLError as err:
            result_str = err.read()
            print('token http response http code : ' + str(err.code) + str(result_str))
            return 1
        result_str = result_str.decode()
        result = json.loads(result_str)
        if 'access_token' in result.keys() and 'scope' in result.keys():
            if self.scope not in result['scope'].split(' '):
                print('scope is not correct')
                return 0
            print('API Handshake success')
            return result['access_token']
        else:
            print('MAYBE API_KEY or SECRET_KEY not correct: access_token or scope not found in token response')
            return 0

    # 将音频文件转化为文字
    def __call__(self, filepath):
        with open(filepath, 'rb') as speech_file:
            speech_data = speech_file.read()
        length = len(speech_data)
        if length == 0:
            print('file %s length read 0 bytes' % filepath)
            return 1
        for i in range(self.retries):
            speech = base64.b64encode(speech_data)
            speech = str(speech, 'utf-8')
            params = {'dev_pid': self.dev_pid,
                      'format': self.format,
                      'rate': self.rate,
                      'token': self.token,
                      'cuid': self.cuid,
                      'channel': 1,
                      'speech': speech,
                      'len': length
                      }
            post_data = json.dumps(params, sort_keys=False)
            req = Request(self.asr_url, post_data.encode('utf-8'))
            req.add_header('Content-Type', 'application/json')
            try:
                f = urlopen(req)
                result_str = f.read()
                result_str = str(result_str, 'utf-8')
                if ((json.loads(result_str))["err_no"]) == 0:
                    result_str = ((json.loads(result_str))["result"])[0]
                    return result_str
                elif ((json.loads(result_str))["err_no"]) == 3301:
                    return ''
                elif ((json.loads(result_str))["err_no"]) == 3302:
                    self.token = self.fetch_token()
                    continue
                else:
                    error_no = ((json.loads(result_str))["err_no"])
                    print('Error % s' % error_no)
                    continue
            except URLError as err:
                print('asr http response http code : ' + str(err.code) + str(err.read()))
                continue
        print("Retry failed !")
        return 'Conversion failed'

#定义generate_subtitles函数，用于生成字幕文件。
#首先调用前面的WAVConverter()和SpeechRecognizer()方法从视频文件中提取音频并找出语音区域，然后创建一个多进程池，并行地将每个语音区域转化为WAV格式的音频文件（临时的，在temp文件夹里），并进行语音识别。最后，将识别结果按照指定的字幕文件格式写入到输出文件中
def generate_subtitles(source_path, output, concurrency, subtitle_file_format, api_key, secret_key, dev_pid, progress_callback=None):
    audio_filename, audio_rate = extract_audio(source_path)
    regions = find_speech_regions(audio_filename)
    total_regions = len(regions)
    pool = multiprocessing.Pool(concurrency)
    converter = WAVConverter(source_path=audio_filename)
    recognizer = SpeechRecognizer(api_key, secret_key, audio_rate, audio_filename[-3:], dev_pid)
    transcripts = []

    if regions:
        # 更新进度：假设提取音频和找到语音区域占总进度的10%
        progress_callback(10)
        extracted_regions = []
        for i, extracted_region in enumerate(pool.imap(converter, regions)):
            extracted_regions.append(extracted_region)
            # 更新进度：转换过程中逐步更新，这里假设转换占40%的进度
            progress_callback(10 + int(((i + 1) / total_regions) * 40))

        for i, transcript in enumerate(pool.imap(recognizer, extracted_regions)):
            transcripts.append(transcript)
            # 更新进度：识别过程中逐步更新，这里假设识别占剩余的50%的进度
            progress_callback(50 + int(((i + 1) / total_regions) * 50))
    #将语音区域（regions）和对应的转录文本（transcripts）配对，创建一个新的列表timed_subtitles,由一个个语音区域和相应的转录文本组成。
    timed_subtitles = [(r, t) for r, t in zip(regions, transcripts) if t]
    #从FORMATTERS字典中获取与指定的字幕文件格式（subtitle_file_format）相对应的格式化函数。这个函数将用于将时间标记的字幕转换成特定格式的字幕文本。
    formatter = FORMATTERS.get(subtitle_file_format)
    #使用上一步获取的格式化函数formatter，将timed_subtitles列表（包含时间和转录文本的元组）转换成特定格式的字幕文本。
    formatted_subtitles = formatter(timed_subtitles)

    dest = output
    if not dest:
        base, ext = os.path.splitext(source_path)
        dest = "{base}.{format}".format(base=base, format=subtitle_file_format)

    with open(dest, 'wb') as f:
        f.write(formatted_subtitles.encode("utf-8"))

    shutil.rmtree('temp')
    # 确保在结束时进度是100%
    progress_callback(100)
    return dest

#定义start函数，作为整个程序的入口点。该函数接受视频文件路径、输出文件路径、并发数、字幕文件格式、API密钥等参数，调用generate_subtitles函数生成字幕文件，如果在转换过程中出现错误，则删除临时文件夹并返回"Conversion failed"，否则返回字幕文件的路径
def start(videopath, outputpath=None, concurrency=10, subformat='srt', api_key=None, secret_key=None, dev_pid=1537):
    if api_key is None or secret_key is None:
        api_key, secret_key = get_api_keys()
    try:
        subtitle_file_path = generate_subtitles(
            source_path=videopath,
            output=outputpath,
            concurrency=concurrency,
            subtitle_file_format=subformat,
            api_key=api_key,
            secret_key=secret_key,
            dev_pid=dev_pid  # 确保generate_subtitles函数可以接收并处理dev_pid参数
        )
    finally:
        if os.path.exists('temp'):
            shutil.rmtree('temp')
    return subtitle_file_path