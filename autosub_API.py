from videotosrt import get_api_keys,generate_subtitles
def start(videopath, dev_pid, progress_callback=None):
    try:
        # 设置默认参数值
        outputpath = None
        concurrency = 10  # 并发处理的数量
        subformat = 'srt'  # 字幕文件的格式
        api_key, secret_key = get_api_keys()  # 获取API密钥

        # 调用generate_subtitles函数生成字幕文件
        subtitle_file_path = generate_subtitles(
            source_path=videopath,
            output=outputpath,
            concurrency=concurrency,
            subtitle_file_format=subformat,
            api_key=api_key,
            secret_key=secret_key,
            dev_pid=dev_pid,
            progress_callback=progress_callback
        )
        return subtitle_file_path
    except Exception as e:
        # 打印或记录异常信息
        print(f"生成字幕时发生错误: {e}")
        return "Conversion failed"