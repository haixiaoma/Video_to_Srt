import json
import pysrt

# 兼容Python 2和Python 3的text_type定义
try:
    text_type = unicode  # Python 2
except NameError:
    text_type = str  # Python 3

# 将输入字符串强制转换为Unicode编码
def force_unicode(s, encoding="utf-8"):
    if isinstance(s, text_type):
        return s
    elif isinstance(s, bytes):  # Python 3中非Unicode字符串是bytes
        return s.decode(encoding)
    else:
        return text_type(s)  # 其他情况，尝试直接转换为text_type


#将字幕转换为SRT（SubRip Text）格式。这是一种常见的字幕文件格式，包含开始时间、结束时间和对应的文本内容
def srt_formatter(subtitles, show_before=0, show_after=0):
    f = pysrt.SubRipFile()
    for i, (rng, text) in enumerate(subtitles, 1):
        item = pysrt.SubRipItem()
        item.index = i
        item.text = force_unicode(text)
        start = rng[0]
        end = rng[1]
        item.start.seconds = max(0, start - show_before)
        item.end.seconds = end + show_after
        f.append(item)
    return '\n'.join(map(str, f))

#将字幕转换为VTT（Web Video Text Tracks）格式。这是HTML5视频支持的一种字幕文件格式
def vtt_formatter(subtitles, show_before=0, show_after=0):
    text = srt_formatter(subtitles, show_before, show_after)
    text = 'WEBVTT\n\n' + text.replace(',', '.')
    return text

#将字幕转换为JSON格式。这种格式方便进行数据交换和处理
def json_formatter(subtitles):
    subtitle_dicts = [{'start': r_t[0][0], 'end': r_t[0][1], 'content': r_t[1]} for r_t in subtitles]
    return json.dumps(subtitle_dicts)

#将字幕转换为原始文本格式。只包含文本内容，不包含时间信息
def raw_formatter(subtitles):
    return ' '.join([rng_text[1] for rng_text in subtitles])

#根据字幕文件格式的名称，查找对应的格式化函数，其实videotosrt里面只设置了生成srt文件
FORMATTERS = {
    'srt': srt_formatter,
    'vtt': vtt_formatter,
    'json': json_formatter,
    'raw': raw_formatter,
}
