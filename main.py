from PyQt5.QtGui import QTextCursor
import autosub_API
from translation import get_token, read_subtitle_file, translate_text, write_subtitle_file
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QComboBox, QTextEdit, QFileDialog, QLabel, QHBoxLayout, \
    QDialog
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import subprocess
from videotosrt import get_api_keys
from translation import get_translation_keys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtWidgets import QProgressBar
from PyQt5.QtGui import QIcon
from multiprocessing import freeze_support
class GenerateSubtitlesThread(QThread):
    signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)  # 新增进度信号

    def __init__(self, video_path, dev_pid):
        super().__init__()
        self.video_path = video_path
        self.dev_pid = dev_pid

    def run(self):
        # 修改autosub_API.start调用，传递进度回调函数
        result = autosub_API.start(self.video_path, self.dev_pid, self.update_progress)
        self.signal.emit(result)

    def update_progress(self, value):
        self.progress_signal.emit(value)

class TranslateSubtitleThread(QThread):
    signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)  # 用于更新进度条的信号

    def __init__(self, subtitle_path, to_lang, include_original=True):
        super().__init__()
        self.subtitle_path = subtitle_path
        self.to_lang = to_lang
        self.include_original = include_original

    def run(self):
        token = get_token()
        subtitle_content = read_subtitle_file(self.subtitle_path)

        # 调用翻译函数时传递更新进度的回调
        translated_content = translate_text(
            subtitle_content,
            token,
            self.to_lang,
            self.include_original,
            progress_callback=self.update_progress
        )
        # 根据是否包含原文来决定文件名的尾缀
        if self.include_original:
            suffix = "zh&en"
        else:
            suffix = self.to_lang
        # 保存翻译后的字幕
        output_file_path = self.subtitle_path.rsplit('.', 1)[0] + '-' + suffix + '.srt'
        write_subtitle_file(translated_content, output_file_path)
        self.signal.emit(output_file_path)  # 发送信号，传递生成字幕的结果

    def update_progress(self, value):
        self.progress_signal.emit(value)
class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
    def showSuccessMessage(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("字幕文件生成完毕！")
        msg.setWindowTitle("成功")
        msg.setStandardButtons(QMessageBox.Ok)
        retval = msg.exec_()

    def showHelpMessage(self):
        helpDialog = QDialog(self)
        helpDialog.setWindowTitle("帮助")
        helpDialog.setFixedSize(400, 200)

        helpText = QTextEdit(helpDialog)
        helpText.setReadOnly(True)  # 设置为只读模式
        helpText.setText("第一次使用请去https://console.bce.baidu.com/\n"
                         "网站里面登录账号，创建语音技术和机器翻译的应用，\n"
                         "获取对应的apikey(API_KEY和SECRET_KEY)\n"
                         "再来使用本软件，生成字幕会保存到与视频同目录下。")  # 帮助信息内容
        helpText.setLineWrapMode(QTextEdit.NoWrap)  # 设置不自动换行
        helpText.selectAll()
        helpText.copy()  # 复制文本到剪贴板
        helpText.moveCursor(QTextCursor.Start)  # 移动光标到文本开始位置
        helpText.setFocusPolicy(Qt.NoFocus)  # 文本框不接受焦点

        layout = QVBoxLayout(helpDialog)
        layout.addWidget(helpText)

        closeButton = QPushButton("关闭", helpDialog)
        closeButton.clicked.connect(helpDialog.close)
        layout.addWidget(closeButton)

        helpDialog.setLayout(layout)
        helpDialog.exec_()

    def initUI(self):

        helpLabel = QLabel("😺点击下方按钮使用对应功能，请先看帮助→", self)
        helpButton = QPushButton('帮助', self)
        helpButton.clicked.connect(self.showHelpMessage)
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(200, 80, 250, 20)

        # 创建下拉框并添加选项
        self.langComboBox = QComboBox(self)
        self.langComboBox.addItem("识别普通话", 1537)
        self.langComboBox.addItem("识别英语", 1737)
        self.langComboBox.setFixedWidth(200)

        self.comboBox = QComboBox(self)
        self.comboBox.addItem("中文转换成中英双语")
        self.comboBox.addItem("英文转换成中英双语")
        # 添加两个新的选项
        self.comboBox.addItem("中文转换成英文")
        self.comboBox.addItem("英文转换成中文")
        self.comboBox.setFixedWidth(200)

        btn1 = QPushButton('播放本地视频', self)
        btn1.clicked.connect(self.openVideo)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center; 
            }
            QProgressBar::chunk {
                background-color: #05B8CC;
                width: 20px; 
            }
        """)
        btn2 = QPushButton('视频生成字幕', self)
        btn2.clicked.connect(self.generateSubtitles)

        btn3 = QPushButton('字幕文件翻译', self)
        btn3.clicked.connect(self.translateSubtitle)

        btn4 = QPushButton('退出', self)
        btn4.clicked.connect(QApplication.instance().quit)
        self.textbox = QTextEdit(self)  # 创建一个文本框

        # 创建水平布局并添加提示标签和帮助按钮
        hboxTop = QHBoxLayout()
        hboxTop.addWidget(helpLabel)
        hboxTop.addWidget(helpButton)

        # 创建水平布局用于视频生成字幕和语言选择
        hboxGenerateSubtitles = QHBoxLayout()
        hboxGenerateSubtitles.addWidget(self.langComboBox)
        hboxGenerateSubtitles.addWidget(btn2)
        # self.langComboBox.setFixedWidth(btn2.sizeHint().width())  # 设置下拉框宽度与按钮相同

        # 创建水平布局用于字幕文件翻译和语言选择
        hboxTranslateSubtitle = QHBoxLayout()
        hboxTranslateSubtitle.addWidget(self.comboBox)
        hboxTranslateSubtitle.addWidget(btn3)

        vbox = QVBoxLayout()
        vbox.addLayout(hboxTop)  # 添加顶部的水平布局到垂直布局
        vbox.addWidget(btn1)
        vbox.addLayout(hboxGenerateSubtitles)  # 添加视频生成字幕和语言选择的水平布局
        vbox.addLayout(hboxTranslateSubtitle)  # 添加字幕文件翻译和语言选择的水平布局
        vbox.addWidget(btn4)
        vbox.addWidget(self.progressBar)
        vbox.addWidget(self.textbox)  # 把文本框添加到布局中

        self.setLayout(vbox)

        self.setWindowIcon(QIcon('./icon/主界面图标.png'))
        self.setWindowTitle('视频字幕生成工具')
        self.setGeometry(400, 400, 400, 400)
        self.show()
    def openVideo(self):
        fname = QFileDialog.getOpenFileName(self, 'Open file', './')
        if fname[0]:
            mpv_path = "./mpv/mpv.exe"
            subprocess.call([mpv_path, fname[0]])

    def translateSubtitle(self):

        ak, sk = get_translation_keys()
        if ak is None or sk is None:
            QMessageBox.warning(self, "错误", "AK或SK无效，请检查translationkey.txt文件。")
            return
        choice = self.comboBox.currentText()
        if choice == "中文转换成中英双语":
            to_lang = 'en'
            include_original = True
        elif choice == "英文转换成中英双语":
            to_lang = 'zh'
            include_original = True
        elif choice == "中文转换成英文":
            to_lang = 'en'
            include_original = False  # 不包含原文
        elif choice == "英文转换成中文":
            to_lang = 'zh'
            include_original = False

        fname = QFileDialog.getOpenFileName(self, 'Select Subtitle', './')
        if fname[0]:
            self.textbox.setText("字幕文件正在翻译，请耐心等待...")
            # 在这里创建线程时传递include_original参数
            self.thread = TranslateSubtitleThread(fname[0], to_lang, include_original)
            self.thread.signal.connect(self.onFinished)  # 连接信号和槽函数
            self.thread.progress_signal.connect(self.progressBar.setValue)  # 更新进度条
            self.thread.start()

    def generateSubtitles(self):
        API_KEY, SECRET_KEY = get_api_keys()
        if not API_KEY or not SECRET_KEY:
            QMessageBox.warning(self, "错误", "API_KEY或SECRET_KEY无效，请检查。")
            return
        fname = QFileDialog.getOpenFileName(self, 'Select Video', './')
        if fname[0]:
            print("开始生成字幕...")
            self.textbox.setText("字幕文件正在生成，请耐心等待...")
            dev_pid = self.langComboBox.currentData()  # 从下拉框获取dev_pid值
            self.progressBar.setValue(0)  # 开始生成字幕前，进度条设置为0
            self.thread = GenerateSubtitlesThread(fname[0], dev_pid)
            print("线程创建成功")
            self.thread.signal.connect(self.onFinished)
            self.thread.progress_signal.connect(self.progressBar.setValue)
            self.thread.start()
            print("线程已启动")

    def onFinished(self, result):
        self.textbox.setText("文件生成地址：" + result)
        self.showSuccessMessage()

if __name__ == '__main__':
    freeze_support()  # 在程序入口处调用freeze_support
    import sys
    app = QApplication(sys.argv)
    ex = MyApp()
    sys.exit(app.exec_())